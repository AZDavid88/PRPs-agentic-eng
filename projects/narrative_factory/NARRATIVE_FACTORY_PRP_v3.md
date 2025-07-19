# PRP: Narrative Factory v3.0 - AI-Powered Serial Fiction Generation with Web UI

**PRP Version:** 3.0  
**Status:** ACTIVE  
**Primary Agent:** Nova  
**Validation Level:** L4 (Full Integration + Creative Output + UI)

---

## 1. Goal

Build a semi-autonomous, genre-agnostic narrative generation engine with a web-based UI for uploading and managing prep materials, featuring AI-powered material classification, Jina v4 late chunking embeddings, and contextual retrieval optimization to produce high-quality, long-form serial fiction while maintaining absolute continuity through a four-agent assembly line powered by Prefect orchestration and Qdrant vector memory.

## 2. Why

- **Creative Amplification**: Enable writers to produce consistent, high-quality serial fiction at scale.
- **Intuitive Material Management**: Provide a web UI for easy upload and organization of world-building materials.
- **Advanced Context Retention**: Use cutting-edge embedding techniques to solve the "lost context" problem.
- **Cost-Effective Operation**: Optimize embedding costs through intelligent hybrid approaches.
- **Narrative Consistency**: Solve the "continuity drift" problem in long-form AI-generated content.
- **Autonomous Operation**: Create a system that can generate chapters with minimal human intervention.

## 3. What

### User-Visible Behavior

#### Web Interface
- **Material Upload Dashboard**: Drag-and-drop interface for uploading lore, style guides, character profiles, thematic lexicons.
- **AI-Powered Classification**: Automatic sorting of uploaded materials into appropriate Qdrant collections.
- **Material Preview & Editing**: In-browser editing of prep materials before ingestion.
- **Progress Monitoring**: Real-time upload and processing status with cost estimates.
- **Collection Management**: Visual interface for viewing and organizing stored materials by type and relationship.

#### Generation Interface  
- **Chapter Generation**: Produce ~3,000-word chapters maintaining style, character voice, and plot continuity.
- **Branch Visualization**: UI for managing parallel narrative branches and experiments.
- **Memory Inspection**: Web interface for exploring story state, character arcs, and tension threads.
- **Quality Metrics**: Dashboard showing continuity scores, voice consistency, and narrative health.

### Technical Requirements

#### Frontend Stack
- **Framework**: React 18+ with TypeScript for type safety.
- **UI Library**: Shadcn/ui for a consistent design system.
- **File Upload**: React-dropzone with progress tracking and chunked uploads.
- **State Management**: Redux Toolkit for complex state and server cache management.
- **Real-time Updates**: WebSocket integration for live progress updates.

#### Backend Architecture
- **API Layer**: FastAPI with async/await for high-performance REST endpoints.
- **Authentication**: Simplified API Key Authentication for secure endpoint access.
- **File Processing**: Celery + Redis for background material processing.
- **WebSocket Server**: FastAPI's native WebSockets for real-time communication.

#### Advanced Memory System
- **Primary Embedding**: Jina v4 with late chunking for contextual embeddings (8K token context).
- **Contextual Enhancement**: LLM-powered chunk descriptions for critical materials.
- **Hybrid Cost Strategy**: Late chunking for `world-bible`, contextual retrieval for `story_so-far`.
- **Smart Batching**: Rate-limit aware processing with cost optimization.

## 4. Success Criteria

### Functional Success
- [ ] Upload and process 100+ prep material files through web UI in under 10 minutes.
- [ ] Generate coherent 3,000+ word chapters maintaining continuity over 50+ chapters.
- [ ] Achieve < 2% context loss in retrieval compared to traditional chunking methods.
- [ ] Process material uploads with < $5 embedding cost per 100,000 words.
- [ ] Complete chapter generation in under 5 minutes with full pipeline execution.

### Quality Metrics
- [ ] Character voice consistency score > 95% (measured by semantic similarity).
- [ ] Plot thread resolution tracking with < 3% abandoned threads.
- [ ] Material classification accuracy > 90% for uploaded content.
- [ ] Zero schema validation errors in production after initial setup.
- [ ] User satisfaction score > 4.5/5 for UI usability.

