# Extend for Visual Dashboard

## EXTEND Phase 3: Build on Existing Web Infrastructure

### Current Foundation:
- ✅ FastAPI web server (`src/web/`)
- ✅ WebSocket real-time communication  
- ✅ Authentication system
- ✅ Job management system
- ✅ Memory/vector database

### Extend for Dashboard (Month 2):

## Add Dashboard API Routes

### Extend `src/web/` with dashboard endpoints:

```python
# src/web/dashboard_routes.py (NEW - extends existing FastAPI app)

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, Any, List

from src.web.auth import get_current_user  # Use existing auth
from src.workflows.jobs import JobStore    # Use existing job system
from src.memory.qdrant import QdrantService # Use existing memory

dashboard_router = APIRouter(prefix="/dashboard")

@dashboard_router.get("/story/{story_id}")
async def get_story_overview(
    story_id: str, 
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get complete story overview using existing memory system.
    
    Extends existing QdrantService for dashboard data.
    """
    qdrant = QdrantService()
    
    # Use existing search methods to gather story data
    characters = await qdrant.search_with_filters(
        filters={"story_id": story_id, "doc_type": "character_sheet"},
        collection_name="world_bible",
        limit=50
    )
    
    locations = await qdrant.search_with_filters(
        filters={"story_id": story_id, "doc_type": "location"},
        collection_name="world_bible", 
        limit=50
    )
    
    plot_threads = await qdrant.search_with_filters(
        filters={"story_id": story_id, "doc_type": "plot_thread"},
        collection_name="world_bible",
        limit=20
    )
    
    return {
        "story_id": story_id,
        "characters": characters,
        "locations": locations, 
        "plot_threads": plot_threads,
        "total_content_pieces": len(characters) + len(locations) + len(plot_threads)
    }

@dashboard_router.get("/jobs/pending")
async def get_pending_jobs(
    user_id: str = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get pending jobs using existing JobStore.
    """
    job_store = JobStore()
    
    # Use existing job store methods
    pending_jobs = job_store.get_pending_jobs()  # This method might need to be added
    
    return [
        {
            "job_id": job.job_id,
            "agent": job.agent,
            "status": job.status,
            "created_at": job.created_at,
            "preview": job.output_payload.get("title", "No title") if job.output_payload else "Processing..."
        }
        for job in pending_jobs
    ]

@dashboard_router.post("/jobs/{job_id}/approve")
async def approve_job_api(
    job_id: str,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Approve job via API (extends existing CLI approve command).
    """
    job_store = JobStore()
    
    # Use existing job store method
    result = job_store.approve_job(job_id)
    
    if result:
        return {"success": True, "message": f"Job {job_id} approved"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@dashboard_router.post("/jobs/{job_id}/reject") 
async def reject_job_api(
    job_id: str,
    feedback: str,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Reject job via API (extends existing CLI reject command).
    """
    job_store = JobStore()
    
    # Use existing job store method
    result = job_store.reject_job(job_id, feedback)
    
    if result:
        return {"success": True, "message": f"Job {job_id} rejected"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")
```

## Simple Dashboard HTML

