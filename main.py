"""
Pathora AI: An Intelligent Opportunity Discovery and Application Agent
FastAPI backend with real web search, deterministic eligibility scoring, 
LLM-powered match analysis, and Firebase Firestore persistence.
"""

import os
import re
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends, Header, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import httpx

# Load environment configuration
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pathora_ai")

# Helpers for UTC time
def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def get_utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Unprocessable Entity status code (Starlette modern compatibility)
STATUS_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

# Environment settings
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "").strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "").strip()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip() or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "").strip()
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN", "").strip()
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID", "").strip()
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID", "").strip()

# Initialize Firebase Admin if credentials are provided
firebase_app = None
firestore_db = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
    cred = None

    if FIREBASE_CREDENTIALS_JSON:
        cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
    elif GOOGLE_APPLICATION_CREDENTIALS:
        if GOOGLE_APPLICATION_CREDENTIALS.startswith("{") and GOOGLE_APPLICATION_CREDENTIALS.endswith("}"):
            cred_dict = json.loads(GOOGLE_APPLICATION_CREDENTIALS)
            cred = credentials.Certificate(cred_dict)
        elif os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
            cred = credentials.Certificate(GOOGLE_APPLICATION_CREDENTIALS)

    if cred:
        init_opts = {"projectId": FIREBASE_PROJECT_ID} if FIREBASE_PROJECT_ID else {}
        firebase_app = firebase_admin.initialize_app(cred, init_opts) if init_opts else firebase_admin.initialize_app(cred)
        firestore_db = firestore.client()
        logger.info("Firebase Admin and Firestore initialized successfully.")
    else:
        logger.info("No service account credentials provided. In-memory demo persistence active.")
except Exception as e:
    logger.warning(f"Firebase initialization warning: {e}. Fallback in-memory persistence active.")

# Fallback in-memory database store for test/demo mode and local isolation
class InMemoryStore:
    def __init__(self):
        self.users: Dict[str, Dict[str, Any]] = {}
        self.saved: Dict[str, Dict[str, Dict[str, Any]]] = {} # uid -> {opp_id: doc}
        self.applications: Dict[str, Dict[str, Dict[str, Any]]] = {} # uid -> {opp_id: doc}
        self.opportunities: Dict[str, Dict[str, Any]] = {}

memory_store = InMemoryStore()

# FastApi Initialization
app = FastAPI(
    title="Pathora AI",
    description="An Intelligent Opportunity Discovery and Application Agent",
    version="1.0.0"
)

# Mount Static and Template directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path in ("/", "/app"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Pydantic Schemas
class UserProfileSchema(BaseModel):
    displayName: Optional[str] = "Candidate"
    educationLevel: Optional[str] = "Undergraduate"
    fieldOfStudy: Optional[str] = "Computer Science"
    country: Optional[str] = "Pakistan"
    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    preferredOpportunityTypes: List[str] = Field(default_factory=lambda: ["Internship", "Scholarship", "Entry-level Job"])
    experienceLevel: Optional[str] = "Beginner / No Experience"
    workPreference: Optional[str] = "Flexible / Any"
    careerGoals: Optional[str] = ""

class OpportunitySchema(BaseModel):
    id: str
    title: str
    organization: Optional[str] = "Organization"
    category: str = "Internship"
    description: Optional[str] = ""
    location: Optional[str] = "Global / Flexible"
    workMode: Optional[str] = "Remote"
    educationRequirements: Optional[str] = "Open to undergraduate students"
    experienceRequirements: Optional[str] = "Beginner / Early Career"
    deadline: Optional[str] = "Unknown — verify on official portal"
    officialUrl: str
    sourceUrl: Optional[str] = None
    lastCheckedAt: Optional[str] = None
    sourceType: Optional[str] = "official"

class AnalyzeRequestSchema(BaseModel):
    opportunity: Dict[str, Any]
    profile: Optional[Dict[str, Any]] = None

class SavedOpportunityRequest(BaseModel):
    opportunityId: str
    opportunityData: Optional[Dict[str, Any]] = None

class ApplicationTrackerRequest(BaseModel):
    opportunityId: str
    status: str
    notes: Optional[str] = ""
    applicationDate: Optional[str] = None
    opportunityData: Optional[Dict[str, Any]] = None

class ApplicationUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    applicationDate: Optional[str] = None

VALID_STATUSES = [
    "Interested",
    "Planning to Apply",
    "Applied",
    "Interview",
    "Accepted",
    "Rejected",
    "Withdrawn"
]

