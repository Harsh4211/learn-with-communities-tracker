# 🌟 Learn With Communities Campaign - Google Skills Credential Tracker

A production-grade, multi-interface tracker for the **Learn With Communities Campaign**. It automatically validates students' public Google Skills Boost profiles, counts completed skill badges against the official 10 campaign requirements, respects platform rate limits, detects private or invalid accounts, and generates verified CSV/JSON reports.

---

## 🎯 Key Features

- **Triple Interface Support**:
  1. 🌐 **Modern Web Dashboard**: Real-time SSE streaming, glassmorphism UI, search/filter, candidate detail drawer, and celebratory confetti.
  2. ⚡ **Rich Terminal CLI**: Progress spinners, colored tables, and automated export.
  3. 💻 **Interactive TUI**: Menu-driven terminal navigation for non-browser workflows.
- **Official 10 Campaign Badges Verification**:
  - Automatically compares earned credentials against the 10 official campaign badges.
  - Distinguishes campaign badges from external profile badges.
  - Provides a complete checklist indicating which badges are completed (with earned dates) and which are still missing.
- **Robust Platform Protection & Rate Limiting**:
  - Built-in configurable delay slider (0.2s – 3.0s, default 0.8s) to prevent Google bot/IP blocks.
  - Concurrency throttling (1 to 3 workers with `asyncio.Semaphore`).
  - Exponential backoff retry on HTTP 429 or 5xx.
- **Resilient Error Handling**:
  - Detects **Private Profiles** (Google Skills redirects to homepage).
  - Handles HTTP 404, malformed URLs, and connection timeouts cleanly.
- **Customizable Student Rosters**:
  - Drag-and-drop CSV upload with automatic column header detection (`Google Skills Profile URL`, `profile_url`, `url`, `[INFO]`, etc.).
  - 1-click sample dataset loader.
- **Exporting**:
  - One-click export to CSV with detailed status, completion counts, and badge lists.
  - Export to JSON for integration into bots or analytics pipelines.

---

## 🏆 The 10 Official Campaign Badges

| # | Badge Title | Category |
|---|-------------|----------|
| 1 | **Explore Generative AI in Agent Platform** | Generative AI |
| 2 | **Store, Process, and Manage Data on Google Cloud - Console** | Cloud Infrastructure & Data |
| 3 | **Using the Google Cloud Speech API** | AI & Machine Learning |
| 4 | **Create Your First Gemini Enterprise Application** | Generative AI |
| 5 | **Build a Website on Google Cloud** | Web & Cloud Run |
| 6 | **Analyze Images with the Cloud Vision API** | AI & Machine Learning |
| 7 | **Develop AI-Powered Prototypes in Google AI Studio** | Generative AI |
| 8 | **Implement Speech and Language Solutions with Pre-trained APIs** | AI & Machine Learning |
| 9 | **Configure Service Accounts and IAM Roles for Google Cloud** | Security & IAM |
| 10 | **The Basics of Google Cloud Compute** | Compute |

---

## 🚀 Quick Start

### 1. Requirements & Setup
Clone the repository and install the dependencies:
```bash
git clone <your-repository-url>
cd learn-with-communities-tracker
pip install -r requirements.txt
```

---

### 2. Launch the Web Dashboard
```bash
python -m uvicorn app:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser:
- Click **"Load Sample CSV"** to load the provided test dataset.
- Click **"Start Live Verification"** to see live SSE streaming progress.
- Click **"Upload CSV"** to check your own customizable student list.
- Click on any candidate's **"Badges"** button to inspect their complete 10-badge checklist.
- Click **"Export CSV"** to download the verified report.

---

### 3. Run the CLI / TUI Tool

#### A. Interactive Terminal UI (TUI)
```bash
python cli.py tui
```
Provides an interactive menu to scan CSV files, check single URLs, or list campaign badges.

#### B. Direct CSV Batch Scan
```bash
python cli.py scan sample_students.csv --delay 0.8 --output report.csv
```
Options:
- `-o, --output`: Output file path (`.csv` or `.json`)
- `-d, --delay`: Seconds to wait between requests (default `0.8`)
- `-c, --concurrency`: Number of concurrent workers (default `2`)

#### C. Inspect Single Profile URL
```bash
python cli.py check "https://www.skills.google/public_profiles/be556f7b-ab4b-4be7-82fb-9be45202ddd7"
```

#### D. View Official Campaign Badges
```bash
python cli.py badges
```

---

## 📊 CSV Input & Output Format

### Input CSV (`sample_students.csv`)
Supports any CSV with standard profile URLs:
```csv
Google Skills Profile URL,[INFO]
https://www.skills.google/public_profiles/be556f7b-ab4b-4be7-82fb-9be45202ddd7,All skill badges completed
https://www.skills.google/public_profiles/8f0d00c3-7674-4042-ba15-d26a3fae84f9,Some skill badges completed
https://www.skills.google/public_profiles/2fafe410-5b6c-463b-9a1d-61dbfb43e9ac,None of the skill badges completed
https://www.skills.google/public_profiles/172773ae-1097-499b-a064-0be32bd06b81,Account which is now private
https://www.skills.google/public_profiles/9f130a25-e289-41ea-a90a-febbf37b8dc1,Randomly Chosen Profile
https://www.skills.google/public_profiles/f0633f18-fd81-4cc0-b375-1454da352885,Randomly Chosen Profile
```

### Generated Report CSV (`campaign_report.csv`)
Output columns:
1. `Candidate Name`
2. `Status` (`Completed (10/10)`, `In Progress (X/10)`, `Not Started (0/10)`, `Private Profile`, `Error`)
3. `Campaign Badges Completed (Out of 10)`
4. `Completion Percentage`
5. `Total Profile Badges`
6. `Google Skills Profile URL`
7. `Original Notes / INFO`
8. `Completed Campaign Badges` (Semicolon-separated list)
9. `Missing Campaign Badges` (Semicolon-separated list)
10. `Report Generated At`

---

## 🛡️ Error Handling & Private Accounts
- **Private Accounts**: Google Skills automatically redirects private accounts to `https://www.skills.google/`. The tracker identifies this redirect, marks the candidate with `🔒 Private Profile`, and notifies the organizer so they can instruct the student to make their profile public in settings.
- **Rate-Limiting**: Respects the host server with configurable delay between requests and User-Agent headers.