### Add `templates/dashboard.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Narrative Factory Dashboard</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .dashboard { max-width: 1200px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; }
        .card h3 { margin-top: 0; }
        .job-item { padding: 10px; border-bottom: 1px solid #eee; }
        .approve-btn { background: #4CAF50; color: white; border: none; padding: 5px 10px; margin-right: 5px; }
        .reject-btn { background: #f44336; color: white; border: none; padding: 5px 10px; }
        .character-list { list-style: none; padding: 0; }
        .character-item { padding: 8px; background: #f9f9f9; margin-bottom: 5px; border-radius: 4px; }
    </style>
</head>
<body>
    <div id="dashboard-root"></div>

    <script type="text/babel">
        const { useState, useEffect } = React;

        function Dashboard() {
            const [storyData, setStoryData] = useState(null);
            const [pendingJobs, setPendingJobs] = useState([]);
            
            useEffect(() => {
                // Load story overview using existing API
                fetch('/dashboard/story/my_serial')
                    .then(res => res.json())
                    .then(data => setStoryData(data));
                
                // Load pending jobs using existing API
                fetch('/dashboard/jobs/pending')
                    .then(res => res.json())
                    .then(data => setPendingJobs(data));
            }, []);

            const approveJob = async (jobId) => {
                // Use existing approve API
                await fetch(`/dashboard/jobs/${jobId}/approve`, { method: 'POST' });
                // Refresh jobs
                const response = await fetch('/dashboard/jobs/pending');
                setPendingJobs(await response.json());
            };

            const rejectJob = async (jobId) => {
                const feedback = prompt("Rejection feedback:");
                if (feedback) {
                    await fetch(`/dashboard/jobs/${jobId}/reject`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ feedback })
                    });
                    // Refresh jobs
                    const response = await fetch('/dashboard/jobs/pending');
                    setPendingJobs(await response.json());
                }
            };

            if (!storyData) return <div>Loading...</div>;

            return (
                <div className="dashboard">
                    <h1>Narrative Factory Dashboard</h1>
                    
                    <div className="grid">
                        <div className="card">
                            <h3>Story Overview</h3>
                            <p><strong>Characters:</strong> {storyData.characters.length}</p>
                            <p><strong>Locations:</strong> {storyData.locations.length}</p>
                            <p><strong>Plot Threads:</strong> {storyData.plot_threads.length}</p>
                            
                            <h4>Characters</h4>
                            <ul className="character-list">
                                {storyData.characters.slice(0, 5).map((char, i) => (
                                    <li key={i} className="character-item">
                                        {char.content.substring(0, 50)}...
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className="card">
                            <h3>Pending Jobs ({pendingJobs.length})</h3>
                            {pendingJobs.map(job => (
                                <div key={job.job_id} className="job-item">
                                    <strong>{job.agent}:</strong> {job.preview}
                                    <br />
                                    <small>{job.created_at}</small>
                                    <br />
                                    <button 
                                        className="approve-btn"
                                        onClick={() => approveJob(job.job_id)}
                                    >
                                        ✓ Approve
                                    </button>
                                    <button 
                                        className="reject-btn"
                                        onClick={() => rejectJob(job.job_id)}
                                    >
                                        ✗ Reject
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="card">
                        <h3>Quick Actions</h3>
                        <button onClick={() => window.location.href = '/chat'}>
                            💬 Open Chat Interface
                        </button>
                        <button onClick={() => alert('Feature coming soon!')}>
                            ➕ Add Character
                        </button>
                        <button onClick={() => alert('Feature coming soon!')}>
                            🗺️ Add Location
                        </button>
                    </div>
                </div>
            );
        }

        ReactDOM.render(<Dashboard />, document.getElementById('dashboard-root'));
    </script>
</body>
</html>
```

## Integration Steps:

### 1. Add Dashboard Routes to Main App

```python
# In your main FastAPI app file:
from src.web.dashboard_routes import dashboard_router

app.include_router(dashboard_router)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Serve dashboard HTML."""
    with open("templates/dashboard.html") as f:
        return f.read()
```

### 2. Extend JobStore with Dashboard Methods

```python
# Add to src/workflows/jobs.py:

def get_pending_jobs(self) -> List[JobState]:
    """Get all pending jobs for dashboard display."""
    # Implementation using existing Redis patterns
    pass

def get_job_stats(self) -> Dict[str, int]:
    """Get job statistics for dashboard."""
    # Implementation using existing Redis patterns  
    pass
```

## Development Timeline:

### Month 2, Week 1: Dashboard API
- Add dashboard routes (extends existing FastAPI)
- Extend JobStore with dashboard methods
- Test API endpoints

### Month 2, Week 2: Basic Dashboard UI  
- Create simple HTML dashboard
- Connect to existing WebSocket for real-time updates
- Test job approval workflow

### Month 2, Week 3: Enhanced Features
- Add character/location management UI
- Integrate with chat interface
- Visual story state overview

### Month 2, Week 4: Polish & Integration
- Connect dashboard to existing CLI commands
- Add real-time updates via existing WebSocket
- User testing and refinement

## Key Extension Points:

1. **API Routes**: Build on existing FastAPI structure
2. **Data Access**: Use existing QdrantService and JobStore
3. **Authentication**: Use existing auth system
4. **Real-time Updates**: Use existing WebSocket infrastructure
5. **Job Management**: Extend existing approve/reject workflow

This gives you a visual interface while preserving all existing CLI and chat functionality.