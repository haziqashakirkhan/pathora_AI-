"""
Unit and Integration Tests for Pakistan-First Discovery, Dynamic Matching,
Email Notification Engine, 7-Day Inactivity Reminders, and SEO endpoints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

import main
from main import (
    app,
    AUTHORITATIVE_SEED_OPPORTUNITIES,
    normalize_search_result,
    compute_match_score,
    memory_store,
    get_utc_now_iso
)
import email_service
from email_service import (
    is_valid_email,
    render_opportunity_alert_html,
    render_inactivity_reminder_html,
    check_and_send_opportunity_alert,
    process_user_inactivity_reminders,
    notification_memory_store
)

client = TestClient(app)

# --- 1. Pakistan-First Opportunity Discovery Tests ---

def test_authoritative_seeds_include_pakistan_institutions():
    """Verify curated seed index contains Pakistani institutions (HEC, NAVTTC, DigiSkills, PEEF, etc.)."""
    pk_seeds = [opp for opp in AUTHORITATIVE_SEED_OPPORTUNITIES if opp.get("isPakistani")]
    assert len(pk_seeds) >= 7

    orgs = [opp["organization"] for opp in pk_seeds]
    assert any("Higher Education Commission" in org for org in orgs)
    assert any("DigiSkills" in org for org in orgs)
    assert any("Punjab Educational Endowment Fund" in org for org in orgs)
    assert any("Saylani" in org for org in orgs)
    assert any("NAVTTC" in org for org in orgs)

def test_country_filter_all_ranks_pakistan_first():
    """Verify that default 'All' search mode ranks Pakistani opportunities before international ones."""
    res = client.get("/api/opportunities/search?country=All")
    assert res.status_code == 200
    opps = res.json()["opportunities"]
    assert len(opps) > 0

    first_opp = opps[0]
    assert first_opp.get("isPakistani") is True
    assert first_opp.get("country") == "Pakistan"

def test_country_filter_pakistan_only():
    """Verify that country=Pakistan filter returns ONLY Pakistani opportunities."""
    res = client.get("/api/opportunities/search?country=Pakistan")
    assert res.status_code == 200
    opps = res.json()["opportunities"]
    assert len(opps) > 0
    assert all(opp.get("isPakistani") is True or opp.get("country") == "Pakistan" for opp in opps)

def test_country_filter_international_only():
    """Verify that country=International filter returns international programs open to Pakistani students."""
    res = client.get("/api/opportunities/search?country=International")
    assert res.status_code == 200
    opps = res.json()["opportunities"]
    assert len(opps) > 0
    assert all(opp.get("country") == "International" for opp in opps)
    assert any("Google" in opp["title"] or "Fulbright" in opp["title"] for opp in opps)

def test_search_multiple_categories_does_not_default_to_internship():
    """Verify query generation does not force 'internship' when multiple categories or scholarships are selected."""
    res = client.get("/api/opportunities/search?category=Scholarship&category=Training+Program")
    assert res.status_code == 200
    data = res.json()
    assert "internship" not in data.get("query_used", "").lower() or "scholarship" in data.get("query_used", "").lower()
    opps = data["opportunities"]
    assert all(opp["category"] in ["Scholarship", "Training Program"] for opp in opps)

def test_normalization_recognizes_pakistani_domains_and_verification():
    """Verify that official Pakistani domains (.edu.pk, .gov.pk) are marked official and verified."""
    raw_item = {
        "title": "HEC PhD Indigenous Scholarship 2026",
        "url": "https://www.hec.gov.pk/scholarships/indigenous-2026",
        "content": "Official announcement for HEC indigenous scholarships for Pakistani students. Apply by May 30, 2026."
    }
    norm = normalize_search_result(raw_item, default_category="Scholarship")
    assert norm is not None
    assert norm["isPakistani"] is True
    assert norm["country"] == "Pakistan"
    assert norm["verified"] is True
    assert norm["sourceType"] == "official"
    assert norm["status"] == "Open"
    assert "May 30, 2026" in norm["deadline"]

def test_normalization_flags_closed_opportunities():
    """Verify that opportunities with expired/past deadlines are honestly marked Closed."""
    raw_item = {
        "title": "Old Software Internship 2023",
        "url": "https://careers.example.com/expired-job",
        "content": "This application cycle is now closed. Deadline was January 15, 2024."
    }
    norm = normalize_search_result(raw_item)
    assert norm is not None
    assert norm["status"] == "Closed"

# --- 2. Dynamic Matching & Eligibility Separation Tests ---

def test_matching_does_not_cluster_at_flat_62_percent():
    """Verify that varied profile attributes produce genuinely dynamic scores and not a static 62%."""
    # Profile A: Perfect alignment for undergraduate CS Pakistan student
    profile_a = {
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Computer Science",
        "skills": ["Python", "Machine Learning", "Web Development"],
        "country": "Pakistan",
        "experienceLevel": "Beginner / No Experience",
        "workPreference": "Remote",
        "preferredOpportunityTypes": ["Training Program"]
    }

    # Profile B: Completely unrelated profile (Medicine, no tech skills)
    profile_b = {
        "educationLevel": "High School",
        "fieldOfStudy": "Medicine",
        "skills": ["Biology", "Chemistry"],
        "country": "Pakistan",
        "experienceLevel": "Beginner / No Experience",
        "workPreference": "On-site",
        "preferredOpportunityTypes": ["Scholarship"]
    }

    # Opportunity: SMIT AI & Python Bootcamp
    opp = {
        "title": "Saylani Mass IT Training (SMIT) AI & Python Program",
        "category": "Training Program",
        "description": "Intensive training in Python, Machine Learning, and Web Development for undergraduate candidates.",
        "educationRequirements": "Undergraduate or Intermediate",
        "workMode": "Remote",
        "isPakistani": True,
        "country": "Pakistan"
    }

    score_a = compute_match_score(opp, profile_a)
    score_b = compute_match_score(opp, profile_b)

    assert score_a["score"] >= 85
    assert score_a["eligibility"] == "Eligible"
    assert score_a["classification"] == "Likely match"

    assert score_b["score"] < 55
    assert score_b["score"] != 62  # Not stuck at 62%
    assert score_b["eligibility"] in ["Potentially eligible", "Not eligible"]

def test_eligibility_separated_from_suitability():
    """Verify that hard requirement mismatches yield 'Not eligible' despite high general keywords."""
    opp_phd = {
        "title": "Doctoral Research Fellowship in Artificial Intelligence",
        "category": "Research",
        "description": "Requires completed Master's degree and doctoral candidacy with 5+ years research experience.",
        "educationRequirements": "PhD candidate required",
        "workMode": "On-site",
        "isPakistani": True
    }
    undergrad_profile = {
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Computer Science",
        "skills": ["Python", "Artificial Intelligence"],
        "experienceLevel": "Beginner / No Experience"
    }

    result = compute_match_score(opp_phd, undergrad_profile)
    assert result["eligibility"] == "Not eligible"
    assert any("doctoral" in c.lower() or "senior" in c.lower() for c in result["concerns"])

def test_batch_match_endpoint_authoritative_backend():
    """Verify POST /api/opportunities/match-batch scores opportunities authoritatively."""
    opps = [
        AUTHORITATIVE_SEED_OPPORTUNITIES[0],
        AUTHORITATIVE_SEED_OPPORTUNITIES[1]
    ]
    profile = {
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Computer Science",
        "skills": ["Python", "Web Development"],
        "country": "Pakistan"
    }

    res = client.post("/api/opportunities/match-batch", json={"opportunities": opps, "profile": profile})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["matches"]) == 2
    assert "matchScore" in data["matches"][0]
    assert "eligibility" in data["matches"][0]
    assert "factors" in data["matches"][0]

# --- 3. Email Notification & 7-Day Inactivity Tracking Tests ---

def test_valid_email_validator():
    """Verify email format validation."""
    assert is_valid_email("student@example.com") is True
    assert is_valid_email("scholar.pk@nust.edu.pk") is True
    assert is_valid_email("invalid-email") is False
    assert is_valid_email("") is False

def test_opportunity_alert_duplicate_prevention():
    """Verify that an opportunity alert is not delivered twice to the same user for the same opportunity."""
    user_id = "test_user_alerts_1"
    user_email = "student1@example.com"
    opp = {
        "id": "opp_unique_test_101",
        "title": "National Tech Scholarship 2026",
        "organization": "HEC",
        "category": "Scholarship",
        "location": "Islamabad",
        "deadline": "April 2026",
        "description": "Full funding for CS candidates.",
        "officialUrl": "https://example.gov.pk/apply"
    }

    import asyncio
    # Run first alert
    res1 = asyncio.run(check_and_send_opportunity_alert(user_id, user_email, "Fatima", opp, firestore_db=None))
    assert res1["status"] == "sent"

    # Attempt second alert for same opportunity
    res2 = asyncio.run(check_and_send_opportunity_alert(user_id, user_email, "Fatima", opp, firestore_db=None))
    assert res2["status"] == "skipped"
    assert "already sent" in res2["reason"].lower()

def test_seven_day_tracker_inactivity_reminders():
    """Verify that application inactive for more than 7 days triggers reminder email and resets on activity."""
    import asyncio
    user_id = "test_user_inactivity_1"
    user_email = "candidate@example.com"
    user_name = "Ali"

    now = datetime.now(timezone.utc)
    eight_days_ago = (now - timedelta(days=8)).isoformat().replace("+00:00", "Z")
    three_days_ago = (now - timedelta(days=3)).isoformat().replace("+00:00", "Z")

    applications = [
        # Application 1: Inactive for 8 days (should trigger reminder)
        {
            "opportunityId": "opp_inactive_1",
            "status": "Planning to Apply",
            "updatedAt": eight_days_ago,
            "notes": "Need to draft SOP",
            "opportunityData": {"title": "PM Youth IT Training", "organization": "PMYP"}
        },
        # Application 2: Active 3 days ago (should NOT trigger reminder)
        {
            "opportunityId": "opp_active_1",
            "status": "Interested",
            "updatedAt": three_days_ago,
            "opportunityData": {"title": "DigiSkills Course", "organization": "Ignite"}
        },
        # Application 3: Inactive for 10 days BUT status is Accepted (terminal status, should NOT trigger)
        {
            "opportunityId": "opp_accepted_1",
            "status": "Accepted",
            "updatedAt": eight_days_ago,
            "opportunityData": {"title": "GSoC 2026", "organization": "Google"}
        }
    ]

    sent_reminders = asyncio.run(process_user_inactivity_reminders(
        user_id, user_email, user_name, applications, firestore_db=None
    ))

    # Only Application 1 should trigger
    assert len(sent_reminders) == 1
    assert sent_reminders[0]["opportunityId"] == "opp_inactive_1"
    assert sent_reminders[0]["days_inactive"] >= 7

    # Run second time immediately: spacing prevents repeated email
    sent_second_run = asyncio.run(process_user_inactivity_reminders(
        user_id, user_email, user_name, applications, firestore_db=None
    ))
    assert len(sent_second_run) == 0

    # Updating activity resets the timer
    applications[0]["updatedAt"] = now.isoformat().replace("+00:00", "Z")
    sent_after_reset = asyncio.run(process_user_inactivity_reminders(
        user_id, user_email, user_name, applications, firestore_db=None
    ))
    assert len(sent_after_reset) == 0

def test_cron_process_notifications_endpoint():
    """Verify that /api/cron/process-notifications endpoint runs without error."""
    # Seed an application in memory store for testing
    user_id = "cron_test_user"
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    memory_store.users[user_id] = {"email": "cron_candidate@example.com", "displayName": "Cron User"}
    memory_store.applications[user_id] = {
        "opp_cron_test": {
            "userId": user_id,
            "opportunityId": "opp_cron_test",
            "status": "Interested",
            "updatedAt": ten_days_ago,
            "notes": "Testing cron worker",
            "opportunityData": {"title": "Cron Test Opportunity"}
        }
    }

    res = client.post("/api/cron/process-notifications")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "processed_users" in data
    assert "reminders_sent" in data
    assert data["reminders_sent"] >= 1

# --- 4. SEO & Accessibility Routes Tests ---

def test_robots_txt_endpoint():
    """Verify /robots.txt exists, is plain text, disallows /api/, and links sitemap."""
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    assert "Disallow: /api/" in res.text
    assert "Sitemap: https://pathora-ai-psi.vercel.app/sitemap.xml" in res.text

def test_sitemap_xml_endpoint():
    """Verify /sitemap.xml exists and outputs valid XML sitemap with public URLs."""
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert "xml" in res.headers["content-type"]
    assert "https://pathora-ai-psi.vercel.app/" in res.text
    assert "https://pathora-ai-psi.vercel.app/app" in res.text
    assert "https://pathora-ai-psi.vercel.app/login" in res.text
    assert "https://pathora-ai-psi.vercel.app/signup" in res.text
    assert "/api/" not in res.text  # Protected APIs must not be in sitemap

