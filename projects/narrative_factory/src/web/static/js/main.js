// Narrative Factory Web Interface JavaScript

class NarrativeFactoryUI {
    constructor() {
        this.currentJobId = null;
        this.progressInterval = null;
        this.apiBase = '/api';
        this.websocket = null;
        this.currentTab = 'upload';
        this.isConnected = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadRecentJobs();
        this.setupFileUpload();
        this.setupTabs();
        this.setupChat();
        this.loadGenres();
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
        
        // Genre detection
        const detectGenreBtn = document.getElementById('detectGenreBtn');
        if (detectGenreBtn) {
            detectGenreBtn.addEventListener('click', () => this.detectGenre());
        }
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
                let errorMessage = 'Upload failed';
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (parseError) {
                    // If JSON parsing fails, use response text
                    const textError = await response.text();
                    errorMessage = textError || `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
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
                    
                    ${results.librarian_analysis && results.librarian_analysis.enhanced ? `
                        <h4>LibrarianAgent Analysis</h4>
                        <div class="librarian-analysis">
                            <p><strong>Enhanced Processing:</strong> ${results.librarian_analysis.analysis_count} materials analyzed by LibrarianAgent</p>
                            <div class="librarian-insights">
                                ${results.librarian_analysis.insights.map(insight => `
                                    <div class="insight-item">
                                        <span class="insight-material">Material ${insight.material_index + 1}:</span>
                                        <span class="insight-category">${insight.categories || 'N/A'}</span>
                                        ${insight.quality_score ? `<span class="insight-quality">(Quality: ${Math.round(insight.quality_score * 100)}%)</span>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
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

    // Tab Management
    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const sections = {
            'upload': document.querySelector('.upload-section'),
            'chat': document.getElementById('chatSection'),
            'jobs': document.getElementById('jobManagementSection')  // Fixed: Use correct section ID
        };

        // Validate all sections exist
        Object.keys(sections).forEach(key => {
            if (!sections[key]) {
                console.error(`Tab section not found: ${key}`);
            }
        });

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                // Update active tab button
                tabButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Show/hide sections with null safety
                Object.keys(sections).forEach(key => {
                    const section = sections[key];
                    if (section) {
                        section.style.display = key === targetTab ? 'block' : 'none';
                    }
                });
                
                this.currentTab = targetTab;
                
                // Special handling for different tabs
                if (targetTab === 'chat' && !this.isConnected) {
                    this.updateConnectionStatus('disconnected', 'Click Connect to start chatting');
                } else if (targetTab === 'jobs') {
                    // Load job management data when switching to jobs tab
                    this.loadJobManagement();
                }
            });
        });
    }

    // Chat Interface Setup
    setupChat() {
        const connectButton = document.getElementById('connectButton');
        const sendButton = document.getElementById('sendButton');
        const chatInput = document.getElementById('chatInput');

        connectButton.addEventListener('click', () => this.connectWebSocket());
        sendButton.addEventListener('click', () => this.sendChatMessage());
        
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendChatMessage();
            }
        });
    }

    // WebSocket Connection
    async connectWebSocket() {
        try {
            // Get demo token
            const tokenResponse = await fetch(`${this.apiBase}/auth/demo-token?user_id=web_user`);
            const tokenData = await tokenResponse.json();
            
            if (!tokenData.token) {
                throw new Error('Failed to get authentication token');
            }

            // Connect WebSocket
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/narrative`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                // Send authentication
                this.websocket.send(JSON.stringify({
                    type: 'authenticate',
                    token: tokenData.token
                }));
            };
            
            this.websocket.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleWebSocketMessage(message);
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('disconnected', 'Connection closed');
                this.updateChatControls(false);
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showToast('WebSocket connection failed', 'error');
            };
            
        } catch (error) {
            console.error('Connection error:', error);
            this.showToast(`Connection failed: ${error.message}`, 'error');
        }
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'authenticate':
                if (message.data.status === 'authenticated') {
                    this.isConnected = true;
                    this.updateConnectionStatus('connected', 'Connected to AI agents');
                    this.updateChatControls(true);
                    this.addChatMessage('system', 'Connected! You can now chat with AI agents.');
                }
                break;
                
            case 'chat_response':
                this.addChatMessage('ai', message.data.response, message.data.agent);
                break;
                
            case 'error':
                this.addChatMessage('error', message.data.error);
                break;
        }
    }

    sendChatMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();
        
        if (!message || !this.isConnected) return;
        
        // Add user message to chat
        this.addChatMessage('user', message);
        
        // Send to WebSocket
        const chatMode = document.getElementById('chatMode').value;
        const storyId = document.getElementById('storyId').value;
        const sessionName = document.getElementById('sessionName').value;
        
        this.websocket.send(JSON.stringify({
            type: 'chat_message',
            data: {
                message: message,
                mode: chatMode,
                story_id: storyId,
                session_name: sessionName
            }
        }));
        
        chatInput.value = '';
    }

    addChatMessage(type, content, agent = null) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${type}`;
        
        let messageHTML = '';
        
        switch (type) {
            case 'user':
                messageHTML = `
                    <div class="message-header">
                        <span class="message-author">You</span>
                        <span class="message-time">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="message-content">${content}</div>
                `;
                break;
                
            case 'ai':
                messageHTML = `
                    <div class="message-header">
                        <span class="message-author">AI Agent${agent ? ` (${agent})` : ''}</span>
                        <span class="message-time">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="message-content">${content}</div>
                `;
                break;
                
            case 'system':
                messageHTML = `
                    <div class="message-content system-text">${content}</div>
                `;
                break;
                
            case 'error':
                messageHTML = `
                    <div class="message-content error-text">Error: ${content}</div>
                `;
                break;
        }
        
        messageDiv.innerHTML = messageHTML;
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    updateConnectionStatus(status, message) {
        const statusIndicator = document.querySelector('.status-indicator');
        const statusText = document.querySelector('.status-text');
        
        statusIndicator.className = `status-indicator ${status}`;
        statusText.textContent = message;
    }

    updateChatControls(enabled) {
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        const connectButton = document.getElementById('connectButton');
        
        chatInput.disabled = !enabled;
        sendButton.disabled = !enabled;
        connectButton.textContent = enabled ? '🔌 Connected' : '🔌 Connect to AI Agents';
        connectButton.disabled = enabled;
    }

    // Genre Management
    async loadGenres() {
        try {
            const response = await fetch(`${this.apiBase}/ingestion/available-genres`);
            const data = await response.json();
            
            const genreSelect = document.getElementById('genre');
            genreSelect.innerHTML = '';
            
            data.genres.forEach(genre => {
                const option = document.createElement('option');
                option.value = genre.value;
                option.textContent = genre.label;
                option.title = genre.description;
                genreSelect.appendChild(option);
            });
            
            // Set default to unknown
            genreSelect.value = 'unknown';
            
        } catch (error) {
            console.error('Failed to load genres:', error);
            // Fallback to basic genres
            const genreSelect = document.getElementById('genre');
            genreSelect.innerHTML = `
                <option value="unknown">Unknown</option>
                <option value="fantasy">Fantasy</option>
                <option value="litrpg">LitRPG</option>
                <option value="sci-fi">Science Fiction</option>
                <option value="contemporary">Contemporary</option>
            `;
        }
    }

    async detectGenre() {
        const fileInput = document.getElementById('files');
        const detectBtn = document.getElementById('detectGenreBtn');
        const resultDiv = document.getElementById('genreDetectionResult');
        
        if (!fileInput.files.length) {
            this.showToast('Please select files first', 'warning');
            return;
        }
        
        try {
            // Disable button and show loading
            detectBtn.disabled = true;
            detectBtn.textContent = '🔄 Detecting...';
            
            // Read first file content for genre detection
            const file = fileInput.files[0];
            const content = await this.readFileContent(file);
            
            if (!content) {
                throw new Error('Could not read file content');
            }
            
            // Call genre detection API
            const response = await fetch(`${this.apiBase}/ingestion/detect-genre`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content: content.substring(0, 1500) })
            });
            
            if (!response.ok) {
                throw new Error('Genre detection failed');
            }
            
            const detection = await response.json();
            
            // Update UI with detection results
            if (detection.detected_genres && detection.detected_genres.length > 0) {
                const topGenre = detection.detected_genres[0];
                
                // Update genre selection
                const genreSelect = document.getElementById('genre');
                genreSelect.value = topGenre.genre;
                
                // Show detection result
                document.getElementById('detectedGenre').textContent = topGenre.genre.toUpperCase();
                document.getElementById('detectionConfidence').textContent = 
                    `(${Math.round(topGenre.confidence * 100)}% confidence)`;
                resultDiv.style.display = 'block';
                
                this.showToast(`Detected genre: ${topGenre.genre} (${Math.round(topGenre.confidence * 100)}% confidence)`, 'success');
            } else {
                this.showToast('Could not detect genre from content', 'warning');
            }
            
        } catch (error) {
            console.error('Genre detection error:', error);
            this.showToast(`Genre detection failed: ${error.message}`, 'error');
        } finally {
            // Re-enable button
            detectBtn.disabled = false;
            detectBtn.textContent = '🔍 Auto-detect';
        }
    }

    async readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    // Job Management Dashboard
    async loadJobManagement() {
        try {
            const response = await fetch(`${this.apiBase}/ingestion/jobs?limit=100`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch job management data');
            }
            
            const data = await response.json();
            this.displayJobManagement(data.jobs);
            this.setupJobManagementControls();
            
        } catch (error) {
            console.error('Job management loading error:', error);
            this.showToast('Failed to load job management data', 'error');
        }
    }

    displayJobManagement(jobs) {
        // Update statistics
        const totalJobs = jobs.length;
        const activeJobs = jobs.filter(job => ['processing', 'queued'].includes(job.status)).length;
        const completedJobs = jobs.filter(job => job.status === 'completed').length;
        const failedJobs = jobs.filter(job => job.status === 'failed').length;

        document.getElementById('totalJobs').textContent = totalJobs;
        document.getElementById('activeJobs').textContent = activeJobs;
        document.getElementById('completedJobs').textContent = completedJobs;
        document.getElementById('failedJobs').textContent = failedJobs;

        // Update job table
        const jobList = document.getElementById('jobManagementList');
        
        if (jobs.length === 0) {
            jobList.innerHTML = `
                <div class="job-table-row no-jobs-row">
                    <div class="no-jobs-message">No jobs found</div>
                </div>
            `;
            return;
        }

        jobList.innerHTML = jobs.map(job => `
            <div class="job-table-row" data-status="${job.status}">
                <div class="job-col-id">
                    <span class="job-id-short" title="${job.job_id}">${job.job_id.substring(0, 12)}...</span>
                </div>
                <div class="job-col-status">
                    <span class="job-status-badge ${job.status}">${job.status}</span>
                    <span class="job-progress">${Math.round(job.progress_percentage)}%</span>
                </div>
                <div class="job-col-files">${job.files_count}</div>
                <div class="job-col-genre">${job.genre_context}</div>
                <div class="job-col-mode">${job.processing_mode}</div>
                <div class="job-col-created">${this.formatDate(job.created_at)}</div>
                <div class="job-col-actions">
                    <button class="job-action-btn view-btn" onclick="ui.viewJobDetails('${job.job_id}')" title="View Details">
                        👁️
                    </button>
                    ${job.status === 'completed' ? `
                        <button class="job-action-btn download-btn" onclick="ui.downloadJobResults('${job.job_id}')" title="Download Results">
                            ⬇️
                        </button>
                    ` : ''}
                    ${['processing', 'queued'].includes(job.status) ? `
                        <button class="job-action-btn cancel-btn" onclick="ui.cancelJob('${job.job_id}')" title="Cancel Job">
                            ❌
                        </button>
                    ` : ''}
                    ${['completed', 'failed'].includes(job.status) ? `
                        <button class="job-action-btn delete-btn" onclick="ui.deleteJob('${job.job_id}')" title="Delete Job">
                            🗑️
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    setupJobManagementControls() {
        const refreshBtn = document.getElementById('refreshJobsBtn');
        const filterSelect = document.getElementById('jobFilterStatus');

        // Refresh button
        refreshBtn.addEventListener('click', () => {
            this.loadJobManagement();
        });

        // Filter functionality
        filterSelect.addEventListener('change', () => {
            this.filterJobsByStatus(filterSelect.value);
        });
    }

    filterJobsByStatus(status) {
        const jobRows = document.querySelectorAll('.job-table-row[data-status]');
        
        jobRows.forEach(row => {
            const jobStatus = row.getAttribute('data-status');
            const shouldShow = status === 'all' || jobStatus === status;
            row.style.display = shouldShow ? 'flex' : 'none';
        });
    }

    async viewJobDetails(jobId) {
        // Switch to upload tab and load job details (reuse existing functionality)
        this.currentJobId = jobId;
        
        // Switch to upload tab
        const uploadTab = document.querySelector('.tab-button[data-tab="upload"]');
        if (uploadTab) {
            uploadTab.click();
        }
        
        // Load job details using existing viewJob method
        this.viewJob(jobId);
    }

    async downloadJobResults(jobId) {
        try {
            const response = await fetch(`${this.apiBase}/ingestion/results/${jobId}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch job results');
            }
            
            const results = await response.json();
            
            // Create downloadable JSON file
            const dataStr = JSON.stringify(results, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            
            const exportFileDefaultName = `job_results_${jobId}.json`;
            
            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportFileDefaultName);
            linkElement.click();
            
            this.showToast('Job results downloaded successfully', 'success');
            
        } catch (error) {
            console.error('Download error:', error);
            this.showToast(`Download failed: ${error.message}`, 'error');
        }
    }

    async cancelJob(jobId) {
        if (!confirm('Are you sure you want to cancel this job?')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBase}/ingestion/jobs/${jobId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to cancel job');
            }
            
            const result = await response.json();
            this.showToast(result.message, 'success');
            
            // Refresh job management display
            this.loadJobManagement();
            
        } catch (error) {
            console.error('Cancel job error:', error);
            this.showToast(`Failed to cancel job: ${error.message}`, 'error');
        }
    }

    async deleteJob(jobId) {
        if (!confirm('Are you sure you want to delete this job? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBase}/ingestion/jobs/${jobId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to delete job');
            }
            
            const result = await response.json();
            this.showToast(result.message, 'success');
            
            // Refresh job management display
            this.loadJobManagement();
            
        } catch (error) {
            console.error('Delete job error:', error);
            this.showToast(`Failed to delete job: ${error.message}`, 'error');
        }
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

// Chat-specific styles
const chatStyles = `
/* Tab Navigation */
.navigation-tabs {
    margin-bottom: 2rem;
}

.tab-container {
    display: flex;
    gap: 0.5rem;
    border-bottom: 2px solid var(--border-color);
}

.tab-button {
    padding: 0.75rem 1.5rem;
    border: none;
    background: transparent;
    cursor: pointer;
    font-weight: 500;
    color: var(--text-secondary);
    border-bottom: 2px solid transparent;
    transition: all 0.2s ease;
}

.tab-button:hover {
    color: var(--primary-color);
    background: rgb(37 99 235 / 0.1);
}

.tab-button.active {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
    background: rgb(37 99 235 / 0.1);
}

/* Chat Interface Styles */
.chat-section {
    margin-bottom: 2rem;
}

.chat-card {
    background: white;
    border-radius: var(--border-radius);
    box-shadow: var(--box-shadow);
    overflow: hidden;
}

.chat-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
    background: var(--background);
}

.chat-header h2 {
    margin: 0;
    color: var(--text-primary);
}

.chat-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.chat-mode-select {
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: white;
}

.connection-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
}

.status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
}

.status-indicator.connected {
    background: #10b981;
}

.status-indicator.offline {
    background: #ef4444;
}

.status-indicator.connecting {
    background: #f59e0b;
}

.chat-container {
    height: 500px;
    display: flex;
    flex-direction: column;
}

.chat-messages {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.chat-message {
    max-width: 80%;
}

.chat-message.user {
    align-self: flex-end;
    background: var(--primary-color);
    color: white;
    padding: 0.75rem;
    border-radius: 1rem 1rem 0.25rem 1rem;
}

.chat-message.ai {
    align-self: flex-start;
    background: var(--background);
    padding: 0.75rem;
    border-radius: 1rem 1rem 1rem 0.25rem;
}

.chat-message.system {
    align-self: center;
    background: var(--background);
    padding: 0.5rem 1rem;
    border-radius: 1rem;
    font-style: italic;
    color: var(--text-secondary);
    max-width: 100%;
    text-align: center;
}

.chat-message.error {
    align-self: center;
    background: #fef2f2;
    color: #dc2626;
    padding: 0.5rem 1rem;
    border-radius: 1rem;
    border: 1px solid #fecaca;
    max-width: 100%;
}

.message-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.25rem;
    font-size: 0.75rem;
    opacity: 0.8;
}

.message-author {
    font-weight: 600;
}

.message-time {
    font-size: 0.7rem;
}

.message-content {
    line-height: 1.4;
}

.system-text {
    color: var(--text-secondary);
    font-style: italic;
}

.error-text {
    color: #dc2626;
}

.chat-input-container {
    border-top: 1px solid var(--border-color);
    padding: 1rem;
}

.chat-input-wrapper {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.chat-input {
    flex: 1;
    padding: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 2rem;
    outline: none;
    font-size: 0.875rem;
}

.chat-input:focus {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgb(37 99 235 / 0.1);
}

.send-button {
    padding: 0.75rem 1.5rem;
    background: var(--primary-color);
    color: white;
    border: none;
    border-radius: 2rem;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.2s ease;
}

.send-button:hover:not(:disabled) {
    background: #1d4ed8;
}

.send-button:disabled {
    background: #9ca3af;
    cursor: not-allowed;
}

.session-config {
    margin-top: 1rem;
}

.session-config summary {
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
}

.config-content {
    background: var(--background);
    padding: 1rem;
    border-radius: var(--border-radius);
    margin-top: 0.5rem;
}

.config-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
}

.config-group {
    flex: 1;
}

.config-group label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
}

.config-group input {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
}

.connect-button {
    width: 100%;
    padding: 0.75rem;
    background: #10b981;
    color: white;
    border: none;
    border-radius: var(--border-radius);
    cursor: pointer;
    font-weight: 500;
    transition: background 0.2s ease;
}

.connect-button:hover:not(:disabled) {
    background: #059669;
}

.connect-button:disabled {
    background: #9ca3af;
    cursor: not-allowed;
}

/* Genre Detection Styles */
.genre-selection-container {
    display: flex;
    gap: 0.5rem;
    align-items: center;
}

.genre-selection-container .form-select {
    flex: 1;
}

.detect-genre-btn {
    padding: 0.5rem 0.75rem;
    background: #10b981;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    white-space: nowrap;
    transition: background 0.2s ease;
}

.detect-genre-btn:hover:not(:disabled) {
    background: #059669;
}

.detect-genre-btn:disabled {
    background: #9ca3af;
    cursor: not-allowed;
}

.genre-detection-result {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 4px;
    font-size: 0.875rem;
}

.detection-label {
    font-weight: 500;
    color: #374151;
}

.detected-genre {
    font-weight: 600;
    color: #059669;
    margin-left: 0.25rem;
}

.detection-confidence {
    color: #6b7280;
    margin-left: 0.25rem;
}

/* LibrarianAgent Analysis Styles */
.librarian-analysis {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 1rem;
    margin: 1rem 0;
}

.librarian-insights {
    margin-top: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.insight-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    background: white;
    border-radius: 4px;
    border: 1px solid #e5e7eb;
}

.insight-material {
    font-weight: 500;
    color: #374151;
    min-width: 80px;
}

.insight-category {
    background: #dbeafe;
    color: #1e40af;
    padding: 0.25rem 0.5rem;
    border-radius: 1rem;
    font-size: 0.875rem;
    font-weight: 500;
}

.insight-quality {
    color: #059669;
    font-size: 0.875rem;
    font-weight: 500;
}

/* Job Management Section Styles */
.job-management-section {
    margin-bottom: 2rem;
}

.job-management-card {
    background: white;
    border-radius: var(--border-radius);
    box-shadow: var(--box-shadow);
    overflow: hidden;
}

.job-management-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
    background: var(--background);
}

