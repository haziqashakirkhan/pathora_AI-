/**
 * PATHORA AI - Core Client Application JavaScript
 * Intelligent Opportunity Discovery and Application Agent
 */

// Application State
const state = {
  user: null, // { uid, email, displayName, token, isGuest }
  profile: {
    displayName: "Candidate",
    educationLevel: "Undergraduate",
    fieldOfStudy: "Computer Science",
    country: "Pakistan",
    skills: ["Python", "JavaScript", "Web Development", "AI/ML"],
    interests: ["Software Engineering", "Artificial Intelligence"],
    experienceLevel: "Beginner / No Experience",
    workPreference: "Flexible / Any",
    preferredOpportunityTypes: ["Internship", "Scholarship", "Entry-level Job"],
    careerGoals: "Secure a competitive summer 2026 internship"
  },
  opportunities: [],
  filteredOpportunities: [],
  savedOpportunities: new Map(), // id -> opp
  applications: new Map(), // id -> appRecord
  activeTab: "discover",
  selectedOpp: null,
  activeFilterTracker: "ALL",
  isLoadingSearch: false
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  initUserSession();
  initProfile();
  initUrlParameters();
  loadSavedAndApplications();
  initScrollReveal();

  // Set up search Enter key handlers
  const searchInput = document.getElementById("workspace-search-input");
  if (searchInput) {
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        executeLiveSearch();
      }
    });
  }

  // Initial opportunity load
  executeLiveSearch();

  // Re-render Lucide icons
  refreshIcons();
});

function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

// --- Session & Authentication ---
function initUserSession() {
  if (window.PathoraAuth) {
    PathoraAuth.onAuthStateChanged((user) => {
      if (user) {
        state.user = {
          uid: user.uid,
          email: user.email,
          displayName: user.displayName,
          token: PathoraAuth.getToken(),
          isGuest: false
        };
      } else {
        const storedToken = localStorage.getItem("pathora_auth_token");
        const storedUser = localStorage.getItem("pathora_user_session");
        if (storedToken && storedUser) {
          try {
            const parsed = JSON.parse(storedUser);
            state.user = {
              uid: parsed.uid,
              email: parsed.email,
              displayName: parsed.displayName,
              token: storedToken,
              isGuest: false
            };
          } catch (e) {
            setDefaultGuestUser();
          }
        } else {
          setDefaultGuestUser();
        }
      }
      updateNavAuthUI();
    });
  } else {
    setDefaultGuestUser();
    updateNavAuthUI();
  }
}

function setDefaultGuestUser() {
  state.user = {
    uid: "guest_demo_user",
    email: "guest@pathora.ai",
    displayName: "Guest Scholar",
    token: "demo_token_guest",
    isGuest: true
  };
}

function updateNavAuthUI() {
  if (window.updateGlobalNavAuth) {
    window.updateGlobalNavAuth(state.user && !state.user.isGuest ? state.user : null);
  }
}

function openAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (modal) {
    modal.classList.add("open");
  } else {
    window.location.href = "/login";
  }
}

function closeAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (modal) modal.classList.remove("open");
}

async function handleSignOut() {
  if (window.PathoraAuth) {
    await PathoraAuth.signOut();
  } else {
    localStorage.removeItem("pathora_user_session");
    localStorage.removeItem("pathora_auth_token");
  }
  state.savedOpportunities.clear();
  state.applications.clear();
  renderSavedView();
  renderTrackerView();
  showToast("Signed out successfully.", "info");
  setTimeout(() => {
    window.location.href = "/";
  }, 400);
}

