/* ========================================================
   LIFELINK: AI BLOOD DONATION FINDER - CORE JS ENGINE
   Handles State, JWT Auth, Maps, Charts, Chatbot & Voice Search
   ======================================================== */

const isLocal = () => {
    const hn = window.location.hostname;
    if (!hn) return false;
    return (
        hn === 'localhost' || 
        hn === '127.0.0.1' || 
        hn === '[::1]' ||
        hn.indexOf('.') === -1 || 
        hn.startsWith('192.168.') || 
        hn.startsWith('10.') || 
        hn.startsWith('172.') || 
        hn.endsWith('.local')
    );
};

const API_BASE = isLocal()
    ? (window.location.port === '5000' ? '/api' : `http://${window.location.hostname}:5000/api`)
    : (window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api');

// --- SESSION & STATE STATE HELPERS ---
function getAuthToken() {
    return localStorage.getItem('lifelink_token');
}

function getLoggedUser() {
    const userStr = localStorage.getItem('lifelink_user');
    return userStr ? JSON.parse(userStr) : null;
}

function saveSession(token, user) {
    localStorage.setItem('lifelink_token', token);
    localStorage.setItem('lifelink_user', JSON.stringify(user));
}

function logout() {
    localStorage.removeItem('lifelink_token');
    localStorage.removeItem('lifelink_user');
    window.location.href = 'login.html';
}

// Protected Route Guard
function protectRoute(requiredRole) {
    const user = getLoggedUser();
    const token = getAuthToken();
    
    if (!token || !user) {
        window.location.href = 'login.html';
        return;
    }
    
    if (requiredRole && user.role !== requiredRole) {
        // Role mismatch redirect
        if (user.role === 'donor') window.location.href = 'donor.html';
        else if (user.role === 'patient') window.location.href = 'patient.html';
        else if (user.role === 'admin') window.location.href = 'admin.html';
        return;
    }
    
    // Fill user context details in UI
    const nameEl = document.getElementById('user-display-name');
    if (nameEl) nameEl.textContent = user.name;
    
    const welcomeEl = document.getElementById('welcome-title');
    if (welcomeEl) welcomeEl.textContent = `Hello, ${user.name.split(' ')[0]}`;
}

// --- DYNAMIC CUSTOM TOAST NOTIFIER ---
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `custom-toast animate-fade-in ${type}`;
    
    let iconClass = 'fa-info-circle info';
    if (type === 'success') iconClass = 'fa-circle-check success';
    else if (type === 'warning') iconClass = 'fa-circle-exclamation warning';
    else if (type === 'emergency') iconClass = 'fa-triangle-exclamation emergency';
    
    toast.innerHTML = `
        <i class="fa-solid ${iconClass} toast-icon fs-4"></i>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <i class="fa-solid fa-xmark toast-close" onclick="this.parentElement.remove()"></i>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px)';
        toast.style.transition = 'all 0.4s ease';
        setTimeout(() => toast.remove(), 400);
    }, 5000);
}

// --- INITIALIZE THEME CONTROL ---
document.addEventListener('DOMContentLoaded', () => {
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        // Load initial theme from localStorage
        const storedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', storedTheme);
        updateThemeToggleIcon(storedTheme);
        
        themeBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeToggleIcon(newTheme);
            showToast("Theme Updated", `Switched layout to ${newTheme} mode!`, "success");
        });
    }
    
    // Initialize Chatbot Message History
    initChatbot();
    
    // Connect Voice Speech Search if Microphone exists
    initVoiceSpeechSearch();

    // Load dynamic public stats on landing page
    loadPublicStats();

    // Hook up home page quick search bar
    initHomepageSearch();

    // --- SIDEBAR SMOOTH SCROLLING & ACTIVE SECTION HIGHIGHTING ---
    const navLinks = document.querySelectorAll('.sidebar-nav-link');
    if (navLinks.length > 0) {
        let isScrollingFromClick = false;
        
        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                const targetId = this.getAttribute('href');
                if (targetId && targetId.startsWith('#') && targetId.length > 1) {
                    const targetEl = document.querySelector(targetId);
                    if (targetEl) {
                        e.preventDefault();
                        
                        isScrollingFromClick = true;
                        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        
                        navLinks.forEach(l => l.classList.remove('active'));
                        this.classList.add('active');
                        
                        if (targetId === '#notifications-tab') {
                            markNotificationsAsRead();
                        }
                        
                        setTimeout(() => {
                            isScrollingFromClick = false;
                        }, 1000);
                    }
                }
            });
        });
        
        const observerOptions = {
            root: null,
            rootMargin: '-10% 0px -50% 0px',
            threshold: 0
        };
        
        const observer = new IntersectionObserver((entries) => {
            if (isScrollingFromClick) return;
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.getAttribute('id');
                    const activeLink = document.querySelector(`.sidebar-nav-link[href="#${id}"]`);
                    if (activeLink) {
                        navLinks.forEach(l => l.classList.remove('active'));
                        activeLink.classList.add('active');
                        
                        if (id === 'notifications-tab') {
                            markNotificationsAsRead();
                        }
                    }
                }
            });
        }, observerOptions);
        
        navLinks.forEach(link => {
            const targetId = link.getAttribute('href');
            if (targetId && targetId.startsWith('#') && targetId.length > 1) {
                const targetEl = document.querySelector(targetId);
                if (targetEl) {
                    observer.observe(targetEl);
                }
            }
        });
    }

    // Initialize Voluntary Donation elements if on donor.html
    const volForm = document.getElementById('voluntary-donation-form');
    if (volForm) {
        const dateInput = document.getElementById('vol-date');
        if (dateInput) {
            dateInput.value = new Date().toISOString().split('T')[0];
        }
        populateVoluntaryHospitals();
        setupVoluntaryDonationSubmission();
    }
});

// --- PUBLIC LANDING PAGE DYNAMIC HELPERS ---
async function loadPublicStats() {
    const donorsEl = document.getElementById('stat-donors');
    const completedEl = document.getElementById('stat-completed');
    const hospitalsEl = document.getElementById('stat-hospitals');
    const livesEl = document.getElementById('stat-lives');
    
    if (!donorsEl && !completedEl && !hospitalsEl && !livesEl) return;
    
    try {
        const response = await fetch(`${API_BASE}/public/stats`);
        const result = await response.json();
        if (result.status === 'success') {
            const data = result.data;
            if (donorsEl) donorsEl.textContent = `${data.donors.toLocaleString()}+`;
            if (completedEl) completedEl.textContent = `${data.completed.toLocaleString()}+`;
            if (hospitalsEl) hospitalsEl.textContent = data.hospitals.toLocaleString();
            if (livesEl) livesEl.textContent = `${data.lives_saved.toLocaleString()}+`;
        }
    } catch (error) {
        console.error("Failed to load public stats:", error);
    }
}

function initHomepageSearch() {
    const searchBtn = document.getElementById('quick-search-btn');
    const searchInput = document.getElementById('quick-blood-search');
    
    if (searchBtn && searchInput) {
        searchBtn.addEventListener('click', () => {
            const query = searchInput.value.trim();
            if (query) {
                window.location.href = `login.html?search=${encodeURIComponent(query)}`;
            }
        });
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const query = searchInput.value.trim();
                if (query) {
                    window.location.href = `login.html?search=${encodeURIComponent(query)}`;
                }
            }
        });
    }
    
    // Prefills/toasts search parameter in login if present
    const urlParams = new URLSearchParams(window.location.search);
    const searchQuery = urlParams.get('search');
    if (searchQuery) {
        showToast("Search Connection", `Log in to find compatible donors matching "${searchQuery}"!`, "info");
    }
}

function updateThemeToggleIcon(theme) {
    const icon = document.querySelector('#theme-toggle-btn i');
    if (icon) {
        if (theme === 'dark') {
            icon.className = 'fa-solid fa-sun';
        } else {
            icon.className = 'fa-solid fa-moon';
        }
    }
}

// --- AUTHENTICATION API CALLS ---

const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const role = document.getElementById('login-role').value;
        
        try {
            const response = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, role })
            });
            
            const result = await response.json();
            if (result.status === 'success') {
                saveSession(result.token, result.user);
                if (result.user.role === 'donor') window.location.href = 'donor.html';
                else if (result.user.role === 'patient') window.location.href = 'patient.html';
                else if (result.user.role === 'admin') window.location.href = 'admin.html';
            } else {
                showToast("Authentication Failed", result.message, "warning");
            }
        } catch (error) {
            console.error("Auth login error:", error);
            showToast("Connection Error", "Could not connect to Flask REST API server. Is it running?", "warning");
        }
    });
}

// --- FORGOT PASSWORD API LOGIC ---

const requestOtpForm = document.getElementById('request-otp-form');
if (requestOtpForm) {
    requestOtpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('forgot-email').value;
        
        try {
            const response = await fetch(`${API_BASE}/auth/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            
            const result = await response.json();
            if (result.status === 'success') {
                // If local testing is enabled, we get the mock OTP directly
                if (result.otp_mock) {
                    showToast("OTP Generated (Local Testing)", `Your OTP is: ${result.otp_mock}`, "info");
                }
                
                // Transition to Step 2
                document.getElementById('forgot-step-1').classList.add('d-none');
                document.getElementById('forgot-step-2').classList.remove('d-none');
            } else {
                showToast("Request Failed", result.message, "warning");
            }
        } catch (error) {
            console.error("Forgot password error:", error);
            showToast("Connection Error", "Could not connect to Flask API server.", "warning");
        }
    });
}

