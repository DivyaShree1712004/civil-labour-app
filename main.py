import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import os

# Create a folder to save uploaded work images if it doesn't exist
IMAGE_DIR = "uploaded_work_images"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# 1. CONNECT TO DATABASE
conn = sqlite3.connect("construction_site.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")

cursor.execute("""
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT,
    daily_rate REAL
)
""")

# UPDATED: Added image_path column to store the reference of the work done image
cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    date TEXT,
    worker_id INTEGER,
    status TEXT,
    advance_paid REAL DEFAULT 0,
    image_path TEXT,
    PRIMARY KEY (date, worker_id)
)
""")
conn.commit()

# 2. APP TITLE & HORIZONTAL NAVIGATION
st.set_page_config(layout="wide")
st.title("🏗️ Civil AI: Labor & Wage Manager")

menu_options = [
    "Mark Attendance", 
    "🎙️ AI Voice Attendance", 
    "Add New Worker", 
    "❌ Delete Worker", 
    "View Wage Reports"
]

choice = st.radio(
    "Navigation Menu", 
    options=menu_options, 
    horizontal=True, 
    label_visibility="collapsed"
)

st.markdown("---") 

# 3. FEATURE: ADD NEW WORKER
if choice == "Add New Worker":
    st.subheader("👤 Register a New Laborer")
    with st.form("worker_form"):
        name = st.text_input("Worker Full Name")
        role = st.selectbox("Role/Craft", ["Mason (Kothanar)", "Helper (Sithal)", "Bar Bender", "Carpenter", "Painter"])
        daily_rate = w_rate = st.number_input("Daily Wage Rate (₹)", min_value=100, max_value=2000, value=600, step=50)
        submit = st.form_submit_button("Save Worker to Database")
        
        if submit and name:
            cursor.execute("INSERT INTO workers (name, role, daily_rate) VALUES (?, ?, ?)", (name, role, daily_rate))
            conn.commit()
            st.success(f"Successfully registered {name} as a {role}!")

# 4. FEATURE: DELETE WORKER
elif choice == "❌ Delete Worker":
    st.subheader("🗑️ Remove a Worker from the System")
    workers_df = pd.read_sql_query("SELECT id, name, role FROM workers", conn)
    
    if workers_df.empty:
        st.warning("No workers available to delete.")
    else:
        worker_options = {f"{row['id']} - {row['name']} ({row['role']})": row['id'] for index, row in workers_df.iterrows()}
        selected_worker_label = st.selectbox("Select Worker to Permanently Remove", list(worker_options.keys()))
        selected_id = worker_options[selected_worker_label]
        
        st.warning("⚠️ Warning: Deleting a worker will permanently erase their registration profile.")
        confirm = st.checkbox("I understand and want to permanently delete this worker.")
        delete_btn = st.button("🚨 Delete Worker Now")
        
        if delete_btn:
            if confirm:
                cursor.execute("DELETE FROM attendance WHERE worker_id = ?", (selected_id,))
                cursor.execute("DELETE FROM workers WHERE id = ?", (selected_id,))
                conn.commit()
                st.success("Worker and all related records have been deleted successfully!")
            else:
                st.error("Please check the confirmation box before clicking Delete.")

# 5. FEATURE: MARK DAILY ATTENDANCE (MANUAL WITH CAMERA)
elif choice == "Mark Attendance":
    st.subheader("📅 Daily Attendance, Cash Advances & Work Proof")
    today = str(date.today())
    st.info(f"Date: {today}")
    
    workers = pd.read_sql_query("SELECT * FROM workers", conn)
    
    if workers.empty:
        st.warning("No workers registered yet. Please go to 'Add New Worker' first.")
    else:
        # We loop through each worker and create an attendance card block
        for index, row in workers.iterrows():
            w_id, w_name, w_role, w_rate = row['id'], row['name'], row['role'], row['daily_rate']
            
            st.markdown(f"### 👷 {w_name} ({w_role})")
            
            col1, col2, col3 = st.columns([1, 1.5, 1.5])
            
            with col1:
                status = st.radio(f"Status", ["Present", "Half-Day", "Absent"], key=f"status_{w_id}", horizontal=True)
                advance = st.number_input(f"Advance Given (₹)", min_value=0, max_value=1000, value=0, step=50, key=f"adv_{w_id}")
            
            with col2:
                # Camera widget for workers to take photo of work done
                img_file = st.camera_input(f"Take a photo of work done", key=f"cam_{w_id}")
            
            with col3:
                # Optional file uploader if camera is busy or they want to choose from mobile gallery
                uploaded_file = st.file_uploader(f"Or upload photo from gallery", type=["jpg", "jpeg", "png"], key=f"file_{w_id}")
            
            # Determine which file to use (prioritize live camera capture)
            final_photo = img_file if img_file is not None else uploaded_file
            saved_image_path = None
            
            if final_photo:
                # Create a unique filename for the image using the date and worker ID
                file_extension = final_photo.name.split(".")[-1]
                saved_image_path = os.path.join(IMAGE_DIR, f"{today}_{w_id}.{file_extension}")
                
                with open(saved_image_path, "wb") as f:
                    f.write(final_photo.getbuffer())
            
            # Insert or update data including the image path reference
            cursor.execute("""
            INSERT INTO attendance (date, worker_id, status, advance_paid, image_path)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date, worker_id) DO UPDATE SET 
                status=excluded.status, 
                advance_paid=excluded.advance_paid,
                image_path=COALESCE(excluded.image_path, attendance.image_path)
            """, (today, w_id, status, advance, saved_image_path))
            
            st.markdown("---")
        
        if st.button("💾 Save Today's Attendance Logs & Images", use_container_width=True):
            conn.commit()
            st.success("All attendance logs and work proof photos saved successfully!")

# 6. FEATURE: AI VOICE ATTENDANCE
elif choice == "🎙️ AI Voice Attendance":
    st.subheader("🎙️ Talk to Mark Attendance")
    today = str(date.today())
    
    c1, c2 = st.columns(2)
    with c1:
        start_rec = st.button("🔴 START", use_container_width=True)
    with c2:
        stop_rec = st.button("⏹️ STOP", use_container_width=True)
        
    if start_rec:
        st.session_state.recording_active = True
        st.info("⏺️ Microphone stream active... Click inside the text box below and press Windows Key + H to start speaking.")
        
    if stop_rec:
        st.session_state.recording_active = False
        st.warning("⏹️ Recording stopped.")
        
    voice_input = st.text_input("📝 Spoken Words Appear Here:", placeholder="Example: priya is present advance 100")
    
    if voice_input:
        st.info("AI Text Processor matching with Database records...")
        workers = pd.read_sql_query("SELECT * FROM workers", conn)
        text_lower = voice_input.lower()
        actions_taken = []
        
        for index, row in workers.iterrows():
            w_id, w_name = row['id'], row['name']
            w_name_lower = w_name.lower()
            
            if w_name_lower in text_lower:
                status = "Present"
                advance = 0
                
                if "absent" in text_lower or "leave" in text_lower:
                    status = "Absent"
                elif "half" in text_lower:
                    status = "Half-Day"
                    
                words = text_lower.split()
                for i, word in enumerate(words):
                    if word == "advance" or word == "cash":
                        if i + 1 < len(words) and words[i+1].isdigit():
                            advance = float(words[i+1])
                
                cursor.execute("""
                INSERT INTO attendance (date, worker_id, status, advance_paid)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, worker_id) DO UPDATE SET status=excluded.status, advance_paid=excluded.advance_paid
                """, (today, w_id, status, advance))
                conn.commit()
                
                actions_taken.append(f"✅ AI Action processed: Marked **{w_name}** as *{status}* (Advance: ₹{advance})")
        
        if actions_taken:
            for action in actions_taken:
                st.write(action)
            st.balloons()
        else:
            st.warning("Processed sentence text string completely but couldn't verify name matches inside the database records.")

# 7. FEATURE: WAGE REPORTS & PAYOUTS (WITH IMAGE LINKS)
elif choice == "View Wage Reports":
    st.subheader("📊 Net Payout Ledger & Work Proof Verification")
    
    # Updated query to pull the latest image path recorded for each worker
    query = """
    SELECT 
        w.name AS [Worker Name],
        w.role AS [Role],
        w.daily_rate AS [Daily Rate],
        COUNT(CASE WHEN a.status = 'Present' THEN 1 END) AS [Full Days Worked],
        COUNT(CASE WHEN a.status = 'Half-Day' THEN 1 END) AS [Half Days Worked],
        SUM(IFNULL(a.advance_paid, 0)) AS [Total Advances Borrowed],
        MAX(a.image_path) AS [Latest Image Path],
        SUM(
            CASE 
                WHEN a.status = 'Present' THEN w.daily_rate
                WHEN a.status = 'Half-Day' THEN (w.daily_rate * 0.5)
                ELSE 0 
            END
        ) - SUM(IFNULL(a.advance_paid, 0)) AS [Net Final Payout (₹)]
    FROM workers w
    LEFT JOIN attendance a ON w.id = a.worker_id
    GROUP BY w.id
    """