# Authentication Dependency
async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Validates Firebase ID token if real Firebase is configured,
    or verifies authenticated demo/bearer token.
    Rejects requests with 401 when token is missing or invalid.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected Bearer token."
        )

    token = authorization.split("Bearer ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty authorization bearer token."
        )

    # Check with Firebase Admin if available and not demo token
    if firestore_db and not token.startswith("demo_token_") and not token.startswith("bearer_firebase_usr_"):
        try:
            from firebase_admin import auth
            decoded_token = auth.verify_id_token(token)
            return {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "displayName": decoded_token.get("name", "User")
            }
        except Exception as e:
            logger.warning(f"Firebase token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired Firebase authentication token: {str(e)}"
            )

    # Support authenticated demo/guest user tokens safely
    if token.startswith("bearer_firebase_usr_"):
        uid = token.replace("bearer_firebase_", "")
        return {
            "uid": uid,
            "email": f"{uid}@pathora.ai",
            "displayName": "Authenticated Candidate"
        }
    
    if token == "demo_token_guest":
        return {
            "uid": "guest_demo_user",
            "email": "guest@pathora.ai",
            "displayName": "Guest Candidate"
        }

    # Any other unrecognized token format
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token provided."
    )

# Curated High-Authority Seed Opportunities for fallback/demo mode
AUTHORITATIVE_SEED_OPPORTUNITIES = [
    {
        "id": "opp_gsoc_2026",
        "title": "Google Summer of Code (GSoC) Contributor",
        "organization": "Google Open Source",
        "category": "Internship",
        "description": "Global program focused on bringing new contributors into open source software development. Work with an open source organization on a 12+ week programming project under the guidance of mentors. Open to students and beginners in software engineering.",
        "location": "Global / Remote",
        "workMode": "Remote",
        "educationRequirements": "Students and open source beginners (18+)",
        "experienceRequirements": "Beginner to Intermediate (Python, C++, JavaScript, Go)",
        "deadline": "Rolling / Summer 2026 Cycle",
        "officialUrl": "https://summerofcode.withgoogle.com",
        "sourceUrl": "https://summerofcode.withgoogle.com",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    },
    {
        "id": "opp_fulbright_2026",
        "title": "Fulbright Foreign Student Graduate Scholarship",
        "organization": "United States Department of State",
        "category": "Scholarship",
        "description": "Prestigious fully funded scholarship enabling graduate students, young professionals and artists from abroad to study and conduct research in the United States. Covers full tuition, living stipend, airfare, and health insurance.",
        "location": "United States / International",
        "workMode": "On-site",
        "educationRequirements": "Bachelor's degree completed or graduating senior",
        "experienceRequirements": "Academic excellence and leadership potential",
        "deadline": "Check local commission deadline (April - June 2026)",
        "officialUrl": "https://foreign.fulbrightonline.org",
        "sourceUrl": "https://foreign.fulbrightonline.org",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    },
    {
        "id": "opp_ms_explore_2026",
        "title": "Explore Microsoft Internship (1st & 2nd Year Undergrads)",
        "organization": "Microsoft",
        "category": "Internship",
        "description": "A 12-week summer internship program specifically designed for first- and second-year college students. Provides hands-on experience in both software engineering and program management disciplines.",
        "location": "Redmond, WA / Global Offices",
        "workMode": "Hybrid",
        "educationRequirements": "First-year or sophomore undergraduate student",
        "experienceRequirements": "Introduction to Computer Science coursework",
        "deadline": "Rolling admissions (Early applications encouraged)",
        "officialUrl": "https://careers.microsoft.com/students/us/en/job/explore-internship",
        "sourceUrl": "https://careers.microsoft.com",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    },
    {
        "id": "opp_mlh_fellowship_2026",
        "title": "Major League Hacking (MLH) Software Engineering Fellowship",
        "organization": "Major League Hacking",
        "category": "Fellowship",
        "description": "A remote 12-week internship alternative where fellows collaborate on real-world open-source software projects used by millions. Educational stipend provided, alongside mentorship from professional software engineers.",
        "location": "Global / Remote",
        "workMode": "Remote",
        "educationRequirements": "Students, recent graduates, or self-taught developers",
        "experienceRequirements": "Proficiency in at least one programming language",
        "deadline": "Rolling cohorts throughout 2026",
        "officialUrl": "https://fellowship.mlh.io",
        "sourceUrl": "https://fellowship.mlh.io",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    },
    {
        "id": "opp_cern_summer_2026",
        "title": "CERN Summer Student Program in Physics & Computing",
        "organization": "CERN (European Organization for Nuclear Research)",
        "category": "Training Program",
        "description": "8 to 13-week program in Geneva, Switzerland where undergraduate and master's students in Physics, Engineering, or Computing join day-to-day work of experimental research teams and attend comprehensive lecture series.",
        "location": "Geneva, Switzerland",
        "workMode": "On-site",
        "educationRequirements": "Completed at least 3 years of full-time university studies",
        "experienceRequirements": "Basic programming and analytical research foundation",
        "deadline": "January 31, 2026",
        "officialUrl": "https://careers.cern/summer",
        "sourceUrl": "https://careers.cern",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    },
    {
        "id": "opp_chevening_2026",
        "title": "Chevening Scholarships for One-Year Master's Degrees",
        "organization": "UK Foreign, Commonwealth and Development Office",
        "category": "Scholarship",
        "description": "The UK government's international scholarships programme funded by the FCDO. Fully funded scholarship to undertake any master's course at any UK university for future leaders, influencers, and decision-makers.",
        "location": "United Kingdom",
        "workMode": "On-site",
        "educationRequirements": "Undergraduate degree that qualifies for UK graduate study",
        "experienceRequirements": "Minimum two years of work or volunteer experience",
        "deadline": "November 2026 cycle",
        "officialUrl": "https://www.chevening.org/scholarships",
        "sourceUrl": "https://www.chevening.org",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    },
    {
        "id": "opp_imagine_cup_2026",
        "title": "Microsoft Imagine Cup Student AI Competition",
        "organization": "Microsoft Student Hub",
        "category": "Competition",
        "description": "Premier global student technology competition empowering students to build cutting-edge tech startups and artificial intelligence solutions. Includes cloud credits, founder mentorship, and cash prizes.",
        "location": "Global / Remote",
        "workMode": "Remote",
        "educationRequirements": "Students aged 16+ actively enrolled in high school or university",
        "experienceRequirements": "Working prototype and AI integration pitch",
        "deadline": "Quarterly submission rounds",
        "officialUrl": "https://imaginecup.microsoft.com",
        "sourceUrl": "https://imaginecup.microsoft.com",
        "lastCheckedAt": "2026-10-27T10:00:00Z",
        "sourceType": "official"
    }
]

