# Pathora AI

> **Your Next Opportunity Starts Here.**
> *Pathora AI: An Intelligent Opportunity Discovery and Application Agent*

Pathora AI is a full-stack, directory-style web application designed for students, recent graduates, and early-career individuals. It brings real-time opportunity discovery across official portals, transparent deterministic eligibility scoring, AI-powered match explanations, and application pipeline tracking into a single, cohesive workspace.

---

## 1. Problem Statement

Students and early-career talent struggle with fragmented discovery across hundreds of university portals, company career boards, and scholarship sites. Key challenges include:
- **Scattered Information:** Opportunities are spread across disconnected websites without standardized metadata.
- **Ambiguous Eligibility:** Candidates often miss nuanced degree requirements or spend hours applying to programs for which they do not qualify.
- **Missed Deadlines:** Deadlines are buried in text snippets or unmaintained directories.
- **Disorganized Tracking:** Spreadsheets and notes quickly become out-of-sync with application deadlines and requirements.

Pathora AI solves this by pairing real web-search indexing with deterministic match evaluation, LLM-generated actionable next steps, and an integrated application tracker.

---

## 2. Core Features

- **TapRefer-Inspired Opportunity Directory:** Clean, search-first information architecture with instant category selection, work-mode filters (Remote, Hybrid, On-site), education requirement filters, and minimum match score filtering.
- **Real Web Search Integration:** Live indexing via Tavily Search API targeting official university, corporate, and foundation portals (with an authoritative verified seed fallback when running offline or in demo mode).
- **Transparent Deterministic Match Engine:** A 100-point scoring model evaluating Education (25 pts), Field & Skills (30 pts), Experience (15 pts), Work Mode & Location (15 pts), and Category Preferences (15 pts). Reproducible and immune to LLM hallucination.
- **Grounded AI Advisory Insights:** Dynamic natural language reasoning powered by Google Gemini (or Groq) explaining why an opportunity suits the candidate, flagging potential eligibility concerns, and suggesting concrete next steps.
- **Honest Metadata & Deadlines:** Does not fabricate dates. Clearly distinguishes confirmed deadlines from rolling cycles or unverified dates ("Unknown — verify on official portal").
- **Private Bookmark & Pipeline Tracker:** Save opportunities and manage applications across 7 verified stages: `Interested`, `Planning to Apply`, `Applied`, `Interview`, `Accepted`, `Rejected`, and `Withdrawn`, complete with personal notes and application dates.
- **Firebase Firestore Security & Isolation:** Enforces strict user isolation at both the backend and Firestore rules level (`firebase/firestore.rules`), ensuring users can only read and write their own data.
- **Refined Visual Design System:** Cohesive editorial palette featuring Graphite (`#292A30`), Silver (`#C5C7CC`), Mist (`#ECEDEF`), White (`#FAFAFB`), and Crimson (`#B8243A`), Manrope headings, Inter body typography, subtle transitions, and full mobile responsiveness.

---

## 3. Technology Stack

### Backend
- **Python 3.10+**
- **FastAPI:** High-performance async REST API and Jinja2 server-rendered views.
- **Uvicorn:** Production ASGI server.
- **Pydantic v2 & Pydantic-Settings:** Robust schema validation and configuration management.
- **HTTPX:** Async HTTP client for Tavily Web Search and Gemini LLM calls.
- **Firebase Admin SDK:** Server-side Firebase Authentication verification and Cloud Firestore persistence.
- **Pytest & Pytest-Asyncio:** Automated testing suite.

### Frontend
- **HTML5 & Jinja2 Templates:** Semantic layouts and component blocks.
- **Vanilla Modern JavaScript (ES6+):** Lightweight reactive client without framework bloat.
- **Custom CSS3 Design Tokens:** Responsive grid/flex layouts, CSS variables, and Lucide icons via CDN.

### Database & Auth
- **Google Firebase Firestore:** NoSQL cloud document database.
- **Firebase Authentication:** Client token authentication with backend ID token verification.

