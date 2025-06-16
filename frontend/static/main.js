// Authentication status
let authStatus = { authenticated: false };

// Check authentication status on page load
async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/status');
        authStatus = await response.json();
        updateAuthUI();
    } catch (error) {
        console.error('Error checking auth status:', error);
    }
}

// Update authentication UI
function updateAuthUI() {
    const authSection = document.getElementById('authSection');
    if (authStatus.authenticated) {
        authSection.innerHTML = `
            <div class="auth-status authenticated">
                <span class="auth-icon">✅</span>
                <span>Authenticated as <strong>${authStatus.username}</strong></span>
                <button onclick="logout()" class="logout-btn">Logout</button>
            </div>
        `;
    } else {
        authSection.innerHTML = `
            <div class="auth-status not-authenticated">
                <span class="auth-icon">ℹ️</span>
                <span>Not authenticated - only public repositories will work</span>
            </div>
        `;
    }
}

// Logout function
async function logout() {
    try {
        await fetch('/auth/logout', { method: 'POST' });
        authStatus = { authenticated: false };
        updateAuthUI();
        showMessage('Successfully logged out', 'success');
    } catch (error) {
        console.error('Error logging out:', error);
        showMessage('Error logging out', 'error');
    }
}

// Show authentication flow
function showAuthFlow(repository, authUrl) {
    const resultDiv = document.getElementById('result');
    resultDiv.innerHTML = `
        <div class="result auth-required">
            <h3>🔒 Authentication Required</h3>
            <p>You don't have access to the repository <strong>${repository}</strong>.</p>
            <p>Please authenticate with GitHub to grant access:</p>
            <div style="text-align: center; margin: 20px 0;">
                <a href="${authUrl}" class="auth-btn">
                    🔗 Authenticate with GitHub
                </a>
            </div>
            <p class="auth-note" style="font-size: 14px; color: #666; text-align: center;">
                This will redirect you to GitHub for secure authentication. 
                You'll be redirected back here after authorization.
            </p>
        </div>
    `;
}

// Show message function
function showMessage(message, type) {
    const resultDiv = document.getElementById('result');
    resultDiv.innerHTML = `
        <div class="result ${type}">
            <p>${message}</p>
        </div>
    `;
}

// Handle URL parameters (for OAuth callbacks)
function handleUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const auth = urlParams.get('auth');
    const repository = urlParams.get('repository');
    const message = urlParams.get('message');
    
    if (auth === 'success') {
        showMessage(`✅ Authentication successful! You can now instrument ${repository}`, 'success');
        // Re-check auth status
        checkAuthStatus();
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (auth === 'error') {
        showMessage(`❌ Authentication failed: ${message || 'Unknown error'}`, 'error');
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
    }
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

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('instrumentForm');
    const submitBtn = document.getElementById('submitBtn');
    const resultDiv = document.getElementById('result');

    // Initialize authentication status
    checkAuthStatus();
    handleUrlParams();

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const repository = document.getElementById('repository').value;
        const cleanRepo = cleanRepositoryUrl(repository);
        
        // Show loading state
        submitBtn.disabled = true;
        submitBtn.textContent = 'Processing...';
        
        resultDiv.innerHTML = `
            <div class="result loading">
                <div class="spinner"></div>
                <div>Analyzing repository and instrumenting with Datadog...</div>
                <div style="margin-top: 10px; font-size: 14px;">This may take a few minutes.</div>
            </div>
        `;
        
        try {
            const response = await fetch(`/instrument?repository=${encodeURIComponent(cleanRepo)}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Success
                let successMessage = `✅ Successfully instrumented repository: ${cleanRepo}\n\n`;
                
                if (data.analysis) {
                    successMessage += `📊 Analysis Results:\n`;
                    successMessage += `- Repository Type: ${data.analysis.type}\n`;
                    successMessage += `- Confidence: ${Math.round(data.analysis.confidence * 100)}%\n`;
                    successMessage += `- Runtime: ${data.analysis.runtime}\n`;
                    if (data.analysis.evidence && data.analysis.evidence.length > 0) {
                        successMessage += `- Evidence: ${data.analysis.evidence.join(', ')}\n`;
                    }
                    successMessage += `\n`;
                }
                
                if (data.pull_request) {
                    successMessage += `🔗 Pull Request Created:\n`;
                    successMessage += `- URL: ${data.pull_request.pr_url}\n`;
                    successMessage += `- Title: ${data.pull_request.title}\n`;
                    successMessage += `- Branch: ${data.pull_request.branch}\n`;
                    successMessage += `- Status: ${data.pull_request.status}\n`;
                    
                    if (data.pull_request.files_changed) {
                        successMessage += `\n📁 Files Modified:\n`;
                        data.pull_request.files_changed.forEach(file => {
                            successMessage += `- ${file}\n`;
                        });
                    }
                }
                
                successMessage += `\n⏱️ Completed at: ${data.completed_at}`;
                
                resultDiv.innerHTML = `<div class="result success">${successMessage}</div>`;
                
                // If there's a PR URL, make it clickable
                if (data.pull_request && data.pull_request.pr_url) {
                    const link = document.createElement('a');
                    link.href = data.pull_request.pr_url;
                    link.target = '_blank';
                    link.style.color = '#155724';
                    link.style.textDecoration = 'underline';
                    link.textContent = 'Open Pull Request →';
                    
                    const linkDiv = document.createElement('div');
                    linkDiv.style.marginTop = '15px';
                    linkDiv.style.textAlign = 'center';
                    linkDiv.appendChild(link);
                    
                    resultDiv.appendChild(linkDiv);
                }
                
            } else if (response.status === 403 && data.error === 'repository_access_denied') {
                // Authentication required
                showAuthFlow(cleanRepo, data.auth_url);
            } else {
                // Other errors
                resultDiv.innerHTML = `
                    <div class="result error">
                        ❌ Error: ${data.detail || data.message || 'Unknown error occurred'}
                    </div>
                `;
            }
            
        } catch (error) {
            // Network or other error
            resultDiv.innerHTML = `
                <div class="result error">
                    ❌ Error: Failed to connect to server. Please try again.
                    
                    Details: ${error.message}
                </div>
            `;
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.textContent = 'Instrument Repository';
        }
    });
    
    // Add some example repositories
    const repositoryInput = document.getElementById('repository');
    repositoryInput.addEventListener('focus', function() {
        if (!this.value) {
            this.placeholder = 'e.g., aws-samples/cdk-typescript-lambda';
        }
    });
}); 