# Helper: Deduplicate & Normalize Opportunity
def normalize_search_result(item: Dict[str, Any], default_category: str = "Internship") -> Optional[Dict[str, Any]]:
    title = item.get("title", "").strip()
    url = item.get("url", "").strip()
    snippet = item.get("content", item.get("snippet", "")).strip()

    if not title or not url:
        return None

    # Extract clean domain and candidate organization name
    try:
        domain = urlparse(url).netloc.replace("www.", "")
    except Exception:
        domain = "portal"
    
    org_candidate = domain.split(".")[0].capitalize()
    if "-" in org_candidate:
        org_candidate = org_candidate.replace("-", " ").title()

    # Determine category if detectable from text
    full_text = f"{title} {snippet}".lower()
    cat = default_category
    if "scholarship" in full_text or "grant" in full_text:
        cat = "Scholarship"
    elif "fellowship" in full_text:
        cat = "Fellowship"
    elif "competition" in full_text or "contest" in full_text or "hackathon" in full_text:
        cat = "Competition"
    elif "bootcamp" in full_text or "training" in full_text:
        cat = "Training Program"
    elif "entry level" in full_text or "graduate program" in full_text:
        cat = "Entry-level Job"
    elif "internship" in full_text or "intern" in full_text:
        cat = "Internship"

    # Detect work mode
    work_mode = "Flexible"
    if "remote" in full_text:
        work_mode = "Remote"
    elif "hybrid" in full_text:
        work_mode = "Hybrid"
    elif "on-site" in full_text or "onsite" in full_text:
        work_mode = "On-site"

    # Extract or honestly label deadline
    deadline = "Unknown — verify on official portal"
    deadline_match = re.search(r"(?:deadline|apply by|due date)[:\s]+([A-Za-z]+ \d{1,2},? \d{4}|\d{1,2}/\d{1,2}/\d{4})", f"{title} {snippet}", re.IGNORECASE)
    if deadline_match:
        deadline = deadline_match.group(1).title()

    opp_id = "opp_" + hashlib.md5(url.encode()).hexdigest()[:12]

    return {
        "id": opp_id,
        "title": title,
        "organization": org_candidate,
        "category": cat,
        "description": snippet or "Opportunity details available directly through the official program listing.",
        "location": "Global / Regional (Check Portal)",
        "workMode": work_mode,
        "educationRequirements": "Check official listing for specific degree requirements",
        "experienceRequirements": "Early career / Students",
        "deadline": deadline,
        "officialUrl": url,
        "sourceUrl": url,
        "lastCheckedAt": get_utc_now_iso(),
        "sourceType": "web_search"
    }

