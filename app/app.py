import streamlit as st
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import DatabaseManager
from core.pipeline import BulkUploadPipeline
from core.phase_engine import PhaseEngine
from core.spreadsheet_generator import SpreadsheetGenerator
from config import DEFAULT_MACHINE, REASON_CLASSIFICATION_MODE

st.set_page_config(page_title="Industrail_App", layout="wide")

st.title("Industrail_App")
st.markdown("> Free Local Architecture Demo")

db = DatabaseManager()
pipeline = BulkUploadPipeline(db)

tab1, tab2, tab3 = st.tabs(["Upload & Process", "Database Search", "History & Analytics"])

with tab1:
    st.header("Process Manual to Spreadsheet")
    
    machine = st.text_input("Machine Name", value=DEFAULT_MACHINE)
    uploaded_file = st.file_uploader("Upload PDF Manual (Alarms or Parameters)", type=["pdf"])
    
    col1, col2 = st.columns(2)
    force = col1.checkbox("Force Reprocess (bypass cache)", value=False)
    
    if st.button("Extract Data & Generate", type="primary"):
        if uploaded_file is None:
            st.error("Please upload a PDF")
        else:
            with st.spinner("Processing PDF (Extraction & Classification via LLM)..."):
                try:
                    log_container = st.empty()
                    debug_logs = []
                    
                    def live_log(msg: str):
                        debug_logs.append(msg)
                        log_container.code("\n".join(debug_logs), language="plaintext")
                        
                    res = pipeline.process_pdf(
                        uploaded_file.read(),
                        uploaded_file.name,
                        machine,
                        force_reprocess=force,
                        log_callback=live_log
                    )
                    
                    st.success(f"Processing Complete! Execution Time: {res.timings.get('total',0):.2f}s")
                    st.info(f"Found {len(res.alarms)} alarms and {len(res.parameters)} parameters.")
                    
                    with st.expander("Show Trace Logs"):
                        for m in res.debug_steps:
                            st.write(m)

                    if res.alarms:
                        st.subheader("Extracted Alarms")
                        import pandas as pd
                        alarm_df = pd.DataFrame([a.dict() for a in res.alarms])
                        st.dataframe(alarm_df, use_container_width=True)

                    if res.parameters:
                        st.subheader("Extracted Parameters")
                        import pandas as pd
                        param_df = pd.DataFrame([p.dict() for p in res.parameters])
                        st.dataframe(param_df, use_container_width=True)

                    if res.alarms or res.parameters:
                        with st.spinner("Service Layer: ExtractionAgent is mapping and generating spreadsheet..."):
                            from service.extraction_agent import ExtractionAgent
                            agent = ExtractionAgent()
                            out_path = agent.generate_excel(machine, res.source_text, res.alarms, res.parameters)
                            
                        st.success(f"Spreadsheet generated locally at: {out_path}")
                        
                        with open(out_path, "rb") as f:
                            file_data = f.read()
                        st.download_button("Download Generated Master_Bulk_Upload_Results.xlsx", data=file_data, file_name=f"Master_Bulk_Upload_Results_{os.path.basename(out_path)}", type="primary")

                except Exception as e:
                    import traceback
                    st.error(f"Failed processing: {e}")
                    st.code(traceback.format_exc())

with tab2:
    st.header("Search & Review Alarms")
    
    query = st.text_input("Search Text:")
    search_type = st.radio("Search Type", ["Keyword (BM25)", "Semantic (Vector)", "Graph (Neo4j/NetworkX)"])
    
    if st.button("Search"):
        alarms_raw = db.get_alarms({})
        if not alarms_raw:
            st.warning("No alarms in database. Please upload a PDF first.")
        else:
            if "Keyword" in search_type:
                from search.bm25_index import BM25AlarmIndex
                idx = BM25AlarmIndex()
                idx.build(alarms_raw)
                res = idx.search(query, top_k=5)
                st.write("Top Alarm IDs matching keywords:", res)
            elif "Semantic" in search_type:
                with st.spinner("Generating embeddings & searching ChromaDB..."):
                    from search.vector_index import VectorAlarmIndex
                    idx = VectorAlarmIndex()
                    idx.add_alarms(alarms_raw)
                    res = idx.search(query, top_k=5)
                    st.write("Semantic Match Results:", res)
            elif "Graph" in search_type:
                with st.spinner("Building network graph..."):
                    from search.graph_index import AlarmGraph
                    idx = AlarmGraph()
                    idx.build(alarms_raw)
                    st.write("Component Risk Ranking:", idx.component_risk_ranking()[:10])

with tab3:
    st.header("History & Analytics")
    
    st.subheader("Previously Processed PDFs")
    history_files = db.get_all_processed_files()
    
    if not history_files:
        st.info("No files processed yet.")
    else:
        for f in history_files:
            colA, colB, colC = st.columns([3, 2, 1])
            with colA:
                st.write(f"**{f.get('filename', 'Unknown')}**")
                st.caption(f"MD5: {f.get('md5')}")
            with colB:
                st.write(f"`Alarms: {f.get('record_counts', {}).get('alarms', 0)}` | `Params: {f.get('record_counts', {}).get('parameters', 0)}`")
                st.caption(f"Extracted: {f.get('processed_at')}")
            with colC:
                if st.button("Delete Data", key=f"del_{f['md5']}"):
                    if db.delete_processed_file(f['md5']):
                        st.success("Deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Deletion failed.")
        
    st.divider()
    st.subheader("Global Fault Analytics")
    
    alarms_raw = db.get_alarms({})
    if not alarms_raw:
        st.info("No alarms to analyze.")
    else:
        from analytics.fault_analytics import FaultAnalytics
        fa = FaultAnalytics(alarms_raw)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Alarms in DB", len(alarms_raw))
            st.metric("Electrical Fault Rate", f"{fa.electrical_fault_rate()}%")
        
        with col2:
            st.write("Top Combined Fault Categories (Reason 1 + 2)")
            st.dataframe(fa.top_fault_categories())
