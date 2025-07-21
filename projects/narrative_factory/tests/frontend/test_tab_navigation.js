/**
 * Tab Navigation Testing Suite
 * 
 * Comprehensive tests for tab switching functionality to prevent
 * the type of bugs we just fixed from recurring.
 */

// Mock DOM environment for testing
const { JSDOM } = require('jsdom');

describe('Tab Navigation', () => {
    let dom;
    let document;
    let window;
    let ui;

    beforeEach(() => {
        // Set up DOM environment
        dom = new JSDOM(`
            <!DOCTYPE html>
            <html>
            <head><title>Test</title></head>
            <body>
                <section class="navigation-tabs">
                    <button class="tab-button active" data-tab="upload">📁 Material Upload</button>
                    <button class="tab-button" data-tab="chat">💬 AI Chat Interface</button>
                    <button class="tab-button" data-tab="jobs">📊 Job Management</button>
                </section>
                
                <section class="upload-section">Upload Content</section>
                <section class="chat-section" id="chatSection" style="display: none;">Chat Content</section>
                <section class="job-management-section" id="jobManagementSection" style="display: none;">Job Management Content</section>
            </body>
            </html>
        `, {
            url: "http://localhost:8000",
            pretendToBeVisual: true,
            resources: "usable"
        });

        document = dom.window.document;
        window = dom.window;

        // Set up global DOM environment
        global.document = document;
        global.window = window;

        // Mock the UI class with minimal implementation
        const NarrativeFactoryUI = require('../../src/web/static/js/main.js');
        ui = new NarrativeFactoryUI();
    });

    afterEach(() => {
        dom.window.close();
    });

    describe('Section Mapping', () => {
        test('should correctly map all tab sections', () => {
            const sections = {
                'upload': document.querySelector('.upload-section'),
                'chat': document.getElementById('chatSection'),
                'jobs': document.getElementById('jobManagementSection')
            };

            // Verify all sections exist
            expect(sections.upload).toBeTruthy();
            expect(sections.chat).toBeTruthy();
            expect(sections.jobs).toBeTruthy();

            // Verify sections have correct initial state
            expect(sections.upload.style.display).not.toBe('none');
            expect(sections.chat.style.display).toBe('none');
            expect(sections.jobs.style.display).toBe('none');
        });

        test('should handle missing sections gracefully', () => {
            // Remove a section to test error handling
            document.getElementById('chatSection').remove();

            const sections = {
                'upload': document.querySelector('.upload-section'),
                'chat': document.getElementById('chatSection'),
                'jobs': document.getElementById('jobManagementSection')
            };

            expect(sections.chat).toBeNull();
            
            // The UI should log an error but not crash
            const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
            ui.setupTabs();
            expect(consoleSpy).toHaveBeenCalledWith('Tab section not found: chat');
            consoleSpy.mockRestore();
        });
    });

    describe('Tab Button Interactions', () => {
        test('should switch to chat tab when clicked', () => {
            const chatButton = document.querySelector('[data-tab="chat"]');
            const uploadSection = document.querySelector('.upload-section');
            const chatSection = document.getElementById('chatSection');

            // Simulate click
            chatButton.click();

            expect(chatButton.classList.contains('active')).toBe(true);
            expect(uploadSection.style.display).toBe('none');
            expect(chatSection.style.display).toBe('block');
        });

        test('should switch to jobs tab when clicked', () => {
            const jobsButton = document.querySelector('[data-tab="jobs"]');
            const uploadSection = document.querySelector('.upload-section');
            const jobsSection = document.getElementById('jobManagementSection');

            // Mock loadJobManagement method
            ui.loadJobManagement = jest.fn();

            // Simulate click
            jobsButton.click();

            expect(jobsButton.classList.contains('active')).toBe(true);
            expect(uploadSection.style.display).toBe('none');
            expect(jobsSection.style.display).toBe('block');
            expect(ui.loadJobManagement).toHaveBeenCalled();
        });

        test('should update active state correctly', () => {
            const uploadButton = document.querySelector('[data-tab="upload"]');
            const chatButton = document.querySelector('[data-tab="chat"]');
            const jobsButton = document.querySelector('[data-tab="jobs"]');

            // Initially upload should be active
            expect(uploadButton.classList.contains('active')).toBe(true);

            // Click chat tab
            chatButton.click();
            expect(uploadButton.classList.contains('active')).toBe(false);
            expect(chatButton.classList.contains('active')).toBe(true);
            expect(jobsButton.classList.contains('active')).toBe(false);

            // Click jobs tab
            jobsButton.click();
            expect(uploadButton.classList.contains('active')).toBe(false);
            expect(chatButton.classList.contains('active')).toBe(false);
            expect(jobsButton.classList.contains('active')).toBe(true);
        });
    });

    describe('Special Tab Behaviors', () => {
        test('should handle chat tab connection status', () => {
            ui.isConnected = false;
            ui.updateConnectionStatus = jest.fn();

            const chatButton = document.querySelector('[data-tab="chat"]');
            chatButton.click();

            expect(ui.updateConnectionStatus).toHaveBeenCalledWith('disconnected', 'Click Connect to start chatting');
        });

        test('should load job management when switching to jobs tab', () => {
            ui.loadJobManagement = jest.fn();

            const jobsButton = document.querySelector('[data-tab="jobs"]');
            jobsButton.click();

            expect(ui.loadJobManagement).toHaveBeenCalled();
        });
    });

    describe('Section Visibility Logic', () => {
        test('should hide all other sections when switching tabs', () => {
            const uploadSection = document.querySelector('.upload-section');
            const chatSection = document.getElementById('chatSection');
            const jobsSection = document.getElementById('jobManagementSection');

            // Switch to chat tab
            const chatButton = document.querySelector('[data-tab="chat"]');
            chatButton.click();

            expect(uploadSection.style.display).toBe('none');
            expect(chatSection.style.display).toBe('block');
            expect(jobsSection.style.display).toBe('none');

            // Switch to jobs tab
            const jobsButton = document.querySelector('[data-tab="jobs"]');
            jobsButton.click();

            expect(uploadSection.style.display).toBe('none');
            expect(chatSection.style.display).toBe('none');
            expect(jobsSection.style.display).toBe('block');
        });
    });

    describe('Error Resistance', () => {
        test('should handle null sections without crashing', () => {
            // Mock a scenario where a section is null
            const originalQuerySelector = document.querySelector;
            document.querySelector = jest.fn((selector) => {
                if (selector === '.upload-section') return null;
                return originalQuerySelector.call(document, selector);
            });

            expect(() => {
                ui.setupTabs();
            }).not.toThrow();

            document.querySelector = originalQuerySelector;
        });

        test('should handle missing data-tab attributes', () => {
            const badButton = document.createElement('button');
            badButton.className = 'tab-button';
            // No data-tab attribute
            document.querySelector('.navigation-tabs').appendChild(badButton);

            expect(() => {
                ui.setupTabs();
                badButton.click();
            }).not.toThrow();
        });
    });
});