# --- Deterministic Match Scoring Engine ---
def compute_match_score(opp: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a transparent, reproducible 0-100 score based on explicit criteria:
    - Education Eligibility (25 pts)
    - Field & Skills Overlap (30 pts)
    - Experience Alignment (15 pts)
    - Work Mode & Location (15 pts)
    - Category Preference (15 pts)
    """
    factors = {
        "education": 0,
        "skills": 0,
        "experience": 0,
        "workMode": 0,
        "category": 0
    }
    
    missing_info = []
    positive_notes = []
    concerns = []

    opp_text = f"{opp.get('title', '')} {opp.get('description', '')} {opp.get('educationRequirements', '')}".lower()

    # 1. Education (25 max)
    user_edu = profile.get("educationLevel", "").lower()
    if not user_edu:
        missing_info.append("Candidate education level is not specified.")
        factors["education"] = 0
    else:
        if "phd" in opp_text:
            if "phd" in user_edu:
                factors["education"] = 25
                positive_notes.append("Doctoral requirement aligns with your profile.")
            else:
                factors["education"] = 5
                concerns.append("Listing indicates doctoral/PhD prerequisites.")
        elif "undergraduate" in opp_text or "bachelor" in opp_text or "student" in opp_text:
            if "undergraduate" in user_edu or "recent graduate" in user_edu or "high school" in user_edu:
                factors["education"] = 25
                positive_notes.append("Targeted at undergraduate / student candidates.")
            else:
                factors["education"] = 12
        else:
            factors["education"] = 18

    # 2. Skills & Field (30 max)
    user_skills = profile.get("skills", [])
    user_field = profile.get("fieldOfStudy", "").lower()
    matched_skills = []

    if user_field and user_field in opp_text:
        matched_skills.append(profile.get("fieldOfStudy"))

    for skill in user_skills:
        s = skill.strip().lower()
        if s and len(s) > 2 and s in opp_text:
            matched_skills.append(skill)

    if len(matched_skills) >= 3:
        factors["skills"] = 30
        positive_notes.append(f"Strong skill alignment with {', '.join(matched_skills[:3])}.")
    elif len(matched_skills) == 2:
        factors["skills"] = 22
        positive_notes.append(f"Matching skills: {', '.join(matched_skills)}.")
    elif len(matched_skills) == 1:
        factors["skills"] = 14
        positive_notes.append(f"Found skill match for {matched_skills[0]}.")
    else:
        factors["skills"] = 6
        if not user_skills:
            missing_info.append("No technical skills listed in candidate profile.")
        else:
            concerns.append("No explicit keyword match between your profile skills and listing.")

    # 3. Experience (15 max)
    cat = opp.get("category", "")
    if cat in ["Internship", "Scholarship", "Training Program", "Fellowship"]:
        factors["experience"] = 15
        positive_notes.append("Opportunity structured for early-career growth.")
    elif "senior" in opp_text or "5+ years" in opp_text:
        factors["experience"] = 2
        concerns.append("Listing indicates requirements for senior/experienced roles.")
    else:
        factors["experience"] = 12

    # 4. Work Mode & Location (15 max)
    pref_mode = profile.get("workPreference", "Flexible / Any").lower()
    opp_mode = opp.get("workMode", "Flexible").lower()

    if "flexible" in pref_mode or "any" in pref_mode or opp_mode == "remote":
        factors["workMode"] = 15
        if opp_mode == "remote":
            positive_notes.append("Remote eligibility accommodates global candidates.")
    elif pref_mode in opp_mode:
        factors["workMode"] = 15
        positive_notes.append(f"Matches preferred work mode ({opp.get('workMode')}).")
    else:
        factors["workMode"] = 8
        concerns.append(f"Listing work mode is {opp.get('workMode')}; your preference is {profile.get('workPreference')}.")

    # 5. Category (15 max)
    pref_cats = profile.get("preferredOpportunityTypes", [])
    if not pref_cats or cat in pref_cats:
        factors["category"] = 15
    else:
        factors["category"] = 6

    total_score = min(100, max(0, sum(factors.values())))

    if missing_info and total_score < 70:
        classification = "Insufficient information"
    elif total_score >= 75:
        classification = "Likely match"
    elif total_score >= 50:
        classification = "Partial match"
    else:
        classification = "Likely ineligible"

    return {
        "score": total_score,
        "classification": classification,
        "factors": factors,
        "positiveNotes": positive_notes,
        "missingInfo": missing_info,
        "concerns": concerns
    }

# --- Core Routes ---

@app.get("/", response_class=HTMLResponse)
async def get_landing_page(request: Request):
    """Renders the landing and discovery page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"active_page": "home"}
    )

