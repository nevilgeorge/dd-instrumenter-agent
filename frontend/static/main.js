// Application state
let appState = {
    repository: '',
    authStatus: { authenticated: false },
    currentStep: 1,
    repositoryAccessible: false,
    pendingRepository: null // Store repo URL when auth is needed
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    handleUrlParams();
});

// Initialize application
async function initializeApp() {
    // Restore pending repository from localStorage if exists
    const storedRepo = localStorage.getItem('pendingRepository');
    if (storedRepo) {
        appState.pendingRepository = storedRepo;
        document.getElementById('repository').value = storedRepo;
        appState.repository = cleanRepositoryUrl(storedRepo);
    }
    
    await checkAuthStatus();
    setupEventListeners();
    updateUI();
}

// Check authentication status
async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/status');
        appState.authStatus = await response.json();
        updateAuthSection();
        
        // If we're authenticated and have a pending repository, restore it and proceed
        if (appState.authStatus.authenticated && appState.pendingRepository) {
            appState.repository = appState.pendingRepository;
            appState.pendingRepository = null;
            localStorage.removeItem('pendingRepository');
            
            // Update UI to show repository is entered
            if (appState.currentStep === 1 && appState.repository) {
                updateStepStatus(1, 'completed');
                enableStep(2);
                appState.currentStep = 2;
            }
            
            // Since we're authenticated, directly proceed to step 3
            if (appState.repository && appState.currentStep === 2) {
                proceedToStep3();
            }
        }
        
        // If we're authenticated and have a repository but no pending repo, enable step 3
        if (appState.authStatus.authenticated && appState.repository && appState.currentStep === 2) {
            proceedToStep3();
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    const repositoryInput = document.getElementById('repository');
    const confirmBtn = document.getElementById('confirmBtn');
    
    // Repository input change handler
    repositoryInput.addEventListener('input', function() {
        appState.repository = cleanRepositoryUrl(this.value.trim());
        updateUI();
    });
    
    // Repository input enter key handler
    repositoryInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && appState.repository) {
            proceedToStep2();
        }
    });
    
    // Confirm button handler
    confirmBtn.addEventListener('click', instrumentRepository);
}

// Clean repository URL to get owner/repo format
function cleanRepositoryUrl(repository) {
    let cleanRepo = repository.trim();
    
    // Handle different repository URL formats
    if (cleanRepo.startsWith('https://github.com/')) {
        cleanRepo = cleanRepo.replace('https://github.com/', '');
    } else if (cleanRepo.startsWith('github.com/')) {
        cleanRepo = cleanRepo.replace('github.com/', '');
    }
    
    // Remove .git suffix if present
    if (cleanRepo.endsWith('.git')) {
        cleanRepo = cleanRepo.slice(0, -4);
    }
    
    return cleanRepo;
}

// Proceed to step 2 after repository is entered
async function proceedToStep2() {
    if (!appState.repository) return;
    
    // Mark step 1 as completed
    updateStepStatus(1, 'completed');
    
    // Enable step 2
    enableStep(2);
    appState.currentStep = 2;
    
    // Check if repository is accessible
    await checkRepositoryAccess();
    
    updateUI();
}