---

## 4. Architecture Overview

```text
[ Browser / Mobile Client ]
       │
       ├─► GET / (Landing & Quick Search)
       ├─► GET /app (Discovery Workspace & Tracker)
       │
       ▼
[ FastAPI Backend (main.py) ]
       │
       ├──► Web Search Service ────► Tavily API / Verified Portals
       │
       ├──► Match Scoring Engine ──► Deterministic Factor Matrix (0-100)
       │         │
       │         └──► LLM Engine ──► Google Gemini API (Advisory Insights)
       │
       └──► Data Persistence ─────► Firebase Firestore / In-Memory Demo Store
```

---

## 5. Project Structure

```text
pathora-ai/
├── main.py                  # FastAPI server, API routes, matching logic, and search handlers
├── requirements.txt         # Pinned backend and testing dependencies
├── .env.example             # Configuration template with placeholder credentials
├── .gitignore               # Excludes secrets, service accounts, and virtual environments
├── README.md                # Comprehensive project documentation and guides
├── templates/
│   ├── base.html            # Shared HTML layout, navigation, modals, and design tokens
│   ├── index.html           # Landing and discovery page with forward pathways motif
│   └── app.html             # Opportunity discovery workspace and application tracker
├── static/
│   ├── css/
│   │   └── style.css        # Visual design system (Graphite, Silver, Mist, Crimson, White)
│   ├── js/
│   │   └── app.js           # Client search, filters, deterministic scoring, and tracker logic
│   └── images/              # Static image assets
├── firebase/
│   └── firestore.rules      # Cloud Firestore security rules with user-level isolation
└── tests/
    └── test_app.py          # Automated unit, integration, and security tests
```

---

## 6. Installation & Setup Instructions

### Prerequisites
- Python 3.10 or higher installed on your machine.
- PowerShell (Windows) or Bash (macOS/Linux).
- Git.

### Step 1: Clone or Navigate to Project
```powershell
cd c:\Users\FC\Documents\antigravity\mysterious-curie
```

### Step 2: Create & Activate Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## 7. Environment Configuration

Copy `.env.example` to create your local `.env` file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` to configure your keys:

```dotenv
# --- Search Provider Configuration ---
# Tavily Search API key (https://tavily.com) - Used for real-time web search
SEARCH_API_KEY=tvly-your_tavily_key_here

# --- LLM Provider Configuration ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=

# --- Firebase & Firestore Configuration ---
FIREBASE_PROJECT_ID=your_firebase_project_id
GOOGLE_APPLICATION_CREDENTIALS=firebase-service-account.json

# --- Application Server ---
PORT=8000
HOST=127.0.0.1
```

> **Note on Demo Mode:** If `SEARCH_API_KEY`, `GEMINI_API_KEY`, or Firebase credentials are not provided, Pathora AI runs in a gracefully labelled **Demo Mode**. It serves verified, authoritative seed opportunities (GSoC, Fulbright, Microsoft Explore, MLH, CERN), computes objective deterministic match scores, and provides in-memory session persistence without crashing.

---

## 8. Firebase & Firestore Setup

1. Go to the [Firebase Console](https://console.firebase.google.com/) and create a project.
2. Under **Build**, select **Firestore Database** and create a database in production mode.
3. Deploy the security rules from `firebase/firestore.rules` via the Firebase CLI or paste them into the Firestore Rules tab:
   ```powershell
   firebase deploy --only firestore:rules
   ```
4. Under **Project Settings** > **Service accounts**, click **Generate new private key**.
5. Save the downloaded JSON file as `firebase-service-account.json` in your project root (ensure it remains git-ignored).
6. Enable **Email/Password** authentication in the **Authentication** tab of the Firebase Console.

---

## 9. Running the Application

Start the FastAPI application with Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
- **Landing Page:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Opportunity Workspace:** [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)
- **API Documentation (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 10. Running Automated Tests

Run the full test suite with pytest:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_app.py -v
```