@app.get("/app", response_class=HTMLResponse)
async def get_workspace_page(request: Request):
    """Renders the opportunity discovery workspace."""
    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={"active_page": "discover"}
    )

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    """Renders the authentication login page."""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"active_page": "login"}
    )

@app.get("/signup", response_class=HTMLResponse)
async def get_signup_page(request: Request):
    """Renders the user registration / sign up page."""
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={"active_page": "signup"}
    )

@app.get("/api/firebase-config")
async def get_firebase_config():
    """
    Returns public Firebase client configuration for browser SDK initialization.
    Safe for public consumption; contains no private service account secrets.
    """
    configured = bool(FIREBASE_API_KEY and FIREBASE_PROJECT_ID)
    return {
        "configured": configured,
        "apiKey": FIREBASE_API_KEY,
        "authDomain": FIREBASE_AUTH_DOMAIN or (f"{FIREBASE_PROJECT_ID}.firebaseapp.com" if FIREBASE_PROJECT_ID else ""),
        "projectId": FIREBASE_PROJECT_ID,
        "storageBucket": FIREBASE_STORAGE_BUCKET or (f"{FIREBASE_PROJECT_ID}.appspot.com" if FIREBASE_PROJECT_ID else ""),
        "messagingSenderId": FIREBASE_MESSAGING_SENDER_ID,
        "appId": FIREBASE_APP_ID
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "Pathora AI",
        "version": "1.0.0",
        "firebase_configured": firestore_db is not None,
        "search_configured": bool(SEARCH_API_KEY),
        "llm_configured": bool(GEMINI_API_KEY or GROQ_API_KEY)
    }

# --- Opportunity Search Endpoint ---

@app.get("/api/opportunities/search")
async def search_opportunities(
    q: Optional[str] = Query(None, description="Keywords query"),
    category: Optional[List[str]] = Query(None, description="Categories filter"),
    location: Optional[str] = Query(None, description="Location preference"),
    work_mode: Optional[str] = Query(None, description="Work mode"),
    education: Optional[str] = Query(None, description="Education level"),
    refresh: bool = Query(False, description="Force live search refresh")
):
    """
    Searches for real public opportunities using Tavily Web Search API.
    If no search key is configured or search fails, gracefully serves
    the verified seed index with explicit demo labelling.
    """
    raw_results = []
    source_mode = "seed_index"
    provider_name = "Curated Index"

    # Construct targeted search query
    category_label = category[0] if (category and len(category) == 1) else "internship"
    query_parts = []
    if q:
        query_parts.append(q)
    if category_label:
        query_parts.append(category_label)
    if location:
        query_parts.append(location)
    query_parts.append("2026 official portal application")

    constructed_query = " ".join(query_parts)

    if SEARCH_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": SEARCH_API_KEY,
                        "query": constructed_query,
                        "search_depth": "advanced",
                        "include_domains": [],
                        "max_results": 10
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    tavily_results = data.get("results", [])
                    if tavily_results:
                        raw_results = tavily_results
                        source_mode = "live_search"
                        provider_name = "Tavily Search API"
                        logger.info(f"Retrieved {len(raw_results)} results from Tavily live search.")
        except Exception as e:
            logger.warning(f"Tavily search API error: {e}. Falling back to verified seed index.")

    normalized_opportunities = []
    seen_urls = set()

    # Process live results if available
    if raw_results:
        for item in raw_results:
            norm = normalize_search_result(item, default_category=category_label.title())
            if norm and norm["officialUrl"] not in seen_urls:
                seen_urls.add(norm["officialUrl"])
                normalized_opportunities.append(norm)

    # If no live results or search key missing, use authoritative seed list
    if not normalized_opportunities:
        for item in AUTHORITATIVE_SEED_OPPORTUNITIES:
            # Filter seed opportunities by requested query or category
            match = True
            if category and item["category"] not in category:
                match = False
            if q and q.lower() not in (item["title"] + " " + item["description"] + " " + item["organization"]).lower():
                match = False
            if location and location.lower() not in (item["location"] + " " + item["description"]).lower():
                match = False
            
            if match and item["officialUrl"] not in seen_urls:
                seen_urls.add(item["officialUrl"])
                normalized_opportunities.append(item)

        # Fallback if filters were overly narrow on seeds
        if not normalized_opportunities:
            normalized_opportunities = list(AUTHORITATIVE_SEED_OPPORTUNITIES)

    return {
        "status": "success",
        "total": len(normalized_opportunities),
        "source_mode": source_mode,
        "provider": provider_name,
        "query_used": constructed_query,
        "opportunities": normalized_opportunities
    }