// Check if repository is accessible
async function checkRepositoryAccess() {
    try {
        const response = await fetch(`/check-access?repository=${encodeURIComponent(appState.repository)}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            // Repository is accessible and can be instrumented
            appState.repositoryAccessible = true;
            proceedToStep3();
        } else if (response.status === 403) {
            // Repository requires authentication
            const data = await response.json();
            
            // Store the repository URL for after authentication
            localStorage.setItem('pendingRepository', appState.repository);
            appState.pendingRepository = appState.repository;
            
            showAuthenticationRequired(data);
        } else if (response.status === 503) {
            // Repository not found or requires authentication
            const data = await response.json();
            if (appState.authStatus.authenticated) {
                // Already authenticated but still can't access - show error
                showError('Repository not found or you don\'t have access to it.');
            } else {
                // Need authentication - store repository URL
                localStorage.setItem('pendingRepository', appState.repository);
                appState.pendingRepository = appState.repository;
                
                showAuthenticationRequired(data);
            }
        } else {
            // Other error
            const data = await response.json();
            showError(data.detail || 'Error accessing repository');
        }
    } catch (error) {
        console.error('Error checking repository access:', error);
        showError('Error checking repository access');
    }
}

// Show authentication required in step 2
function showAuthenticationRequired(data) {
    const authButton = document.getElementById('authButton');
    const githubAuthLink = document.getElementById('githubAuthLink');
    
    // Set up the authentication URL
    githubAuthLink.href = `/auth/github?repository=${encodeURIComponent(appState.repository)}`;
    
    // Show the authentication button
    authButton.style.display = 'block';
    
    // Update step 2 status
    updateStepStatus(2, 'current');
    
    // Show helpful message
    const authSection = document.getElementById('authSection');
    authSection.innerHTML = `
        <div class="auth-status needs-auth">
            <span>🔒</span>
            <span>This repository requires authentication. Click "Authenticate with GitHub" to proceed.</span>
        </div>
    `;
}

// Proceed to step 3 (confirmation)
function proceedToStep3() {
    // Mark step 2 as completed
    updateStepStatus(2, 'completed');
    
    // Enable step 3
    enableStep(3);
    updateStepStatus(3, 'current');
    appState.currentStep = 3;
    
    // Hide auth button since we're authenticated
    const authButton = document.getElementById('authButton');
    authButton.style.display = 'none';
    
    updateUI();
}

// Instrument the repository (step 3)
async function instrumentRepository() {
    const confirmBtn = document.getElementById('confirmBtn');
    const resultDiv = document.getElementById('result');
    
    // Show loading state
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Processing...';
    
    resultDiv.innerHTML = `
        <div class="result loading">
            <div class="spinner"></div>
            <div>Analyzing repository and instrumenting with Datadog...</div>
            <div style="margin-top: 8px; font-size: 12px;">This may take a few minutes.</div>
        </div>
    `;
    
    try {
        const additionalContext = document.getElementById('additionalContext').value.trim();
        const response = await fetch(`/instrument?repository=${encodeURIComponent(appState.repository)}&additional_context=${encodeURIComponent(additionalContext)}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Success
            showSuccess(data);
            updateStepStatus(3, 'completed');
            
            // Clear any stored pending repository
            localStorage.removeItem('pendingRepository');
        } else if (response.status === 403) {
            // Authentication required - redirect to auth
            localStorage.setItem('pendingRepository', appState.repository);
            window.location.href = `/auth/github?repository=${encodeURIComponent(appState.repository)}`;
        } else {
            // Error
            showError(data.detail || 'Error instrumenting repository');
        }
    } catch (error) {
        console.error('Error instrumenting repository:', error);
        showError('Error instrumenting repository');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Instrument Lambda Function';
    }
}

// Show success result
function showSuccess(data) {
    const resultDiv = document.getElementById('result');
    
    let successHtml = `
        <div class="result success">
            <h4 style="margin: 0 0 12px 0; color: #155724;">✅ Successfully instrumented repository!</h4>
    `;
    
    if (data.analysis) {
        successHtml += `
            <div style="margin-bottom: 12px;">
                <strong>📊 Analysis Results:</strong><br>
                • Repository Type: ${data.analysis.type}<br>
                • Confidence: ${Math.round(data.analysis.confidence * 100)}%<br>
                • Runtime: ${data.analysis.runtime}
        `;
        
        if (data.analysis.evidence && data.analysis.evidence.length > 0) {
            successHtml += `<br>• Evidence: ${data.analysis.evidence.join(', ')}`;
        }
        
        successHtml += `</div>`;
    }
    
    if (data.pull_request) {
        successHtml += `
            <div style="margin-bottom: 12px;">
                <strong>🔗 Pull Request Created:</strong><br>
                • Title: ${data.pull_request.title}<br>
                • Branch: ${data.pull_request.branch}<br>
                • Status: ${data.pull_request.status}
            </div>
        `;
        
        if (data.pull_request.files_changed && data.pull_request.files_changed.length > 0) {
            successHtml += `
                <div style="margin: 8px; font-size: 12px;">
                    <strong>📁 Files Modified:</strong><br>
                    ${data.pull_request.files_changed.map(file => `• ${file.split('/').pop()}`).join('<br>')}
                </div>
            `;
        }

        if (data.pull_request.pr_url) {
            successHtml += `
                <a href="${data.pull_request.pr_url}" target="_blank" class="pr-link">
                    View Pull Request →
                </a>
            `;
        }

        if (data.next_steps && data.next_steps.length > 0) {
            successHtml += `
                <div style="margin-top: 16px;">
                    <div style="font-weight: 600; margin-bottom: 8px;">Next Steps:</div>
                    <ol style="margin-left: 20px; color: #495057;">
                        ${data.next_steps.map(step => `<li>${simpleFormat(step)}</li>`).join('')}
                    </ol>
                </div>
            `;
        }
    }
    
    if (data.completed_at) {
        successHtml += `
            <div style="margin-top: 12px; font-size: 12px; color: #6c757d;">
                ⏱️ Completed at: ${data.completed_at}
            </div>
        `;
    }

    successHtml += `</div>`;
    resultDiv.innerHTML = successHtml;
}

