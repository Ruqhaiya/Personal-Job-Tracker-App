import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI
import re
import os
from dotenv import load_dotenv

st.set_page_config(page_title="Job Tracker", layout="wide")

load_dotenv()

# Get API keys and password from environment variables or Streamlit secrets

openai_key = st.secrets["OPENAI_API_KEY"]
password_check = st.secrets["APP_PASSWORD"]

# Set up data directory - this ensures we have a consistent place to store CSV files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Custom Login ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.authenticated:
    st.title("Login")
    username_input = st.text_input("Username")
    password_input = st.text_input("Password", type="password")
    login_button = st.button("Login")

    if login_button:
        # Simple username/password check (replace with secure hash check in real use)
        if username_input in ["ruqhaiya", "Missy"] and password_input == password_check:
            st.session_state.authenticated = True
            st.session_state.username = username_input
            st.rerun()
        else:
            st.error("Invalid username or password")
else:
    username = st.session_state.username
    st.sidebar.success(f"Welcome, {username}")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

    st.title("Job Tracker")

    if not openai_key:
        st.error("Missing OpenAI API key. Please set it in your environment or Streamlit secrets.")
    else:
        client = OpenAI(api_key=openai_key)
    
    # Use the data directory for CSVs with proper path joining
    csv_path = os.path.join(DATA_DIR, f"job_tracker_{username}.csv")
    contacts_csv = os.path.join(DATA_DIR, f"job_contacts_{username}.csv")

    tab1, tab2, tab_dashboard, tab4 = st.tabs(["Add Job", "Data", "Dashboard", "Networking"])

    # --- Add Job Tab ---
    with tab1:
        st.header("Add Job to Tracker")
        job_link = st.text_input("Paste Job Link", placeholder="https://www.linkedin.com/jobs/view/...")
        job_description = st.text_area("Paste Job Description", height=300)

        def extract_company_name(job_link, job_description):
            # Try to extract from description first (after "at" or "with")
            match_desc = re.search(r'(?i)(?:at|with)\s+([A-Z][a-zA-Z0-9&.\s]+?)(?=[.,\n])', job_description)
            if match_desc:
                return match_desc.group(1).strip()

            # Fallback to extracting from link
            match_link = re.search(r'https?://(?:www\.)?([a-zA-Z0-9_-]+)\.', job_link)
            if match_link:
                return match_link.group(1).capitalize()

            return "Unknown"

        def clean_gpt_output(text):
            return re.sub(r"[\*\n]+", " ", text).strip()

        def extract_skills_with_openai(text):
            try:
                simple_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Return only the top 5 skills from this job description as a comma-separated list, no bullets, no markdown, no explanation."},
                        {"role": "user", "content": text}
                    ]
                )
                skill_list = clean_gpt_output(simple_response.choices[0].message.content)

                detailed_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Write a clean, markdown-free summary of the top 5 required skills in paragraph form (no * or ** or -)."},
                        {"role": "user", "content": text}
                    ]
                )
                skill_details = clean_gpt_output(detailed_response.choices[0].message.content)

                return skill_list, skill_details
            except Exception as e:
                return f"Error: {e}", f"Error: {e}"

        if st.button("Add to Tracker"):
            if job_link and job_description:
                company = extract_company_name(job_link, job_description)
                skills_list, skills_detail = extract_skills_with_openai(job_description)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                row = {
                    "Timestamp": timestamp,
                    "Job Link": job_link,
                    "Company": company,
                    "Job Description": job_description,
                    "Top Skills List": skills_list,
                    "Detailed Skills Summary": skills_detail
                }

                df = pd.DataFrame([row])
                
                # Make sure the data directory exists
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                
                if os.path.exists(csv_path):
                    df.to_csv(csv_path, mode='a', header=False, index=False)
                else:
                    df.to_csv(csv_path, index=False)

                st.success("Job added successfully!")
            else:
                st.warning("Please enter both job link and description.")

    # --- Data Tab  ---
    with tab2:
        st.markdown("## Job Tracker Data")

        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, parse_dates=["Timestamp"], on_bad_lines='skip')
                
                # Fallback before rendering the slider
                if "num_days_slider" not in st.session_state:
                    st.session_state["num_days_slider"] = 30

                with st.sidebar:
                    st.markdown("### Filters")

                    with st.form("filter_form"):
                        company_filter = st.text_input("Filter by Company", value=st.session_state.get("company_filter", ""))
                        keyword_filter = st.text_input("Search Keywords", value=st.session_state.get("keyword_filter", ""))
                        # Safely provide a fallback value without writing to session_state directly
                        num_days_value = st.session_state.get("num_days_slider", 30)
                        num_days = st.slider(
                            "Show jobs from last N days", 0, 60, value=num_days_value, key="num_days_slider"
                        )

                        submitted = st.form_submit_button("Apply Filters")
                        reset = st.form_submit_button("Reset Filters")

                        if reset:
                            # Remove values safely using pop
                            st.session_state.pop("company_filter", None)
                            st.session_state.pop("keyword_filter", None)
                            st.session_state.pop("num_days_slider", None)
                            st.rerun()
                        elif submitted:
                            st.session_state["company_filter"] = company_filter
                            st.session_state["keyword_filter"] = keyword_filter


                # Apply filters from session state
                filtered_df = df.copy()

                if st.session_state.get("company_filter"):
                    filtered_df = filtered_df[
                        filtered_df["Company"].str.contains(st.session_state["company_filter"], case=False, na=False)
                    ]

                if st.session_state.get("keyword_filter"):
                    filtered_df = filtered_df[
                        filtered_df["Top Skills List"].str.contains(st.session_state["keyword_filter"], case=False, na=False) |
                        filtered_df["Detailed Skills Summary"].str.contains(st.session_state["keyword_filter"], case=False, na=False) |
                        filtered_df["Job Description"].str.contains(st.session_state["keyword_filter"], case=False, na=False)
                    ]

                cutoff = pd.Timestamp.now() - pd.Timedelta(days=st.session_state.get("num_days_slider", 30))
                filtered_df = filtered_df[filtered_df["Timestamp"] >= cutoff]

                st.markdown(f"### Showing {len(filtered_df)} Jobs")
                st.dataframe(filtered_df, use_container_width=True, height=500)

                csv = filtered_df.to_csv(index=False)
                st.download_button("Download Filtered CSV", csv, "filtered_jobs.csv", "text/csv")
            except Exception as e:
                st.error(f"Error loading job data: {e}")
        else:
            st.info("No job data found. Add jobs in the 'Add Job' tab.")

    with tab_dashboard:
        st.markdown("## Job Insights Dashboard")

        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, parse_dates=["Timestamp"], on_bad_lines='skip')

                today = datetime.now()
                df['Date'] = df['Timestamp'].dt.date

                one_day_ago = today - timedelta(days=1)
                one_week_ago = today - timedelta(days=7)
                one_month_ago = today - timedelta(days=30)

                last_day = df[df['Timestamp'] >= one_day_ago]
                last_week = df[df['Timestamp'] >= one_week_ago]
                last_month = df[df['Timestamp'] >= one_month_ago]

                col1, col2, col3 = st.columns(3)
                col1.metric("Last 1 Day", f"{len(last_day)} Jobs")
                col2.metric("Last 7 Days", f"{len(last_week)} Jobs")
                col3.metric("Last 30 Days", f"{len(last_month)} Jobs")

                with st.expander("See more time-based insights"):
                    st.markdown("### Jobs Over Time")
                    if not df['Date'].empty:
                        date_counts = df['Date'].value_counts().sort_index()
                        if not date_counts.empty:
                            st.bar_chart(date_counts)
                        else:
                            st.info("Not enough data to show time-based insights.")
                    else:
                        st.info("No date data available for time-based insights.")
            except Exception as e:
                st.error(f"Error loading dashboard data: {e}")
        else:
            st.info("No job data found. Add jobs in the 'Add Job' tab.")

    with tab4:
        # st.markdown("### People Contacted for Jobs")

        # Show/hide contact form
        show_form = st.toggle("➕ Add New Contact", value=False)

        if show_form:
            st.markdown("### Add a New Contact Entry")
            with st.form("contact_form"):
                job_role = st.text_input("Job Role", placeholder="e.g., Data Analyst")
                company = st.text_input("Company", placeholder="e.g., Google")
                job_link = st.text_input("Job Link", placeholder="Paste the job link")
                people_contacted = st.text_area("People Contacted", placeholder="Comma-separated names")

                submitted = st.form_submit_button("Save Contact")
                if submitted:
                    if job_role and company and job_link and people_contacted:
                        new_row = {
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Job Role": job_role,
                            "Company": company,
                            "Job Link": job_link,
                            "People Contacted": people_contacted
                        }

                        # Make sure the data directory exists
                        os.makedirs(os.path.dirname(contacts_csv), exist_ok=True)
                        
                        new_df = pd.DataFrame([new_row])
                        if os.path.exists(contacts_csv):
                            new_df.to_csv(contacts_csv, mode="a", header=False, index=False)
                        else:
                            new_df.to_csv(contacts_csv, index=False)

                        st.success("Contact entry saved!")
                    else:
                        st.warning("Please fill out all fields.")

        # Show cards by default
        if os.path.exists(contacts_csv):
            try:
                st.markdown("### People You've Reached Out To")
                df = pd.read_csv(contacts_csv)

                for i, row in df.iterrows():
                    with st.expander(f"🔹 {row['Job Role']} @ {row['Company']}"):
                        st.markdown(f"People Contacted: {row['People Contacted']}")
                        st.markdown(f"Job Link: [Click here]({row['Job Link']})")
                        st.caption(f" Logged on {row['Timestamp']}")
            except Exception as e:
                st.error(f"Error loading contacts data: {e}")
        else:
            st.info("You haven't logged any contacts yet.")