### Performance Metrics
- [ ] Web UI loads in < 2 seconds on 3G connections.
- [ ] File uploads process at > 1MB/second with progress feedback.
- [ ] Real-time updates delivered within 200ms of backend events.

## 5. Technology Stack & Documentation

#### 5.1 Frontend Stack

**React 18+ with TypeScript**
- Docs: https://react.dev/learn
- Key patterns: The core of our UI. We will use functional components, hooks, and strict TypeScript mode.

**Vite**
- Docs: https://vitejs.dev/guide/
- Key patterns: The build tool and development server for our frontend. Configuration will be in `vite.config.ts`.

**Shadcn/ui Components**
- Docs: https://ui.shadcn.com/docs
- Key patterns: Our core visual design system. We will use its components (`Button`, `Input`, `Dialog`, `Progress`) to build the entire UI.

**React Dropzone**
- Docs: https://react-dropzone.js.org/
- Key patterns: The engine for our drag-and-drop material upload dashboard. We will use its hooks for file validation and progress tracking.

**Redux Toolkit with RTK Query**
- Docs: https://redux-toolkit.js.org/
- Key patterns: The central state manager for the entire frontend. We will use it to manage UI state, server cache, and all asynchronous API interactions via RTK Query.

#### 5.2 Backend Stack

**FastAPI**
- Docs: https://fastapi.tiangolo.com/
- Key patterns: The foundation of our backend. We will heavily use `async/await`, dependency injection, and its built-in support for WebSockets and asynchronous file uploads.

**Celery & Flower**
- Docs (Celery): https://docs.celeryq.dev/en/stable/getting-started/first-steps-with-celery.html
- Docs (Flower): https://flower.readthedocs.io/en/latest/
- Key patterns: The asynchronous task processing backbone. All heavy lifting (classification, embedding) will be done by Celery workers, monitored by the Flower dashboard.

#### 5.3 AI & Orchestration

**Prefect**
- Docs: https://docs.prefect.io/v3/get-started/
- Key patterns: The master orchestrator for the four-agent narrative pipeline. We will define our generation sequence as a Prefect `@flow`.

**Controlflow**
- Docs: https://controlflow.ai/welcome/
- Key patterns: To be used for building advanced, dynamic, and stateful agentic workflows, particularly for the "Conductor's Toolkit" protocols.

**Pydantic**
- Docs: https://docs.pydantic.dev/latest/
- Key patterns: The blueprint for all data structures in our Python code. Every model, from API responses to agent outputs, will be a Pydantic model.

**Instructor**
- Docs: https://python.useinstructor.com/
- Key patterns: The critical link between the LLM and our code. It will be used to force the unstructured text output of our AI agents into the strict Pydantic models we define, ensuring pipeline stability.

#### 5.4 Database & Embeddings

**Jina v4 Embedding API**
- Docs: https://jina.ai/api-dashboard/embedding
- Key patterns: The core of our advanced memory system. We will use its `late-chunking` feature for cost-effective embedding of large lore documents.

**Qdrant - Advanced Filtering**
- Docs: https://qdrant.tech/documentation/concepts/filtering/
- Key patterns: The key to intelligent context retrieval. We will use its advanced filtering capabilities to implement the "Two-Tiered Context Retrieval" and "Narrative Spotlight" protocols by querying on metadata fields.

## 6. Core Architecture & Data Contracts

### 6.1 Data Models & Schemas