function handleDemoSignIn() {
  state.user = {
    uid: "guest_demo_user",
    email: "guest@pathora.ai",
    displayName: "Guest Candidate",
    token: "demo_token_guest",
    isGuest: true
  };
  localStorage.setItem("pathora_user", JSON.stringify(state.user));
  updateNavAuthUI();
  closeAuthModal();
  showToast("Switched to Demo Mode. All search and scoring features active.", "info");
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const email = document.getElementById("auth-email").value.trim();
  const isCreate = document.getElementById("auth-create-account").checked;
  const submitBtn = document.getElementById("auth-submit-btn");

  if (!email) return;
  submitBtn.disabled = true;
  submitBtn.innerText = "Authenticating...";

  try {
    // Generate authenticated session identity
    const cleanUid = "usr_" + btoa(email).replace(/[^a-zA-Z0-9]/g, "").slice(0, 16);
    state.user = {
      uid: cleanUid,
      email: email,
      displayName: email.split("@")[0],
      token: "bearer_firebase_" + cleanUid,
      isGuest: false
    };
    localStorage.setItem("pathora_user", JSON.stringify(state.user));

    // Fetch user profile from backend
    await fetchProfile();
    updateNavAuthUI();
    closeAuthModal();
    showToast(`Signed in successfully as ${email}`, "success");
    await loadSavedAndApplications();
  } catch (err) {
    showToast("Authentication failed: " + err.message, "error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerText = "Continue with Email";
  }
}

function handleSignOut() {
  localStorage.removeItem("pathora_user");
  state.user = {
    uid: "guest_demo_user",
    email: "guest@pathora.ai",
    displayName: "Guest Scholar",
    token: "demo_token_guest",
    isGuest: true
  };
  updateNavAuthUI();
  showToast("You have been signed out.", "info");
  loadSavedAndApplications();
}

// --- Candidate Profile Management ---
function initProfile() {
  const storedProfile = localStorage.getItem("pathora_profile");
  if (storedProfile) {
    try {
      state.profile = { ...state.profile, ...JSON.parse(storedProfile) };
    } catch (e) {
      console.error("Profile parse failed", e);
    }
  }
  populateProfileForm();
}

function populateProfileForm() {
  const p = state.profile;
  const nameEl = document.getElementById("profile-name");
  const eduEl = document.getElementById("profile-education");
  const fieldEl = document.getElementById("profile-field");
  const countryEl = document.getElementById("profile-country");
  const skillsEl = document.getElementById("profile-skills");
  const interestsEl = document.getElementById("profile-interests");
  const expEl = document.getElementById("profile-experience");
  const workEl = document.getElementById("profile-work-pref");
  const goalsEl = document.getElementById("profile-goals");

  if (nameEl) nameEl.value = p.displayName || "";
  if (eduEl) eduEl.value = p.educationLevel || "Undergraduate";
  if (fieldEl) fieldEl.value = p.fieldOfStudy || "";
  if (countryEl) countryEl.value = p.country || "";
  if (skillsEl) skillsEl.value = Array.isArray(p.skills) ? p.skills.join(", ") : (p.skills || "");
  if (interestsEl) interestsEl.value = Array.isArray(p.interests) ? p.interests.join(", ") : (p.interests || "");
  if (expEl) expEl.value = p.experienceLevel || "Beginner / No Experience";
  if (workEl) workEl.value = p.workPreference || "Any";
  if (goalsEl) goalsEl.value = p.careerGoals || "";
}

function openProfileModal() {
  populateProfileForm();
  const modal = document.getElementById("profile-modal");
  if (modal) modal.classList.add("open");
}

function closeProfileModal() {
  const modal = document.getElementById("profile-modal");
  if (modal) modal.classList.remove("open");
}

async function handleSaveProfile(event) {
  event.preventDefault();
  const skillsRaw = document.getElementById("profile-skills").value;
  const interestsRaw = document.getElementById("profile-interests").value;

  const newProfile = {
    displayName: document.getElementById("profile-name").value.trim() || "Candidate",
    educationLevel: document.getElementById("profile-education").value,
    fieldOfStudy: document.getElementById("profile-field").value.trim(),
    country: document.getElementById("profile-country").value.trim(),
    skills: skillsRaw.split(",").map(s => s.trim()).filter(Boolean),
    interests: interestsRaw.split(",").map(i => i.trim()).filter(Boolean),
    experienceLevel: document.getElementById("profile-experience").value,
    workPreference: document.getElementById("profile-work-pref").value,
    careerGoals: document.getElementById("profile-goals").value.trim()
  };

  state.profile = newProfile;
  localStorage.setItem("pathora_profile", JSON.stringify(newProfile));

  // Sync to backend if authenticated
  try {
    const headers = { "Content-Type": "application/json" };
    if (state.user && state.user.token) {
      headers["Authorization"] = `Bearer ${state.user.token}`;
    }
    await fetch("/api/profile", {
      method: "PUT",
      headers: headers,
      body: JSON.stringify(newProfile)
    });
  } catch (err) {
    console.warn("Could not sync profile to backend:", err);
  }

  updateNavAuthUI();
  closeProfileModal();
  showToast("Profile saved! Recalculating match scores...", "success");

  // Re-score visible opportunities against updated profile
  recalculateAllMatchScores();
  applyFilters();
}

async function fetchProfile() {
  if (!state.user || !state.user.token) return;
  try {
    const res = await fetch("/api/profile", {
      headers: { "Authorization": `Bearer ${state.user.token}` }
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.profile) {
        state.profile = { ...state.profile, ...data.profile };
        localStorage.setItem("pathora_profile", JSON.stringify(state.profile));
        populateProfileForm();
      }
    }
  } catch (err) {
    console.warn("fetchProfile error:", err);
  }
}

// --- Live Opportunity Search & Directory (TapRefer Style) ---
function initUrlParameters() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");
  const category = params.get("category");

  if (q) {
    const searchInput = document.getElementById("workspace-search-input");
    if (searchInput) searchInput.value = q;
  }

  if (category) {
    const checkboxes = document.querySelectorAll("input[name='filter-cat']");
    checkboxes.forEach(cb => {
      cb.checked = (cb.value.toLowerCase() === category.toLowerCase());
    });
  }
}

