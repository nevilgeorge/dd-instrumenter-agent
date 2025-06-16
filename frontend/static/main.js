document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('instrumentForm');
    const submitBtn = document.getElementById('submitBtn');
    const resultDiv = document.getElementById('result');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const repository = document.getElementById('repository').value;
        
        // Clean up repository input
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
                
            } else {
                // Error from API
                resultDiv.innerHTML = `
                    <div class="result error">
                        ❌ Error: ${data.detail || 'Unknown error occurred'}
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