**Enhanced Material Types**
```json
{
    "character-profile": {
        "required-fields": ["id", "name", "role", "arc", "goals", "flaws", "voice-tone", "relationships"],
        "optional-fields": ["faction-id", "secret-knowledge", "backstory", "physical-description"],
        "collection": "world-bible",
        "embedding-strategy": "late-chunking"
    },
    "style-guide": {
        "required-fields": ["id", "genre", "tone", "voice-patterns", "example-passages", "pov-style"],
        "optional-fields": ["dialogue-style", "description-density", "pacing-notes"],
        "collection": "world-bible", 
        "embedding-strategy": "late-chunking"
    },
    "thematic-lexicon": {
        "required-fields": ["id", "terms", "definitions", "usage-context", "emotional-weight"],
        "optional-fields": ["synonyms", "antonyms", "genre_specific-usage"],
        "collection": "world-bible",
        "embedding-strategy": "contextual-retrieval"
    },
    "lodestone": {
        "required-fields": ["id", "core-premise", "key-conflicts", "thematic-anchors", "genre"],
        "optional-fields": ["target-audience", "content-warnings", "narrative-constraints"],
        "collection": "world-bible",
        "embedding-strategy": "contextual-retrieval"
    },
    "lore-document": {
        "required-fields": ["id", "title", "content", "category", "importance-level"],
        "optional-fields": ["related-characters", "related-locations", "timeline-position"],
        "collection": "world-bible",
        "embedding-strategy": "late-chunking"
    }
}
```

**API Response Models**
```python
# Material upload response
class UploadResponse(BaseModel):
    upload-id: UUID
    status: Literal["processing", "completed", "failed"]
    classification: Optional[str] = None
    confidence: Optional[float] = None
    embedding-cost: Optional[float] = None
    processing-time: Optional[float] = None
    validation-errors: List[str] = []

# Chapter generation response  
class GenerationResponse(BaseModel):
    chapter-id: UUID
    status: Literal["generating", "completed", "failed"]
    progress: Dict[str, str]
    estimated-completion: datetime
    word-count: int = 0
    quality-metrics: Dict[str, Any] = {}
```

## 7. Implementation Blueprint

### 7.1 Project Structure

```
narrative-factory/
├── frontend/                   # React TypeScript app
│   ├── src/
│   │   ├── app/                # Redux Toolkit store and slices
│   │   ├── components/
│   │   │   ├── upload/         # Material upload components
│   │   │   ├── dashboard/      # Main dashboard
│   │   │   └── common/         # Shared components
│   │   ├── features/           # Feature-based component groups
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # API client services (RTK Query)
│   │   └── types/              # TypeScript definitions
│   ├── package.json
│   └── vite.config.ts
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/                # API route handlers
│   │   ├── core/               # Core business logic & security
│   │   ├── models/             # Pydantic data models
│   │   ├── services/           # Business services
│   │   └── workers/            # Celery task workers
│   ├── scripts/                # Original core modules (enhanced)
│   └── requirements.txt
├── shared/                     # Shared schemas and types
│   ├── schemas.json           # Enhanced schema definitions
│   └── contracts/             # MCP contracts
└── deployment/                # Docker and deployment configs
```

### 7.2 Critical Implementation Notes

**Simplified API Key Security**
- A single, hardcoded API key will be stored in the `.env` file.
- The frontend will send this key in the `X-API-KEY` header.
- A FastAPI `Security` dependency will validate this key for all protected endpoints, providing a simple but effective security layer for a single-user application.

**Advanced Embedding Patterns**
- **Late Chunking (Jina v4):** For large, static documents (`lore-document`, `style-guide`), the entire text will be sent to the Jina API with `late-chunking: True`. This is the most cost-effective method for bulk data.
- **Contextual Retrieval:** For critical, relationship-heavy content (`character-profile`, `thematic-lexicon`), we will use an LLM to generate a concise summary of each chunk *before* embedding. The summary and the chunk are then combined, creating a highly context-aware vector. This is more expensive and reserved for high-impact data.

**File Processing Pipeline**
1. **Upload** → Validate file type, size, content.
2. **Classification** → AI-powered content type detection.
3. **Preprocessing** → Text extraction, cleaning, structure detection.
4. **Embedding Strategy Selection** → Based on content type and importance.
5. **Embedding Generation** → Late chunking or contextual retrieval via Celery worker.
6. **Qdrant Ingestion** → Upsert with rich metadata.
7. **Validation** → Quality checks and user notification via WebSocket.

### 7.3 Core Module & API Specifications

