# Agent-to-Model Optimization Analysis
## Document Categorization & Vector Ingestion Workflow

### **AGENT ROLE ANALYSIS**

#### **1. THE LIBRARIAN - Document Categorization & Indexing Specialist**
**Role**: Primary document categorization, temporal gating, and ingestion oversight
**Current Persona**: `/src/agents/prompts/librarian.txt`

**Core Responsibilities**:
- **MaterialClassifier**: Type identification (character, location, system, etc.)
- **TemporalGatingProtocol**: Spoiler analysis and chapter availability
- **StructuralIntegrityAuditor**: Cross-reference detection and consistency checking
- **DataStructuringEngine**: Metadata enrichment and late chunking coordination

**Optimal Model Assignment**: **OpenAI GPT-4** 
**Rationale**: 
- Superior JSON structure compliance for MaterialClassification outputs
- Better instruction following for complex classification schemas
- More reliable for structured data extraction
- Cost-effective for batch processing

#### **2. THE CANONIST - Post-Processing Analysis & Reconciliation**
**Role**: Deep content analysis after ingestion, continuity validation
**Current Persona**: `/src/agents/prompts/canonist.txt`

**Core Responsibilities**:
- **DataForensicsEngine**: Semantic parsing and entity recognition
- **SystemicIntegrityAuditor**: Cross-referencing against existing knowledge base
- **EvolutionaryPsychologyModel**: Character arc analysis
- **ReportCompiler**: Intelligence structuring and metadata tagging

**Optimal Model Assignment**: **Google Gemini Pro**
**Rationale**:
- Excellent at long-context analysis for deep content understanding
- Strong reasoning capabilities for consistency checking
- Good at relationship mapping between documents
- Free tier available for development

#### **3. THE DIRECTOR - Strategic Narrative Planning**
**Role**: High-level narrative coordination using ingested materials

**Optimal Model Assignment**: **OpenAI GPT-4**
**Rationale**: Strategic planning requires precise reasoning

#### **4. THE TACTICIAN - Detailed Scene Planning**
**Role**: Scene-level planning using character and location data

**Optimal Model Assignment**: **Google Gemini Pro** 
**Rationale**: Good at detailed tactical planning with long context

#### **5. THE WEAVER - Prose Generation**
**Role**: Final prose generation using all contextual materials

**Optimal Model Assignment**: **OpenAI GPT-4**
**Rationale**: Superior prose quality and creative output

### **VECTOR INGESTION WORKFLOW**

#### **Phase 1: Document Classification (Librarian Agent)**
```
Input: Raw lore document (character_profile.md, cosmology.md, etc.)
↓
Librarian Agent + OpenAI GPT-4:
  1. Analyze document type (character, location, system, lore, etc.)
  2. Extract key entities and relationships
  3. Assign genre-specific categories 
  4. Perform spoiler risk assessment
  5. Generate MaterialClassification object
↓
Output: Structured MaterialClassification with metadata
```

#### **Phase 2: Late Chunking & Embedding (Automated)**
```
Input: MaterialClassification object
↓
Late Chunking Coordinator:
  1. Analyze document structure and context
  2. Create semantic chunks preserving context
  3. Generate embeddings with Jina v4 (2048-dim)
  4. Prepare for vector storage
↓
Output: Context-aware vector chunks
```

#### **Phase 3: Vector Storage (Qdrant Integration)**
```
Input: Vector chunks with metadata
↓
Qdrant Storage with Memory Passport System:
  - doc_id: Unique identifier
  - doc_type: Classification category
  - chapter_index: Temporal positioning  
  - present_characters: Character IDs involved
  - thread_id: Narrative thread identifier
  - tension_status: Current tension state
↓
Output: Indexed vectors ready for two-tier retrieval
```

#### **Phase 4: Two-Tier Retrieval System**
```
Query: "Ren character abilities and motivations"
↓
Spotlight Query (Immediate Relevance):
  - Filter: present_characters = ["Ren", "protagonist"]
  - Collection: world_bible, story_so_far
  - Limit: 5 results
↓
Ambient Echo Query (Background Context):
  - Filter: doc_type = "tension_report", tension_status = ["unresolved", "escalating"]
  - Exclude: Character-specific to avoid tunnel vision
  - Limit: 3 results
↓
Context Fusion: Combine spotlight + ambient for comprehensive context
```

### **RAG & LATE CHUNKING IMPLEMENTATION**

#### **Late Chunking Strategy**:
1. **Document-Level Embedding**: Send entire document to Jina v4 (8K context)
2. **Semantic Chunking**: Split on logical boundaries (sections, paragraphs)
3. **Vector Extraction**: Map chunk boundaries to token vectors
4. **Context Preservation**: Each chunk retains full document context

#### **Benefits**:
- 35% reduction in retrieval failure rates
- 67% improvement with reranking
- Preserves narrative context across chunks
- Prevents "character reference" disambiguation issues

### **CURRENT IMPLEMENTATION GAPS**

1. **Librarian Agent JSON Parsing**: Fix MaterialClassifier LLM prompt formatting
2. **Model Assignment**: Switch Librarian to OpenAI for better structured output
3. **Content Ingestion**: Complete the material ingestion pipeline
4. **Memory Population**: Get actual content into Qdrant for testing

### **IMMEDIATE ACTION PLAN**

1. Fix Librarian Agent JSON parsing issues with OpenAI model
2. Complete lore example ingestion to populate memory system
3. Test two-tier retrieval with real content
4. Verify character analysis extraction works with ingested materials
5. Proceed with Controlflow agent conversion