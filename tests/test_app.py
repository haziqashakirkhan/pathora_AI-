"""
Automated Unit and Integration Tests for Pathora AI
Tests cover endpoints, search normalization, deterministic scoring,
auth protection, data isolation, and validation rules.
"""

import pytest
from fastapi.testclient import TestClient
from main import (
    app,
    normalize_search_result,
    compute_match_score,
    VALID_STATUSES,
    memory_store
)

client = TestClient(app)

# --- 1. General & Health Endpoint Tests ---

def test_health_check_endpoint():
    """Verify health endpoint returns healthy status and metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Pathora AI"
    assert "version" in data

def test_landing_page_loads():
    """Verify landing page renders successfully with proper title and elements."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Pathora AI" in response.text
    assert "Find the opportunities that" in response.text

def test_app_workspace_page_loads():
    """Verify opportunity discovery workspace page renders with TapRefer directory components."""
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Opportunity Workspace" in response.text
    assert "workspace-search-input" in response.text
    assert "filter-sidebar" in response.text

# --- 2. Search & Normalization Tests ---

def test_search_endpoint_default():
    """Verify search endpoint returns formatted results and respects query parameters."""
    response = client.get("/api/opportunities/search?q=software")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "opportunities" in data
    assert isinstance(data["opportunities"], list)
    assert len(data["opportunities"]) > 0

def test_search_normalization_logic():
    """Verify that search result normalization handles messy titles, domains, and extracts categories."""
    raw_item = {
        "title": "Software Engineering Summer 2026 Internship Program",
        "url": "https://careers.example.org/jobs/12345",
        "content": "Join our remote software engineering internship. Apply by April 15, 2026."
    }
    normalized = normalize_search_result(raw_item, default_category="Internship")
    assert normalized is not None
    assert normalized["category"] == "Internship"
    assert normalized["workMode"] == "Remote"
    assert normalized["deadline"] == "April 15, 2026"
    assert normalized["organization"] == "Careers"
    assert normalized["officialUrl"] == "https://careers.example.org/jobs/12345"

def test_search_normalization_missing_deadline():
    """Verify missing deadlines are honestly marked as unknown rather than fabricated."""
    raw_item = {
        "title": "Data Analyst Fellowship Opportunity",
        "url": "https://fellowships.example.edu/apply",
        "content": "Fellowship program open for recent graduates. No specific date mentioned."
    }
    normalized = normalize_search_result(raw_item, default_category="Fellowship")
    assert normalized is not None
    assert "Unknown" in normalized["deadline"]

def test_search_normalization_handles_empty():
    """Verify that malformed or empty search results return None."""
    assert normalize_search_result({}) is None
    assert normalize_search_result({"title": "", "url": ""}) is None

# --- 3. Deterministic Matching Logic Tests ---

def test_deterministic_matching_high_match():
    """Test candidate with matching education, field, skills, and work preference receives a high score."""
    opp = {
        "title": "Undergraduate Python Software Engineering Internship",
        "category": "Internship",
        "description": "Looking for undergraduate students with Python and Web Development experience.",
        "educationRequirements": "Currently enrolled undergraduate",
        "workMode": "Remote"
    }
    profile = {
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Computer Science",
        "skills": ["Python", "Web Development", "Git"],
        "experienceLevel": "Beginner / No Experience",
        "workPreference": "Remote",
        "preferredOpportunityTypes": ["Internship"]
    }

    result = compute_match_score(opp, profile)
    assert result["score"] >= 75
    assert result["classification"] == "Likely match"
    assert len(result["positiveNotes"]) >= 2

def test_deterministic_matching_missing_profile_info():
    """Verify that missing profile criteria does NOT produce false eligibility claims."""
    opp = {
        "title": "Bioinformatics Research Fellowship",
        "category": "Fellowship",
        "description": "Requires advanced molecular biology background.",
        "educationRequirements": "PhD candidate",
        "workMode": "On-site"
    }
    empty_profile = {
        "educationLevel": "",
        "fieldOfStudy": "",
        "skills": [],
        "workPreference": ""
    }

    result = compute_match_score(opp, empty_profile)
    assert result["classification"] in ["Insufficient information", "Likely ineligible"]
    assert len(result["missingInfo"]) > 0

def test_deterministic_matching_is_reproducible():
    """Verify that given identical inputs, scoring produces identical results every time."""
    opp = {
        "title": "Frontend Engineering Intern",
        "category": "Internship",
        "description": "JavaScript and React foundation preferred.",
        "educationRequirements": "Undergraduate",
        "workMode": "Hybrid"
    }
    profile = {
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Software Engineering",
        "skills": ["JavaScript", "HTML", "CSS"],
        "workPreference": "Flexible / Any"
    }

    run1 = compute_match_score(opp, profile)
    run2 = compute_match_score(opp, profile)
    assert run1["score"] == run2["score"]
    assert run1["classification"] == run2["classification"]

# --- 4. Protected Routes & Authentication Tests ---

def test_protected_routes_reject_unauthenticated():
    """Verify that endpoints requiring authentication return 401 when unauthenticated."""
    # Profile
    res_prof = client.get("/api/profile")
    assert res_prof.status_code == 401

    # Saved
    res_saved = client.get("/api/saved")
    assert res_saved.status_code == 401

    # Applications
    res_apps = client.get("/api/applications")
    assert res_apps.status_code == 401