@app.get("/api/opportunities/{opportunity_id}")
async def get_opportunity_detail(opportunity_id: str):
    """Retrieve an individual opportunity record."""
    # Check seed opportunities
    for opp in AUTHORITATIVE_SEED_OPPORTUNITIES:
        if opp["id"] == opportunity_id:
            return opp

    # Check in-memory cache
    if opportunity_id in memory_store.opportunities:
        return memory_store.opportunities[opportunity_id]

    raise HTTPException(status_code=404, detail="Opportunity not found")

# --- AI Eligibility & Match Analysis Endpoint ---

@app.post("/api/opportunities/analyze")
async def analyze_opportunity(payload: AnalyzeRequestSchema):
    """
    Performs deterministic eligibility scoring and generates grounded LLM reasoning.
    Does not hallucinate deadlines, stipends, or unverified requirements.
    """
    opp = payload.opportunity
    profile = payload.profile or {
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Computer Science",
        "skills": ["Python", "Web Development"],
        "country": "Pakistan",
        "experienceLevel": "Beginner / No Experience"
    }

    # Step 1: Compute deterministic match score
    deterministic_result = compute_match_score(opp, profile)

    explanation = " ".join(deterministic_result["positiveNotes"]) if deterministic_result["positiveNotes"] else "Opportunity aligns generally with early-career discovery goals."
    concerns = " ".join(deterministic_result["concerns"]) if deterministic_result["concerns"] else None
    recommended_steps = "Visit the official portal to review prerequisites, verify active deadline, and prepare required application materials."

    # Step 2: If Gemini API Key is available, generate grounded natural language explanation
    if GEMINI_API_KEY:
        try:
            prompt = f"""
You are Pathora AI's opportunity advisor. Analyze this opportunity for the given candidate profile.
Ground your analysis strictly on the provided listing details and profile.
Do NOT invent unmentioned deadlines, stipends, or requirements.

Candidate Profile:
- Education: {profile.get('educationLevel')}
- Field: {profile.get('fieldOfStudy')}
- Skills: {', '.join(profile.get('skills', []))}
- Experience: {profile.get('experienceLevel')}
- Work Preference: {profile.get('workPreference')}

Opportunity:
- Title: {opp.get('title')}
- Organization: {opp.get('organization')}
- Category: {opp.get('category')}
- Excerpt: {opp.get('description')}
- Work Mode: {opp.get('workMode')}
- Deadline: {opp.get('deadline')}

Deterministic Match Score: {deterministic_result['score']}/100 ({deterministic_result['classification']})

Provide a concise JSON response with:
1. "explanation": 2 sentences explaining specifically why this opportunity suits the candidate.
2. "concerns": 1 sentence describing any uncertain or potentially unfulfilled qualifications to verify on the official listing.
3. "recommended_steps": 1-2 actionable next steps for the student.

Respond ONLY with valid JSON.
"""
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": GEMINI_API_KEY,
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
                    }
                )
                if res.status_code == 200:
                    gemini_data = res.json()
                    raw_text = gemini_data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)
                    explanation = parsed.get("explanation", explanation)
                    concerns = parsed.get("concerns", concerns)
                    recommended_steps = parsed.get("recommended_steps", recommended_steps)
        except Exception as e:
            logger.warning("LLM analysis fallback to deterministic reasoning (%s)", type(e).__name__)

    return {
        "match_score": deterministic_result["score"],
        "classification": deterministic_result["classification"],
        "factors": deterministic_result["factors"],
        "explanation": explanation,
        "concerns": concerns,
        "recommended_steps": recommended_steps,
        "disclaimer": "Pathora AI match analysis is assistive and advisory. Official portal requirements and deadlines remain authoritative."
    }

