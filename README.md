# Job Tracker Web App

The Job Tracker App is a thoughtfully designed, AI-powered tool that helps you manage your job applications and networking efforts—without the clutter. Unlike overwhelming job tracking tools with complex dashboards and endless fields, this app was built to be minimal, user-friendly, and focused on what actually matters.

## Why This App?

Most job tracking tools try to do too much. This app does just enough.

- A clean, tab-based interface
- Only the most essential fields (job link, company, role, people contacted)
- Zero clutter, zero distractions
- Built for simplicity and speed, not feature bloat

It's ideal for students, job seekers, or anyone who wants to keep their job search organized and stress-free.

## Features

- Secure login using credentials stored in `config.yaml`
- Add job listings and auto-extract skills using OpenAI
- Track people you've contacted for each job
- View clean, resettable filters by company, skills, and date
- Compact card-style layouts instead of overwhelming tables
- User-specific CSV storage (no shared clutter)

## How It Works

1. Each user logs in with their username and password.
2. Each user’s job and contact data is saved in their own CSV files:
   - `job_tracker_<username>.csv`
   - `job_contacts_<username>.csv`
3. A simple and intuitive interface helps you:
   - Log new job roles
   - Track networking activity
   - Filter and analyze past applications
## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/job-tracker-app.git
cd job-tracker-app
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file with your OpenAI API key:

```
OPENAI_API_KEY=your-openai-key
```

You’ll also need a `config.yaml` file structured like this:

```yaml
credentials:
  usernames:
    yourusername:
      name: Your Name
      email: your@email.com
      password: your_hashed_password

cookie:
  name: job_tracker_auth
  key: auth_key_123
  expiry_days: 100
```

## Running the App

```bash
streamlit run app.py
```

## Deployment

This app is ready for deployment on [Streamlit Cloud](https://streamlit.io/cloud).  
Push your repository to GitHub and follow the Streamlit Cloud deployment steps. Make sure to set environment variables like `OPENAI_API_KEY` in the app settings panel.

## License

This project is open-source and available under the MIT License.
```
