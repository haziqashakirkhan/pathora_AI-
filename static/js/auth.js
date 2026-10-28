/**
 * Pathora AI — Firebase Authentication & Firestore Client Integration
 * Handles real Firebase Auth with email/password, session persistence, 
 * token management, and fallback in-memory simulation for guest/offline demo mode.
 */

const PathoraAuth = (function () {
  let isFirebaseConfigured = false;
  let authInstance = null;
  let dbInstance = null;
  let currentUser = null;
  let currentToken = null;
  const authStateListeners = [];

  // Local storage keys for session fallback
  const STORAGE_USER_KEY = "pathora_user_session";
  const STORAGE_TOKEN_KEY = "pathora_auth_token";
  const STORAGE_USERS_DB_KEY = "pathora_local_users";

  /**
   * Initializes Firebase from backend public configuration
   */
  async function init() {
    try {
      const res = await fetch("/api/firebase-config");
      if (res.ok) {
        const config = await res.json();
        if (config.configured && window.firebase && window.firebase.initializeApp) {
          try {
            if (!window.firebase.apps.length) {
              window.firebase.initializeApp({
                apiKey: config.apiKey,
                authDomain: config.authDomain,
                projectId: config.projectId,
                storageBucket: config.storageBucket,
                messagingSenderId: config.messagingSenderId,
                appId: config.appId
              });
            }
            authInstance = window.firebase.auth();
            dbInstance = window.firebase.firestore();
            isFirebaseConfigured = true;

            // Set up real Firebase auth state listener
            authInstance.onAuthStateChanged(async (firebaseUser) => {
              if (firebaseUser) {
                currentUser = {
                  uid: firebaseUser.uid,
                  email: firebaseUser.email,
                  displayName: firebaseUser.displayName || firebaseUser.email.split("@")[0]
                };
                try {
                  currentToken = await firebaseUser.getIdToken();
                } catch (e) {
                  currentToken = `bearer_firebase_usr_${firebaseUser.uid}`;
                }
                localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(currentUser));
                localStorage.setItem(STORAGE_TOKEN_KEY, currentToken);
              } else {
                currentUser = null;
                currentToken = null;
                localStorage.removeItem(STORAGE_USER_KEY);
                localStorage.removeItem(STORAGE_TOKEN_KEY);
              }
              notifyListeners(currentUser);
              updateGlobalNavAuth(currentUser);
            });

            console.log("Pathora AI: Real Firebase Authentication initialized successfully.");
            return;
          } catch (initErr) {
            console.warn("Pathora AI: Firebase initialization error, activating fallback demo auth:", initErr);
          }
        }
      }
    } catch (e) {
      console.warn("Pathora AI: Could not reach /api/firebase-config, falling back to local demo auth:", e);
    }

    // Fallback Local Demo Auth Mode
    isFirebaseConfigured = false;
    const storedUser = localStorage.getItem(STORAGE_USER_KEY);
    const storedToken = localStorage.getItem(STORAGE_TOKEN_KEY);
    if (storedUser && storedToken) {
      try {
        currentUser = JSON.parse(storedUser);
        currentToken = storedToken;
      } catch (e) {
        currentUser = null;
        currentToken = null;
      }
    }
    notifyListeners(currentUser);
    updateGlobalNavAuth(currentUser);
    console.log("Pathora AI: Demo Auth Mode active (Guest and local candidate simulation).");
  }

  function notifyListeners(user) {
    authStateListeners.forEach((fn) => {
      try { fn(user); } catch (e) { console.error("Auth listener error:", e); }
    });
  }

  /**
   * Registers a listener callback for auth state changes
   */
  function onAuthStateChanged(callback) {
    if (typeof callback === "function") {
      authStateListeners.push(callback);
      // Immediately call with current state
      callback(currentUser);
    }
  }

  /**
   * Signs up a new user with Email, Password, and Display Name
   */
  async function signUp(displayName, email, password) {
    displayName = (displayName || "").trim();
    email = (email || "").trim().toLowerCase();
    password = password || "";

    if (!displayName) throw new Error("Please enter your full name.");
    if (!email || !email.includes("@")) throw new Error("Please enter a valid email address.");
    if (password.length < 6) throw new Error("Password must be at least 6 characters.");

    if (isFirebaseConfigured && authInstance) {
      // Real Firebase Authentication
      const userCredential = await authInstance.createUserWithEmailAndPassword(email, password);
      const user = userCredential.user;

      // Update Display Name
      if (displayName && user.updateProfile) {
        await user.updateProfile({ displayName: displayName });
      }

      // Initial user profile in Firestore
      if (dbInstance) {
        try {
          await dbInstance.collection("users").doc(user.uid).set({
            displayName: displayName,
            email: email,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
          }, { merge: true });
        } catch (dbErr) {
          console.warn("Firestore profile creation warning:", dbErr);
        }
      }

      const token = await user.getIdToken();
      currentUser = { uid: user.uid, email: user.email, displayName: displayName };
      currentToken = token;
      localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(currentUser));
      localStorage.setItem(STORAGE_TOKEN_KEY, currentToken);
      notifyListeners(currentUser);
      updateGlobalNavAuth(currentUser);
      return currentUser;
    }

    // Local Demo / Offline Fallback Registration
    let users = [];
    try {
      users = JSON.parse(localStorage.getItem(STORAGE_USERS_DB_KEY) || "[]");
    } catch (e) {
      users = [];
    }

    if (users.find(u => u.email === email)) {
      throw new Error("An account with this email address already exists.");
    }

    const uid = "usr_" + Math.random().toString(36).substring(2, 10);
    const newUser = {
      uid: uid,
      displayName: displayName,
      email: email,
      passwordHash: btoa(password), // simple client hash for demo isolation
      createdAt: new Date().toISOString()
    };
    users.push(newUser);
    localStorage.setItem(STORAGE_USERS_DB_KEY, JSON.stringify(users));

    currentUser = { uid: uid, email: email, displayName: displayName };
    currentToken = `bearer_firebase_usr_${uid}`;
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(currentUser));
    localStorage.setItem(STORAGE_TOKEN_KEY, currentToken);
    notifyListeners(currentUser);
    updateGlobalNavAuth(currentUser);
    return currentUser;
  }

  /**
   * Signs in an existing user with Email and Password
   */
  async function signIn(email, password, rememberMe = true) {
    email = (email || "").trim().toLowerCase();
    password = password || "";

    if (!email || !email.includes("@")) throw new Error("Please enter your registered email address.");
    if (!password) throw new Error("Please enter your password.");

    if (isFirebaseConfigured && authInstance) {
      // Set persistence
      try {
        const persistence = rememberMe
          ? window.firebase.auth.Auth.Persistence.LOCAL
          : window.firebase.auth.Auth.Persistence.SESSION;
        await authInstance.setPersistence(persistence);
      } catch (pErr) {
        // Continue if persistence setting is not supported in current environment
      }

      const userCredential = await authInstance.signInWithEmailAndPassword(email, password);
      const user = userCredential.user;
      const token = await user.getIdToken();

      currentUser = {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName || user.email.split("@")[0]
      };
      currentToken = token;
      localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(currentUser));
      localStorage.setItem(STORAGE_TOKEN_KEY, currentToken);
      notifyListeners(currentUser);
      updateGlobalNavAuth(currentUser);
      return currentUser;
    }

    // Local Demo / Offline Fallback Authentication
    let users = [];
    try {
      users = JSON.parse(localStorage.getItem(STORAGE_USERS_DB_KEY) || "[]");
    } catch (e) {
      users = [];
    }

    // Check if user exists or support default demo accounts
    let match = users.find(u => u.email === email && u.passwordHash === btoa(password));
    if (!match) {
      // If no users registered yet, allow demo test accounts
      if (email.endsWith("@pathora.ai") || email === "demo@example.com") {
        match = {
          uid: "usr_demo_" + Math.random().toString(36).substring(2, 8),
          displayName: email.split("@")[0],
          email: email
        };
      } else {
        throw new Error("Invalid email or password. Please check your credentials.");
      }
    }

    currentUser = { uid: match.uid, email: match.email, displayName: match.displayName };
    currentToken = `bearer_firebase_usr_${match.uid}`;
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(currentUser));
    localStorage.setItem(STORAGE_TOKEN_KEY, currentToken);
    notifyListeners(currentUser);
    updateGlobalNavAuth(currentUser);
    return currentUser;
  }

  /**
   * Password Reset Flow
   */
  async function resetPassword(email) {
    email = (email || "").trim().toLowerCase();
    if (!email || !email.includes("@")) throw new Error("Please provide a valid email address.");

    if (isFirebaseConfigured && authInstance) {
      await authInstance.sendPasswordResetEmail(email);
      return true;
    }

    // Demo mode: simulate successful reset request safely
    await new Promise(r => setTimeout(r, 600));
    return true;
  }

  /**
   * Signs out the current active user
   */
  async function signOut() {
    if (isFirebaseConfigured && authInstance) {
      try {
        await authInstance.signOut();
      } catch (e) {
        console.warn("Firebase sign out error:", e);
      }
    }
    currentUser = null;
    currentToken = null;
    localStorage.removeItem(STORAGE_USER_KEY);
    localStorage.removeItem(STORAGE_TOKEN_KEY);
    notifyListeners(null);
    updateGlobalNavAuth(null);
  }

  /**
   * Returns current active user object
   */
  function getUser() {
    return currentUser;
  }

  /**
   * Returns current authentication token
   */
  function getToken() {
    return currentToken || localStorage.getItem(STORAGE_TOKEN_KEY) || "demo_token_guest";
  }

  function isConfigured() {
    return isFirebaseConfigured;
  }

  return {
    init,
    onAuthStateChanged,
    signUp,
    signIn,
    resetPassword,
    signOut,
    getUser,
    getToken,
    isConfigured
  };
})();

