import streamlit as st
from cassandra.cluster import Cluster
import pandas as pd
import plotly.graph_objs as go
from streamlit_autorefresh import st_autorefresh
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# -------------------- Page Setup --------------------
st.set_page_config(page_title="Real-Time Patient Monitoring Using Apache Spark and Kafka", layout="wide", page_icon="🫀")
st.title("🩺 Real-Time Monitoring Dashboard ")

# -------------------- Custom CSS --------------------
st.markdown("""
<style>
    body {
        background-color: #0D1117;
        color: white;
    }
    .stSidebar {
        background-color: #111827;
        color: #f0f0f0;
    }
    h1 {
        color: #ff6b81;
        font-size: 40px;
        text-align: center;
    }
    h2, h3, h4 {
        color: #00B4D8;
    }
    .stMetric {
        background: linear-gradient(135deg, #1f2937, #4b5563);
        border-radius: 12px;
        padding: 10px;
        color: #ffffff;
        box-shadow: 0 4px 8px rgba(0,0,0,0.4);
    }
    hr {
        border-top: 2px solid #00B4D8;
    }
    .stDataFrame {
        background-color: #1E293B;
        border-radius: 10px;
    }
    .stAlert {
        font-size: 18px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Session State --------------------
if 'alerted_patients' not in st.session_state:
    st.session_state.alerted_patients = set()

# -------------------- Cassandra Connection --------------------
@st.cache_resource
def connect_cassandra():
    cluster = Cluster(['127.0.0.1'])
    session = cluster.connect('bda_project')
    return session

session = connect_cassandra()

# -------------------- Load Real-Time Data --------------------
def fetch_data():
    query = """
        SELECT patient_id, spo2, pulse, resp, hr, anomaly_label, timestamp
        FROM ppg_signals_realtime
        ALLOW FILTERING
    """
    rows = session.execute(query)
    df = pd.DataFrame(rows.all())
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values("timestamp")

# -------------------- Email Alert --------------------
def send_email_alert(patient_id, anomalies_count, last_anomaly_time):
    sender_email = "tanmeshsingh979@gmail.com"
    sender_password = "with gina svwi lypi"
    receiver_email = "tanmeshveersingh@gmail.com"

    subject = "🚨 Patient Health Alert: Anomaly Detected"

    body = f"""
Dear Medical Team,

This is an automated alert from the Real-Time Patient Monitoring System.

📍 Patient ID: {patient_id}  
⚠️ Anomalies Detected: {anomalies_count}  
⏰ Last Anomaly Timestamp: {last_anomaly_time.strftime('%Y-%m-%d %H:%M:%S')}

Abnormal vital signs have been detected within the recent monitoring window. Please review the patient's data immediately on the monitoring dashboard and take necessary action.

Stay vigilant,  
— Real-Time Patient Monitoring System
    """

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        server.quit()
        st.success(f"📩 Alert email sent for Patient {patient_id}")
    except Exception as e:
        st.error(f"Failed to send alert email: {e}")

# -------------------- Sidebar Settings --------------------
st.sidebar.header("Settings 🛠️")
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 1, 10, 2)
window_seconds = st.sidebar.slider("Time Window (seconds)", 10, 120, 30)

st_autorefresh(interval=refresh_interval * 1000, key="auto_refresh")

# -------------------- Main --------------------
df = fetch_data()

if df.empty:
    st.warning("⏳ Waiting for real-time patient data...")
    st.stop()

# Patient selection
patient_ids = sorted(df['patient_id'].unique())
selected_patient = st.sidebar.selectbox("Select Patient ID", patient_ids, key="patient_select")

# Filter for selected patient
patient_df = df[df['patient_id'] == selected_patient].sort_values("timestamp")

if patient_df.empty:
    st.warning("No data available for this patient.")
    st.stop()

# Limit time window
latest_time = patient_df['timestamp'].max()
window_start = latest_time - pd.Timedelta(seconds=window_seconds)
patient_df = patient_df[patient_df['timestamp'] >= window_start]

# -------------------- Top Summary --------------------
st.subheader(f"🧑‍⚕️ Live Vitals for Patient {selected_patient}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("❤️ Heart Rate (bpm)", f"{patient_df['hr'].iloc[-1]:.1f} bpm", delta="Stable", delta_color="normal")

with col2:
    st.metric("💓 Pulse Rate", f"{patient_df['pulse'].iloc[-1]:.1f}", delta="Normal", delta_color="off")

with col3:
    st.metric("🌬️ Respiration Rate", f"{patient_df['resp'].iloc[-1]:.1f}", delta="Stable", delta_color="normal")

with col4:
    st.metric("🫁 SpO₂ Level (%)", f"{patient_df['spo2'].iloc[-1]:.1f} %", delta="Good", delta_color="normal")

# -------------------- Real-Time Graphs --------------------
st.divider()
st.subheader("📊 Live Vital Signs Graphs")

def create_graph(y, y_title, color):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=patient_df["timestamp"],
        y=patient_df[y],
        mode="lines+markers",
        line=dict(color=color, width=4),
        marker=dict(size=8, color=color, symbol="circle-open-dot"),
        name=y_title
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font=dict(color="white"),
        xaxis_title="🕒 Time",
        yaxis_title=f"{y_title}",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False,
        xaxis=dict(range=[window_start, latest_time])
    )
    return fig

col_graph1, col_graph2 = st.columns(2)
with col_graph1:
    st.plotly_chart(create_graph("hr", "Heart Rate (bpm)", "#ff4d6d"), use_container_width=True)
with col_graph2:
    st.plotly_chart(create_graph("pulse", "Pulse Rate", "#f9c74f"), use_container_width=True)

col_graph3, col_graph4 = st.columns(2)
with col_graph3:
    st.plotly_chart(create_graph("resp", "Respiration Rate", "#43aa8b"), use_container_width=True)
with col_graph4:
    st.plotly_chart(create_graph("spo2", "SpO₂ Level (%)", "#577590"), use_container_width=True)

# -------------------- Anomaly Detection Section --------------------
st.divider()
st.subheader("🚨 Anomaly Detection")

anomalies = patient_df[patient_df["anomaly_label"] == 1]

if not anomalies.empty:
    st.error(f"🚨 {len(anomalies)} Anomalies detected in last {window_seconds} seconds! 🚑")
    st.dataframe(anomalies[["timestamp", "hr", "pulse", "resp", "spo2"]])

    with st.spinner('🚨 Sending alert to Team...'):
        time.sleep(1)

    if selected_patient not in st.session_state.alerted_patients:
        send_email_alert(
            patient_id=selected_patient,
            anomalies_count=len(anomalies),
            last_anomaly_time=anomalies['timestamp'].iloc[-1]
        )
        st.session_state.alerted_patients.add(selected_patient)
else:
    st.success("✅ Patient vitals normal. Monitoring continuously...")
    if selected_patient in st.session_state.alerted_patients:
        st.session_state.alerted_patients.remove(selected_patient)