**`embedder_v2.py` - Advanced Embedding Engine**
- Must implement two distinct methods: `create_late_chunking-embedding` and `create_contextual-embedding` to handle the hybrid strategy.

**`classifier.py` - AI-Powered Content Classification**
- Must use an LLM to analyze file content and return a predicted `material-type` and a confidence score.

**API Endpoint: `POST /api/materials/upload`**
- Must use the simplified API key security dependency.
- Must accept a file, queue a background task with Celery, and return an `upload-id` for tracking.

**WebSocket Endpoint: `WS /ws/upload-progress/{upload-id}`**
- The frontend will connect to this endpoint after an upload.
- The Celery worker will publish progress updates (e.g., `{"stage": "classifying", "progress": 0.25}`) to a Redis channel, which the WebSocket handler will then forward to the client.

## 8. Ordered Task List

### Phase 0: Enhanced Foundation
1. Set up monorepo structure with `frontend/`, `backend/`, `shared/` separation.
2. Configure development environment with Docker Compose.
3. Initialize React + TypeScript frontend with Vite and Redux Toolkit.
4. Set up FastAPI backend with async database connections.
5. Configure Celery + Redis for background processing.
6. Set up enhanced Qdrant collections with new schemas.
7. Implement simple, hardcoded API key check for backend security.

### Phase 1: Material Upload System
1. Build file upload UI with drag-and-drop and progress tracking
2. Implement chunked file upload API with resumable uploads
3. Create AI-powered content classification service
4. Build material preview and editing interface
5. Implement enhanced validator with new schema types
6. Create embedder_v2 with Jina v3 late chunking support
7. Add contextual retrieval for critical content types

### Phase 2: Advanced Embedding Pipeline
1. Implement hybrid embedding strategy selection
2. Create cost-aware batch processing for embeddings
3. Add Gemini context caching for contextual retrieval
4. Build smart rate limiting and retry mechanisms
5. Implement embedding quality validation
6. Create material relationship mapping
7. Add embedding cost tracking and reporting

### Phase 3: Web Interface & Real-time Features
1. Build material management dashboard
2. Create collection visualization and browsing
3. Implement WebSocket infrastructure for real-time updates
4. Build generation monitoring interface
5. Add quality metrics dashboard
6. Create material search and filtering
7. Implement user preference and workspace management

### Phase 4: Enhanced Generation Pipeline
1. Update agent MCP contracts for new material types
2. Enhance Director agent with advanced context selection
3. Improve Tactician with UI feedback integration
4. Update Weaver with style guide integration
5. Enhance Canonist with relationship tracking
6. Add branch management through web interface
7. Implement generation queue management

### Phase 5: Production & Optimization
1. Add comprehensive error handling and user feedback
2. Implement performance monitoring and alerting
3. Create automated testing for UI and API
4. Add data backup and recovery systems
5. Optimize for multi-user concurrent access
6. Deploy with auto-scaling and load balancing
7. Create user onboarding and documentation

## 9. Validation Loops

### Level 1: Frontend Development & Static Analysis
```bash
# Run these FIRST - fix any errors before proceeding
# Ensure code quality and style consistency
npm run lint

# Check for TypeScript type errors across the entire project
npx tsc --noEmit

# Run all unit and component tests using Vitest
npm run test

# Expected: No errors. If errors, READ the error and fix.
# Test command will specifically target:
# - Redux Toolkit slice reducers to ensure state logic is correct.
# - React components using @testing-library/react with a mock Redux store.
# - RTK Query endpoint definitions to ensure they are correctly formed.
```

### Level 2: Backend API & Logic Testing
```bash
# Run all backend tests with Pytest
uv run pytest tests/ -v --cov=app

# Expected: All tests passing with >90% code coverage.
# Test suite will specifically target:
# - API endpoints, including testing the new API Key security dependency.
# - Core service logic in app/services/.
# - Celery workers in "eager" mode to test task logic without a broker.
# - embedder_v2.py and classifier.py with mocked API calls to Jina/LLM providers.
# - Pydantic model validation and serialization.
```