// Show error result
function showError(message) {
    const resultDiv = document.getElementById('result');
    resultDiv.innerHTML = `
        <div class="result error">
            <strong>❌ Error:</strong> ${message}
        </div>
    `;
}

// Update step status (completed, current, disabled)
function updateStepStatus(stepNumber, status) {
    const stepElement = document.getElementById(`step${stepNumber}`);
    const stepNumberElement = document.getElementById(`step${stepNumber}-number`);
    
    // Remove all status classes
    stepNumberElement.classList.remove('completed', 'current');
    
    // Add new status class
    if (status === 'completed') {
        stepNumberElement.classList.add('completed');
        stepNumberElement.textContent = '✓';
    } else if (status === 'current') {
        stepNumberElement.classList.add('current');
        stepNumberElement.textContent = stepNumber;
    } else {
        stepNumberElement.textContent = stepNumber;
    }
}

function simpleFormat(str) {
    return str.replace(/`([^`]+)`/g, '<code>$1</code>');
}

// Enable a step
function enableStep(stepNumber) {
    const stepElement = document.getElementById(`step${stepNumber}`);
    stepElement.classList.remove('disabled');
}

// Update authentication section
function updateAuthSection() {
    const authSection = document.getElementById('authSection');
    
    if (appState.authStatus.authenticated) {
        authSection.innerHTML = `
            <div class="auth-status authenticated">
                <span>✅</span>
                <span>Authenticated as <strong>${appState.authStatus.username}</strong></span>
            </div>
        `;
    } else {
        authSection.innerHTML = `
            <div class="auth-status not-authenticated">
                <span>ℹ️</span>
                <span>Not authenticated - only public repositories will work</span>
            </div>
        `;
    }
}

// Update UI based on current state
function updateUI() {
    // If repository is entered and we're on step 1, proceed to step 2
    if (appState.repository && appState.currentStep === 1) {
        proceedToStep2();
    }
    
    // If authenticated OR repository accessible, enable step 3
    if ((appState.authStatus.authenticated || appState.repositoryAccessible) && appState.currentStep === 2) {
        proceedToStep3();
    }
}

// Handle URL parameters (for OAuth callbacks)
function handleUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const auth = urlParams.get('auth');
    const repository = urlParams.get('repository');
    const message = urlParams.get('message');
    
    if (auth === 'success') {
        // Authentication successful
        
        // Re-check auth status and proceed
        setTimeout(async () => {
            await checkAuthStatus();
            
            // Show success message temporarily
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = `
                <div class="result success">
                    ✅ Authentication successful! 
                    ${appState.repository ? 'Proceeding with repository instrumentation...' : 'You can now instrument private repositories.'}
                </div>
            `;
            
            // If we have a repository and we're authenticated, automatically proceed to step 3
            if (appState.repository && appState.authStatus.authenticated) {
                setTimeout(() => {
                    // Clear the success message and proceed
                    resultDiv.innerHTML = '';
                    // Always proceed to step 3 if authenticated, regardless of repositoryAccessible
                    proceedToStep3();
                }, 2000);
            } else {
                // Clear the message after 3 seconds
                setTimeout(() => {
                    resultDiv.innerHTML = '';
                }, 3000);
            }
        }, 500);
        
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (auth === 'error') {
        showError(`Authentication failed: ${message || 'Unknown error'}`);
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
    }
} 