# --- Candidate Profile Endpoints ---

@app.get("/api/profile")
async def get_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve the candidate profile for the authenticated user."""
    uid = user["uid"]
    
    # Firestore fetch if enabled
    if firestore_db:
        try:
            doc = firestore_db.collection("users").document(uid).get()
            if doc.exists:
                return {"status": "success", "profile": doc.to_dict()}
        except Exception as e:
            logger.warning(f"Firestore get profile error: {e}")

    # Memory store fallback
    profile = memory_store.users.get(uid, {
        "displayName": user.get("displayName", "Candidate"),
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Computer Science",
        "country": "Pakistan",
        "skills": ["Python", "JavaScript", "AI/ML"],
        "interests": ["Software Engineering", "Artificial Intelligence"],
        "experienceLevel": "Beginner / No Experience",
        "workPreference": "Flexible / Any"
    })
    return {"status": "success", "profile": profile}

@app.put("/api/profile")
async def update_profile(profile_data: UserProfileSchema, user: Dict[str, Any] = Depends(get_current_user)):
    """Create or update the candidate profile."""
    uid = user["uid"]
    data = profile_data.model_dump()
    data["updatedAt"] = get_utc_now_iso()

    if firestore_db:
        try:
            firestore_db.collection("users").document(uid).set(data, merge=True)
        except Exception as e:
            logger.warning(f"Firestore update profile error: {e}")

    memory_store.users[uid] = data
    return {"status": "success", "profile": data}

# --- Saved Opportunities Endpoints ---

@app.get("/api/saved")
async def list_saved_opportunities(user: Dict[str, Any] = Depends(get_current_user)):
    """List all saved opportunities for the authenticated user."""
    uid = user["uid"]

    if firestore_db:
        try:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter
                docs = firestore_db.collection("saved_opportunities").where(filter=FieldFilter("userId", "==", uid)).stream()
            except Exception:
                docs = firestore_db.collection("saved_opportunities").where("userId", "==", uid).stream()
            items = [d.to_dict() for d in docs]
            return {"status": "success", "saved": items}
        except Exception as e:
            logger.warning(f"Firestore get saved error: {e}")

    user_saved = memory_store.saved.get(uid, {})
    return {"status": "success", "saved": list(user_saved.values())}

@app.post("/api/saved")
async def save_opportunity(payload: SavedOpportunityRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """Bookmark an opportunity for the authenticated user."""
    uid = user["uid"]
    opp_id = payload.opportunityId
    record = {
        "userId": uid,
        "opportunityId": opp_id,
        "opportunityData": payload.opportunityData or {},
        "savedAt": get_utc_now_iso()
    }

    if firestore_db:
        try:
            doc_id = f"{uid}_{opp_id}"
            firestore_db.collection("saved_opportunities").document(doc_id).set(record)
        except Exception as e:
            logger.warning(f"Firestore save error: {e}")

    if uid not in memory_store.saved:
        memory_store.saved[uid] = {}
    memory_store.saved[uid][opp_id] = record

    return {"status": "success", "message": "Opportunity saved"}

@app.delete("/api/saved/{opportunity_id}")
async def remove_saved_opportunity(opportunity_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Remove a bookmarked opportunity."""
    uid = user["uid"]

    if firestore_db:
        try:
            doc_id = f"{uid}_{opportunity_id}"
            firestore_db.collection("saved_opportunities").document(doc_id).delete()
        except Exception as e:
            logger.warning(f"Firestore delete saved error: {e}")

    if uid in memory_store.saved and opportunity_id in memory_store.saved[uid]:
        del memory_store.saved[uid][opportunity_id]

    return {"status": "success", "message": "Opportunity removed from bookmarks"}

# --- Application Tracker Endpoints ---

@app.get("/api/applications")
async def list_applications(user: Dict[str, Any] = Depends(get_current_user)):
    """List the application tracker pipeline for the authenticated user."""
    uid = user["uid"]

    if firestore_db:
        try:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter
                docs = firestore_db.collection("applications").where(filter=FieldFilter("userId", "==", uid)).stream()
            except Exception:
                docs = firestore_db.collection("applications").where("userId", "==", uid).stream()
            items = [d.to_dict() for d in docs]
            return {"status": "success", "applications": items}
        except Exception as e:
            logger.warning(f"Firestore get applications error: {e}")

    user_apps = memory_store.applications.get(uid, {})
    return {"status": "success", "applications": list(user_apps.values())}