### Level 3: Full-Stack Integration & E2E
```bash
# Start the full environment via Docker Compose
docker-compose up -d --build

# Run the end-to-end test suite using a framework like Playwright or Cypress
npm run test:e2e

# Expected: Full user workflows pass without errors.
# E2E suite will cover:
# - User drag-and-drop file upload.
# - Real-time progress updates via WebSockets during ingestion.
# - Verification that uploaded material appears in the dashboard.
# - Starting a generation job and seeing the monitor update.

# Stop the environment after tests
docker-compose down
```

### Level 4: User Experience & Quality Validation
```bash
# These are semi-automated scripts to validate the quality of the output.

# Validate the hybrid embedding strategy against a golden dataset
python scripts/validate-embeddings.py --cost-analysis

# Generate a 5-chapter arc and analyze for continuity and quality
python scripts/validate_generation-quality.py --chapters 5

# Analyze API performance under simulated load
python scripts/load-test.py --concurrent-users 5 --duration 60

# Expected: Scripts complete successfully and report metrics within acceptable thresholds
# (e.g., continuity score > 0.95, p95 response time < 500ms).
```

## 10. Known Gotchas & Solutions

### Jina v4 Embedding Considerations
- **Token Limits**: 8K tokens max - implement smart document splitting.
- **Rate Limits**: 60 requests/minute free tier - batch multiple chunks per request.
- **Cost Optimization**: Use late chunking for bulk content, save contextual retrieval for critical materials.
- **Error Handling**: API can be flaky - implement exponential backoff with circuit breakers.

### Contextual Retrieval Cost Management  
- **Caching Strategy**: Cache document contexts in Gemini for 1-hour TTL
- **Batch Processing**: Process similar materials together to maximize cache hits
- **Smart Selection**: Only use for high-impact content (character sheets, critical lore)
- **Cost Monitoring**: Track spend per material type and set budget alerts

### File Upload & Processing
- **Large File Handling**: Split documents > 50MB into segments before processing
- **Concurrent Processing**: Limit to 5 concurrent embedding requests per user
- **Progress Tracking**: Use WebSockets for real-time upload and processing updates
- **Error Recovery**: Implement resumable uploads and processing restart capability

### UI Performance & Responsiveness
- **Virtual Scrolling**: Use for large material lists (> 100 items)
- **Optimistic Updates**: Show immediate feedback before backend confirmation
- **Error Boundaries**: Graceful degradation when components fail
- **Mobile Optimization**: Responsive design for tablet/mobile material review

### Multi-User Considerations
- **Concurrent Editing**: Implement optimistic locking for material edits
- **Resource Quotas**: Limit embedding costs per user/organization
- **Session Management**: WebSocket reconnection and state recovery
- **Data Isolation**: Ensure user materials are properly segregated

## 11. Cost Analysis & Optimization

### Embedding Cost Projections

**Scenario: 500,000 words of prep materials**

| Strategy | Cost per 100K words | Total Cost | Use Case |
|----------|---------------------|------------|----------|
| **Jina v4 Late Chunking** | $2.00 | $10.00 | World bible, lore documents |
| **Contextual Retrieval** | $26.00 | $130.00 | Character sheets, critical content |
| **Standard Chunking** | $2.40 | $12.00 | Simple reference materials |

**Recommended Hybrid Approach:**
- 80% Late Chunking: $8.00 (400K words of lore, style guides)
- 20% Contextual Retrieval: $26.00 (100K words of character sheets, core themes)
- **Total: $34.00** (vs $130.00 pure contextual or $10.00 pure late chunking)

### Processing Time Estimates
- **Late Chunking**: ~30 seconds per 100K words
- **Contextual Retrieval**: ~15 minutes per 100K words (with rate limiting)
- **Classification**: ~5 seconds per document
- **UI Upload**: ~10MB/second with progress feedback

## 11. Progressive Enhancement Path

### MVP (Material Upload + Basic Generation)
1. Web UI for material upload and basic classification
2. Jina v3 late chunking for all content types
3. Enhanced four-agent pipeline with UI monitoring
4. Basic material browsing and editing

