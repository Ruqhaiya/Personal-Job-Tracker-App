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
import base64, json

st.set_page_config(page_title="Job Tracker", layout="wide")

# openai_key = os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))
# password_check = os.getenv("APP_PASSWORD", st.secrets.get("APP_PASSWORD", ""))

openai_key = st.secrets["OPENAI_API_KEY"]
password_check = st.secrets["APP_PASSWORD"]

def get_gsheet_client():
    # 1. Base64-decode the JSON
    b64 = st.secrets["GCP_SA_B64"]
    creds_json = base64.b64decode(b64).decode("utf-8")

    # 2. Parse it
    creds_info = json.loads(creds_json)

    # 3. Build the credentials and authorize
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

    tab1, tab2, tab_dashboard, tab4 = st.tabs(["Add Job", "Data", "Dashboard", "Networking"])

    # --- Add Job Tab ---
    # with tab1:
    #     st.header("Add Job to Tracker")
    #     job_link = st.text_input("Paste Job Link", placeholder="https://www.linkedin.com/jobs/view/...")
    #     job_description = st.text_area("Paste Job Description", height=300)

    def extract_company_name(job_link: str, job_description: str) -> str:
        """
        Uses OpenAI to reliably extract the company name from a job link and description.
        Falls back to "Unknown" on any error.
        """
        try:
            prompt = (
                "You are a data extraction assistant.  \n"
                "Given a job posting, identify and return only the name of the hiring company.  \n"
                "If you cannot determine it, return 'Unknown'.\n\n"
                f"Job Link: {job_link}\n\n"
                f"Job Description:\n{job_description}"
            )
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",  "content": "You extract structured fields from unstructured text."},
                    {"role": "user",    "content": prompt}
                ]
            )
            company = resp.choices[0].message.content.strip()
            # Make sure we never return an empty string
            return company if company else "Unknown"
        except Exception as e:
            # On error, log and return Unknown
            st.error(f"Error extracting company name: {e}")
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

        # if st.button("Add to Tracker"):
        #     if job_link and job_description:
        #         company = extract_company_name(job_link, job_description)
        #         skills_list, skills_detail = extract_skills_with_openai(job_description)
        #         timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        #         row = {
        #             "Timestamp": timestamp,
        #             "Job Link": job_link,
        #             "Company": company,
        #             "Job Description": job_description,
        #             "Top Skills List": skills_list,
        #             "Detailed Skills Summary": skills_detail
        #         }

        #         append_job_row(username, row)

        #         st.success("Job added successfully!")
        #     else:
        #         st.warning("Please enter both job link and description.")

    # --- Add Job Tab ---
    with tab1:
        st.header("Add Job to Tracker")

        # Wrap inputs in a st.form so we can have two buttons
        with st.form("job_form"):
            job_link = st.text_input(
                "Paste Job Link",
                placeholder="https://www.linkedin.com/jobs/view/...",
                key="job_link_input"
            )
            job_description = st.text_area(
                "Paste Job Description",
                height=300,
                key="job_desc_input"
            )

            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Add to Tracker")
            with col2:
                clear = st.form_submit_button("Clear Form")

            if clear:
                # Clear the inputs by resetting the session state
                st.session_state["job_link_input"] = ""
                st.session_state["job_desc_input"] = ""
                st.rerun()

            if submit:
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

                    # Optionally, clear the form right after successful submit
                    st.session_state["job_link_input"] = ""
                    st.session_state["job_desc_input"] = ""
                    st.rerun()

                else:
                    st.warning("Please enter both job link and description.")
    # --- Data Tab ---
    with tab2:
        st.markdown("## Job Tracker Data")
        df = fetch_job_df(username)

        if df.empty:
            st.info("No job data found. Add a job in the \"Add Job\" tab.")
        else:
            # Ensure Timestamp is datetime
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])

            # Initialize filter defaults
            if "company_filter" not in st.session_state:
                st.session_state.company_filter = ""
            if "keyword_filter" not in st.session_state:
                st.session_state.keyword_filter = ""
            if "num_days_slider" not in st.session_state:
                st.session_state.num_days_slider = 30

            # Sidebar filter form
            with st.sidebar:
                st.markdown("### Filters")
                with st.form("filter_form"):
                    company_filter = st.text_input(
                        "Filter by Company",
                        value=st.session_state.company_filter
                    )
                    keyword_filter = st.text_input(
                        "Search Keywords",
                        value=st.session_state.keyword_filter
                    )
                    num_days = st.slider(
                        "Show jobs from last N days",
                        0, 60,
                        value=st.session_state.num_days_slider,
                        key="num_days_slider"
                    )
                    apply = st.form_submit_button("Apply Filters")
                    reset = st.form_submit_button("Reset Filters")

                    if reset:
                        st.session_state.company_filter = ""
                        st.session_state.keyword_filter = ""
                        st.session_state.num_days_slider = 30
                        st.experimental_rerun()
                    if apply:
                        st.session_state.company_filter = company_filter
                        st.session_state.keyword_filter = keyword_filter

            # Apply filters
            filtered = df
            if st.session_state.company_filter:
                filtered = filtered[
                    filtered["Company"]
                            .str.contains(st.session_state.company_filter, case=False, na=False)
                ]
            if st.session_state.keyword_filter:
                filtered = filtered[
                    filtered["Top Skills List"].str.contains(st.session_state.keyword_filter, case=False, na=False)
                | filtered["Detailed Skills Summary"].str.contains(st.session_state.keyword_filter, case=False, na=False)
                | filtered["Job Description"].str.contains(st.session_state.keyword_filter, case=False, na=False)
                ]
            if st.session_state.num_days_slider > 0:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=st.session_state.num_days_slider)
                filtered = filtered[filtered["Timestamp"] >= cutoff]

            # Show table & download
            st.markdown(f"### Showing {len(filtered)} jobs")
            st.dataframe(filtered, use_container_width=True, height=400)
            csv = filtered.to_csv(index=False)
            st.download_button("Download Filtered CSV", csv, "filtered_jobs.csv", "text/csv")

    # --- Dashboard Tab ---
    with tab_dashboard:
        st.markdown("## Job Insights Dashboard")

        # Fetch & prepare data
        df = fetch_job_df(username)
        if df.empty or "Timestamp" not in df.columns:
            st.info("No job data to show. Add a job in the \"Add Job\" tab first.")
        else:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
            df["Date"] = df["Timestamp"].dt.date

        # Summary metrics
        today = datetime.now()
        last_day   = df[df['Timestamp'] >= today - timedelta(days=1)]
        last_week  = df[df['Timestamp'] >= today - timedelta(days=7)]
        last_month = df[df['Timestamp'] >= today - timedelta(days=30)]

        col1, col2, col3 = st.columns(3)
        col1.metric("Last 1 Day",   f"{len(last_day)}")
        col2.metric("Last 7 Days",  f"{len(last_week)}")
        col3.metric("Last 30 Days", f"{len(last_month)}")

        st.markdown("---")

        # 1) Jobs Over Time (line chart)
        jobs_per_day = df['Date'].value_counts().sort_index()
        st.subheader("Jobs Over Time")
        st.line_chart(jobs_per_day)

        # 2) Top Companies (bar chart)
        st.subheader("Top Companies Applied To")
        company_counts = df['Company'].value_counts().head(10)
        st.bar_chart(company_counts)

        # # 3) Top Skills (bar chart)
        # st.subheader("Top Skills Across All Applications")
        # # explode the comma-separated skill lists into a Series of individual skills
        # all_skills = (
        #     df['Top Skills List']
        #     .dropna()
        #     .str.split(',')
        #     .explode()
        #     .str.strip()
        # )
        # skill_counts = all_skills.value_counts().head(10)
        # st.bar_chart(skill_counts)


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