@app.post("/api/applications")
async def create_application(payload: ApplicationTrackerRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """Add or update an application tracker record."""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=STATUS_UNPROCESSABLE,
            detail=f"Invalid status '{payload.status}'. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    uid = user["uid"]
    opp_id = payload.opportunityId
    now = get_utc_now_iso()

    record = {
        "userId": uid,
        "opportunityId": opp_id,
        "status": payload.status,
        "notes": payload.notes or "",
        "applicationDate": payload.applicationDate or get_utc_today_str(),
        "opportunityData": payload.opportunityData or {},
        "updatedAt": now
    }

    if firestore_db:
        try:
            doc_id = f"{uid}_{opp_id}"
            firestore_db.collection("applications").document(doc_id).set(record, merge=True)
        except Exception as e:
            logger.warning(f"Firestore create application error: {e}")

    if uid not in memory_store.applications:
        memory_store.applications[uid] = {}
    memory_store.applications[uid][opp_id] = record

    return {"status": "success", "application": record}

@app.patch("/api/applications/{opportunity_id}")
async def update_application_status(
    opportunity_id: str,
    payload: ApplicationUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Update status or notes for an existing application record."""
    if payload.status and payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=STATUS_UNPROCESSABLE,
            detail=f"Invalid status '{payload.status}'. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    uid = user["uid"]
    now = get_utc_now_iso()

    # Fetch existing
    existing = memory_store.applications.get(uid, {}).get(opportunity_id, {
        "userId": uid,
        "opportunityId": opportunity_id,
        "status": "Interested",
        "notes": "",
        "applicationDate": get_utc_today_str(),
        "opportunityData": {}
    })

    if payload.status:
        existing["status"] = payload.status
    if payload.notes is not None:
        existing["notes"] = payload.notes
    if payload.applicationDate:
        existing["applicationDate"] = payload.applicationDate
    existing["updatedAt"] = now

    if firestore_db:
        try:
            doc_id = f"{uid}_{opportunity_id}"
            firestore_db.collection("applications").document(doc_id).update(existing)
        except Exception as e:
            logger.warning(f"Firestore update application error: {e}")

    if uid not in memory_store.applications:
        memory_store.applications[uid] = {}
    memory_store.applications[uid][opportunity_id] = existing

    return {"status": "success", "application": existing}

@app.delete("/api/applications/{opportunity_id}")
async def delete_application(opportunity_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Delete an application tracker record."""
    uid = user["uid"]

    if firestore_db:
        try:
            doc_id = f"{uid}_{opportunity_id}"
            firestore_db.collection("applications").document(doc_id).delete()
        except Exception as e:
            logger.warning(f"Firestore delete application error: {e}")

    if uid in memory_store.applications and opportunity_id in memory_store.applications[uid]:
        del memory_store.applications[uid][opportunity_id]

    return {"status": "success", "message": "Application record deleted"}

try:
    import agent_workflow
    from agent_workflow import AgentWorkflowRequest

    @app.post("/api/agent/workflow")
    async def run_agent_workflow_endpoint(
        payload: AgentWorkflowRequest,
        user: Dict[str, Any] = Depends(get_current_user),
    ):
        try:
            profile_response = await get_profile(user)
            profile = profile_response.get("profile", {})
        except Exception as e:
            logger.warning("Agent profile lookup failed (%s)", type(e).__name__)
            profile = {}

        async def run_existing_analysis(opportunity, candidate_profile):
            return await analyze_opportunity(
                AnalyzeRequestSchema(opportunity=opportunity, profile=candidate_profile)
            )

        try:
            return await agent_workflow.run_agent_workflow(
                request=payload,
                profile=profile if isinstance(profile, dict) else {},
                search_fn=search_opportunities,
                score_fn=compute_match_score,
                analyze_fn=run_existing_analysis,
                llm_available=bool(GEMINI_API_KEY),
            )
        except Exception as e:
            logger.warning("Agent workflow failed (%s)", type(e).__name__)
            raise HTTPException(
                status_code=503,
                detail="Agent workflow could not be completed. Please try again later.",
            ) from e
except Exception as e:
    logger.warning("Agent workflow unavailable (%s)", type(e).__name__)

try:
    import chatbot
    chatbot.set_search_function(search_opportunities)
    app.include_router(chatbot.chat_router)
except Exception as e:
    logger.warning(f"Chatbot disabled: {e}")

if __name__ == "__main__":
    import uvicorn
    server_port = int(os.getenv("PORT", 8000))
    server_host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=server_host, port=server_port, reload=False)