/**
 * Updates desktop and mobile navigation header state
 */
function updateGlobalNavAuth(user) {
  const authGroup = document.getElementById("nav-auth-group");
  const guestGroup = document.getElementById("nav-guest-group");
  const profileLabel = document.getElementById("nav-profile-label");
  const mobileAuthLinks = document.getElementById("mobile-auth-links");
  const mobileFooterGuest = document.getElementById("mobile-auth-footer-guest");
  const mobileFooterUser = document.getElementById("mobile-auth-footer-user");

  if (user) {
    // Authenticated State
    if (authGroup) authGroup.style.display = "flex";
    if (guestGroup) guestGroup.style.display = "none";
    if (profileLabel) {
      profileLabel.innerText = user.displayName ? user.displayName.split(" ")[0] : "Profile";
    }
    if (mobileAuthLinks) mobileAuthLinks.style.display = "flex";
    if (mobileFooterGuest) mobileFooterGuest.style.display = "none";
    if (mobileFooterUser) mobileFooterUser.style.display = "flex";
  } else {
    // Unauthenticated / Guest State
    if (authGroup) authGroup.style.display = "none";
    if (guestGroup) guestGroup.style.display = "flex";
    if (profileLabel) profileLabel.innerText = "Profile";
    if (mobileAuthLinks) mobileAuthLinks.style.display = "none";
    if (mobileFooterGuest) mobileFooterGuest.style.display = "flex";
    if (mobileFooterUser) mobileFooterUser.style.display = "none";
  }

  if (window.lucide && window.lucide.createIcons) {
    window.lucide.createIcons();
  }
}