async function executeLiveSearch(forceRefresh = false) {
  const container = document.getElementById("opp-results-container");
  const searchInput = document.getElementById("workspace-search-input");
  const statusBadge = document.getElementById("live-search-status-badge");
  const countText = document.getElementById("results-count-text");

  if (!container) return; // Might be on a different page

  const query = searchInput ? searchInput.value.trim() : "";
  const location = document.getElementById("filter-location-input") ? document.getElementById("filter-location-input").value.trim() : "";
  const workMode = document.getElementById("filter-work-mode") ? document.getElementById("filter-work-mode").value : "";
  const education = document.getElementById("filter-education") ? document.getElementById("filter-education").value : "";

  // Selected categories
  const selectedCats = Array.from(document.querySelectorAll("input[name='filter-cat']:checked")).map(cb => cb.value);

  // Render skeleton loaders
  renderSkeletons(container, 4);
  if (countText) countText.innerText = "Querying live web search index...";

  const params = new URLSearchParams();
  if (query) params.append("q", query);
  if (location) params.append("location", location);
  if (workMode) params.append("work_mode", workMode);
  if (education) params.append("education", education);
  if (selectedCats.length > 0 && selectedCats.length < 6) {
    selectedCats.forEach(c => params.append("category", c));
  }
  if (forceRefresh) params.append("refresh", "true");

  state.isLoadingSearch = true;

  try {
    const response = await fetch(`/api/opportunities/search?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Search failed with status ${response.status}`);
    }
    const data = await response.json();

    // Store opportunities
    state.opportunities = data.opportunities || [];

    // Check status attribution
    if (statusBadge) {
      if (data.source_mode === "live_search") {
        statusBadge.innerHTML = `<i data-lucide="globe" style="width:12px;height:12px;"></i> Live Web Search (${data.provider || "Tavily"})`;
        statusBadge.className = "badge badge-success";
      } else {
        statusBadge.innerHTML = `<i data-lucide="database" style="width:12px;height:12px;"></i> Curated Seed Index (Demo Mode)`;
        statusBadge.className = "badge badge-mist";
      }
    }

    // Deterministically score each opportunity against user profile
    recalculateAllMatchScores();
    applyFilters();

  } catch (err) {
    console.error("Search error:", err);
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i data-lucide="alert-triangle" style="width:36px;height:36px; color:var(--color-crimson);"></i></div>
        <h3>Search Encountered an Error</h3>
        <p>${escapeHtml(err.message)}</p>
        <button class="btn btn-secondary btn-sm" onclick="executeLiveSearch(true)" style="margin-top:1rem;">
          Retry Search
        </button>
      </div>
    `;
    if (countText) countText.innerText = "Search error";
  } finally {
    state.isLoadingSearch = false;
    refreshIcons();
  }
}

// --- Deterministic Matching Engine ---
function calculateDeterministicMatch(opp, profile) {
  // Configurable Factor Weights: Total = 100
  // 1. Education (25 pts)
  // 2. Field of study & Skills (30 pts)
  // 3. Experience level (15 pts)
  // 4. Work Mode & Location (15 pts)
  // 5. Category Preference (15 pts)

  let score = 0;
  const factors = {
    education: { score: 0, max: 25, label: "Education" },
    skills: { score: 0, max: 30, label: "Field & Skills" },
    experience: { score: 0, max: 15, label: "Experience" },
    workMode: { score: 0, max: 15, label: "Location & Mode" },
    category: { score: 0, max: 15, label: "Opportunity Type" }
  };

  const missingInfo = [];
  const positiveNotes = [];
  const cautionNotes = [];

  const oppText = `${opp.title || ""} ${opp.description || ""} ${opp.educationRequirements || ""} ${opp.experienceRequirements || ""}`.toLowerCase();

  // 1. Education evaluation
  if (!profile.educationLevel) {
    missingInfo.push("Your education level is not specified in profile.");
  } else {
    const userEdu = profile.educationLevel.toLowerCase();
    const reqEdu = (opp.educationRequirements || "").toLowerCase();

    if (!reqEdu || reqEdu.includes("open") || reqEdu.includes("any") || reqEdu.includes("unspecified")) {
      factors.education.score = 20;
      positiveNotes.push("Open / flexible education requirements.");
    } else if (oppText.includes("undergraduate") || oppText.includes("bachelor") || oppText.includes("college student")) {
      if (userEdu.includes("undergraduate") || userEdu.includes("recent graduate")) {
        factors.education.score = 25;
        positiveNotes.push("Matches undergraduate/bachelor candidate status.");
      } else {
        factors.education.score = 10;
        cautionNotes.push(`Listing specifically references undergraduate students (Your profile: ${profile.educationLevel}).`);
      }
    } else if (oppText.includes("phd") || oppText.includes("postdoc")) {
      if (userEdu.includes("phd")) {
        factors.education.score = 25;
        positiveNotes.push("Matches doctoral level requirement.");
      } else {
        factors.education.score = 0;
        cautionNotes.push("Listing may require PhD/Doctorate level research qualifications.");
      }
    } else {
      factors.education.score = 18;
    }
  }

  // 2. Field of study & Skills evaluation
  const userSkills = Array.isArray(profile.skills) ? profile.skills : [];
  const userField = profile.fieldOfStudy ? profile.fieldOfStudy.toLowerCase() : "";
  let matchedSkillsCount = 0;
  const matchedSkillNames = [];

  if (userField && oppText.includes(userField)) {
    matchedSkillsCount += 2;
    positiveNotes.push(`Field of study (${profile.fieldOfStudy}) matches listing focus.`);
  }

  userSkills.forEach(skill => {
    const s = skill.trim().toLowerCase();
    if (s && s.length > 2 && oppText.includes(s)) {
      matchedSkillsCount++;
      matchedSkillNames.push(skill);
    }
  });

  if (matchedSkillsCount >= 3) {
    factors.skills.score = 30;
    positiveNotes.push(`Strong skills alignment (${matchedSkillNames.slice(0, 3).join(", ")}).`);
  } else if (matchedSkillsCount === 2) {
    factors.skills.score = 22;
    positiveNotes.push(`Good overlap with required skills (${matchedSkillNames.join(", ")}).`);
  } else if (matchedSkillsCount === 1) {
    factors.skills.score = 15;
    positiveNotes.push(`Partial skill match found (${matchedSkillNames[0]}).`);
  } else {
    factors.skills.score = 6;
    if (userSkills.length === 0) {
      missingInfo.push("No skills listed on your profile to verify alignment.");
    } else {
      cautionNotes.push("No explicit keyword match between your profile skills and listing excerpt.");
    }
  }

  // 3. Experience level evaluation
  const userExp = (profile.experienceLevel || "").toLowerCase();
  if (opp.category === "Internship" || opp.category === "Training Program" || opp.category === "Scholarship") {
    factors.experience.score = 15;
    positiveNotes.push("Opportunity is designed for early-career/student applicants.");
  } else if (oppText.includes("senior") || oppText.includes("5+ years") || oppText.includes("lead")) {
    factors.experience.score = 2;
    cautionNotes.push("Listing indicates requirements for senior/experienced roles.");
  } else {
    factors.experience.score = 12;
  }

  // 4. Work Mode & Location
  const userMode = profile.workPreference || "Any";
  const oppMode = opp.workMode || "Unspecified";

  if (userMode === "Any" || oppMode.toLowerCase() === "remote") {
    factors.workMode.score = 15;
    if (oppMode.toLowerCase() === "remote") {
      positiveNotes.push("Remote opportunity matches flexible work preference.");
    }
  } else if (userMode.toLowerCase() === oppMode.toLowerCase()) {
    factors.workMode.score = 15;
    positiveNotes.push(`Work mode (${oppMode}) matches your preference.`);
  } else {
    factors.workMode.score = 8;
    cautionNotes.push(`Work mode is ${oppMode}; your preference is ${userMode}.`);
  }

  // 5. Category Preference
  const preferredCats = profile.preferredOpportunityTypes || [];
  if (preferredCats.length === 0 || preferredCats.includes(opp.category)) {
    factors.category.score = 15;
  } else {
    factors.category.score = 6;
  }

  // Compute final score
  score = factors.education.score + factors.skills.score + factors.experience.score + factors.workMode.score + factors.category.score;
  score = Math.min(100, Math.max(0, score));

  // Determine classification
  let classification = "Likely match";
  let pillClass = "match-high";

  if (missingInfo.length > 0 && score < 70) {
    classification = "Insufficient information";
    pillClass = "match-uncertain";
  } else if (score >= 75) {
    classification = "Likely match";
    pillClass = "match-high";
  } else if (score >= 50) {
    classification = "Partial match";
    pillClass = "match-partial";
  } else {
    classification = "Likely ineligible";
    pillClass = "match-low";
  }

  return {
    score,
    classification,
    pillClass,
    factors,
    positiveNotes,
    missingInfo,
    cautionNotes
  };
}

function recalculateAllMatchScores() {
  state.opportunities.forEach(opp => {
    opp.matchAnalysis = calculateDeterministicMatch(opp, state.profile);
    opp.matchScore = opp.matchAnalysis.score;
  });
}

// --- Filters & Sorting ---
function applyFilters() {
  const container = document.getElementById("opp-results-container");
  const countText = document.getElementById("results-count-text");
  const chipsContainer = document.getElementById("active-filter-chips");
  const minScore = parseInt(document.getElementById("filter-match-slider") ? document.getElementById("filter-match-slider").value : "0", 10);
  const workMode = document.getElementById("filter-work-mode") ? document.getElementById("filter-work-mode").value : "";
  const education = document.getElementById("filter-education") ? document.getElementById("filter-education").value : "";
  const selectedCats = Array.from(document.querySelectorAll("input[name='filter-cat']:checked")).map(cb => cb.value);

  const activeChips = [];
  if (workMode) activeChips.push({ label: workMode, type: "workMode" });
  if (education) activeChips.push({ label: education, type: "education" });
  if (minScore > 0) activeChips.push({ label: `Match ≥ ${minScore}%`, type: "score" });

  if (chipsContainer) {
    chipsContainer.innerHTML = activeChips.map(chip => `
      <span class="filter-chip">
        ${escapeHtml(chip.label)}
      </span>
    `).join("");
  }

  state.filteredOpportunities = state.opportunities.filter(opp => {
    // Category filter
    if (selectedCats.length > 0 && !selectedCats.includes(opp.category)) {
      return false;
    }
    // Work mode filter
    if (workMode && opp.workMode && opp.workMode.toLowerCase() !== workMode.toLowerCase()) {
      return false;
    }
    // Education filter
    if (education && opp.educationRequirements) {
      if (!opp.educationRequirements.toLowerCase().includes(education.toLowerCase()) &&
        !opp.educationRequirements.toLowerCase().includes("any") &&
        !opp.educationRequirements.toLowerCase().includes("open")) {
        return false;
      }
    }
    // Min score filter
    if (opp.matchScore < minScore) {
      return false;
    }
    return true;
  });

  applySorting();
}

function applySorting() {
  const sortVal = document.getElementById("sort-select") ? document.getElementById("sort-select").value : "match-desc";
  const container = document.getElementById("opp-results-container");
  const countText = document.getElementById("results-count-text");

  if (!container) return;

  state.filteredOpportunities.sort((a, b) => {
    if (sortVal === "match-desc") {
      return (b.matchScore || 0) - (a.matchScore || 0);
    } else if (sortVal === "title-asc") {
      return (a.title || "").localeCompare(b.title || "");
    } else if (sortVal === "newest") {
      return new Date(b.lastCheckedAt || 0) - new Date(a.lastCheckedAt || 0);
    }
    return 0;
  });

  if (countText) {
    countText.innerText = `${state.filteredOpportunities.length} opportunities discovered`;
  }

  renderOpportunitiesList(container, state.filteredOpportunities);
}

function resetFilters() {
  const checkboxes = document.querySelectorAll("input[name='filter-cat']");
  checkboxes.forEach(cb => cb.checked = true);

  if (document.getElementById("filter-work-mode")) document.getElementById("filter-work-mode").value = "";
  if (document.getElementById("filter-education")) document.getElementById("filter-education").value = "";
  if (document.getElementById("filter-location-input")) document.getElementById("filter-location-input").value = "";
  if (document.getElementById("filter-match-slider")) {
    document.getElementById("filter-match-slider").value = "0";
    document.getElementById("filter-match-val").innerText = "0%";
  }
  applyFilters();
  showToast("Filters reset to default", "info");
}

// --- Card Rendering ---
function renderOpportunitiesList(container, items) {
  if (!items || items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i data-lucide="search-x" style="width:36px;height:36px;"></i></div>
        <h3>No Opportunities Found</h3>
        <p>No listings match your current search query or filter thresholds.</p>
        <button class="btn btn-secondary btn-sm" onclick="resetFilters()" style="margin-top:1rem;">
          Reset Filters & Query
        </button>
      </div>
    `;
    refreshIcons();
    return;
  }

  container.innerHTML = items.map(opp => renderOpportunityCardHtml(opp)).join("");
  refreshIcons();
}

