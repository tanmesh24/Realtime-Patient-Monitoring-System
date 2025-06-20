from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, IntegerType, DoubleType
from sklearn.ensemble import IsolationForest
import pandas as pd

# Initialize Spark Session
spark = SparkSession.builder \
    .appName("PPG Anomaly Detection") \
    .config("spark.cassandra.connection.host", "localhost") \
    .getOrCreate()

# Define schema for PPG data
schema = StructType() \
    .add("patient_id", IntegerType()) \
    .add("time_seconds", DoubleType()) \
    .add("hr", DoubleType()) \
    .add("pulse", DoubleType()) \
    .add("resp", DoubleType()) \
    .add("spo2", DoubleType())

# Read from Kafka topic
df_raw = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "ppg_realtime") \
    .option("startingOffsets", "latest") \
    .load()

# Extract and parse JSON from Kafka
df_parsed = df_raw.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# Batch anomaly detection function
def detect_anomalies(batch_df, batch_id):
    try:
        if batch_df.rdd.isEmpty():
            print(f"[Batch {batch_id}] Empty batch received, skipping.")
            return

        print(f"[Batch {batch_id}] Starting anomaly detection...")
        batch_df.show(5, truncate=False)  # Optional: show sample records

        pdf = batch_df.toPandas()

        # Fill missing vitals before prediction
        features = pdf[["hr", "pulse", "resp", "spo2"]].fillna(
            pdf[["hr", "pulse", "resp", "spo2"]].mean()
        )

        # Apply Isolation Forest
        model = IsolationForest(contamination=0.05, random_state=42)
        labels = model.fit_predict(features)
        pdf["anomaly_label"] = (labels == -1).astype(int)
        pdf["timestamp"] = pd.Timestamp.now()

        # Fill any remaining nulls
        pdf = pdf.fillna(0)
        pdf["patient_id"] = pdf["patient_id"].astype(int)

        # Create final Spark DataFrame
        result_df = spark.createDataFrame(pdf[[
            "patient_id", "time_seconds", "hr", "pulse", "resp", "spo2", "anomaly_label", "timestamp"
        ]])

        # Save to Cassandra
        result_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .options(table="ppg_signals_realtime", keyspace="bda_project") \
            .mode("append") \
            .save()

        print(f"[Batch {batch_id}] Anomaly detection and save completed.")

    except Exception as e:
        print(f"[Batch {batch_id}] Error during anomaly detection: {e}")

# Start stream query
query = df_parsed.writeStream \
    .foreachBatch(detect_anomalies) \
    .outputMode("append") \
    .option("checkpointLocation", "file:///home/tanmesh/kafka/spark_checkpoints_ppg") \
    .start()

query.awaitTermination()

