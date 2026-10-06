"""
ui/app.py
===============================================================================
Streamlit Web Application for AI-Powered University Student Services Assistant.

Features:
1. Student Assistant Chat Portal (Q&A with authentication, citations, & audit traces)
2. Admin Dashboard:
   - PDF Document Ingestion (POST /ingest)
   - Student Dataset Loader (POST /load-students)
   - Ingested Sources Catalog Viewer (GET /sources)
   - System Diagnostics (GET /health)
===============================================================================
"""

import os
import json
import requests
import streamlit as st

# Configure Streamlit page layout
st.set_page_config(
    page_title="University AI Student Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_api_url() -> str:
    """Finds working backend API URL automatically (env var -> http://api:8000 -> http://localhost:8000)."""
    env_url = os.getenv("API_BASE_URL")
    urls_to_try = [env_url, "http://api:8000", "http://localhost:8000"]
    urls_to_try = [u for u in urls_to_try if u]
    
    for url in urls_to_try:
        try:
            res = requests.get(f"{url}/health", timeout=1)
            if res.status_code == 200:
                return url
        except Exception:
            continue
    return urls_to_try[0]

# Dynamic API BASE URL
API_BASE_URL = get_api_url()

st.sidebar.title("🎓 University AI Assistant")
app_mode = st.sidebar.radio(
    "Navigation Menu",
    ["💬 Student Assistant Portal", "⚙️ Admin & Data Pipeline Dashboard"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 LLM Engine Settings")
provider_choice = st.sidebar.selectbox(
    "Select LLM Provider",
    ["Auto (Cloud / Ollama / Fallback RAG)", "Groq Cloud (Free/Fast)", "OpenAI (GPT-4o-mini)", "Google Gemini", "Local Ollama"]
)

if provider_choice == "Groq Cloud (Free/Fast)":
    gkey = st.sidebar.text_input("Groq API Key (gsk_...)", type="password", value=os.getenv("GROQ_API_KEY", ""))
    if gkey:
        os.environ["GROQ_API_KEY"] = gkey
elif provider_choice == "OpenAI (GPT-4o-mini)":
    okey = st.sidebar.text_input("OpenAI API Key (sk-...)", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    if okey:
        os.environ["OPENAI_API_KEY"] = okey
elif provider_choice == "Google Gemini":
    gmkey = st.sidebar.text_input("Gemini API Key (AIza...)", type="password", value=os.getenv("GEMINI_API_KEY", ""))
    if gmkey:
        os.environ["GEMINI_API_KEY"] = gmkey
elif provider_choice == "Local Ollama":
    ourl = st.sidebar.text_input("Ollama Base URL", value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    os.environ["OLLAMA_BASE_URL"] = ourl


# =============================================================================
# Mode 1: Student Assistant Portal (Q&A)
# =============================================================================
if app_mode == "💬 Student Assistant Portal":
    st.header("🎓 Student Services Assistant")
    st.markdown("Ask questions about academic regulations, eligibility, attendance, and campus policies.")

    # Student Authentication Sidebar / Header
    with st.expander("👤 Student Login & Identity (Optional)", expanded=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            student_id = st.text_input("Student ID (e.g. S1001)", value=st.session_state.get("student_id", ""))
        with col2:
            student_pass = st.text_input("Password (fullname+programme)", type="password", value=st.session_state.get("student_pass", ""))
        with col3:
            st.write(" ")
            st.write(" ")
            if st.button("Authenticate Student"):
                if student_id and student_pass:
                    try:
                        res = requests.post(f"{API_BASE_URL}/auth/login", data={"student_id": student_id, "password": student_pass})
                        if res.status_code == 200:
                            st.session_state["authenticated"] = True
                            st.session_state["student_info"] = res.json()["student"]
                            st.session_state["student_id"] = student_id
                            st.session_state["student_pass"] = student_pass
                            st.success(f"Welcome, {st.session_state['student_info']['full_name']}!")
                        else:
                            st.error("Invalid Student ID or Password.")
                    except Exception as e:
                        st.error(f"Failed to connect to API server: {e}")
                else:
                    st.warning("Please enter both Student ID and Password.")

    # Display logged in student profile details if authenticated
    if st.session_state.get("authenticated") and st.session_state.get("student_info"):
        s = st.session_state["student_info"]
        st.info(f"**Logged in as:** {s['full_name']} ({s['student_id']}) | **Programme:** {s['programme']} | **CGPA:** {s['cgpa']} | **Backlogs:** {s['active_backlogs']}")

    # Q&A Input Section
    st.subheader("Ask a Question")
    user_question = st.text_input(
        "Enter your query:", 
        placeholder="e.g. What is my attendance in CS201? Or Am I eligible for supplementary exams?"
    )
    
    col_ask, col_date = st.columns([4, 1])
    with col_date:
        eval_date = st.date_input("As-of Date")
    
    if col_ask.button("Submit Question", type="primary"):
        if not user_question.strip():
            st.warning("Please enter a valid question.")
        else:
            headers = {}
            if st.session_state.get("authenticated") and st.session_state.get("student_id"):
                headers["X-Student-Id"] = st.session_state["student_id"]

            payload = {
                "question": user_question,
                "as_of_date": str(eval_date)
            }

            with st.spinner("Processing question through RAG vector store & rules engine..."):
                try:
                    response = requests.post(f"{API_BASE_URL}/ask", json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()

                        # Display Assistant Answer
                        st.subheader("💡 Answer")
                        st.success(data["answer"])

                        # Display Metadata Tabs
                        tab_exp, tab_cit, tab_tools, tab_rules, tab_audit = st.tabs([
                            "📝 Explanation", "📚 Citations", "🛠 Tools Executed", "⚖️ Applied Rules", "🔍 Audit Trace"
                        ])

                        with tab_exp:
                            st.write(data.get("explanation") or "No detailed step explanation required.")

                        with tab_cit:
                            if data.get("citations"):
                                for c in data["citations"]:
                                    st.markdown(f"- **Doc ID:** `{c['doc_id']}` | **Title:** {c['title']} | **Section:** {c['section']} | **Version:** {c['version']}")
                            else:
                                st.write("No document citations required for this answer.")

                        with tab_tools:
                            if data.get("tools_invoked"):
                                st.json(data["tools_invoked"])
                            else:
                                st.write("No external tools executed.")

                        with tab_rules:
                            if data.get("applied_rules"):
                                st.json(data["applied_rules"])
                            else:
                                st.write("No policy rules evaluated.")

                        with tab_audit:
                            st.write(f"**Trace ID:** `{data['trace_id']}`")
                            st.json(data)

                    else:
                        st.error(f"API Error ({response.status_code}): {response.text}")
                except Exception as e:
                    st.error(f"Could not connect to FastAPI server at `{API_BASE_URL}`: {e}")


# =============================================================================
# Mode 2: Admin & Data Pipeline Dashboard (Protected by Admin Auth)
# =============================================================================
else:
    st.header("⚙️ Admin & Pipeline Management")

    # Check if Admin is authenticated
    if not st.session_state.get("admin_authenticated"):
        st.warning("🔒 Admin Authentication Required")
        with st.form("admin_login_form"):
            admin_user = st.text_input("Admin Username", value="admin")
            admin_pass = st.text_input("Admin Password", type="password", value="admin123")
            submitted = st.form_submit_button("Login as Admin", type="primary")

            if submitted:
                try:
                    res = requests.post(f"{API_BASE_URL}/auth/admin-login", data={"username": admin_user, "password": admin_pass})
                    if res.status_code == 200:
                        st.session_state["admin_authenticated"] = True
                        st.session_state["admin_user"] = admin_user
                        st.success("Admin Authentication Successful!")
                        st.rerun()
                    else:
                        st.error("Invalid Admin Username or Password.")
                except Exception as e:
                    st.error(f"Failed to connect to API server at `{API_BASE_URL}`: {e}")
    else:
        st.success(f"🔓 Logged in as Admin (`{st.session_state.get('admin_user', 'admin')}`)")
        if st.button("Logout Admin"):
            st.session_state["admin_authenticated"] = False
            st.rerun()

        admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
            "📄 Document Ingestion (POST /ingest)", 
            "👥 Load Student Dataset (POST /load-students)",
            "📋 Ingested Sources Catalog (GET /sources)",
            "💚 System Health Diagnostic"
        ])

        # -------------------------------------------------------------------------
        # Tab 1: PDF Document Ingestion
        # -------------------------------------------------------------------------
        with admin_tab1:
            st.subheader("Upload & Index University Regulation PDF")
            
            uploaded_pdf = st.file_uploader("Upload Policy Document (PDF)", type=["pdf"])
            
            col1, col2 = st.columns(2)
            with col1:
                doc_id = st.text_input("Document ID (doc_id)", value="ACAD-REG-2024")
                title = st.text_input("Document Title", value="Academic Regulations for B.Tech")
                issuer = st.text_input("Issuer", value="Office of the Dean (Academics)")
                authority_level = st.slider("Authority Level (1 = Highest, 5 = Untrusted)", 1, 5, 1)
                doc_type = st.selectbox("Document Type", ["regulation", "circular", "notice", "faq", "handbook", "unofficial"])
            with col2:
                version = st.text_input("Version", value="3.1")
                effective_from = st.date_input("Effective From Date")
                effective_to = st.text_input("Effective To Date (YYYY-MM-DD or empty)", value="")
                supersedes = st.text_input("Supersedes (doc_id)", value="")
                scope_programmes = st.text_input("Scope Programmes", value="B.Tech CSE, B.Tech ECE")
                scope_batches = st.text_input("Scope Batches", value="2023+")

            if st.button("Upload & Process Ingestion Pipeline", type="primary"):
                if not uploaded_pdf:
                    st.warning("Please select a PDF file to upload.")
                elif not doc_id or not title:
                    st.warning("doc_id and title are required fields.")
                else:
                    meta_json = {
                        "doc_id": doc_id,
                        "title": title,
                        "issuer": issuer,
                        "authority_level": authority_level,
                        "doc_type": doc_type,
                        "version": version,
                        "effective_from": str(effective_from),
                        "effective_to": effective_to if effective_to else None,
                        "supersedes": supersedes if supersedes else None,
                        "scope_programmes": scope_programmes,
                        "scope_batches": scope_batches,
                        "provenance": "Streamlit Admin Upload",
                        "synthetic": 0
                    }

                    files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
                    data = {"metadata": json.dumps(meta_json)}

                    with st.spinner("Extracting text, computing vector embeddings, and updating ChromaDB..."):
                        try:
                            res = requests.post(f"{API_BASE_URL}/ingest", files=files, data=data)
                            if res.status_code == 201:
                                st.balloons()
                                st.success(f"Successfully Ingested Document `{doc_id}`!")
                                st.json(res.json())
                            else:
                                st.error(f"Ingestion Error ({res.status_code}): {res.text}")
                        except Exception as e:
                            st.error(f"Failed to connect to API server: {e}")

        # -------------------------------------------------------------------------
        # Tab 2: Load Student Dataset
        # -------------------------------------------------------------------------
        with admin_tab2:
            st.subheader("Load Student Test Dataset (Annex C Schema)")
            st.markdown("Upload a JSON file containing students, courses, attendance, and exam results.")
            
            json_file = st.file_uploader("Upload Dataset (JSON)", type=["json"])
            
            if st.button("Load Student Dataset into Database"):
                if json_file:
                    try:
                        payload = json.load(json_file)
                        res = requests.post(f"{API_BASE_URL}/load-students", json=payload)
                        if res.status_code == 200:
                            st.success("Student Dataset Loaded Successfully!")
                            st.json(res.json())
                        else:
                            st.error(f"Error ({res.status_code}): {res.text}")
                    except Exception as e:
                        st.error(f"Failed to load JSON file: {e}")
                else:
                    st.warning("Please select a JSON file first.")

        # -------------------------------------------------------------------------
        # Tab 3: Ingested Sources Catalog
        # -------------------------------------------------------------------------
        with admin_tab3:
            st.subheader("Catalog of Ingested Documents (source_register)")
            if st.button("Refresh Sources List"):
                try:
                    res = requests.get(f"{API_BASE_URL}/sources")
                    if res.status_code == 200:
                        sources = res.json()
                        if sources:
                            st.dataframe(sources)
                        else:
                            st.info("No documents currently ingested in source_register.")
                    else:
                        st.error(f"Error ({res.status_code}): {res.text}")
                except Exception as e:
                    st.error(f"Failed to fetch sources: {e}")

        # -------------------------------------------------------------------------
        # Tab 4: System Health Diagnostics
        # -------------------------------------------------------------------------
        with admin_tab4:
            st.subheader("System Infrastructure Health Diagnostics")
            if st.button("Run Health Probe"):
                try:
                    res = requests.get(f"{API_BASE_URL}/health")
                    if res.status_code == 200:
                        health = res.json()
                        st.json(health)
                        if health["status"] == "healthy":
                            st.success("All systems operational (SQLite & ChromaDB connected).")
                        else:
                            st.warning("System reporting degraded performance.")
                    else:
                        st.error(f"Health Probe Failed: {res.text}")
                except Exception as e:
                    st.error(f"Could not connect to FastAPI server: {e}")