.job-management-header h2 {
    margin: 0;
    color: var(--text-primary);
}

.job-management-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.refresh-jobs-btn {
    padding: 0.5rem 1rem;
    background: #10b981;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    transition: background 0.2s ease;
}

.refresh-jobs-btn:hover {
    background: #059669;
}

.job-filter-select {
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: white;
    font-size: 0.875rem;
}

.job-management-content {
    padding: 1.5rem;
}

.job-stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}

.job-stat-item {
    text-align: center;
    padding: 1rem;
    background: var(--background);
    border-radius: var(--border-radius);
    border: 1px solid var(--border-color);
}

.stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary-color);
    margin-bottom: 0.25rem;
}

.stat-label {
    font-size: 0.875rem;
    color: var(--text-secondary);
    font-weight: 500;
}

.job-management-table {
    background: white;
    border-radius: var(--border-radius);
    border: 1px solid var(--border-color);
    overflow: hidden;
}

.job-table-header {
    display: grid;
    grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr 1.5fr 2fr;
    gap: 1rem;
    padding: 1rem;
    background: var(--background);
    border-bottom: 1px solid var(--border-color);
    font-weight: 600;
    color: var(--text-primary);
    font-size: 0.875rem;
}

.job-table-body {
    max-height: 400px;
    overflow-y: auto;
}

