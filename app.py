import streamlit as st
import sqlite3
import PyPDF2
import pandas as pd
from datetime import datetime
import base64
import io
import hashlib

st.set_page_config(page_title="AURA", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FAFAFC; }
    .custom-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #E5E7EB;
        margin-bottom: 20px;
    }
    .custom-card h4 { color: #111827; margin-bottom: 10px; font-weight: 600; }
    .custom-card p { color: #4B5563; font-size: 14px; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E5E7EB; }
    .stTextInput input { border-radius: 8px; border: 1px solid #D1D5DB; }
    .stButton>button { border-radius: 8px; font-weight: 500; transition: all 0.2s; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

CORE_DEPTS = ["CIVIL", "MECH", "CSE", "IT", "ECE", "EEE", "MECHATRONICS", "CSBS", "AIML", "DS", "VLSA", "EEE(CS)", "ARCH"]
ALL_DEPTS = ["General"] + CORE_DEPTS

def init_db():
    conn = sqlite3.connect('campusconnect.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, 
                    role TEXT, department TEXT, year TEXT, interests TEXT, is_approved INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, uploader TEXT, category TEXT, 
                    department TEXT, upload_date TEXT, content TEXT, summary TEXT, file_data BLOB, verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS qa_board (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, asker TEXT, answer TEXT, answerer TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, author TEXT, post_type TEXT, content TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

def execute_query(query, params=()):
    conn = sqlite3.connect('campusconnect.db')
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def fetch_data(query, params=()):
    conn = sqlite3.connect('campusconnect.db')
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'role' not in st.session_state: st.session_state.role = ""
if 'dept' not in st.session_state: st.session_state.dept = ""
if 'year' not in st.session_state: st.session_state.year = ""
if 'interests' not in st.session_state: st.session_state.interests = ""
if 'current_page' not in st.session_state: st.session_state.current_page = "🏠 Dashboard"

init_db()

def extract_text(file_bytes):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "".join([page.extract_text() + " " for page in reader.pages if page.extract_text()]).strip()
    except Exception as e:
        return f"Error reading PDF: {e}"

def generate_ai_summary(text):
    if len(text) > 400: return text[:400] + "... [AI Summary: Document covers key concepts based on extracted text.]"
    return text + " [AI Summary Generated]"

def auto_categorize(text):
    text_lower = text.lower()
    if "syllabus" in text_lower or "unit" in text_lower: return "Syllabus/Notes"
    elif "question" in text_lower and "marks" in text_lower: return "Previous Year Papers"
    elif "placement" in text_lower or "interview" in text_lower: return "Placement Guide"
    return "General Academic Resource"

def display_resource_card(row, unique_key):
    verified_badge = "✅ Verified" if row['verified'] == 1 else "⏳ Unverified"
    with st.expander(f"📄 {row['filename']} ({verified_badge})"):
        st.write(f"**Uploader:** {row['uploader']} | **Dept:** {row['department']} | **Date:** {row['upload_date']}")
        st.info(f"**AI Summary:** {row['summary']}")
        
        if row['verified'] == 0 and st.session_state.role in ["Senior Student", "Faculty", "Admin"]:
            if st.button("✅ Verify Content", key=f"verify_{unique_key}_{row['id']}"):
                execute_query("UPDATE resources SET verified = 1 WHERE id = ?", (row['id'],))
                st.rerun()

        col1, col2 = st.columns([1, 4])
        with col1:
            st.download_button(label="📥 Download", data=row['file_data'], file_name=row['filename'], mime='application/pdf', key=f"dl_{unique_key}_{row['id']}")
        
        if st.toggle("👁️ Read Here", key=f"toggle_{unique_key}_{row['id']}"):
            base64_pdf = base64.b64encode(row['file_data']).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🎓 CampusConnect</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #4B5563;'>The AI-powered knowledge sharing platform.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])
        
        with tab_login:
            with st.form("login_form"):
                log_user = st.text_input("Username")
                log_pass = st.text_input("Password", type="password")
                if st.form_submit_button("Log In", use_container_width=True):
                    user_df = fetch_data("SELECT * FROM users WHERE username = ? AND password = ?", (log_user, hash_password(log_pass)))
                    if not user_df.empty:
                        # Check admin approval status
                        if user_df.iloc[0]['is_approved'] == 0:
                            st.error("Your Admin account is currently pending approval from an existing Admin.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.username = user_df.iloc[0]['username']
                            st.session_state.role = user_df.iloc[0]['role']
                            st.session_state.dept = user_df.iloc[0]['department']
                            st.session_state.year = user_df.iloc[0]['year']
                            st.session_state.interests = user_df.iloc[0]['interests']
                            st.rerun()
                    else:
                        st.error("Invalid username or password.")
                        
        with tab_register:
            # Removed st.form here to allow dynamic UI rendering (Year changing based on Role)
            reg_user = st.text_input("Choose Username")
            reg_pass = st.text_input("Choose Password", type="password")
            reg_role = st.selectbox("Role", ["Student", "Senior Student", "Faculty", "Admin"])
            reg_dept = st.selectbox("Department", CORE_DEPTS)
            
            # Dynamic Year Selection
            reg_year = "N/A"
            if reg_role == "Student":
                reg_year = st.selectbox("Year", ["1st Year", "2nd Year"])
            elif reg_role == "Senior Student":
                reg_year = st.selectbox("Year", ["3rd Year", "4th Year"])
                
            reg_inter = st.text_input("Core Interests (e.g., Robotics, Placements)")
            
            if st.button("Sign Up", use_container_width=True):
                if reg_user and reg_pass:
                    if fetch_data("SELECT * FROM users WHERE username = ?", (reg_user,)).empty:
                        
                        # First-Admin Verification Logic
                        is_approved = 1
                        if reg_role == "Admin":
                            # Check if ANY approved admin already exists
                            admin_count = fetch_data("SELECT COUNT(*) FROM users WHERE role = 'Admin' AND is_approved = 1").iloc[0,0]
                            if admin_count > 0:
                                is_approved = 0 # Requires approval from the first admin
                        
                        execute_query("INSERT INTO users (username, password, role, department, year, interests, is_approved) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                      (reg_user, hash_password(reg_pass), reg_role, reg_dept, reg_year, reg_inter, is_approved))
                        
                        if is_approved == 1:
                            st.success("Account created! Please switch to the Sign In tab.")
                        else:
                            st.warning("Account created! Since you requested Admin rights, you must wait for an existing Admin to approve you.")
                    else:
                        st.error("Username already exists.")
                else:
                    st.error("Please fill out username and password.")

else:
    # --- DYNAMIC SIDEBAR NAVIGATION ---
    with st.sidebar:
        st.markdown(f"### 📘 CampusConnect")
        st.caption(f"Logged in as **{st.session_state.username}**")
        st.write(f"**Role:** {st.session_state.role}")
        st.write(f"**Dept:** {st.session_state.dept}")
        if st.session_state.role in ["Student", "Senior Student"]:
            st.write(f"**Year:** {st.session_state.year}")
            
        st.divider()
        st.markdown("**GETTING STARTED**")
        if st.button("🏠 Dashboard", use_container_width=True, type="primary" if st.session_state.current_page == "🏠 Dashboard" else "secondary"):
            st.session_state.current_page = "🏠 Dashboard"
            st.rerun()
            
        st.markdown("**KNOWLEDGE BASE**")
        pages = ["📚 Academic Library", "💬 Q&A Platform", "💡 Senior Experiences"]
        for p in pages:
            if st.button(p, use_container_width=True, type="primary" if st.session_state.current_page == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()
                
        st.markdown("**AI TOOLS**")
        ai_pages = ["🔍 Global AI Search", "🤖 Ask CampusConnect", "☁️ Upload Hub"]
        for p in ai_pages:
            if st.button(p, use_container_width=True, type="primary" if st.session_state.current_page == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()
                
        st.divider()
        st.markdown("**ACCOUNT & SETTINGS**")
        if st.button("👤 My Profile", use_container_width=True, type="primary" if st.session_state.current_page == "👤 My Profile" else "secondary"):
            st.session_state.current_page = "👤 My Profile"
            st.rerun()
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # --- TOP NAVIGATION BREADCRUMB ---
    st.caption(f"Home > **{st.session_state.current_page.replace(' ', ' > ', 1)}**")

    # --- PAGE ROUTING LOGIC ---
    if st.session_state.current_page == "🏠 Dashboard":
        st.title("Dashboard Overview")
        st.write("Welcome to CampusConnect! This guide will help you understand the basics and get started with the platform.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
                <div class="custom-card">
                    <h4>🤖 AI-Powered Search</h4>
                    <p>Discover intelligent resources, automated summaries, and direct answers in seconds.</p>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("""
                <div class="custom-card">
                    <h4>📚 Verified Content</h4>
                    <p>Get reliable, actionable academic insights verified by seniors and faculty members.</p>
                </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown("""
                <div class="custom-card">
                    <h4>🤝 Peer Collaboration</h4>
                    <p>Connect with your department, ask questions, and share experiences safely.</p>
                </div>
            """, unsafe_allow_html=True)
            
        st.header(f"Recommended for {st.session_state.dept}")
        dept_resources = fetch_data("SELECT * FROM resources WHERE department = ? OR department = 'General' ORDER BY id DESC LIMIT 5", (st.session_state.dept,))
        if not dept_resources.empty:
            for _, row in dept_resources.iterrows():
                display_resource_card(row, "dash")
        else:
            st.write(f"No recent resources uploaded for {st.session_state.dept} yet.")

    elif st.session_state.current_page == "📚 Academic Library":
        st.title("Academic Resource Library")
        col1, col2 = st.columns([1, 2])
        with col1:
            # Allows searching in General + Core Depts
            filter_dept = st.selectbox("Filter by Department", ["All"] + ALL_DEPTS)
        with col2:
            lib_search = st.text_input("Search library by filename...")
            
        query = "SELECT * FROM resources" if filter_dept == "All" else f"SELECT * FROM resources WHERE department = '{filter_dept}'"
        library_df = fetch_data(query)
        
        if lib_search and not library_df.empty:
            library_df = library_df[library_df['filename'].str.contains(lib_search, case=False, na=False)]
            
        if not library_df.empty:
            for _, row in library_df.iterrows():
                display_resource_card(row, "lib")
        else:
            st.info("No documents found.")

    elif st.session_state.current_page == "💬 Q&A Platform":
        st.title("Student Q&A Platform")
        with st.form("ask_question"):
            new_q = st.text_input("Ask a question to your peers:")
            if st.form_submit_button("Post Question"):
                execute_query("INSERT INTO qa_board (question, asker, timestamp) VALUES (?, ?, ?)", (new_q, st.session_state.username, datetime.now().strftime("%Y-%m-%d %H:%M")))
                st.success("Question posted!")
                st.rerun()
                
        qa_search = st.text_input("Search discussions...")
        qa_df = fetch_data("SELECT * FROM qa_board ORDER BY id DESC")
        if qa_search and not qa_df.empty:
            mask = qa_df['question'].str.contains(qa_search, case=False, na=False) | qa_df['answer'].str.contains(qa_search, case=False, na=False)
            qa_df = qa_df[mask]
            
        for _, row in qa_df.iterrows():
            with st.expander(f"Q: {row['question']} (by {row['asker']})"):
                if row['answer']:
                    st.success(f"**{row['answerer']}:** {row['answer']}")
                else:
                    st.warning("No answer yet.")
                    with st.form(f"answer_form_{row['id']}"):
                        new_ans = st.text_area("Write an answer:")
                        if st.form_submit_button("Submit"):
                            execute_query("UPDATE qa_board SET answer = ?, answerer = ? WHERE id = ?", (new_ans, st.session_state.username, row['id']))
                            st.rerun()

    elif st.session_state.current_page == "💡 Senior Experiences":
        st.title("Senior Experiences & Guides")
        col1, col2 = st.columns([2, 1])
        with col1:
            exp_search = st.text_input("Search guides...")
            exp_df = fetch_data("SELECT * FROM experiences ORDER BY id DESC")
            if exp_search and not exp_df.empty:
                mask = exp_df['title'].str.contains(exp_search, case=False, na=False) | exp_df['content'].str.contains(exp_search, case=False, na=False)
                exp_df = exp_df[mask]
                
            for _, row in exp_df.iterrows():
                st.markdown(f"""
                <div class="custom-card">
                    <h4>{row['title']}</h4>
                    <p><b>By {row['author']}</b> | {row['post_type']} | {row['timestamp']}</p>
                    <hr>
                    <p>{row['content']}</p>
                </div>
                """, unsafe_allow_html=True)
                
        with col2:
            st.subheader("Share a Guide")
            with st.form("post_experience"):
                exp_title = st.text_input("Title")
                exp_type = st.selectbox("Category", ["Placement Tip", "Campus Life", "Study Hack"])
                exp_content = st.text_area("Your Guide")
                if st.form_submit_button("Publish"):
                    execute_query("INSERT INTO experiences (title, author, post_type, content, timestamp) VALUES (?, ?, ?, ?, ?)", 
                                  (exp_title, st.session_state.username, exp_type, exp_content, datetime.now().strftime("%Y-%m-%d")))
                    st.rerun()

    elif st.session_state.current_page == "🔍 Global AI Search":
        st.title("Global Natural-Language Search")
        search_query = st.text_input("Deep search through the full text of all uploaded PDF documents (Press Enter)...")
        if search_query:
            query_words = search_query.lower().split()
            all_resources = fetch_data("SELECT * FROM resources")
            if not all_resources.empty:
                all_resources['score'] = all_resources['content'].apply(lambda x: sum(1 for w in query_words if w in str(x).lower()))
                results = all_resources[all_resources['score'] > 0].sort_values(by='score', ascending=False)
                st.write(f"Found {len(results)} matches.")
                for _, row in results.iterrows():
                    display_resource_card(row, "search")

    elif st.session_state.current_page == "🤖 Ask CampusConnect":
        st.title("Ask CampusConnect")
        st.info("Ask questions and get AI answers directly from the college knowledge base (Verified PDFs only).")
        ai_query = st.text_input("What do you want to know?")
        if ai_query:
            # Queries ONLY verified resources as per DT Slide 10
            all_res = fetch_data("SELECT content FROM resources WHERE verified = 1")
            if not all_res.empty and any(any(w in str(row['content']).lower() for w in ai_query.lower().split()) for _, row in all_res.iterrows()):
                st.success(f"**CampusConnect AI:** Based on the verified resources uploaded by students, here is what I found regarding '{ai_query}'. (Simulated Response)")
            else:
                st.warning("**CampusConnect AI:** I couldn't find specific information about that in the verified database.")

    elif st.session_state.current_page == "☁️ Upload Hub":
        st.title("Upload & Process Resources")
        with st.form("upload_form", clear_on_submit=True):
            uploaded_file = st.file_uploader("Upload PDF Document", type=['pdf'])
            st.caption("⚙️ Powered by PyPDF2 Extraction Engine")
            # Includes General as an option for uploading
            target_dept = st.selectbox("Target Department", ALL_DEPTS)
            if st.form_submit_button("Process & Upload"):
                if uploaded_file:
                    with st.spinner("Extracting & Summarizing..."):
                        file_bytes = uploaded_file.getvalue()
                        extracted_text = extract_text(file_bytes)
                        execute_query(
                            "INSERT INTO resources (filename, uploader, category, department, upload_date, content, summary, file_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (uploaded_file.name, st.session_state.username, auto_categorize(extracted_text), target_dept, datetime.now().strftime("%Y-%m-%d %H:%M"), extracted_text, generate_ai_summary(extracted_text), file_bytes)
                        )
                    st.success("File uploaded successfully!")
                else:
                    st.error("Please attach a file.")

    elif st.session_state.current_page == "👤 My Profile":
        st.title(f"{st.session_state.username}'s Profile")
        
        # Calculate statistics
        uploads_count = fetch_data("SELECT COUNT(*) FROM resources WHERE uploader = ?", (st.session_state.username,)).iloc[0,0]
        qa_count = fetch_data("SELECT COUNT(*) FROM qa_board WHERE asker = ? OR answerer = ?", (st.session_state.username, st.session_state.username)).iloc[0,0]
        exp_count = fetch_data("SELECT COUNT(*) FROM experiences WHERE author = ?", (st.session_state.username,)).iloc[0,0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Resources Uploaded", uploads_count)
        c2.metric("Q&A Interactions", qa_count)
        c3.metric("Guides Shared", exp_count)
        
        # Admin Specific Controls
        if st.session_state.role == "Admin":
            st.divider()
            st.subheader("🛠️ Admin Controls - Pending Approvals")
            st.write("Review users who have requested Admin access.")
            
            pending_admins = fetch_data("SELECT id, username, department FROM users WHERE role = 'Admin' AND is_approved = 0")
            if not pending_admins.empty:
                for _, row in pending_admins.iterrows():
                    colA, colB = st.columns([4, 1])
                    with colA:
                        st.info(f"**Username:** {row['username']} | **Dept:** {row['department']}")
                    with colB:
                        if st.button("Approve", key=f"approve_{row['id']}", use_container_width=True):
                            execute_query("UPDATE users SET is_approved = 1 WHERE id = ?", (row['id'],))
                            st.rerun()
            else:
                st.success("No pending admin requests at this time.")
        
        st.divider()
        st.subheader("Your Recent Uploads")
        my_uploads = fetch_data("SELECT * FROM resources WHERE uploader = ? ORDER BY id DESC", (st.session_state.username,))
        if not my_uploads.empty:
            for _, row in my_uploads.iterrows():
                display_resource_card(row, "profile")
        else:
            st.info("You haven't uploaded any resources yet.")