function renderOpportunityCardHtml(opp) {
  const isSaved = state.savedOpportunities.has(opp.id);
  const match = opp.matchAnalysis || calculateDeterministicMatch(opp, state.profile);

  // Format deadline honestly
  let deadlineBadge = `<span class="badge badge-mist"><i data-lucide="help-circle" style="width:11px;height:11px;"></i> Check official source</span>`;
  if (opp.deadline && opp.deadline.toLowerCase() !== "unknown") {
    deadlineBadge = `<span class="badge badge-amber"><i data-lucide="clock" style="width:11px;height:11px;"></i> ${escapeHtml(opp.deadline)}</span>`;
  }

  // Work mode badge
  let modeBadge = `<span class="badge badge-mist">${escapeHtml(opp.workMode || "Flexible")}</span>`;
  if (opp.workMode && opp.workMode.toLowerCase() === "remote") {
    modeBadge = `<span class="badge badge-blue"><i data-lucide="globe" style="width:11px;height:11px;"></i> Remote</span>`;
  } else if (opp.workMode && opp.workMode.toLowerCase() === "hybrid") {
    modeBadge = `<span class="badge badge-mist">Hybrid</span>`;
  }

  // Funding / Perk tag (TapRefer dollar/perk style)
  let fundingTag = `<span class="badge badge-green"><i data-lucide="dollar-sign" style="width:11px;height:11px;"></i> Stipend / Funding Available</span>`;
  if (opp.category === "Scholarship") {
    fundingTag = `<span class="badge badge-green"><i data-lucide="award" style="width:11px;height:11px;"></i> Full / Partial Tuition Grant</span>`;
  }

  const domain = extractDomain(opp.officialUrl || opp.sourceUrl);
  const orgInitials = (opp.organization || "O").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();

  return `
    <article class="opp-card" id="card-${escapeHtml(opp.id)}">
      <div class="opp-card-top-row">
        <div class="opp-card-left">
          <div class="opp-avatar">${escapeHtml(orgInitials)}</div>
          <div class="opp-titles-box">
            <span class="opp-meta-org">${escapeHtml(opp.organization || "Organization")}</span>
            <h2 class="opp-title">
              <a href="javascript:void(0)" onclick="openOppModal('${escapeHtml(opp.id)}')" class="opp-title-link">
                ${escapeHtml(opp.title)}
              </a>
            </h2>
          </div>
        </div>

        <button class="btn btn-secondary btn-sm" onclick="openOppModal('${escapeHtml(opp.id)}')" title="View complete details">
          <span>Details</span>
          <i data-lucide="chevron-right" style="width:14px;height:14px;"></i>
        </button>
      </div>

      <div class="opp-badges-row">
        ${fundingTag}
        <span class="badge badge-crimson">${escapeHtml(opp.category || "General")}</span>
        ${modeBadge}
        ${deadlineBadge}
        <div class="match-score-pill ${match.pillClass}" title="${escapeHtml(match.classification)}">
          ${match.score}% Match
        </div>
      </div>

      <p class="opp-description">
        ${escapeHtml(opp.description || "Detailed requirements and application guidelines are available through the official portal.")}
      </p>

      <div class="opp-card-footer">
        <div class="opp-source-info">
          <a href="${escapeHtml(opp.officialUrl || opp.sourceUrl)}" target="_blank" rel="noopener noreferrer" class="source-link-tag" title="Visit verified official site">
            <i data-lucide="external-link" style="width:12px;height:12px;"></i>
            <span>${escapeHtml(domain)}</span>
          </a>
          <span>•</span>
          <span style="font-size:0.78rem; color:var(--text-dim);">
            ${escapeHtml(opp.sourceType === "official" ? "Authoritative Source" : "Public Web Index")}
          </span>
        </div>

        <div class="opp-actions">
          <button class="btn btn-ghost btn-sm btn-icon-only" onclick="toggleSaveOpportunity('${escapeHtml(opp.id)}')" title="${isSaved ? 'Remove from Bookmarks' : 'Bookmark Opportunity'}">
            <i data-lucide="${isSaved ? 'bookmark-check' : 'bookmark'}" style="width:16px;height:16px; color:${isSaved ? 'var(--color-crimson-bright)' : 'var(--text-muted)'};"></i>
          </button>
          
          <button class="btn btn-secondary btn-sm" onclick="openTrackerModal('${escapeHtml(opp.id)}')">
            <i data-lucide="plus-circle" style="width:14px;height:14px;"></i>
            <span>Track</span>
          </button>

          <a href="${escapeHtml(opp.officialUrl || opp.sourceUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">
            <span>Apply Now</span>
            <i data-lucide="external-link" style="width:12px;height:12px;"></i>
          </a>
        </div>
      </div>
    </article>
  `;
}