const resetPasswordForm = document.getElementById('reset-password-form');
if (resetPasswordForm) {
    resetPasswordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('forgot-email').value; // from step 1
        const otp = document.getElementById('reset-otp').value;
        const new_password = document.getElementById('new-password').value;
        
        try {
            const response = await fetch(`${API_BASE}/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, otp, new_password })
            });
            
            const result = await response.json();
            if (result.status === 'success') {
                showToast("Password Reset Successful", result.message, "success");
                
                // Close modal
                const modalElement = document.getElementById('forgotPasswordModal');
                const modalInstance = bootstrap.Modal.getInstance(modalElement);
                if (modalInstance) {
                    modalInstance.hide();
                }
                
                // Reset form states
                document.getElementById('forgot-step-2').classList.add('d-none');
                document.getElementById('forgot-step-1').classList.remove('d-none');
                requestOtpForm.reset();
                resetPasswordForm.reset();
            } else {
                showToast("Reset Failed", result.message, "warning");
            }
        } catch (error) {
            console.error("Reset password error:", error);
            showToast("Connection Error", "Could not connect to Flask API server.", "warning");
        }
    });
}

const registerForm = document.getElementById('register-form');
if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const name = document.getElementById('register-name').value;
        const phone = document.getElementById('register-phone').value;
        const role = document.getElementById('register-role').value;
        const latitude = document.getElementById('register-latitude').value;
        const longitude = document.getElementById('register-longitude').value;
        
        const payload = { email, password, name, phone, role, latitude, longitude };
        
        if (role === 'donor') {
            payload.blood_group = document.getElementById('register-blood-group').value;
            const isAvail = document.getElementById('register-available').checked;
            payload.is_available = isAvail ? 1 : 0;
        } else {
            // Handle new location-based hospital dropdown + custom fallback
            const hospitalSelect = document.getElementById('register-hospital-select');
            const hospitalCustomInput = document.getElementById('register-hospital-custom');
            const hospitalTextInput = document.getElementById('register-hospital');
            
            if (hospitalSelect && hospitalSelect.value) {
                const selectedVal = hospitalSelect.value;
                if (selectedVal === 'custom') {
                    payload.hospital_name = hospitalCustomInput ? hospitalCustomInput.value.trim() : '';
                } else {
                    payload.hospital_name = selectedVal;
                }
            } else if (hospitalTextInput) {
                payload.hospital_name = hospitalTextInput.value;
            }
            payload.medical_condition = document.getElementById('register-condition').value;
        }
        
        try {
            const response = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                window.location.href = `login.html?role=${role}`;
            } else {
                showToast("Registration Error", result.message, "warning");
            }
        } catch (error) {
            console.error("Auth register error:", error);
            showToast("Connection Error", "Failed to communicate with Flask server.", "warning");
        }
    });
}

// --- LOCATION-BASED HOSPITAL REGISTRATION HELPER ---

async function fetchNearbyHospitalsForRegistration(lat, lon) {
    const select = document.getElementById('register-hospital-select');
    const statusEl = document.getElementById('hospital-fetch-status');
    const customGroup = document.getElementById('register-hospital-custom-group');
    const customInput = document.getElementById('register-hospital-custom');
    if (!select) return;

    select.disabled = true;
    select.innerHTML = '<option value="">\uD83D\uDD04 Loading nearby hospitals...</option>';
    if (statusEl) {
        statusEl.className = 'form-text fs-8 text-info mt-1';
        statusEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i>Searching hospitals within 50km of your location...';
    }

    try {
        const response = await fetch(`${API_BASE}/hospitals?latitude=${lat}&longitude=${lon}&max_distance=50`);
        const result = await response.json();

        select.innerHTML = '<option value="" disabled selected>Select a nearby hospital or blood bank...</option>';

        if (result.status === 'success' && result.data && result.data.length > 0) {
            const hospitals = result.data.filter(h => h.type === 'Hospital');
            const bloodBanks = result.data.filter(h => h.type === 'Blood Bank');

            if (hospitals.length > 0) {
                const grp1 = document.createElement('optgroup');
                grp1.label = '\uD83C\uDFE5 Hospitals';
                hospitals.forEach(h => {
                    const opt = document.createElement('option');
                    opt.value = h.name;
                    opt.textContent = `${h.name}  \u2014  ${h.distance_km} km away`;
                    grp1.appendChild(opt);
                });
                select.appendChild(grp1);
            }

            if (bloodBanks.length > 0) {
                const grp2 = document.createElement('optgroup');
                grp2.label = '\uD83E\uDE78 Blood Banks';
                bloodBanks.forEach(h => {
                    const opt = document.createElement('option');
                    opt.value = h.name;
                    opt.textContent = `${h.name}  \u2014  ${h.distance_km} km away`;
                    grp2.appendChild(opt);
                });
                select.appendChild(grp2);
            }

            const customOpt = document.createElement('option');
            customOpt.value = 'custom';
            customOpt.textContent = '\u270F\uFE0F Other / Enter hospital name manually...';
            select.appendChild(customOpt);

            if (statusEl) {
                statusEl.className = 'form-text fs-8 text-success mt-1';
                statusEl.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i>Found <strong>${result.data.length}</strong> facility(s) near your location, sorted by distance.`;
            }
        } else {
            select.innerHTML = '<option value="custom">\u270F\uFE0F No registered facilities found nearby \u2014 enter name manually</option>';
            if (customGroup) customGroup.classList.remove('d-none');
            if (customInput) customInput.required = true;
            if (statusEl) {
                statusEl.className = 'form-text fs-8 text-warning mt-1';
                statusEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation me-1"></i>No registered facilities within 50km. Enter the hospital name below.';
            }
        }

        select.disabled = false;

        // Handle "Other" toggle
        select.addEventListener('change', () => {
            if (select.value === 'custom') {
                if (customGroup) customGroup.classList.remove('d-none');
                if (customInput) customInput.required = true;
            } else {
                if (customGroup) customGroup.classList.add('d-none');
                if (customInput) { customInput.required = false; customInput.value = ''; }
            }
        });

    } catch (error) {
        console.error("Failed to fetch nearby hospitals:", error);
        select.innerHTML = '<option value="custom">\u270F\uFE0F Could not load hospitals \u2014 enter manually</option>';
        select.disabled = false;
        if (customGroup) customGroup.classList.remove('d-none');
        if (customInput) customInput.required = true;
        if (statusEl) {
            statusEl.className = 'form-text fs-8 text-danger mt-1';
            statusEl.innerHTML = '<i class="fa-solid fa-circle-xmark me-1"></i>Failed to load hospitals. Please enter manually.';
        }
    }
}

