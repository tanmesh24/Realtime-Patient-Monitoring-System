# kafka_producer.py

from kafka import KafkaProducer
import pandas as pd
import json
import time

# Load your CSV (ensure it's numeric and cleaned)
df = pd.read_csv("merged_numeric.csv")

# Fix columns
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_").str.replace("[\[\]]", "", regex=True)

# Fill missing values (optional)
df.fillna(0, inplace=True)

# Initialize Kafka Producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Send each row as JSON to Kafka
for _, row in df.iterrows():
    data = {
        "patient_id": int(row.get("patient_id", 0)),
        "time_seconds": float(row.get("time_s", 0)),
        "hr": float(row.get("hr", 0)),
        "pulse": float(row.get("pulse", 0)),
        "resp": float(row.get("resp", 0)),
        "spo2": float(row.get("spo2", 0))
    }
    print("Sending:", data)  # Debug print
    producer.send('ppg_realtime', value=data)
    time.sleep(1)  # simulate real-time

