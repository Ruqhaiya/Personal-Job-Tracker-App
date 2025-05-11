import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI
import re
import os
from dotenv import load_dotenv

import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Job Tracker", layout="wide")

# openai_key = os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))
# password_check = os.getenv("APP_PASSWORD", st.secrets.get("APP_PASSWORD", ""))

openai_key = st.secrets["OPENAI_API_KEY"]
password_check = st.secrets["APP_PASSWORD"]

def get_gsheet_client():
    creds_info = json.loads(st.secrets["GCP_SA_JSON"])
    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def get_user_sheet(username):
    client = get_gsheet_client()
    sh = client.open_by_key(st.secrets["GSHEET_ID"])
    try:
        ws = sh.worksheet(username)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=username, rows="1000", cols="20")
        ws.append_row(["Timestamp","Job Link","Company","Job Description","Top Skills List","Detailed Skills Summary"])
    return ws

def append_job_row(username, row):
    ws = get_user_sheet(username)
    ws.append_row([
        row["Timestamp"],
        row["Job Link"],
        row["Company"],
        row["Job Description"],
        row["Top Skills List"],
        row["Detailed Skills Summary"]
    ])

def fetch_job_df(username):
    ws = get_user_sheet(username)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def get_contacts_sheet(username):
    client = get_gsheet_client()
    sh = client.open_by_key(st.secrets["GSHEET_ID"])
    title = f"contacts_{username}"
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows="1000", cols="10")
        ws.append_row(["Timestamp","Job Role","Company","Job Link","People Contacted"])
    return ws

def append_contact_row(username, row):
    ws = get_contacts_sheet(username)
    ws.append_row([
        row["Timestamp"],
        row["Job Role"],
        row["Company"],
        row["Job Link"],
        row["People Contacted"]
    ])

def fetch_contacts_df(username):
    ws = get_contacts_sheet(username)
    data = ws.get_all_records()
    return pd.DataFrame(data)

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
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")
else:
    username = st.session_state.username
    st.sidebar.success(f"Welcome, {username}")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.experimental_rerun()

    st.title("Job Tracker")

    if not openai_key:
        st.error("Missing OpenAI API key. Please set it in your environment or Streamlit secrets.")
    else:
        client = OpenAI(api_key=openai_key)

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

                append_job_row(username, row)

                st.success("Job added successfully!")
            else:
                st.warning("Please enter both job link and description.")

    # --- Data Tab  ---
    with tab2:
        st.markdown("## Job Tracker Data")

        df = fetch_job_df(username)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
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
                    st.experimental_rerun()

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

    # --- Dashboard Tab ---
    with tab_dashboard:
        st.markdown("## Job Insights Dashboard")
        df = fetch_job_df(username)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])

        today = datetime.now()
        df['Date'] = df['Timestamp'].dt.date

        last_day   = df[df['Timestamp'] >= today - timedelta(days=1)]
        last_week  = df[df['Timestamp'] >= today - timedelta(days=7)]
        last_month = df[df['Timestamp'] >= today - timedelta(days=30)]

        col1, col2, col3 = st.columns(3)
        col1.metric("Last 1 Day",   f"{len(last_day)} Jobs")
        col2.metric("Last 7 Days",  f"{len(last_week)} Jobs")
        col3.metric("Last 30 Days", f"{len(last_month)} Jobs")

        with st.expander("See more time-based insights"):
            st.markdown("### Jobs Over Time")
            st.bar_chart(df['Date'].value_counts().sort_index())


    # --- Networking Tab ---
    with tab4:
        st.markdown("## People You’ve Reached Out To")

        show_form = st.toggle("Add New Contact", value=False)
        if show_form:
            with st.form("contact_form"):
                job_role        = st.text_input("Job Role")
                company         = st.text_input("Company")
                job_link        = st.text_input("Job Link")
                people_contacted= st.text_area("People Contacted")

                submitted = st.form_submit_button("Save Contact")
                if submitted:
                    new_row = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Job Role": job_role,
                        "Company": company,
                        "Job Link": job_link,
                        "People Contacted": people_contacted
                    }
                    append_contact_row(username, new_row)
                    st.success("Contact entry saved!")

        contacts_df = fetch_contacts_df(username)
        if contacts_df.empty:
            st.info("You haven’t logged any contacts yet.")
        else:
            for _, row in contacts_df.sort_values("Timestamp", ascending=False).iterrows():
                with st.expander(f"{row['Job Role']} @ {row['Company']}"):
                    st.markdown(f"**People Contacted:** {row['People Contacted']}")
                    st.markdown(f"**Job Link:** [Link]({row['Job Link']})")
                    st.caption(f"Logged on {row['Timestamp']}")
