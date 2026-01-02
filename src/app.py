import streamlit as st
import asyncio
import os
import time
from datetime import datetime
from dotenv import load_dotenv

from generators import ChaosGenerator
from ingestor import Ingestor
from agent import Analyzer, IncidentReport

# Load environment variables
load_dotenv()

# --- CSS Styling ---
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 5rem;
        padding-right: 5rem;
    }
    .report-card {
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 20px;
    }
    .status-normal {
        color: green;
        font-weight: bold;
    }
    .status-meltdown {
        color: red;
        font-weight: bold;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- Page Config ---
st.set_page_config(
    page_title="Incident Commander",
    page_icon="🚨",
    layout="wide",
)

# --- Async Monitoring Loop ---
async def run_monitoring(status_placeholder, stats_placeholder, log_stream_placeholder, incident_placeholder, meltdown_enabled):
    # Initialize Components
    generator = ChaosGenerator()
    ingestor = Ingestor()
    analyzer = Analyzer()
    
    if meltdown_enabled:
        generator.toggle_meltdown(True)
        status_placeholder.markdown("### System Status: <span class='status-meltdown'>MELTDOWN</span>", unsafe_allow_html=True)
    else:
        status_placeholder.markdown("### System Status: <span class='status-normal'>NORMAL</span>", unsafe_allow_html=True)

    # State tracking
    total_logs_processed = 0
    raw_logs_buffer = []

    # Start the Generator feeding the Ingestor in background
    async def feed_ingestor():
        async for log in generator.generate_log_stream():
            await ingestor.add_log(log)
            # We append to local buffer for display purposes sparingly? 
            # Or we wait for batch to display to avoid race/lag?
            # Let's rely on batch processing for UI updates to keep it synced.
    
    feed_task = asyncio.create_task(feed_ingestor())
    
    try:
        # Process Batches
        async for batch in ingestor.process_stream():
            batch_size = len(batch)
            total_logs_processed += batch_size
            
            # Update Stats
            stats_placeholder.metric("Logs Processed", total_logs_processed)
            
            # Update Raw Log Stream (Sidebar)
            # Take last 20 from batch or combined
            for log in batch[-20:]:
                raw_logs_buffer.append(log)
            
            # Keep only last 50 in buffer
            if len(raw_logs_buffer) > 50:
                raw_logs_buffer = raw_logs_buffer[-50:]
                
            # Render raw logs (as text)
            log_text = "\n".join(raw_logs_buffer)
            log_stream_placeholder.text_area("Log Stream", log_text, height=800, label_visibility="collapsed")
            
            # Analyze Batch
            with st.spinner("Analyzing batch..."):
                report = await analyzer.analyze_batch(batch)
            
            # Render Incident Report
            if report.severity == "Critical":
                container = incident_placeholder.container()
                container.error(f"🚨 **{report.title}**")
                container.markdown(f"**Severity:** {report.severity}")
                container.markdown(f"**Impacted Services:** {', '.join(report.impacted_services)}")
                container.markdown(f"**Summary:** {report.summary}")
                container.markdown(f"**Noise Reduction:** {report.noise_reduction_ratio:.1f}x")
            elif report.severity == "Warning":
                container = incident_placeholder.container()
                container.warning(f"⚠️ **{report.title}**")
                container.markdown(f"**Severity:** {report.severity}")
                container.markdown(f"**Summary:** {report.summary}")
            else:
                container = incident_placeholder.container()
                container.info(f"ℹ️ **{report.title}**")
                container.markdown(f"**Summary:** {report.summary}")

            # Small sleep to yield control if needed, though Streamlit usually handles render on write
            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        pass
    finally:
        generator.is_running = False
        ingestor.is_running = False
        feed_task.cancel()

# --- Main App Layout ---
def main():
    st.title("🚨 Incident Commander: NOC AI Assistant")
    
    # Sidebar - Raw Log Stream Only
    st.sidebar.header("Raw Log Stream")
    log_stream_placeholder = st.sidebar.empty()
    
    # Controls and Metrics in One Row
    col1, col2, col3, col4 = st.columns([1.5, 1.5, 2, 1.5])
    with col1:
        start_btn = st.button("▶️ Start Monitoring", use_container_width=True)
    with col2:
        meltdown_check = st.checkbox("🔥 Simulate Meltdown", value=False)
    with col3:
        status_placeholder = st.empty()
        status_placeholder.markdown("**System Status:** <span class='status-normal'>OFFLINE</span>", unsafe_allow_html=True)
    with col4:
        stats_placeholder = st.empty()
        stats_placeholder.metric("Logs Processed", 0)

    st.divider()
    
    # Main Content
    st.subheader("Situation Report")
    incident_placeholder = st.empty()
    incident_placeholder.info("Waiting for data stream...")

    # Run Loop
    if start_btn:
        asyncio.run(run_monitoring(
            status_placeholder, 
            stats_placeholder, 
            log_stream_placeholder, 
            incident_placeholder,
            meltdown_check
        ))

if __name__ == "__main__":
    main()