### Verified Test Suite Summary
- `test_health_check_endpoint`: Verifies service health and configuration flags.
- `test_landing_page_loads`: Ensures landing page HTML renders with branding and quick search.
- `test_app_workspace_page_loads`: Verifies TapRefer-style directory filters and containers render.
- `test_search_endpoint_default`: Checks query validation and search response formatting.
- `test_search_normalization_logic`: Tests parsing of titles, domains, organizations, and categories.
- `test_search_normalization_missing_deadline`: Confirms missing deadlines are labeled as unknown rather than fabricated.
- `test_search_normalization_handles_empty`: Ensures invalid/empty input is safely rejected.
- `test_deterministic_matching_high_match`: Verifies scoring when skills, education, and mode align.
- `test_deterministic_matching_missing_profile_info`: Asserts missing criteria never trigger false eligibility claims.
- `test_deterministic_matching_is_reproducible`: Proves scoring results are 100% deterministic and reproducible.
- `test_protected_routes_reject_unauthenticated`: Confirms unauthenticated requests receive HTTP 401.
- `test_authenticated_profile_crud`: Verifies profile updates and retrieval.
- `test_user_data_isolation`: Confirms User A cannot view or manipulate User B's bookmarks or applications.
- `test_application_tracker_invalid_status_rejected`: Asserts invalid status names receive HTTP 422.
- `test_application_tracker_valid_lifecycle`: Validates complete application lifecycle (Create -> Update -> List -> Delete).

---

## 11. REST API Specification

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/` | Render Landing & Discovery Page | No |
| `GET` | `/app` | Render Opportunity Workspace | No |
| `GET` | `/health` | Service Health and Config Status | No |
| `GET` | `/api/opportunities/search` | Search web & retrieve normalized listings | No |
| `GET` | `/api/opportunities/{id}` | Get opportunity details | No |
| `POST` | `/api/opportunities/analyze` | Deterministic scoring & LLM explanation | No |
| `GET` | `/api/profile` | Retrieve candidate profile | Yes |
| `PUT` | `/api/profile` | Update candidate profile | Yes |
| `GET` | `/api/saved` | List bookmarked opportunities | Yes |
| `POST` | `/api/saved` | Bookmark an opportunity | Yes |
| `DELETE` | `/api/saved/{id}` | Remove bookmarked opportunity | Yes |
| `GET` | `/api/applications` | List application tracker pipeline | Yes |
| `POST` | `/api/applications` | Create application tracker record | Yes |
| `PATCH` | `/api/applications/{id}` | Update status, notes, or date | Yes |
| `DELETE` | `/api/applications/{id}` | Delete application tracker record | Yes |

---

## 12. Security & Privacy Notes

- **Zero Secret Leakage:** No API keys, database credentials, or service account paths are exposed to the client or checked into Git.
- **Strict Authorization:** Protected endpoints require a valid Bearer token.
- **Data Minimization:** Pathora AI collects only functional academic details (education level, study field, skills) and explicitly avoids sensitive identity documents or passwords.
- **Transparent Advisory Notice:** All AI explanations are labeled as assistive. Users are directed to official source URLs for authoritative confirmation.

---

## 13. Limitations & Future Roadmap

- **Live Search Rate Limits:** External search providers (e.g. Tavily) enforce rate limits. Pathora AI provides graceful fallback to verified opportunities when limits are reached.
- **Application Automation:** Pathora AI intentionally does not submit job or scholarship applications automatically on third-party portals; users remain in full control of their applications.
- **Future Improvements:**
  - Automated deadline calendar synchronization (Google Calendar / iCal export).
  - Resume PDF parsing to automatically populate candidate profile skills.
  - Email notification reminders for upcoming deadlines in the Application Tracker.

---

## 14. License & Credits

Built from scratch for the Pathora AI initiative. Visual design inspired by TapRefer's directory architecture, adapted into an original, accessible opportunity discovery agent for early-career growth.