// --- Form Event Handlers for /signup and /login ---

function togglePasswordVisibility(fieldId, btn) {
  const input = document.getElementById(fieldId);
  if (!input) return;
  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  if (btn) {
    btn.innerHTML = `<i data-lucide="${isPassword ? 'eye-off' : 'eye'}" style="width:16px;height:16px;"></i>`;
    if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
  }
}

function toggleForgotPasswordView(show) {
  const pane = document.getElementById("reset-password-pane");
  if (pane) {
    pane.style.display = show ? "block" : "none";
  }
}

async function handleSignupSubmit(event) {
  event.preventDefault();
  const alertEl = document.getElementById("signup-alert");
  const submitBtn = document.getElementById("signup-submit-btn");
  const btnText = document.getElementById("signup-btn-text");

  const name = document.getElementById("signup-name").value.trim();
  const email = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  const confirmPassword = document.getElementById("signup-confirm-password").value;

  if (alertEl) {
    alertEl.style.display = "none";
    alertEl.className = "auth-alert";
  }

  if (!name) {
    showAuthAlert(alertEl, "Please enter your full name.", "error");
    return;
  }
  if (!email || !email.includes("@")) {
    showAuthAlert(alertEl, "Please enter a valid email address.", "error");
    return;
  }
  if (password.length < 6) {
    showAuthAlert(alertEl, "Password must be at least 6 characters.", "error");
    return;
  }
  if (password !== confirmPassword) {
    showAuthAlert(alertEl, "Passwords do not match. Please re-enter.", "error");
    return;
  }

  // Loading state
  if (submitBtn) submitBtn.disabled = true;
  if (btnText) btnText.innerText = "Creating Account...";

  try {
    await PathoraAuth.signUp(name, email, password);
    showAuthAlert(alertEl, "Account created successfully! Redirecting to workspace...", "success");
    setTimeout(() => {
      window.location.href = "/app";
    }, 800);
  } catch (err) {
    showAuthAlert(alertEl, err.message || "Failed to create account. Please try again.", "error");
    if (submitBtn) submitBtn.disabled = false;
    if (btnText) btnText.innerText = "Create Account ✦";
  }
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  const alertEl = document.getElementById("login-alert");
  const submitBtn = document.getElementById("login-submit-btn");
  const btnText = document.getElementById("login-btn-text");

  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const remember = document.getElementById("login-remember") ? document.getElementById("login-remember").checked : true;

  if (alertEl) {
    alertEl.style.display = "none";
    alertEl.className = "auth-alert";
  }

  if (!email || !email.includes("@")) {
    showAuthAlert(alertEl, "Please enter your registered email address.", "error");
    return;
  }
  if (!password) {
    showAuthAlert(alertEl, "Please enter your password.", "error");
    return;
  }

  // Loading state
  if (submitBtn) submitBtn.disabled = true;
  if (btnText) btnText.innerText = "Signing In...";

  try {
    await PathoraAuth.signIn(email, password, remember);
    showAuthAlert(alertEl, "Signed in successfully! Redirecting to workspace...", "success");
    setTimeout(() => {
      window.location.href = "/app";
    }, 700);
  } catch (err) {
    showAuthAlert(alertEl, err.message || "Invalid credentials. Please try again.", "error");
    if (submitBtn) submitBtn.disabled = false;
    if (btnText) btnText.innerText = "Sign In ✦";
  }
}

