// Narrative Factory Web Interface JavaScript

class NarrativeFactoryUI {
    constructor() {
        this.currentJobId = null;
        this.progressInterval = null;
        this.apiBase = '/api';
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadRecentJobs();
        this.setupFileUpload();
    }
    
    setupEventListeners() {
        // Form submission
        const form = document.getElementById('uploadForm');
        form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // File input change
        const fileInput = document.getElementById('files');
        fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        
        // Drag and drop
        const fileWrapper = document.querySelector('.file-input-wrapper');
        fileWrapper.addEventListener('dragover', (e) => this.handleDragOver(e));
        fileWrapper.addEventListener('drop', (e) => this.handleDrop(e));
    }
    
    setupFileUpload() {
        const fileInput = document.getElementById('files');
        const fileList = document.getElementById('fileList');
        
        // Update display when files are selected
        fileInput.addEventListener('change', () => {
            this.updateFileList();
        });
    }
    
    handleDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('drag-over');
    }
    
    handleDrop(e) {
        e.preventDefault();
        e.currentTarget.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        const fileInput = document.getElementById('files');
        fileInput.files = files;
        this.updateFileList();
    }
    
    handleFileSelection(e) {
        this.updateFileList();
    }
    
    updateFileList() {
        const fileInput = document.getElementById('files');
        const fileList = document.getElementById('fileList');
        const files = Array.from(fileInput.files);
        
        if (files.length === 0) {
            fileList.innerHTML = '';
            return;
        }
        
        fileList.innerHTML = files.map((file, index) => `
            <div class="file-item">
                <div class="file-info">
                    <span class="file-name">📄 ${file.name}</span>
                    <span class="file-size">${this.formatFileSize(file.size)}</span>
                </div>
                <button type="button" class="file-remove" onclick="ui.removeFile(${index})">
                    Remove
                </button>
            </div>
        `).join('');
        
        // Update file input display
        const fileText = document.querySelector('.file-text');
        fileText.textContent = `${files.length} file(s) selected`;
    }
    
    removeFile(index) {
        const fileInput = document.getElementById('files');
        const files = Array.from(fileInput.files);
        
        // Create new file list without the removed file
        const dt = new DataTransfer();
        files.forEach((file, i) => {
            if (i !== index) {
                dt.items.add(file);
            }
        });
        
        fileInput.files = dt.files;
        this.updateFileList();
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const files = formData.getAll('files');
        
        if (files.length === 0 || files[0].size === 0) {
            this.showToast('Please select at least one file', 'error');
            return;
        }
        
        // Disable submit button
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="btn-icon">⏳</span> Uploading...';
        
        try {
            const response = await fetch(`${this.apiBase}/ingestion/upload`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }
            
            const result = await response.json();
            this.currentJobId = result.job_id;
            
            this.showToast(`Upload successful! Processing ${result.files_count} files.`, 'success');
            this.showProgressSection();
            this.startProgressTracking();
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showToast(`Upload failed: ${error.message}`, 'error');
        } finally {
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span class="btn-icon">🚀</span> Start Processing';
        }
    }
    
    showProgressSection() {
        document.getElementById('progressSection').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';
        document.getElementById('jobId').textContent = this.currentJobId;
        
        // Scroll to progress section
        document.getElementById('progressSection').scrollIntoView({ 
            behavior: 'smooth' 
        });
    }
    
    startProgressTracking() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        // Update progress immediately
        this.updateProgress();
        
        // Set up interval for regular updates
        this.progressInterval = setInterval(() => {
            this.updateProgress();
        }, 2000); // Update every 2 seconds
    }
    
    async updateProgress() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`${this.apiBase}/ingestion/progress/${this.currentJobId}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch progress');
            }
            
            const progress = await response.json();
            this.displayProgress(progress);
            
            // Check if job is complete
            if (progress.status === 'completed' || progress.status === 'failed') {
                clearInterval(this.progressInterval);
                this.progressInterval = null;
                
                if (progress.status === 'completed') {
                    await this.loadResults();
                } else {
                    this.showToast('Processing failed', 'error');
                }
                
                // Refresh recent jobs
                this.loadRecentJobs();
            }
            
        } catch (error) {
            console.error('Progress update error:', error);
        }
    }
    
    displayProgress(progress) {
        // Update progress bar
        const progressFill = document.getElementById('progressFill');
        const progressPercentage = document.getElementById('progressPercentage');
        progressFill.style.width = `${progress.progress_percentage}%`;
        progressPercentage.textContent = `${Math.round(progress.progress_percentage)}%`;
        
        // Update status
        const statusElement = document.getElementById('progressStatus');
        statusElement.textContent = progress.status;
        statusElement.className = `progress-status ${progress.status}`;
        
        // Update details
        document.getElementById('currentStage').textContent = progress.current_stage;
        document.getElementById('materialsProcessed').textContent = progress.materials_processed;
        document.getElementById('materialsRemaining').textContent = progress.materials_remaining;
        document.getElementById('estimatedTime').textContent = this.formatTime(progress.estimated_time_remaining);
        document.getElementById('progressMessage').textContent = progress.message || 'Processing...';
    }
    
    async loadResults() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`${this.apiBase}/ingestion/results/${this.currentJobId}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch results');
            }
            
            const results = await response.json();
            this.displayResults(results);
            this.showToast('Processing completed successfully!', 'success');
            
        } catch (error) {
            console.error('Results loading error:', error);
            this.showToast('Failed to load results', 'error');
        }
    }
    
    displayResults(results) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsContent = document.getElementById('resultsContent');
        
        if (results.status === 'failed') {
            resultsContent.innerHTML = `
                <div class="error-message">
                    <h4>Processing Failed</h4>
                    <p>${results.error}</p>
                </div>
            `;
        } else {
            const { results: data } = results;
            
            resultsContent.innerHTML = `
                <div class="results-summary">
                    <div class="summary-item">
                        <div class="summary-value">${data.materials_processed}</div>
                        <div class="summary-label">Materials Processed</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">${data.processing_time.toFixed(1)}s</div>
                        <div class="summary-label">Processing Time</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">$${data.cost_estimate.toFixed(3)}</div>
                        <div class="summary-label">Cost Estimate</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">${(data.average_confidence * 100).toFixed(1)}%</div>
                        <div class="summary-label">Avg Confidence</div>
                    </div>
                </div>
                
                <div class="results-details">
                    <h4>Category Distribution</h4>
                    <div class="category-chart">
                        ${Object.entries(data.category_distribution).map(([category, count]) => `
                            <div class="category-item">
                                <span class="category-name">${category}</span>
                                <span class="category-count">${count}</span>
                            </div>
                        `).join('')}
                    </div>
                    
                    ${data.cross_references_identified > 0 ? `
                        <h4>Cross-References</h4>
                        <p>${data.cross_references_identified} cross-references identified between materials.</p>
                    ` : ''}
                    
                    ${results.failed_materials && results.failed_materials.length > 0 ? `
                        <h4>Failed Materials</h4>
                        <p>${results.failed_materials.length} materials failed processing.</p>
                    ` : ''}
                </div>
            `;
        }
        
        resultsSection.style.display = 'block';
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    async loadRecentJobs() {
        try {
            const response = await fetch(`${this.apiBase}/ingestion/jobs?limit=10`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch jobs');
            }
            
            const data = await response.json();
            this.displayRecentJobs(data.jobs);
            
        } catch (error) {
            console.error('Jobs loading error:', error);
        }
    }
    
    displayRecentJobs(jobs) {
        const jobsList = document.getElementById('jobsList');
        
        if (jobs.length === 0) {
            jobsList.innerHTML = '<p class="no-jobs">No recent jobs</p>';
            return;
        }
        
        jobsList.innerHTML = jobs.map(job => `
            <div class="job-item" onclick="ui.viewJob('${job.job_id}')">
                <div class="job-info">
                    <div class="job-id-display">${job.job_id}</div>
                    <div class="job-details">
                        ${job.files_count} files • ${job.genre_context} • ${job.processing_mode}
                    </div>
                    <div class="job-details">
                        ${this.formatDate(job.created_at)}
                    </div>
                </div>
                <div class="job-status ${job.status}">
                    ${job.status} (${Math.round(job.progress_percentage)}%)
                </div>
            </div>
        `).join('');
    }
    
    async viewJob(jobId) {
        this.currentJobId = jobId;
        
        try {
            // Check if job is still running
            const progressResponse = await fetch(`${this.apiBase}/ingestion/progress/${jobId}`);
            
            if (progressResponse.ok) {
                const progress = await progressResponse.json();
                
                if (progress.status === 'processing' || progress.status === 'queued') {
                    this.showProgressSection();
                    this.startProgressTracking();
                    return;
                }
            }
            
            // Try to load results for completed jobs
            const resultsResponse = await fetch(`${this.apiBase}/ingestion/results/${jobId}`);
            
            if (resultsResponse.ok) {
                const results = await resultsResponse.json();
                this.displayResults(results);
                document.getElementById('resultsSection').style.display = 'block';
                document.getElementById('progressSection').style.display = 'none';
            }
            
        } catch (error) {
            console.error('View job error:', error);
            this.showToast('Failed to load job details', 'error');
        }
    }
    
    // Utility functions
    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    formatTime(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
            return `${Math.round(seconds / 60)}m`;
        } else {
            return `${Math.round(seconds / 3600)}h`;
        }
    }
    
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = document.getElementById('toastContainer');
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <strong>${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                <p>${message}</p>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto-remove toast
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, duration);
        
        // Click to dismiss
        toast.addEventListener('click', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }
}

// Initialize UI when DOM is loaded
let ui;
document.addEventListener('DOMContentLoaded', () => {
    ui = new NarrativeFactoryUI();
});

// Add some additional CSS for the category chart and error messages
const additionalStyles = `
.category-chart {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 1rem 0;
}

.category-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    background: var(--background);
    border-radius: 4px;
}

.category-name {
    font-weight: 500;
}

.category-count {
    background: var(--primary-color);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 1rem;
    font-size: 0.875rem;
}

.error-message {
    background: var(--error-color);
    color: white;
    padding: 1rem;
    border-radius: var(--border-radius);
    text-align: center;
}

.results-details {
    margin-top: 2rem;
}

.results-details h4 {
    margin: 1.5rem 0 0.5rem 0;
    color: var(--text-primary);
}

.drag-over .file-input-display {
    border-color: var(--primary-color) !important;
    background: rgb(37 99 235 / 0.1) !important;
}

.toast-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.toast-content p {
    margin: 0;
    color: var(--text-secondary);
}
`;

// Add additional styles to the page
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);