function renderSkeletons(container, count = 3) {
  let html = "";
  for (let i = 0; i < count; i++) {
    html += `
      <div class="opp-card" style="opacity:0.7;">
        <div class="skeleton skeleton-title" style="width:40%;"></div>
        <div class="skeleton skeleton-title" style="width:75%;"></div>
        <div style="display:flex; gap:0.5rem; margin-bottom:0.75rem;">
          <div class="skeleton" style="height:20px; width:70px;"></div>
          <div class="skeleton" style="height:20px; width:90px;"></div>
        </div>
        <div class="skeleton skeleton-text" style="width:100%;"></div>
        <div class="skeleton skeleton-text" style="width:85%;"></div>
      </div>
    `;
  }
  container.innerHTML = html;
}

// --- Detail & AI Match Modal ---
async function openOppModal(oppId) {
  const opp = state.opportunities.find(o => o.id === oppId);
  if (!opp) return;

  state.selectedOpp = opp;

  const modal = document.getElementById("opp-detail-modal");
  const titleEl = document.getElementById("modal-opp-title");
  const orgEl = document.getElementById("modal-opp-org");
  const badgesEl = document.getElementById("modal-opp-badges");
  const descEl = document.getElementById("modal-opp-desc");
  const sourceBtn = document.getElementById("modal-source-btn");
  const saveBtn = document.getElementById("modal-save-btn");
  const scorePill = document.getElementById("modal-ai-score-pill");
  const insightsEl = document.getElementById("modal-ai-insights");
  const nextStepsEl = document.getElementById("modal-ai-next-steps-text");
  const checkedEl = document.getElementById("modal-opp-checked");

  titleEl.innerText = opp.title;
  orgEl.innerText = opp.organization || "Opportunity";
  descEl.innerText = opp.description || "No full description provided. Refer to official portal.";

  if (sourceBtn) {
    sourceBtn.href = opp.officialUrl || opp.sourceUrl;
  }

  if (checkedEl) {
    checkedEl.innerText = opp.lastCheckedAt ? `Indexed: ${new Date(opp.lastCheckedAt).toLocaleDateString()}` : "Live Web Result";
  }

  // Populate badges
  badgesEl.innerHTML = `
    <span class="badge badge-crimson">${escapeHtml(opp.category)}</span>
    <span class="badge badge-mist">${escapeHtml(opp.workMode || "Location flexible")}</span>
    <span class="badge badge-mist">${escapeHtml(opp.location || "Global / Unrestricted")}</span>
    ${opp.deadline && opp.deadline.toLowerCase() !== "unknown" ? `<span class="badge badge-warning">Deadline: ${escapeHtml(opp.deadline)}</span>` : '<span class="badge badge-mist">Deadline: Check Source</span>'}
  `;

  // Update save button state
  const isSaved = state.savedOpportunities.has(opp.id);
  if (saveBtn) {
    saveBtn.innerHTML = `<i data-lucide="${isSaved ? 'bookmark-check' : 'bookmark'}" style="width:15px;height:15px;"></i> ${isSaved ? 'Saved' : 'Save Opportunity'}`;
  }

  // Deterministic local match
  const match = opp.matchAnalysis || calculateDeterministicMatch(opp, state.profile);
  scorePill.className = `match-score-pill ${match.pillClass}`;
  scorePill.innerText = `${match.score}% • ${match.classification}`;

  // Animate the actual score progress bar
  const progressBar = document.getElementById("modal-ai-progress-bar");
  if (progressBar) {
    progressBar.style.width = "0%";
    if (match.score >= 75) {
      progressBar.style.backgroundColor = "var(--tag-green-text)";
    } else if (match.score >= 50) {
      progressBar.style.backgroundColor = "var(--tag-amber-text)";
    } else {
      progressBar.style.backgroundColor = "var(--color-crimson-bright)";
    }
    setTimeout(() => {
      progressBar.style.width = `${Math.max(4, match.score)}%`;
    }, 60);
  }

  // Render initial deterministic insights
  renderMatchInsights(match, insightsEl, nextStepsEl);

  modal.classList.add("open");
  refreshIcons();

  // Call LLM endpoint for dynamic grounded reasoning if credentials exist
  try {
    const res = await fetch("/api/opportunities/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        opportunity: opp,
        profile: state.profile
      })
    });
    if (res.ok) {
      const analysisData = await res.json();
      if (analysisData.explanation) {
        // Render LLM enriched explanation
        insightsEl.innerHTML = `
          <div class="ai-insight-item positive">
            <i data-lucide="check-circle" style="width:16px;height:16px;"></i>
            <span>${escapeHtml(analysisData.explanation)}</span>
          </div>
          ${analysisData.concerns ? `
            <div class="ai-insight-item uncertain">
              <i data-lucide="alert-circle" style="width:16px;height:16px;"></i>
              <span>${escapeHtml(analysisData.concerns)}</span>
            </div>
          ` : ''}
        `;
        if (nextStepsEl && analysisData.recommended_steps) {
          nextStepsEl.innerText = analysisData.recommended_steps;
        }
        refreshIcons();
      }
    }
  } catch (e) {
    console.log("Using deterministic match fallback:", e);
  }
}