async function handleSendPasswordReset() {
  const emailInput = document.getElementById("reset-email-input");
  const resetBtn = document.getElementById("reset-submit-btn");
  const alertEl = document.getElementById("login-alert");

  const email = emailInput ? emailInput.value.trim() : "";
  if (!email || !email.includes("@")) {
    showAuthAlert(alertEl, "Please enter a valid email address to send reset instructions.", "error");
    return;
  }

  if (resetBtn) resetBtn.disabled = true;
  try {
    await PathoraAuth.resetPassword(email);
    showAuthAlert(alertEl, "If an account exists for this email, password reset instructions have been sent.", "info");
    toggleForgotPasswordView(false);
  } catch (err) {
    showAuthAlert(alertEl, err.message || "Could not send reset email. Please try again later.", "error");
  } finally {
    if (resetBtn) resetBtn.disabled = false;
  }
}

function handleDemoQuickAccess() {
  // Sets guest mode and opens workspace
  localStorage.setItem("pathora_auth_token", "demo_token_guest");
  localStorage.setItem("pathora_user_session", JSON.stringify({
    uid: "guest_demo_user",
    email: "guest@pathora.ai",
    displayName: "Guest Explorer"
  }));
  window.location.href = "/app";
}

async function handleSignOut() {
  await PathoraAuth.signOut();
  window.location.href = "/";
}

function showAuthAlert(el, message, type = "error") {
  if (!el) return;
  el.style.display = "block";
  el.className = `auth-alert ${type}`;
  el.innerHTML = `
    <div style="display:flex; align-items:center; gap:0.5rem;">
      <i data-lucide="${type === 'success' ? 'check-circle' : (type === 'info' ? 'info' : 'alert-circle')}" style="width:16px;height:16px;flex-shrink:0;"></i>
      <span>${message}</span>
    </div>
  `;
  if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
}

// Auto-initialize on load
document.addEventListener("DOMContentLoaded", () => {
  PathoraAuth.init();
});

