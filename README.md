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

## Tech stack

- **Backend:** Python, FastAPI, Jinja2 templates
- **Frontend:** HTML, CSS, vanilla JavaScript
- **Search:** Tavily
- **AI:** Google Gemini
- **Auth and data:** Firebase Authentication, Cloud Firestore
- **Hosting:** Vercel

## Project structure

```
.
|-- main.py              # FastAPI app, routes, scoring and orchestration
|-- templates/           # Jinja2 pages: base, index, app, login, signup
|-- static/              # Styles and client-side scripts
|-- requirements.txt     # Python dependencies
|-- vercel.json          # Vercel deployment configuration
`-- .env.example         # Example environment variables
```

If the chatbot is enabled in your checkout, it adds `chatbot.py` and `static/chat-widget.js`.

## Getting started

### Prerequisites

- Python 3.10 or newer
- A Tavily API key
- A Google Gemini API key
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
TAVILY_API_KEY=your_tavily_key
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=your_current_gemini_model

# Firebase (omit to run in demo mode)
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_CREDENTIALS=path_or_json_for_service_account

# Optional AI chatbot (off unless set to true)
CHATBOT_ENABLED=false
```

Check Google AI Studio for the current Gemini model name and set it in `GEMINI_MODEL`. Never commit real keys.

### Run locally

```bash
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

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

## Roadmap

- Better personalization of matches
- More opportunity sources
- Deadline reminders
- Clearer eligibility explanations
- Accessibility and mobile refinements

## Team

Built by Haziqa shkair khan