// --- PATIENT PORTAL INTERACTIVITIES ---
let patientMap = null;
let mapRadiusCircle = null;
let donorMarkersLayer = null;

async function loadPatientRequests() {
    const user = getLoggedUser();
    if (!user) return;
    
    // Fill coordinates display
    const coordsEl = document.getElementById('patient-coords');
    if (coordsEl && user.profile) {
        coordsEl.textContent = `${parseFloat(user.profile.latitude).toFixed(4)}, ${parseFloat(user.profile.longitude).toFixed(4)}`;
    }
    
    try {
        const response = await fetch(`${API_BASE}/requests?patient_id=${user.id}`);
        const result = await response.json();
        
        const tbody = document.getElementById('patient-requests-table-body');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        if (result.data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-secondary">You haven't raised any blood requests yet. Complete the form to broadcast.</td></tr>`;
            return;
        }
        
        result.data.forEach(req => {
            let priorityBadgeClass = 'priority-badge priority-medium';
            if (req.priority === 'Critical') priorityBadgeClass = 'priority-badge priority-critical';
            else if (req.priority === 'High') priorityBadgeClass = 'priority-badge priority-high';
            else if (req.priority === 'Low') priorityBadgeClass = 'priority-badge priority-low';
            
            let statusBadgeClass = 'badge bg-warning text-dark';
            if (req.status === 'Fulfilled') statusBadgeClass = 'badge bg-success text-white';
            else if (req.status === 'Matching') statusBadgeClass = 'badge bg-info text-white';
            
            tbody.innerHTML += `
                <tr class="cursor-pointer" onclick="selectPatientRequestForMatching(${req.id}, '${req.blood_group}', ${req.latitude}, ${req.longitude})">
                    <td class="fw-bold">REQ-${req.id}</td>
                    <td class="fw-bold text-danger">${req.blood_group}</td>
                    <td>${req.units_needed} Unit(s)</td>
                    <td><span class="${priorityBadgeClass}">${req.priority}</span></td>
                    <td><span class="${statusBadgeClass}">${req.status}</span></td>
                    <td>${req.created_at ? req.created_at.split(' ')[0] : '-'}</td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-premium py-1 px-3 fs-9">
                            <i class="fa-solid fa-brain me-1"></i>AI Matches
                        </button>
                    </td>
                </tr>
            `;
        });
    } catch (error) {
        console.error("Load patient requests error:", error);
    }
}

// Raising new emergency blood request (assesses AI priority level)
const emergencyRequestForm = document.getElementById('emergency-request-form');
if (emergencyRequestForm) {
    emergencyRequestForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const user = getLoggedUser();
        const token = getAuthToken();
        
        const blood_group = document.getElementById('req-blood-group').value;
        const units_needed = document.getElementById('req-units').value;
        const hospital_name = document.getElementById('req-hospital').value;
        
        const hemoglobin_level = document.getElementById('req-hemoglobin').value;
        const patient_age = document.getElementById('req-age').value;
        
        const active_bleeding = document.getElementById('req-bleeding').checked ? 1 : 0;
        const trauma_or_accident = document.getElementById('req-trauma').checked ? 1 : 0;
        const surgery_scheduled = document.getElementById('req-surgery').checked ? 1 : 0;
        
        const details = document.getElementById('req-details').value;
        
        const payload = {
            blood_group, units_needed, hospital_name, details,
            hemoglobin_level, patient_age, active_bleeding, trauma_or_accident, surgery_scheduled
        };
        
        try {
            const response = await fetch(`${API_BASE}/requests`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                showToast("Request Broadcasted!", result.message, "success");
                emergencyRequestForm.reset();
                loadPatientRequests();
                
                // Highlight the matching and leaflet section
                const matchesRow = document.getElementById('map-recommendations-row');
                if (matchesRow) matchesRow.scrollIntoView({ behavior: 'smooth' });
                
                // Select newly created request
                setTimeout(() => {
                    selectPatientRequestForMatching(result.data.id, blood_group, user.profile.latitude, user.profile.longitude);
                }, 1000);
            } else {
                showToast("Alert Failed", result.message, "warning");
            }
        } catch (error) {
            console.error("Create request error:", error);
            showToast("Connection Error", "Could not broadcast requests.", "warning");
        }
    });
}

// Select a specific request and call the AI models
// Select a specific request and call the AI models
let cachedFacilities = [];
let cachedDonors = [];
let lastCenterLat = null;
let lastCenterLon = null;

async function loadNearbyFacilities(lat, lon, radiusLimit) {
    try {
        const response = await fetch(`${API_BASE}/hospitals?latitude=${lat}&longitude=${lon}&max_distance=50.0`);
        const result = await response.json();
        if (result.status === 'success') {
            cachedFacilities = result.data;
            renderFacilitiesTable(radiusLimit);
        }
    } catch (error) {
        console.error("Load nearby facilities error:", error);
    }
}

function renderFacilitiesTable(radiusLimit) {
    const tbody = document.getElementById('facilities-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    const filtered = cachedFacilities.filter(f => f.distance_km <= radiusLimit);
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-secondary">No blood banks or hospitals found within ${radiusLimit}km.</td></tr>`;
        return;
    }
    
    filtered.forEach(f => {
        const typeBadge = f.type === 'Blood Bank' ? 'badge bg-danger text-white' : 'badge bg-primary text-white';
        tbody.innerHTML += `
            <tr>
                <td class="fw-bold text-dark">${f.name}</td>
                <td><span class="${typeBadge}">${f.type}</span></td>
                <td><a href="tel:${f.phone}" class="text-secondary"><i class="fa-solid fa-phone me-1"></i>${f.phone}</a></td>
                <td class="text-muted text-truncate" style="max-width: 150px;" title="${f.address}">${f.address}</td>
                <td class="text-end fw-bold text-danger">${f.distance_km} km</td>
            </tr>
        `;
    });
}