function renderMatchInsights(match, container, nextStepsEl) {
  let html = "";
  if (match.positiveNotes.length > 0) {
    match.positiveNotes.forEach(note => {
      html += `
        <div class="ai-insight-item positive">
          <i data-lucide="check-circle-2" style="width:15px;height:15px;"></i>
          <span>${escapeHtml(note)}</span>
        </div>
      `;
    });
  }
  if (match.missingInfo.length > 0) {
    match.missingInfo.forEach(info => {
      html += `
        <div class="ai-insight-item uncertain">
          <i data-lucide="help-circle" style="width:15px;height:15px;"></i>
          <span>${escapeHtml(info)}</span>
        </div>
      `;
    });
  }
  if (match.cautionNotes.length > 0) {
    match.cautionNotes.forEach(caution => {
      html += `
        <div class="ai-insight-item negative">
          <i data-lucide="alert-circle" style="width:15px;height:15px;"></i>
          <span>${escapeHtml(caution)}</span>
        </div>
      `;
    });
  }
  container.innerHTML = html || "<p style='font-size:0.85rem;'>Match criteria computed from your candidate profile.</p>";

  if (nextStepsEl) {
    if (match.score >= 75) {
      nextStepsEl.innerText = "Review the official application guidelines, customize your CV with matched skills, and submit early.";
    } else if (match.score >= 50) {
      nextStepsEl.innerText = "Confirm specific eligibility nuances on the official listing and clarify any uncertain qualifications.";
    } else {
      nextStepsEl.innerText = "Check whether prerequisite educational requirements or location boundaries fit before preparing an application.";
    }
  }
}

function closeOppModal() {
  const modal = document.getElementById("opp-detail-modal");
  if (modal) modal.classList.remove("open");
}

function handleModalSave() {
  if (state.selectedOpp) {
    toggleSaveOpportunity(state.selectedOpp.id);
    const isSaved = state.savedOpportunities.has(state.selectedOpp.id);
    const saveBtn = document.getElementById("modal-save-btn");
    if (saveBtn) {
      saveBtn.innerHTML = `<i data-lucide="${isSaved ? 'bookmark-check' : 'bookmark'}" style="width:15px;height:15px;"></i> ${isSaved ? 'Saved' : 'Save Opportunity'}`;
      refreshIcons();
    }
  }
}

function handleModalTrack() {
  if (state.selectedOpp) {
    closeOppModal();
    openTrackerModal(state.selectedOpp.id);
  }
}

// --- Bookmarking / Saved Opportunities ---
async function toggleSaveOpportunity(oppId) {
  const isSaved = state.savedOpportunities.has(oppId);
  const opp = state.opportunities.find(o => o.id === oppId);

  const headers = { "Content-Type": "application/json" };
  if (state.user && state.user.token) {
    headers["Authorization"] = `Bearer ${state.user.token}`;
  }

  if (isSaved) {
    // Unsave
    state.savedOpportunities.delete(oppId);
    try {
      await fetch(`/api/saved/${oppId}`, { method: "DELETE", headers });
    } catch (e) {
      console.warn("Backend unsave error", e);
    }
    showToast("Removed from saved opportunities", "info");
  } else {
    // Save
    if (opp) {
      state.savedOpportunities.set(oppId, opp);
      try {
        await fetch("/api/saved", {
          method: "POST",
          headers,
          body: JSON.stringify({ opportunityId: oppId, opportunityData: opp })
        });
      } catch (e) {
        console.warn("Backend save error", e);
      }
      showToast("Opportunity saved to your bookmarks", "success");
    }
  }

  updateSavedCountBadge();
  applyFilters();
  renderSavedView();
}

function updateSavedCountBadge() {
  const badge = document.getElementById("saved-count-badge");
  if (badge) {
    const count = state.savedOpportunities.size;
    badge.innerText = count;
    badge.style.display = count > 0 ? "inline-flex" : "none";
  }
}