### Enhancement 1: Advanced Embedding Intelligence
1. AI-powered content classification with confidence scoring
2. Hybrid embedding strategy (late chunking + contextual retrieval)
3. Material relationship mapping and visualization
4. Cost optimization and budget monitoring

### Enhancement 2: Production User Experience
1. Real-time collaboration and material sharing
2. Advanced search and filtering across all materials
3. Generation branch management through UI
4. Comprehensive quality metrics and analytics

### Enhancement 3: Scale & Performance
1. Multi-tenant architecture with organization support
2. Advanced caching and performance optimization
3. Automated quality assurance and content validation
4. Enterprise-grade security and compliance features

---

## 12. Appendix: Technical Implementation Details

### Frontend Package Configuration
```json
// package.json dependencies
{
  "@radix-ui/react-*": "^1.0.0",
  "react": "^18.2.0", 
  "react-dom": "^18.2.0",
  "react-dropzone": "^14.2.0",
  "react-redux": "^8.1.0",
  "@reduxjs/toolkit": "^1.9.0",
  "tailwindcss": "^3.3.0",
  "vite": "^4.4.0"
}
```

### Backend Dependencies
```txt
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
celery==5.3.4
redis==5.0.1
qdrant-client==1.7.0
pydantic==2.5.0
python-multipart==0.0.6
jina-embeddings==0.6.0 # Or latest Jina v4 client
google-generativeai==0.3.2
openai==1.3.0
instructor==0.4.0
```

### Environment Configuration
```bash
# .env.template
# Frontend
VITE_API_BASE-URL=http://localhost:8000
VITE_WS-URL=ws://localhost:8000

# Backend  
API_SECRET-KEY=your_super_secret_key-here
REDIS-URL=redis://localhost:6379
QDRANT-URL=http://localhost:6333

# AI Services
JINA_API-KEY=your_jina_api-key
GEMINI_API-KEY=your_gemini_api-key
OPENAI_API-KEY=your_openai_api-key

# Processing
CELERY_BROKER-URL=redis://localhost:6379
CELERY_RESULT-BACKEND=redis://localhost:6379
```

### Docker Compose Configuration
```yaml
docker-compose.yml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
        - "3000:3000"
    environment:
        - VITE_API_BASE-URL=http://backend:8000
        - VITE_WS-URL=ws://backend:8000
    depends-on:
        - backend


  backend:
    build: ./backend
    ports:
        - "8000:8000"
    environment:
        - API_SECRET-KEY=${API_SECRET-KEY}
        - REDIS-URL=redis://redis:6379
        - QDRANT-URL=http://qdrant:6333
        - JINA_API-KEY=${JINA_API-KEY}
        - GEMINI_API-KEY=${GEMINI_API-KEY}
        - OPENAI_API-KEY=${OPENAI_API-KEY}
        - CELERY_BROKER-URL=redis://redis:6379/0
        - CELERY_RESULT-BACKEND=redis://redis:6379/1
    depends-on:
        - redis
        - qdrant


  worker:
    build: ./backend
    command: celery -A app.workers.tasks worker --loglevel=info
    environment:
        - API_SECRET-KEY=${API_SECRET-KEY}
        - REDIS-URL=redis://redis:6379
        - QDRANT-URL=http://qdrant:6333
        - JINA_API-KEY=${JINA_API-KEY}
        - GEMINI_API-KEY=${GEMINI_API-KEY}
        - OPENAI_API-KEY=${OPENAI_API-KEY}
        - CELERY_BROKER-URL=redis://redis:6379/0
        - CELERY_RESULT-BACKEND=redis://redis:6379/1
    depends-on:
        - redis
        - qdrant


  redis:
    image: redis:7-alpine
    ports:
        - "6379:6379"


  qdrant:
    image: qdrant/qdrant:v1.7.0
    ports:
        - "6333:6333"
```
---

*This enhanced PRP serves as the complete implementation guide for Narrative Factory v3.0 with a web UI and advanced embedding capabilities. All development should reference this document for authoritative specifications.*