async function selectPatientRequestForMatching(reqId, bloodGroup, lat, lon) {
    const token = getAuthToken();
    
    // Update target indicator labels
    const targetBadge = document.getElementById('req-match-target-group');
    if (targetBadge) targetBadge.textContent = `Type ${bloodGroup} Needed`;
    
    showToast("Evaluating Matching Donors", `Running Scikit-Learn matching engines for request REQ-${reqId}...`, "info");
    
    try {
        const response = await fetch(`${API_BASE}/requests/${reqId}/matches`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const result = await response.json();
        
        const container = document.getElementById('ai-matches-list-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (result.data.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-secondary fs-7">
                    <i class="fa-solid fa-face-frown fs-4 text-warning mb-2"></i>
                    <br>No available matching compatible donors found inside a 50km bracket.
                </div>
            `;
            return;
        }
        
        // Populate AI Recommended list
        result.data.forEach((match, index) => {
            const isCooldown = match.cooldown_days_left > 0;
            const badgeTagsHTML = match.badges.map(b => `<span class="badge bg-danger-light text-danger fs-9"><i class="fa-solid fa-medal me-1"></i>${b}</span>`).join(' ');
            
            // Availability probability progress color
            let progressClass = 'bg-success';
            if (match.ai_availability_probability < 50) progressClass = 'bg-danger';
            else if (match.ai_availability_probability < 75) progressClass = 'bg-warning';
            
            container.innerHTML += `
                <div class="glass-card p-3 border border-light shadow-sm" style="transition: none; transform: none;">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <h6 class="fw-bold mb-0 text-dark">${match.name} <span class="badge bg-danger ms-2">${match.blood_group}</span></h6>
                            <span class="fs-8 text-secondary"><i class="fa-solid fa-map-marker-alt me-1"></i>${match.distance_km} km away</span>
                        </div>
                        <div class="text-end">
                            <span class="badge bg-danger text-white fw-bold fs-8 p-2 shadow-sm">AI Score: ${match.ai_match_score}</span>
                        </div>
                    </div>
                    
                    <div class="row g-2 align-items-center mb-3">
                        <div class="col-8">
                            <span class="fs-8 text-secondary fw-semibold">Predicted Response Rate:</span>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${progressClass}" role="progressbar" style="width: ${match.ai_availability_probability}%"></div>
                            </div>
                        </div>
                        <div class="col-4 text-end">
                            <span class="fw-bold fs-7 text-dark">${match.ai_availability_probability}%</span>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                        <div class="d-flex gap-1 flex-wrap">
                            ${badgeTagsHTML}
                            ${isCooldown ? `<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation"></i> Cooldown: ${match.cooldown_days_left}d</span>` : ''}
                        </div>
                        <button class="btn btn-premium py-1 px-3 fs-8" onclick="triggerAlertAlert('${match.name}', '${match.phone}')" ${isCooldown ? 'disabled' : ''}>
                            <i class="fa-solid fa-bell me-1"></i>Alert
                        </button>
                    </div>
                </div>
            `;
        });
        
        lastCenterLat = lat;
        lastCenterLon = lon;
        cachedDonors = result.data;
        
        const slider = document.getElementById('map-radius-slider');
        const radiusLimit = slider ? parseInt(slider.value) : 15;
        
        await loadNearbyFacilities(lat, lon, radiusLimit);
        
        // PLOT MAP CHANNELS
        initializeLeafletPatientMap(lat, lon, cachedDonors, cachedFacilities);
    } catch (error) {
        console.error("AI recommendations error:", error);
    }
}

function triggerAlertAlert(name, phone) {
    showToast("Notification Sent", `Broadcasted direct emergency SMS/Ping alert to donor ${name} (${phone})!`, "success");
}

let facilitiesMarkersLayer = null;

// Leaflet geodetic map plotting
function initializeLeafletPatientMap(centerLat, centerLon, compatibleDonors, facilities = []) {
    const slider = document.getElementById('map-radius-slider');
    const radiusLabel = document.getElementById('radius-value');
    
    let radiusKm = slider ? parseInt(slider.value) : 15;
    
    if (patientMap === null) {
        // Create leaflet instance
        patientMap = L.map('map').setView([centerLat, centerLon], 12);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(patientMap);
        
        // Marker for hospital/patient center
        const centerIcon = L.icon({
            iconUrl: 'https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        
        L.marker([centerLat, centerLon], { icon: centerIcon }).addTo(patientMap)
            .bindPopup(`<strong class="text-danger">Your Hospital / Location</strong><br>Center of emergency search.`)
            .openPopup();
            
        // Radius vector circle
        mapRadiusCircle = L.circle([centerLat, centerLon], {
            color: 'red',
            fillColor: '#f03',
            fillOpacity: 0.08,
            radius: radiusKm * 1000 // meters
        }).addTo(patientMap);
        
        donorMarkersLayer = L.layerGroup().addTo(patientMap);
        facilitiesMarkersLayer = L.layerGroup().addTo(patientMap);
        
        // Listen slider updates
        if (slider) {
            slider.addEventListener('input', (e) => {
                const newRadius = parseInt(e.target.value);
                if (radiusLabel) radiusLabel.textContent = `${newRadius} km`;
                if (mapRadiusCircle) {
                    mapRadiusCircle.setRadius(newRadius * 1000);
                }
                filterMapMarkersByRadius(newRadius);
                renderFacilitiesTable(newRadius);
            });
        }

        // Listen map layer toggle clicks
        const layerToggles = document.getElementById('map-layer-toggles');
        if (layerToggles) {
            layerToggles.addEventListener('change', () => {
                filterMapMarkersByRadius(slider ? parseInt(slider.value) : 15);
            });
        }
    } else {
        // Recenter
        patientMap.setView([centerLat, centerLon], 12);
        if (mapRadiusCircle) {
            mapRadiusCircle.setLatLng([centerLat, centerLon]);
            mapRadiusCircle.setRadius(radiusKm * 1000);
        }
    }
    
    // Clear old markers
    donorMarkersLayer.clearLayers();
    facilitiesMarkersLayer.clearLayers();
    
    // Icon variations for donors
    const availableIcon = L.icon({
        iconUrl: 'https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });
    
    const busyIcon = L.icon({
        iconUrl: 'https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });

    // Icon variations for facilities
    const hospitalIcon = L.icon({
        iconUrl: 'https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });

    const bankIcon = L.icon({
        iconUrl: 'https://cdn.rawgit.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });
    
    // Add compatible donor pins
    compatibleDonors.forEach(d => {
        const icon = d.cooldown_days_left === 0 && d.is_available === 1 ? availableIcon : busyIcon;
        const marker = L.marker([d.latitude, d.longitude], { icon: icon });
        marker.distance_km = d.distance_km;
        
        const popupText = `
            <div style="font-family: var(--font-sans); min-width: 150px;">
                <strong class="text-danger">${d.name} (${d.blood_group})</strong>
                <br><b>Distance:</b> ${d.distance_km} km
                <br><b>AI Match:</b> ${d.ai_match_score}%
                <br><b>Status:</b> ${d.cooldown_days_left > 0 ? `Cooldown (${d.cooldown_days_left}d)` : (d.is_available ? 'Available' : 'Offline')}
            </div>
        `;
        marker.bindPopup(popupText);
        donorMarkersLayer.addLayer(marker);
    });

    // Add facility pins
    facilities.forEach(f => {
        const icon = f.type === 'Blood Bank' ? bankIcon : hospitalIcon;
        const marker = L.marker([f.latitude, f.longitude], { icon: icon });
        marker.distance_km = f.distance_km;
        
        const popupText = `
            <div style="font-family: var(--font-sans); min-width: 150px;">
                <strong class="text-primary">${f.name}</strong>
                <br><b>Type:</b> <span class="badge bg-secondary">${f.type}</span>
                <br><b>Distance:</b> ${f.distance_km} km
                <br><b>Phone:</b> ${f.phone}
                <br><b>Address:</b> ${f.address}
            </div>
        `;
        marker.bindPopup(popupText);
        facilitiesMarkersLayer.addLayer(marker);
    });
    
    filterMapMarkersByRadius(radiusKm);
}

function filterMapMarkersByRadius(radiusLimit) {
    if (!patientMap) return;
    const showDonors = document.getElementById('layer-donors')?.checked || document.getElementById('layer-all')?.checked || false;
    const showFacilities = document.getElementById('layer-facilities')?.checked || document.getElementById('layer-all')?.checked || false;

    // Control Donors layer visibility
    if (showDonors && donorMarkersLayer) {
        if (!patientMap.hasLayer(donorMarkersLayer)) {
            donorMarkersLayer.addTo(patientMap);
        }
        donorMarkersLayer.eachLayer(marker => {
            if (marker.distance_km > radiusLimit) {
                patientMap.removeLayer(marker);
            } else {
                marker.addTo(patientMap);
            }
        });
    } else if (donorMarkersLayer) {
        patientMap.removeLayer(donorMarkersLayer);
    }

    // Control Facilities layer visibility
    if (showFacilities && facilitiesMarkersLayer) {
        if (!patientMap.hasLayer(facilitiesMarkersLayer)) {
            facilitiesMarkersLayer.addTo(patientMap);
        }
        facilitiesMarkersLayer.eachLayer(marker => {
            if (marker.distance_km > radiusLimit) {
                patientMap.removeLayer(marker);
            } else {
                marker.addTo(patientMap);
            }
        });
    } else if (facilitiesMarkersLayer) {
        patientMap.removeLayer(facilitiesMarkersLayer);
    }
}

// --- DONOR PORTAL INTERACTIVITIES ---

async function loadDonorAlerts() {
    const user = getLoggedUser();
    const token = getAuthToken();
    if (!user) return;
    
    // Set health metrics values
    const scoreVal = document.getElementById('donor-ai-score-value');
    if (scoreVal && user.profile) scoreVal.textContent = user.profile.ai_donor_score;
    
    const speedVal = document.getElementById('donor-response-speed');
    if (speedVal && user.profile) speedVal.textContent = user.profile.response_speed_history;
    
    // Compute cooldown eligibility display
    computeDonorCooldownDisplay(user.profile.last_donation_date);
    
    try {
        const response = await fetch(`${API_BASE}/requests`);
        const result = await response.json();
        
        const container = document.getElementById('donor-alerts-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (!result.data) {
            console.error("Load donor alerts error:", result.message);
            return;
        }
        
        // Filter requests matching compatible groups and location radius (within 20km simulated)
        let alertCount = 0;
        
        result.data.forEach(req => {
            // Blood group compatibility check
            const compScore = ai_models.is_blood_compatible(user.profile.blood_group, req.blood_group);
            if (compScore > 0 && req.status !== 'Fulfilled') {
                // Proximity check (simulate geodetic check)
                const dist = haversine(user.profile.latitude, user.profile.longitude, req.latitude, req.longitude);
                if (dist <= 25.0) {
                    alertCount++;
                    
                    let priorityBadgeClass = 'priority-badge priority-medium';
                    if (req.priority === 'Critical') priorityBadgeClass = 'priority-badge priority-critical animate-pulse-indicator';
                    else if (req.priority === 'High') priorityBadgeClass = 'priority-badge priority-high';
                    
                    container.innerHTML += `
                        <div class="glass-card p-4 border border-light shadow-sm" style="transition: none; transform: none;">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <span class="${priorityBadgeClass} mb-2">${req.priority} Emergency</span>
                                    <h5 class="fw-bold mb-1 text-dark">${req.hospital_name}</h5>
                                    <span class="fs-8 text-secondary"><i class="fa-solid fa-map-marker-alt text-danger me-1"></i>Geodetic Proximity: ${round(dist, 1)} km</span>
                                </div>
                                <div class="text-end">
                                    <span class="fs-9 text-secondary d-block fw-bold mb-1">RECIPIENT GROUP</span>
                                    <span class="badge bg-danger fs-5 px-3 py-2 shadow-sm">${req.blood_group}</span>
                                </div>
                            </div>
                            
                            <p class="text-secondary fs-7 bg-light p-3 rounded-md mb-3 border">
                                <strong>Request Details:</strong> ${req.details}
                            </p>
                            
                            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                                <span class="fs-8 text-muted">Requested Units: <strong>${req.units_needed}</strong></span>
                                <button class="btn btn-premium" onclick="acceptAndDonateBlood(${req.id})">
                                    <i class="fa-solid fa-square-check me-1"></i>Accept & Donate
                                </button>
                            </div>
                        </div>
                    `;
                }
            }
        });
        
        // Show badges counts
        const badgeCount = document.getElementById('sidebar-alerts-badge');
        if (badgeCount) {
            if (alertCount > 0) {
                badgeCount.textContent = alertCount;
                badgeCount.classList.remove('d-none');
            } else {
                badgeCount.classList.add('d-none');
            }
        }
        
        if (alertCount === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-secondary fs-7">
                    <i class="fa-solid fa-circle-check fs-3 text-success mb-2"></i>
                    <br>All quiet! No active emergency matching demands raised nearby.
                </div>
            `;
        }
    } catch (error) {
        console.error("Load donor alerts error:", error);
    }
}

function computeDonorCooldownDisplay(lastDonationStr) {
    const circle = document.getElementById('eligibility-circle-indicator');
    const valText = document.getElementById('eligibility-value-text');
    const labelText = document.getElementById('eligibility-label-text');
    const descText = document.getElementById('eligibility-description-text');
    
    if (!circle || !valText || !labelText || !descText) return;
    
    if (!lastDonationStr) {
        circle.className = "eligibility-circle eligible";
        valText.textContent = "YES";
        valText.className = "eligibility-value text-success";
        labelText.textContent = "Ready";
        descText.innerHTML = "You have no recorded past donations. You are fully eligible to assist emergency broadcasts!";
        return;
    }
    
    const lastDate = new Date(lastDonationStr);
    const today = new Date();
    const daysPassed = Math.floor((today - lastDate) / (1000 * 60 * 60 * 24));
    
    if (daysPassed >= 90) {
        circle.className = "eligibility-circle eligible";
        valText.textContent = "YES";
        valText.className = "eligibility-value text-success";
        labelText.textContent = "Ready";
        descText.innerHTML = `It has been <strong>${daysPassed} days</strong> since your last donation (${lastDonationStr}). You are eligible!`;
    } else {
        const remaining = 90 - daysPassed;
        circle.className = "eligibility-circle cooldown";
        valText.textContent = `${remaining}d`;
        valText.className = "eligibility-value text-warning";
        labelText.textContent = "Remaining";
        descText.innerHTML = `Rest cooldown active. <strong>${daysPassed} days</strong> passed since last donation (${lastDonationStr}). Eligible in ${remaining} days.`;
    }
}

async function acceptAndDonateBlood(reqId) {
    const token = getAuthToken();
    
    showToast("Fulfilling Donation", "Registering transaction credentials and generating certificates...", "info");
    
    try {
        const response = await fetch(`${API_BASE}/requests/${reqId}/donate`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const result = await response.json();
        
        if (result.status === 'success') {
            showToast("Transaction Fulfilling", "Emergency status marked fulfilled. Certificate ready!", "success");
            
            // Reload alert list and history
            loadDonorAlerts();
            loadDonorHistory();
            
            // Fetch updated profile
            fetchDonorUpdatedProfile(token);
            
            // Trigger Certificate display modal
            setTimeout(() => {
                triggerDonationCertificateModal(result.data.certificate_code);
            }, 1200);
        } else {
            showToast("Transaction Failed", result.message, "warning");
        }
    } catch (error) {
        console.error("Accept donation error:", error);
    }
}

async function fetchDonorUpdatedProfile(token) {
    try {
        const response = await fetch(`${API_BASE}/user/profile`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const result = await response.json();
        if (result.status === 'success') {
            localStorage.setItem('lifelink_user', JSON.stringify(result.data));
            // Recalculate score and labels
            const scoreVal = document.getElementById('donor-ai-score-value');
            if (scoreVal) scoreVal.textContent = result.data.ai_donor_score;
            
            const speedVal = document.getElementById('donor-response-speed');
            if (speedVal) speedVal.textContent = result.data.response_speed_history;
            
            computeDonorCooldownDisplay(result.data.last_donation_date);
            loadAchievementsBadges(result.data.badges);
        }
    } catch (error) {
        console.error("Fetch profile update error:", error);
    }
}

function loadAchievementsBadges(badgesStr) {
    const badges = typeof badgesStr === 'string' ? JSON.parse(badgesStr || '[]') : (badgesStr || []);
    
    badges.forEach(b => {
        const el = document.getElementById(`badge-${b}`);
        if (el) {
            el.classList.add('unlocked');
        }
    });
}

// Donation history loading
async function loadDonorHistory() {
    const token = getAuthToken();
    const user = getLoggedUser();
    if (!token || !user) return;
    
    try {
        const response = await fetch(`${API_BASE}/donor/history`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const result = await response.json();
        
        const tbody = document.getElementById('donor-history-table-body');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (!result.data) {
            console.error("Load donor history error:", result.message);
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-danger">Error loading history: ${result.message || 'Unknown error'}</td></tr>`;
            return;
        }
        
        if (result.data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-secondary">You haven't completed any donations on this platform yet.</td></tr>`;
            return;
        }
        
        result.data.forEach(dh => {
            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold">TX-${dh.id}</td>
                    <td>${dh.hospital_name || 'Direct Bank Drive'}</td>
                    <td>${dh.patient_name || 'Emergency Reserve'}</td>
                    <td><span class="badge bg-danger">${dh.blood_group || user.profile.blood_group}</span></td>
                    <td>${dh.units} Unit(s)</td>
                    <td>${dh.donation_date}</td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-danger py-1 px-3 fs-9" onclick="triggerDonationCertificateModal('${dh.certificate_code}')">
                            <i class="fa-solid fa-file-signature me-1"></i>View certificate
                        </button>
                    </td>
                </tr>
            `;
        });
        
        // Trigger achievements badges
        loadAchievementsBadges(user.profile.badges);
    } catch (error) {
        console.error("Load donor history error:", error);
    }
}

// --- NOTIFICATIONS MANAGEMENT ---

async function loadPatientNotifications() {
    const token = getAuthToken();
    if (!token) return;
    
    try {
        const response = await fetch(`${API_BASE}/notifications`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const result = await response.json();
        
        const container = document.getElementById('patient-notifications-list');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (!result || result.length === 0) {
            container.innerHTML = `<div class="text-center py-4 text-secondary fs-7">No notifications found.</div>`;
            return;
        }
        
        // Update badge count
        const badge = document.getElementById('notif-badge-count');
        const unread = result.filter(n => !n.is_read).length;
        if (badge) {
            if (unread > 0) {
                badge.textContent = unread;
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
        }
        
        result.forEach(n => {
            let iconClass = 'fa-info-circle text-primary';
            let bgClass = 'bg-light';
            if (n.type === 'emergency') {
                iconClass = 'fa-triangle-exclamation text-danger';
                bgClass = 'bg-danger-light';
            } else if (n.type === 'success') {
                iconClass = 'fa-circle-check text-success';
                bgClass = 'bg-success-light';
            }
            
            container.innerHTML += `
                <div class="p-3 border rounded-md d-flex align-items-center gap-3 ${bgClass} mb-2">
                    <i class="fa-solid ${iconClass} fs-5"></i>
                    <div>
                        <strong class="d-block fs-7 text-dark">${n.title}</strong>
                        <span class="fs-8 text-secondary">${n.message}</span>
                    </div>
                </div>
            `;
        });
    } catch (error) {
        console.error("Load patient notifications error:", error);
    }
}

async function markNotificationsAsRead() {
    const token = getAuthToken();
    if (!token) return;
    try {
        await fetch(`${API_BASE}/notifications/read`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const badge = document.getElementById('notif-badge-count');
        if (badge) {
            badge.classList.add('d-none');
            badge.textContent = '0';
        }
    } catch (error) {
        console.error("Failed to mark notifications read:", error);
    }
}

// Certificate generator populator
async function triggerDonationCertificateModal(code) {
    try {
        const response = await fetch(`${API_BASE}/donor/certificate/${code}`);
        const result = await response.json();
        
        if (result.status === 'success') {
            const cert = result.data;
            
            document.getElementById('cert-donor-name').textContent = cert.donor_name;
            document.getElementById('cert-units').textContent = `${cert.units} Unit(s)`;
            document.getElementById('cert-bg').textContent = cert.blood_group;
            document.getElementById('cert-hospital').textContent = cert.hospital_name || 'Emergency Blood Reserve';
            document.getElementById('cert-date').textContent = cert.donation_date;
            document.getElementById('cert-code').textContent = cert.certificate_code;
            
            // Open modal
            const certModal = new bootstrap.Modal(document.getElementById('certificateModal'));
            certModal.show();
        } else {
            showToast("Certificate Error", "Invalid tracking code context.", "warning");
        }
    } catch (error) {
        console.error("Fetch certificate error:", error);
    }
}

// Toggle donor availability
async function toggleDonorAvailabilityState(checked) {
    const token = getAuthToken();
    const status = checked ? 1 : 0;
    
    // Visual indicators
    const pulseDot = document.getElementById('availability-pulse-dot');
    const label = document.getElementById('availability-label-text');
    
    if (pulseDot && label) {
        if (checked) {
            pulseDot.className = "pulse-indicator-green";
            label.textContent = "ONLINE & AVAILABLE";
        } else {
            pulseDot.className = "pulse-indicator-red";
            label.textContent = "OFFLINE (COOLDOWN)";
        }
    }
    
    try {
        const response = await fetch(`${API_BASE}/user/toggle-availability`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ is_available: status })
        });
        const result = await response.json();
        showToast("Status Synchronized", result.message, checked ? "success" : "warning");
    } catch (error) {
        console.error("Toggle availability error:", error);
    }
}


// --- ADMINISTRATOR PORTAL INTERACTIVITIES ---
let adminDemandChart = null;
let adminForecastChart = null;

async function loadAdminAnalytics() {
    const token = getAuthToken();
    if (!token) return;

    // Show loading spinners in tables while fetching
    const usersTbody = document.getElementById('admin-users-table-body');
    const reqsTbody = document.getElementById('admin-requests-table-body');
    
    try {
        const response = await fetch(`${API_BASE}/admin/analytics`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const result = await response.json();
        
        if (result.status !== 'success') {
            const errMsg = result.message || 'Unknown error from server.';
            showToast('Admin Dashboard Error', errMsg, 'warning');
            if (usersTbody) usersTbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger"><i class="fa-solid fa-circle-xmark me-2"></i>${errMsg}</td></tr>`;
            if (reqsTbody) reqsTbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger"><i class="fa-solid fa-circle-xmark me-2"></i>Could not load requests.</td></tr>`;
            return;
        }
        
        const data = result.data;
        
        // Populate stats counts
        document.getElementById('admin-stat-users').textContent = data.statistics.total_users;
        document.getElementById('admin-stat-donors').textContent = data.statistics.total_donors;
        document.getElementById('admin-stat-online').textContent = data.statistics.available_donors;
        document.getElementById('admin-stat-saved').textContent = data.statistics.total_units_donated * 3 || '-'; // simulated lives saved multiplier
        
        // Populate users database table
        const usersTbody = document.getElementById('admin-users-table-body');
        if (usersTbody) {
            usersTbody.innerHTML = '';
            data.users_grid.forEach(u => {
                let roleBadge = `<span class="badge bg-secondary">${u.role.toUpperCase()}</span>`;
                if (u.role === 'donor') roleBadge = `<span class="badge bg-success">DONOR</span>`;
                else if (u.role === 'admin') roleBadge = `<span class="badge bg-danger">ADMIN</span>`;
                
                usersTbody.innerHTML += `
                    <tr>
                        <td class="fw-bold">UID-${u.id}</td>
                        <td>${u.name}</td>
                        <td>${roleBadge}</td>
                        <td>${u.phone}</td>
                        <td class="text-secondary">${u.email}</td>
                    </tr>
                `;
            });
        }
        
        // Populate requests history table
        const reqsTbody = document.getElementById('admin-requests-table-body');
        if (reqsTbody) {
            reqsTbody.innerHTML = '';
            data.recent_requests_grid.forEach(r => {
                let pBadge = 'priority-badge priority-medium';
                if (r.priority === 'Critical') pBadge = 'priority-badge priority-critical';
                else if (r.priority === 'High') pBadge = 'priority-badge priority-high';
                
                reqsTbody.innerHTML += `
                    <tr>
                        <td class="fw-bold">REQ-${r.id}</td>
                        <td>${r.patient_name}</td>
                        <td class="text-danger fw-bold">${r.blood_group}</td>
                        <td>${r.units_needed} Units</td>
                        <td><span class="${pBadge}">${r.priority}</span></td>
                        <td><span class="badge bg-light text-dark">${r.status}</span></td>
                    </tr>
                `;
            });
        }
        
        // Populate duplicate request alerts (Fraud)
        const fraudTbody = document.getElementById('admin-fraud-table-body');
        const fraudBadge = document.getElementById('fraud-total-alerts-badge');
        const spamSidebarBadge = document.getElementById('sidebar-spam-badge');
        
        if (fraudTbody) {
            fraudTbody.innerHTML = '';
            
            if (data.fraud_spam_alerts.warnings_count === 0) {
                fraudTbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-secondary"><i class="fa-solid fa-circle-check text-success me-2"></i>Safe. No duplicate fraud clusters recorded.</td></tr>`;
                if (fraudBadge) fraudBadge.className = "badge bg-success text-white rounded-full fs-8 px-3 py-1";
                if (spamSidebarBadge) spamSidebarBadge.classList.add('d-none');
            } else {
                if (spamSidebarBadge) {
                    spamSidebarBadge.textContent = data.fraud_spam_alerts.warnings_count;
                    spamSidebarBadge.classList.remove('d-none');
                }
                if (fraudBadge) {
                    fraudBadge.className = "badge bg-danger text-white rounded-full fs-8 px-3 py-1";
                    fraudBadge.textContent = `${data.fraud_spam_alerts.warnings_count} Suspicious Alerts`;
                }
                
                data.fraud_spam_alerts.suspicious_accounts.forEach(f => {
                    fraudTbody.innerHTML += `
                        <tr>
                            <td class="fw-bold">PAT-${f.patient_id}</td>
                            <td class="fw-bold text-danger">${f.request_count} Requests</td>
                            <td>${f.last_time}</td>
                            <td><span class="priority-badge priority-critical">DUPLICATE SPAM</span></td>
                            <td class="text-end">
                                <button class="btn btn-sm btn-outline-danger py-1" onclick="alert('Action simulated. Patient account has been restricted!')">
                                    Restrict account
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }
        }
        
        // DRAW CHART 1 & CHART 2
        plotAdminAnalyticsCharts(data.blood_demand_forecasts);
        
    } catch (error) {
        console.error("Load admin analytics error:", error);
        showToast("Connection Error", "Could not connect to the Flask API server. Ensure it is running.", "warning");
        const usersTbodyErr = document.getElementById('admin-users-table-body');
        const reqsTbodyErr = document.getElementById('admin-requests-table-body');
        if (usersTbodyErr) usersTbodyErr.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger"><i class="fa-solid fa-wifi me-2"></i>Connection failed. Is the server running?</td></tr>`;
        if (reqsTbodyErr) reqsTbodyErr.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger"><i class="fa-solid fa-wifi me-2"></i>Connection failed.</td></tr>`;
    }
}

// Chart.js double chart plotters
function plotAdminAnalyticsCharts(forecasts) {
    const bgLabels = forecasts.map(f => f.blood_group);
    
    // Chart 1: Supply Levels vs Outstanding Requests
    const ctx1 = document.getElementById('bloodSupplyDemandChart');
    if (ctx1) {
        const supplyData = forecasts.map(f => f.current_supply_count);
        const outstandingData = forecasts.map(f => f.outstanding_requests_units);
        
        if (adminDemandChart) adminDemandChart.destroy();
        
        adminDemandChart = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: bgLabels,
                datasets: [
                    {
                        label: 'Online Compatible Donors Supply',
                        data: supplyData,
                        backgroundColor: '#10b981',
                        borderRadius: 4
                    },
                    {
                        label: 'Outstanding Requested Units',
                        data: outstandingData,
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }
    
    // Chart 2: AI Forecasting Chart (Ridge Regression outputs)
    const ctx2 = document.getElementById('bloodForecastChart');
    if (ctx2) {
        const forecastData = forecasts.map(f => f.ai_forecasted_demand_units);
        
        if (adminForecastChart) adminForecastChart.destroy();
        
        adminForecastChart = new Chart(ctx2, {
            type: 'line',
            data: {
                labels: bgLabels,
                datasets: [{
                    label: 'Predicted Needed Units (Next Month)',
                    data: forecastData,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#d97706',
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }
}


// --- FLOATING AI CHATBOT SYSTEM ---

function initChatbot() {
    const trigger = document.getElementById('chatbot-trigger');
    const window = document.getElementById('chatbot-window');
    const closeBtn = document.getElementById('chatbot-close-btn');
    
    if (!trigger || !window || !closeBtn) return;
    
    trigger.addEventListener('click', () => {
        window.classList.toggle('active');
        if (window.classList.contains('active')) {
            // Trigger welcome if empty
            const msgs = document.getElementById('chatbot-messages');
            if (msgs && msgs.innerHTML === '') {
                sendChatbotQuery('');
            }
        }
    });
    
    closeBtn.addEventListener('click', () => {
        window.classList.remove('active');
    });
    
    // Send message triggers
    const input = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send-btn');
    
    if (sendBtn && input) {
        sendBtn.addEventListener('click', () => {
            const query = input.value.trim();
            if (query) {
                appendChatMessage("user", query);
                sendChatbotQuery(query);
                input.value = '';
            }
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const query = input.value.trim();
                if (query) {
                    appendChatMessage("user", query);
                    sendChatbotQuery(query);
                    input.value = '';
                }
            }
        });
    }
}

async function sendChatbotQuery(query) {
    try {
        const response = await fetch(`${API_BASE}/chatbot`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: query })
        });
        const result = await response.json();
        
        // Append bot reply
        appendChatMessage("bot", result.response);
        
        // Populate quick tips suggestions
        const tipsContainer = document.getElementById('chatbot-tips');
        if (tipsContainer) {
            tipsContainer.innerHTML = '';
            result.tips.forEach(tip => {
                tipsContainer.innerHTML += `
                    <button class="chatbot-tip-btn" onclick="triggerQuickTipQuery('${tip.replace(/'/g, "\\'")}')">
                        ${tip}
                    </button>
                `;
            });
        }
    } catch (error) {
        console.error("Chatbot query error:", error);
    }
}

function triggerQuickTipQuery(tipText) {
    appendChatMessage("user", tipText);
    sendChatbotQuery(tipText);
}

function appendChatMessage(sender, text) {
    const msgs = document.getElementById('chatbot-messages');
    if (!msgs) return;
    
    const msg = document.createElement('div');
    msg.className = `chat-message ${sender}`;
    
    // If bot, support rich HTML details
    if (sender === 'bot') {
        // Simple markdown links or line break translates
        let processedText = text
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Map headers
        if (processedText.includes('###')) {
            processedText = processedText.replace(/### (.*?)(<br>|$)/g, '<h5>$1</h5>');
        }
        
        msg.innerHTML = processedText;
    } else {
        msg.textContent = text;
    }
    
    msgs.appendChild(msg);
    msgs.scrollTop = msgs.scrollHeight;
}

// --- VOICE SEARCH (WEB SPEECH RECOGNITION INTERFACE) ---

function initVoiceSpeechSearch() {
    const micBtn = document.getElementById('chatbot-mic-btn');
    const input = document.getElementById('chatbot-input');
    
    if (!micBtn || !input) return;
    
    // Check compatibility
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        micBtn.style.display = 'none'; // hide if not supported
        return;
    }
    
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    
    micBtn.addEventListener('click', () => {
        if (micBtn.classList.contains('active')) {
            recognition.stop();
        } else {
            micBtn.classList.add('active');
            showToast("Voice Recognition Active", "Speak your blood question clearly...", "info");
            recognition.start();
        }
    });
    
    recognition.addEventListener('result', (e) => {
        const transcript = e.results[0][0].transcript;
        input.value = transcript;
        showToast("Voice Transcribed!", `Searching for: "${transcript}"`, "success");
        
        // Auto trigger search
        appendChatMessage("user", transcript);
        sendChatbotQuery(transcript);
        input.value = '';
    });
    
    recognition.addEventListener('speechend', () => {
        recognition.stop();
    });
    
    recognition.addEventListener('end', () => {
        micBtn.classList.remove('active');
    });
    
    recognition.addEventListener('error', (e) => {
        console.error("Speech Recognition error:", e.error);
        micBtn.classList.remove('active');
        showToast("Speech Error", `Could not recognize audio: ${e.error}`, "warning");
    });
}

// --- COMMON UTIL MATHS HELPERS ---

// Haversine formula — calculates geodetic distance in km between two lat/lon points
function haversine(lat1, lon1, lat2, lon2) {
    if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return 9999.0;
    const R = 6371.0; // Earth's radius in kilometers
    const toRad = (deg) => deg * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

function round(num, decimals) {
    const t = Math.pow(10, decimals);
    return Math.round(num * t) / t;
}

// Seed copy of compatibility to match backend calculations without API delays
const ai_models = {
    is_blood_compatible: function(donor_bg, patient_bg) {
        const map = {
            'A+': ['A+', 'A-', 'O+', 'O-'],
            'A-': ['A-', 'O-'],
            'B+': ['B+', 'B-', 'O+', 'O-'],
            'B-': ['B-', 'O-'],
            'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
            'AB-': ['A-', 'B-', 'AB-', 'O-'],
            'O+': ['O+', 'O-'],
            'O-': ['O-']
        };
        if (donor_bg === patient_bg) return 100;
        if (map[patient_bg] && map[patient_bg].includes(donor_bg)) return 70;
        return 0;
    }
};

// --- VOLUNTARY DONATION ENGINE ---

async function populateVoluntaryHospitals() {
    const select = document.getElementById('vol-hospital');
    const customGroup = document.getElementById('custom-hospital-input-group');
    const customInput = document.getElementById('vol-custom-hospital');
    if (!select) return;
    
    select.addEventListener('change', (e) => {
        if (e.target.value === 'custom') {
            customGroup.classList.remove('d-none');
            customInput.required = true;
        } else {
            customGroup.classList.add('d-none');
            customInput.required = false;
            customInput.value = '';
        }
    });

    try {
        const response = await fetch(`${API_BASE}/hospitals`);
        const result = await response.json();
        
        select.innerHTML = '<option value="" disabled selected>Select accredited center...</option>';
        
        if (result.status === 'success' && result.data.length > 0) {
            result.data.forEach(h => {
                select.innerHTML += `<option value="${h.name}">${h.name} (${h.type})</option>`;
            });
        }
        
        select.innerHTML += '<option value="custom">Other / Custom Center...</option>';
    } catch (error) {
        console.error("Failed to load voluntary hospitals:", error);
        select.innerHTML = '<option value="custom">Other / Custom Center...</option>';
        customGroup.classList.remove('d-none');
        customInput.required = true;
    }
}

function setupVoluntaryDonationSubmission() {
    const form = document.getElementById('voluntary-donation-form');
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const token = getAuthToken();
        if (!token) return;
        
        const select = document.getElementById('vol-hospital');
        const customInput = document.getElementById('vol-custom-hospital');
        const unitsInput = document.getElementById('vol-units');
        const dateInput = document.getElementById('vol-date');
        
        let hospitalName = select.value;
        if (hospitalName === 'custom') {
            hospitalName = customInput.value.trim();
        }
        
        const units = parseInt(unitsInput.value);
        const donation_date = dateInput.value;
        
        showToast("Fulfilling Donation", "Logging voluntary transaction and generating certificate...", "info");
        
        try {
            const response = await fetch(`${API_BASE}/donor/voluntary-donate`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    hospital_name: hospitalName,
                    units: units,
                    donation_date: donation_date
                })
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                showToast("Donation Recorded!", result.message, "success");
                
                form.reset();
                select.value = '';
                customInput.value = '';
                document.getElementById('custom-hospital-input-group').classList.add('d-none');
                customInput.required = false;
                if (dateInput) {
                    dateInput.value = new Date().toISOString().split('T')[0];
                }
                
                loadDonorAlerts();
                loadDonorHistory();
                fetchDonorUpdatedProfile(token);
                
                setTimeout(() => {
                    triggerDonationCertificateModal(result.data.certificate_code);
                }, 1200);
            } else {
                showToast("Transaction Failed", result.message, "warning");
            }
        } catch (error) {
            console.error("Voluntary donation submit error:", error);
            showToast("Connection Error", "Could not connect to Flask API server.", "warning");
        }
    });
}
