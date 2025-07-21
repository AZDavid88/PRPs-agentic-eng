# Human-in-the-Loop Control Workflow for Narrative Factory

## Current State vs. Needed State

### ✅ What Works Now
- **Material Ingestion**: `factory ingest-materials` adds new content
- **Job Management**: Backend approval/rejection system exists
- **Agent Pipeline**: 4-agent flow validated (Director→Tactician→Weaver→Canonist)

### ❌ What's Missing for Human Control
- **Interactive approval interface**
- **Vector content management (delete/edit)**
- **Mid-story dynamic injection**
- **Iterative editing workflows**

## Recommended Immediate Workflow

### 1. Content Management Commands (NEEDED)
```bash
# Add new character mid-story
factory ingest-materials new_character.txt --story-id "my_serial" --chapter 45

# List what's in memory
factory list-memory --filter "character_sheet" --story-id "my_serial"

# Remove incorrect content (MISSING - needs implementation)
factory remove-content --doc-id "char_villain_uuid" --confirm

# Update existing content (MISSING - needs implementation)
factory update-content --doc-id "char_kael_uuid" --file updated_kael.txt
```

### 2. Job Approval Workflow (EXISTS but no interface)
```bash
# Start chapter generation
factory generate-chapter "Chapter 67: The Discovery" --story-id "my_serial"
# Output: "Director job created: job_abc123 (pending approval)"

# Review director output (MISSING - needs interface)
factory review-job job_abc123
# Should show: strategic brief, key events, emotional arc, etc.

# Approve or reject with feedback
factory approve-job job_abc123
# OR
factory reject-job job_abc123 --feedback "Too rushed, need more character development"
```

### 3. Dynamic Story Steering (NEEDED)
```bash
# Inject new context mid-stream
factory inject-context --type "character" --content "Zara: Former spy, now ally" --from-chapter 45

# Change story direction
factory add-catalyst "Unexpected betrayal by trusted friend" --next-chapter

# Add new location/tech/magic
factory add-worldbuilding "Neural interfaces common in this city" --genre-expansion "cyberpunk"
```

## Implementation Priority

### PHASE 1: Essential Missing Commands
1. **Vector Management**: delete, update, list ingested content
2. **Job Review Interface**: CLI tool to view pending jobs and approve/reject
3. **Dynamic Content Injection**: mid-story character/location/tech addition

### PHASE 2: Workflow Improvements  
1. **Interactive Editor**: Edit agent outputs before approval
2. **Story State Dashboard**: Visual overview of characters, locations, plot threads
3. **WebSocket Interface**: Real-time approval/rejection GUI

### PHASE 3: Advanced Features
1. **Version Control**: Track changes to characters/world over time
2. **A/B Testing**: Generate multiple options for human choice
3. **Automated Continuity Checking**: Alert when new content conflicts with existing