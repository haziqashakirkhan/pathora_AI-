<div align="center">

# Pathora AI

**Your next opportunity starts here.**

An AI-assisted platform that helps students and early-career talent discover scholarships, internships, fellowships, training programs and entry-level jobs, check how well they match, and track every application in one place.

[Live demo](https://pathora-ai-psi.vercel.app) &nbsp;|&nbsp; [Report an issue](https://github.com/haziqashakirkhan/pathora_AI-/issues)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Auth%20%2B%20Firestore-FFCA28?style=flat-square&logo=firebase&logoColor=black)
![Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-000000?style=flat-square&logo=vercel&logoColor=white)

</div>

---

## Overview

Opportunities are scattered across many portals, eligibility rules are buried in long listings, and deadlines are easy to miss. Pathora AI brings the whole journey into one workspace:

1. **Search** live opportunities from the web.
2. **Match** each listing against your profile with a transparent score.
3. **Understand** the result through a plain-language explanation.
4. **Save and track** applications from first interest to final decision.

Pathora AI is a guidance tool. Scores are computed by fixed rules, and the language model only writes the explanation. It never decides eligibility.

## Features

| Area | What it does |
| --- | --- |
| Opportunity search | Live web search through Tavily, with a curated seed list used as a fallback when search is unavailable. |
| Filters | Narrow results by category, location, work mode and education level. |
| Match score | A rule-based 100-point score with clear labels, so every result is explainable. |
| AI explanations | Gemini writes a short explanation of each match. If it fails, the app falls back to rule-based text. |
| Bookmarks | Save opportunities to review later. |
| Application tracker | Seven statuses: Interested, Planning to Apply, Applied, Interview, Accepted, Rejected, Withdrawn. |
| Accounts | Sign up and sign in with Firebase Authentication. |
| AI chatbot (optional) | A floating chat widget that answers questions using the real listings. Disabled unless explicitly enabled. |

## How the match score works

Each opportunity is scored out of 100 against your profile.

| Factor | Weight |
| --- | --- |
| Skills | 30 |
| Education | 25 |
| Experience | 15 |
| Work mode | 15 |
| Category | 15 |

| Score | Label |
| --- | --- |
| 75 and above | Likely match |
| 50 to 74 | Partial match |
| Below 50 | Likely ineligible |
| Missing data | Insufficient information |

## Architecture

```
Browser (Jinja2 pages + vanilla JS)
        |
        v
FastAPI backend  --->  Tavily search  (curated list as fallback)
        |
        +---------->  Rule-based scoring (100 points)
        |
        +---------->  Gemini  (explanations only, rule-based fallback)
        |
        +---------->  Firebase Authentication + Firestore
                      (in-memory fallback for demo mode)
```

Design principles:

- **Search and AI are separate steps.** Tavily finds listings, rules compute the score, and Gemini only explains.
- **Every external service has a fallback**, so a missing key or an outage never blocks the user.
- **Optional features are guarded.** The chatbot is off by default and cannot affect existing pages.

## Agent workflow (LangGraph)

Pathora addresses the difficulty of finding opportunities across fragmented portals, understanding eligibility, keeping track of deadlines, and organizing applications. Its agent workflow coordinates existing backend capabilities; it does not automatically apply, guarantee eligibility, or verify an opportunity on behalf of the student.

The workflow is available through the authenticated `POST /api/agent/workflow` endpoint. It reads the signed-in user's existing profile and calls the existing search, deterministic scoring, and opportunity-analysis functions. Existing endpoints and frontend behavior are unchanged.

```mermaid
flowchart TD
    START([START]) --> validate[Validate query and profile]
    validate -->|blank query| complete[Build structured response]
    validate -->|profile incomplete| profileNote[Record missing profile fields]
    validate -->|profile complete| search[Search via existing search function]
    profileNote --> search
    search -->|exception or no opportunities| review[Human review checkpoint]
    search -->|opportunities found| match[Score with existing deterministic matcher]
    match -->|scoring fails| review
    match -->|scores available| explain[Explain highest-ranked result via existing analyzer]
    explain -->|analysis or deterministic fallback| review
    review --> complete
    complete --> END([END])
```

### State, nodes, routing, and review

- **State:** The per-request LangGraph `TypedDict` contains the query, filters, a minimal scoring-only profile, opportunity results, scores, explanations, source metadata, missing profile fields, warnings/errors, and review status. It excludes user IDs, contact details, secrets, and conversation history. The graph is compiled and invoked for a single request; it has no persistent checkpoint store.
- **Nodes:** Query/profile validation, incomplete-profile notice, opportunity search, deterministic match evaluation, explanation generation, human-review checkpoint, and structured response completion.
- **Edges and conditional routing:** Blank queries skip search. Incomplete profiles are noted before search continues. Search exceptions or empty results bypass scoring. Scoring failures bypass explanations. Otherwise, the highest-scoring result receives an explanation through the existing analyzer; other results retain deterministic notes. Limiting the workflow to one analyzer call bounds request latency and external usage.
- **Human-in-the-loop:** Results are explicitly marked as requiring the student to verify current requirements and deadlines on official portals. This is a review checkpoint and flag, **not** an interactive pause/approval/resume workflow.
- **Fallbacks:** The existing search function may return the curated seed index when live results are unavailable or unusable; the workflow preserves its `source_mode` and adds a warning. Search exceptions return an error status without inventing results. The existing analyzer falls back to deterministic text when Gemini is unavailable; workflow-level analyzer failures also use deterministic match notes.

### Actual component roles and modes

- **FastAPI/Python:** Hosts the existing APIs and the authenticated agent endpoint.
- **Tavily:** Used by the existing search function when `SEARCH_API_KEY` is configured. The existing curated seed index remains its demo/fallback source.
- **Gemini:** Used by the existing opportunity analyzer for explanations when `GEMINI_API_KEY` is configured. The optional chatbot also uses Gemini; `GEMINI_MODEL` applies to the chatbot. The analyzer currently selects its Gemini model in code.
- **Groq:** `GROQ_API_KEY` is loaded for configuration reporting, but the current analysis implementation does not call Groq.
- **Firebase:** Firebase Authentication identifies users; Firestore persists profiles, bookmarks, and application records when configured. Local/demo fallback storage is in memory and is not durable.
- **LangGraph:** Coordinates the agent request's state, nodes, explicit edges, and conditional routes. It does not replace search, scoring, or analysis.

## Tech stack

- **Backend:** Python, FastAPI, Jinja2 templates
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Search:** Tavily
- **AI:** Google Gemini
- **Workflow orchestration:** LangGraph
- **Auth and data:** Firebase Authentication, Cloud Firestore
- **Hosting:** Vercel

## Project structure

```
.
|-- main.py              # FastAPI app, routes, scoring and orchestration
|-- agent_workflow.py    # LangGraph workflow for authenticated recommendations
|-- templates/           # Jinja2 pages: base, index, app, login, signup
|-- static/              # Styles and client-side scripts
|-- tests/               # API and agent workflow tests
|-- requirements.txt     # Python dependencies
|-- vercel.json          # Vercel deployment configuration
`-- .env.example         # Example environment variables
```

The optional chatbot is implemented in `chatbot.py` and `static/chat-widget.js`.

## Getting started

### Prerequisites

- Python 3.10 or newer
- A Tavily API key for live opportunity search (optional; curated demo data is used otherwise)
- A Google Gemini API key for generated explanations and chatbot replies (optional; deterministic/list fallbacks remain available)
- A Firebase project with Authentication and Firestore (optional for a local demo, which falls back to in-memory storage)

### Installation

```bash
git clone https://github.com/haziqashakirkhan/pathora_AI-.git
cd pathora_AI-

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root. The variable names below are examples; match them to the names used in `main.py`.

```env
SEARCH_API_KEY=your_tavily_key
GEMINI_API_KEY=your_gemini_key

# Firebase (omit to run in demo mode)
FIREBASE_PROJECT_ID=your_project_id
GOOGLE_APPLICATION_CREDENTIALS=path_to_service_account_json

# Optional AI chatbot (off unless set to true)
CHATBOT_ENABLED=false
GEMINI_MODEL=gemini-flash-lite-latest
```

The existing opportunity analyzer currently uses its Gemini model endpoint directly; `GEMINI_MODEL` configures the optional chatbot. Never commit real keys or service-account credentials.

### Run locally

```bash
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

### Run tests

```bash
python -m pytest -q
```

### Run the agent workflow

Sign in to obtain a Firebase ID token, then send it as a bearer token. For example:

```bash
curl -X POST http://127.0.0.1:8000/api/agent/workflow ^
  -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"q\":\"software engineering internship\",\"category\":[\"Internship\"],\"refresh\":false}"
```

The response contains ranked results, deterministic match data, explanation/fallback source, search source metadata, warnings, and a human-review reminder. No profile details beyond fields used by the existing scorer are put into graph state.

## Deployment

The project is configured for Vercel through `vercel.json`.

1. Import the repository into Vercel.
2. Add the environment variables from the configuration section in the project settings.
3. Deploy. Test on a preview deployment before promoting to production.

## Responsible AI

- The match score is rule-based and explainable.
- The language model writes explanations only and never decides eligibility.
- Results are guidance, not a guarantee. Always confirm requirements on the official opportunity page.
- The chatbot answers from the listings it is given.
- The LangGraph review flag asks the student to verify results; it does not pause execution for approval.

## Current limitations and future improvements

- The agent endpoint requires authentication and uses the signed-in user's stored profile; it does not introduce an unauthenticated profile-submission path.
- Gemini explanation generation is limited to the highest-scoring match per workflow request to bound latency and external API usage.
- When Firestore is not configured, profile/bookmark/application fallback data exists only in process memory and may not survive a restart or serverless invocation.
- Search results and match scores are guidance. Official portals remain authoritative for eligibility and deadlines.
- An interactive LangGraph interrupt/resume approval flow, durable graph checkpoints, more search providers, and deadline reminders are future work, not implemented features.

## Roadmap

- Better personalization of matches
- More opportunity sources
- Deadline reminders
- Clearer eligibility explanations
- Accessibility and mobile refinements

## Team

Built by Haziqa shkair khan