.job-table-row {
    display: grid;
    grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr 1.5fr 2fr;
    gap: 1rem;
    padding: 1rem;
    border-bottom: 1px solid var(--border-color);
    font-size: 0.875rem;
    align-items: center;
}

.job-table-row:hover {
    background: var(--background);
}

.job-table-row.no-jobs-row {
    grid-template-columns: 1fr;
    text-align: center;
    color: var(--text-secondary);
    font-style: italic;
    padding: 2rem;
}

.job-id-short {
    font-family: monospace;
    font-size: 0.8rem;
    color: var(--text-secondary);
    cursor: help;
}

.job-col-status {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.job-status-badge {
    padding: 0.25rem 0.5rem;
    border-radius: 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.job-status-badge.processing {
    background: #fef3c7;
    color: #d97706;
}

.job-status-badge.completed {
    background: #d1fae5;
    color: #059669;
}

.job-status-badge.failed {
    background: #fee2e2;
    color: #dc2626;
}

.job-status-badge.queued {
    background: #e0e7ff;
    color: #3730a3;
}

.job-progress {
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.job-col-actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-start;
}

.job-action-btn {
    padding: 0.25rem 0.5rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: background 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.job-action-btn.view-btn {
    background: #e0e7ff;
    color: #3730a3;
}

.job-action-btn.view-btn:hover {
    background: #c7d2fe;
}

.job-action-btn.download-btn {
    background: #d1fae5;
    color: #059669;
}

.job-action-btn.download-btn:hover {
    background: #a7f3d0;
}

.job-action-btn.cancel-btn {
    background: #fed7d7;
    color: #c53030;
}

.job-action-btn.cancel-btn:hover {
    background: #feb2b2;
}

.job-action-btn.delete-btn {
    background: #fee2e2;
    color: #dc2626;
}

.job-action-btn.delete-btn:hover {
    background: #fecaca;
}
`;

// Add additional styles to the page
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles + chatStyles;
document.head.appendChild(styleSheet);