def test_authenticated_profile_crud():
    """Verify authenticated user can get and update their profile."""
    headers = {"Authorization": "Bearer demo_token_guest"}

    # Get profile
    res_get = client.get("/api/profile", headers=headers)
    assert res_get.status_code == 200
    assert "profile" in res_get.json()

    # Update profile
    new_profile = {
        "displayName": "Test Candidate",
        "educationLevel": "Undergraduate",
        "fieldOfStudy": "Data Science",
        "country": "Pakistan",
        "skills": ["Python", "SQL"],
        "interests": ["Data Engineering"],
        "preferredOpportunityTypes": ["Internship"],
        "experienceLevel": "Beginner / No Experience",
        "workPreference": "Remote",
        "careerGoals": "Data Analyst role in 2026"
    }
    res_put = client.put("/api/profile", json=new_profile, headers=headers)
    assert res_put.status_code == 200
    assert res_put.json()["profile"]["fieldOfStudy"] == "Data Science"

# --- 5. User Data Isolation Tests ---

def test_user_data_isolation():
    """Verify User A cannot see or mutate User B's saved items or applications."""
    user_a_headers = {"Authorization": "Bearer bearer_firebase_usr_user_a"}
    user_b_headers = {"Authorization": "Bearer bearer_firebase_usr_user_b"}

    # User A saves an opportunity
    opp_payload = {
        "opportunityId": "opp_test_isolation_1",
        "opportunityData": {"title": "User A Opportunity", "organization": "Org A"}
    }
    res_save_a = client.post("/api/saved", json=opp_payload, headers=user_a_headers)
    assert res_save_a.status_code == 200

    # User B lists saved opportunities -> User A's item must NOT appear
    res_saved_b = client.get("/api/saved", headers=user_b_headers)
    assert res_saved_b.status_code == 200
    b_saved_ids = [item["opportunityId"] for item in res_saved_b.json().get("saved", [])]
    assert "opp_test_isolation_1" not in b_saved_ids

    # User A lists saved -> should see item
    res_saved_a = client.get("/api/saved", headers=user_a_headers)
    a_saved_ids = [item["opportunityId"] for item in res_saved_a.json().get("saved", [])]
    assert "opp_test_isolation_1" in a_saved_ids

# --- 6. Application Tracker Validation Tests ---

def test_application_tracker_invalid_status_rejected():
    """Verify that arbitrary or invalid application statuses are rejected with 422."""
    headers = {"Authorization": "Bearer demo_token_guest"}
    payload = {
        "opportunityId": "opp_invalid_status",
        "status": "RandomInvalidStatus",
        "notes": "Testing invalid status"
    }
    res = client.post("/api/applications", json=payload, headers=headers)
    assert res.status_code == 422
    assert "Invalid status" in res.json()["detail"]

def test_application_tracker_valid_lifecycle():
    """Verify full application tracker lifecycle (Create, Update, List, Delete)."""
    headers = {"Authorization": "Bearer bearer_firebase_usr_lifecycle_user"}

    # 1. Create tracker item
    create_payload = {
        "opportunityId": "opp_lifecycle_test",
        "status": "Planning to Apply",
        "notes": "Drafting cover letter",
        "applicationDate": "2026-03-01",
        "opportunityData": {"title": "Lifecycle Internship", "organization": "Lifecycle Org"}
    }
    res_create = client.post("/api/applications", json=create_payload, headers=headers)
    assert res_create.status_code == 200
    assert res_create.json()["application"]["status"] == "Planning to Apply"

    # 2. Update status to Applied
    update_payload = {
        "status": "Applied",
        "notes": "Application submitted via company portal"
    }
    res_update = client.patch("/api/applications/opp_lifecycle_test", json=update_payload, headers=headers)
    assert res_update.status_code == 200
    assert res_update.json()["application"]["status"] == "Applied"

    # 3. List applications
    res_list = client.get("/api/applications", headers=headers)
    assert res_list.status_code == 200
    apps = res_list.json()["applications"]
    assert any(a["opportunityId"] == "opp_lifecycle_test" and a["status"] == "Applied" for a in apps)

    # 4. Delete record
    res_delete = client.delete("/api/applications/opp_lifecycle_test", headers=headers)
    assert res_delete.status_code == 200

    # 5. Verify deleted
    res_list_after = client.get("/api/applications", headers=headers)
    remaining_ids = [a["opportunityId"] for a in res_list_after.json()["applications"]]
    assert "opp_lifecycle_test" not in remaining_ids

# --- 7. Authentication Pages & Config Tests ---

def test_login_page_renders():
    """Verify login page renders with authentication form and visual branding."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Sign in to your account" in response.text
    assert "login-email" in response.text
    assert "login-password" in response.text

def test_signup_page_renders():
    """Verify registration page renders with full name, email, and password confirmation."""
    response = client.get("/signup")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Create your account" in response.text
    assert "signup-name" in response.text
    assert "signup-email" in response.text
    assert "signup-password" in response.text
    assert "signup-confirm-password" in response.text

def test_firebase_config_endpoint():
    """Verify safe public Firebase config endpoint returns structured schema."""
    response = client.get("/api/firebase-config")
    assert response.status_code == 200
    data = response.json()
    assert "configured" in data
    assert "projectId" in data
    assert "apiKey" in data