function renderSavedView() {
  const container = document.getElementById("saved-items-list");
  if (!container) return;

  const items = Array.from(state.savedOpportunities.values());
  if (items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i data-lucide="bookmark" style="width:36px;height:36px;"></i></div>
        <h3>No Saved Opportunities Yet</h3>
        <p>Click the bookmark icon on any opportunity card to save it for quick reference.</p>
        <button class="btn btn-primary btn-sm" onclick="switchAppTab('discover')" style="margin-top:1rem;">
          Discover Opportunities
        </button>
      </div>
    `;
    refreshIcons();
    return;
  }

  container.innerHTML = items.map(opp => renderOpportunityCardHtml(opp)).join("");
  refreshIcons();
}

// --- Application Tracker ---
function openTrackerModal(oppId) {
  const opp = state.opportunities.find(o => o.id === oppId) || state.savedOpportunities.get(oppId);
  if (!opp) return;

  const modal = document.getElementById("tracker-modal");
  document.getElementById("tracker-item-id").value = oppId;
  document.getElementById("tracker-opp-title").innerText = `${opp.organization} — ${opp.title}`;

  // Pre-fill existing record if available
  const existing = state.applications.get(oppId);
  if (existing) {
    document.getElementById("tracker-status-select").value = existing.status || "Interested";
    document.getElementById("tracker-app-date").value = existing.applicationDate || "";
    document.getElementById("tracker-notes").value = existing.notes || "";
  } else {
    document.getElementById("tracker-status-select").value = "Planning to Apply";
    document.getElementById("tracker-app-date").value = new Date().toISOString().split("T")[0];
    document.getElementById("tracker-notes").value = "";
  }

  modal.classList.add("open");
}

function closeTrackerModal() {
  const modal = document.getElementById("tracker-modal");
  if (modal) modal.classList.remove("open");
}

async function handleSaveTrackerRecord(event) {
  event.preventDefault();
  const oppId = document.getElementById("tracker-item-id").value;
  const status = document.getElementById("tracker-status-select").value;
  const appDate = document.getElementById("tracker-app-date").value;
  const notes = document.getElementById("tracker-notes").value.trim();

  const opp = state.opportunities.find(o => o.id === oppId) || state.savedOpportunities.get(oppId);
  const record = {
    opportunityId: oppId,
    status: status,
    applicationDate: appDate,
    notes: notes,
    opportunityData: opp || { title: "Tracked Opportunity", organization: "Organization" }
  };

  state.applications.set(oppId, record);

  const headers = { "Content-Type": "application/json" };
  if (state.user && state.user.token) {
    headers["Authorization"] = `Bearer ${state.user.token}`;
  }

  try {
    await fetch("/api/applications", {
      method: "POST",
      headers,
      body: JSON.stringify(record)
    });
  } catch (e) {
    console.warn("Backend application save error", e);
  }

  closeTrackerModal();
  showToast(`Application record updated: ${status}`, "success");
  updateTrackerStats();
  renderTrackerView();
}

async function deleteTrackerRecord(oppId) {
  state.applications.delete(oppId);

  const headers = {};
  if (state.user && state.user.token) {
    headers["Authorization"] = `Bearer ${state.user.token}`;
  }

  try {
    await fetch(`/api/applications/${oppId}`, { method: "DELETE", headers });
  } catch (e) {
    console.warn("Backend delete tracker record error", e);
  }

  showToast("Application tracker item removed", "info");
  updateTrackerStats();
  renderTrackerView();
}

function updateTrackerStats() {
  const items = Array.from(state.applications.values());
  const counts = {
    total: items.length,
    interested: items.filter(i => i.status === "Interested" || i.status === "Planning to Apply").length,
    applied: items.filter(i => i.status === "Applied").length,
    interview: items.filter(i => i.status === "Interview").length,
    accepted: items.filter(i => i.status === "Accepted").length
  };

  if (document.getElementById("stat-total")) document.getElementById("stat-total").innerText = counts.total;
  if (document.getElementById("stat-interested")) document.getElementById("stat-interested").innerText = counts.interested;
  if (document.getElementById("stat-applied")) document.getElementById("stat-applied").innerText = counts.applied;
  if (document.getElementById("stat-interview")) document.getElementById("stat-interview").innerText = counts.interview;
  if (document.getElementById("stat-accepted")) document.getElementById("stat-accepted").innerText = counts.accepted;

  const countBadge = document.getElementById("tracker-count-badge");
  if (countBadge) {
    countBadge.innerText = counts.total;
    countBadge.style.display = counts.total > 0 ? "inline-flex" : "none";
  }
}

function filterTracker(status, btn) {
  state.activeFilterTracker = status;
  document.querySelectorAll(".tracker-filter-btn").forEach(b => {
    b.classList.remove("btn-dark");
    b.classList.add("btn-ghost");
  });
  if (btn) {
    btn.classList.add("btn-dark");
    btn.classList.remove("btn-ghost");
  }
  renderTrackerView();
}

function renderTrackerView() {
  const container = document.getElementById("tracker-items-list");
  if (!container) return;

  let items = Array.from(state.applications.values());
  if (state.activeFilterTracker !== "ALL") {
    items = items.filter(i => i.status === state.activeFilterTracker);
  }

  if (items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon"><i data-lucide="clipboard-list" style="width:36px;height:36px;"></i></div>
        <h3>No Tracked Applications</h3>
        <p>Start tracking by clicking "Track" on any opportunity in the Discover tab.</p>
        <button class="btn btn-primary btn-sm" onclick="switchAppTab('discover')" style="margin-top:1rem;">
          Find Opportunities
        </button>
      </div>
    `;
    refreshIcons();
    return;
  }

  container.innerHTML = items.map(item => {
    const opp = item.opportunityData || {};
    let statusClass = "badge-mist";
    if (item.status === "Applied") statusClass = "badge-info";
    if (item.status === "Interview") statusClass = "badge-warning";
    if (item.status === "Accepted") statusClass = "badge-success";
    if (item.status === "Rejected") statusClass = "badge-crimson";

    return `
      <div class="opp-card">
        <div class="opp-card-header">
          <div>
            <span class="opp-meta-org">${escapeHtml(opp.organization || "Organization")}</span>
            <h3 class="opp-title">${escapeHtml(opp.title || "Tracked Opportunity")}</h3>
          </div>
          <span class="badge ${statusClass}" style="font-size:0.82rem; padding:0.35rem 0.75rem;">
            ${escapeHtml(item.status)}
          </span>
        </div>

        ${item.notes ? `
          <div style="background:var(--color-mist-light); padding:0.6rem 0.85rem; border-radius:var(--radius-xs); border:1px solid var(--color-border); font-size:0.87rem; color:var(--color-graphite-light);">
            <strong>Notes:</strong> ${escapeHtml(item.notes)}
          </div>
        ` : ''}

        <div class="opp-card-footer">
          <div style="font-size:0.82rem; color:var(--color-text-muted);">
            ${item.applicationDate ? `<span>Date: ${escapeHtml(item.applicationDate)}</span> • ` : ''}
            <a href="${escapeHtml(opp.officialUrl || opp.sourceUrl || '#')}" target="_blank" rel="noopener noreferrer" class="source-link-tag">
              Official Site <i data-lucide="external-link" style="width:11px;height:11px;"></i>
            </a>
          </div>

          <div class="opp-actions">
            <button class="btn btn-secondary btn-sm" onclick="openTrackerModal('${escapeHtml(item.opportunityId)}')">
              <i data-lucide="edit-3" style="width:14px;height:14px;"></i> Update
            </button>
            <button class="btn btn-ghost btn-sm btn-icon-only" onclick="deleteTrackerRecord('${escapeHtml(item.opportunityId)}')" title="Remove from tracker">
              <i data-lucide="trash-2" style="width:15px;height:15px; color:var(--color-crimson);"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");

  refreshIcons();
}

async function loadSavedAndApplications() {
  const headers = {};
  if (state.user && state.user.token) {
    headers["Authorization"] = `Bearer ${state.user.token}`;
  }

  try {
    // Load saved
    const savedRes = await fetch("/api/saved", { headers });
    if (savedRes.ok) {
      const data = await savedRes.json();
      if (Array.isArray(data.saved)) {
        state.savedOpportunities.clear();
        data.saved.forEach(item => {
          if (item.opportunityData) {
            state.savedOpportunities.set(item.opportunityId, item.opportunityData);
          }
        });
        updateSavedCountBadge();
      }
    }

    // Load applications
    const appRes = await fetch("/api/applications", { headers });
    if (appRes.ok) {
      const data = await appRes.json();
      if (Array.isArray(data.applications)) {
        state.applications.clear();
        data.applications.forEach(app => {
          state.applications.set(app.opportunityId, app);
        });
        updateTrackerStats();
      }
    }
  } catch (e) {
    console.warn("Error loading persistent saved/tracker data:", e);
  }
}

// --- Workspace Tab Switcher ---
function switchAppTab(tab) {
  state.activeTab = tab;
  const viewDiscover = document.getElementById("view-discover");
  const viewTracker = document.getElementById("view-tracker");
  const viewSaved = document.getElementById("view-saved");

  const btnDiscover = document.getElementById("tab-btn-discover");
  const btnTracker = document.getElementById("tab-btn-tracker");
  const btnSaved = document.getElementById("tab-btn-saved");

  if (!viewDiscover || !viewTracker || !viewSaved) return;

  // Reset tab button styling
  [btnDiscover, btnTracker, btnSaved].forEach(b => {
    if (b) {
      b.classList.remove("btn-dark");
      b.classList.add("btn-ghost");
      b.setAttribute("aria-selected", "false");
    }
  });

  // Hide all views
  viewDiscover.style.display = "none";
  viewTracker.style.display = "none";
  viewSaved.style.display = "none";

  if (tab === "discover") {
    viewDiscover.style.display = "block";
    btnDiscover.classList.add("btn-dark");
    btnDiscover.classList.remove("btn-ghost");
    btnDiscover.setAttribute("aria-selected", "true");
  } else if (tab === "tracker") {
    viewTracker.style.display = "block";
    btnTracker.classList.add("btn-dark");
    btnTracker.classList.remove("btn-ghost");
    btnTracker.setAttribute("aria-selected", "true");
    renderTrackerView();
  } else if (tab === "saved") {
    viewSaved.style.display = "block";
    btnSaved.classList.add("btn-dark");
    btnSaved.classList.remove("btn-ghost");
    btnSaved.setAttribute("aria-selected", "true");
    renderSavedView();
  }

  window.location.hash = tab;
  refreshIcons();
}

// --- Responsive Drawers & Mobile Nav ---
function toggleMobileNav(forceState) {
  const menu = document.getElementById("mobile-nav-menu");
  const backdrop = document.getElementById("mobile-nav-backdrop");
  const toggleBtn = document.getElementById("mobile-nav-toggle-btn") || document.querySelector(".mobile-nav-toggle");
  if (!menu) return;

  const willOpen = typeof forceState === "boolean" ? forceState : !menu.classList.contains("open");
  
  if (willOpen) {
    menu.classList.add("open");
    if (backdrop) backdrop.classList.add("active");
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "true");
      toggleBtn.innerHTML = '<i data-lucide="x" style="width:20px;height:20px;"></i>';
    }
  } else {
    menu.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "false");
      toggleBtn.innerHTML = '<i data-lucide="menu" style="width:20px;height:20px;"></i>';
    }
  }
  refreshIcons();
}

function openFilterDrawer() {
  const sidebar = document.getElementById("filter-sidebar");
  const backdrop = document.getElementById("filter-drawer-backdrop");
  const closeBtn = document.getElementById("mobile-filter-close-btn");
  if (sidebar) {
    sidebar.classList.add("drawer-open");
    if (backdrop) backdrop.classList.add("active");
    if (closeBtn) closeBtn.style.display = "block";
    document.body.style.overflow = "hidden";
  }
}

function closeFilterDrawer() {
  const sidebar = document.getElementById("filter-sidebar");
  const backdrop = document.getElementById("filter-drawer-backdrop");
  const closeBtn = document.getElementById("mobile-filter-close-btn");
  if (sidebar) {
    sidebar.classList.remove("drawer-open");
    if (backdrop) backdrop.classList.remove("active");
    if (closeBtn) closeBtn.style.display = "none";
    document.body.style.overflow = "";
  }
}

// Global Keyboard Escape Handler
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const mobileMenu = document.getElementById("mobile-nav-menu");
    if (mobileMenu && mobileMenu.classList.contains("open")) {
      toggleMobileNav(false);
    }
    const filterSidebar = document.getElementById("filter-sidebar");
    if (filterSidebar && filterSidebar.classList.contains("drawer-open")) {
      closeFilterDrawer();
    }
    const oppModal = document.getElementById("opp-detail-modal");
    if (oppModal && oppModal.classList.contains("active")) {
      closeOppModal();
    }
    const trackerModal = document.getElementById("tracker-modal");
    if (trackerModal && trackerModal.classList.contains("active")) {
      closeTrackerModal();
    }
    const profileModal = document.getElementById("profile-modal");
    if (profileModal && profileModal.classList.contains("active")) {
      closeProfileModal();
    }
  }
});

// --- Toast System ---
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast`;

  let iconName = "info";
  if (type === "success") iconName = "check-circle";
  if (type === "error") iconName = "alert-circle";

  toast.innerHTML = `
    <i data-lucide="${iconName}" style="width:16px;height:16px; color:${type === 'error' ? 'var(--color-crimson)' : 'var(--color-white)'};"></i>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  refreshIcons();

  setTimeout(() => {
    toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// --- Utilities ---
function extractDomain(url) {
  if (!url) return "official-portal.org";
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "");
  } catch (e) {
    return url.slice(0, 30);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// --- Scroll-Triggered Reveal Animation (IntersectionObserver) ---
function initScrollReveal() {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }
  const elements = document.querySelectorAll('.reveal-on-scroll');
  if (!elements.length || !('IntersectionObserver' in window)) return;

  document.documentElement.classList.add('js-ready');
  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

  elements.forEach(el => observer.observe(el));
}
