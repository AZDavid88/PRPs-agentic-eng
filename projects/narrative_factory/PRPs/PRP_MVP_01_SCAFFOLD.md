name: "MVP Phase 1: Initial Project Scaffolding"
description: "Establishes the foundational directory structure and configuration for the Narrative Factory CLI-based MVP."

---

## Goal

To create a clean, self-contained, and standardized Python project structure within the `narrative_factory` directory. This scaffold will form the basis for all subsequent development phases of the MVP.

## Why

- **Modularity:** A well-defined structure separates concerns (e.g., `src`, `tests`, `scripts`), making the codebase easier to understand, maintain, and extend.
- **Deployability:** Proper packaging (`pyproject.toml`), environment management (`.env`), and a stateful job store (`redis`) are critical for creating a robust, pausable, and deployable application.
- **Consistency:** Establishes a standard layout that all team members (including AI agents) can rely on, reducing cognitive overhead.

## What

### Desired Codebase Tree

The following directory and file structure must be created.

```
/workspaces/PRPs-agentic-eng/projects/narrative_factory/
├── PRPs/
│   └── ... (This PRP and others)
├── pyproject.toml           # Core dependencies and project metadata
├── .gitignore               # Specifies files/directories to be ignored by Git
├── .env.template            # Template for environment variables (API keys, etc.)
├── .env                     # Local environment variables (MUST be in .gitignore)
├── factory.py               # Main entry point for the CLI
├── scripts/
│   ├── ingest.py            # Script for one-off data ingestion
│   └── bootstrap_qdrant.py  # Script to initialize Qdrant collections
├── src/
│   └── narrative_factory/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── models.py    # NEW: Pydantic models for agent inputs/outputs
│       │   └── personas.py  # Agent classes (Director, Tactician, etc.)
│       ├── memory/
│       │   ├── __init__.py
│       │   └── qdrant.py    # Qdrant client and RAG logic
│       ├── workflows/
│       │   ├── __init__.py
│       │   ├── generation.py # The main Prefect flow
│       │   └── jobs.py       # NEW: Service for interacting with the Redis job store
│       └── cli/
│           ├── __init__.py
│           └── commands.py  # Logic for the CLI commands
├── tests/
│   ├── __init__.py
│   ├── test_agents.py
│   └── test_memory.py
├── memory/
│   └── ... (Existing world bible, story so far)
├── contracts/
│   └── ... (Existing agent contracts)
└── outputs/
    └── ... (Generated chapters and logs)
```

## Context7 Documentation Injection

Before implementation, inject real-time documentation for key libraries:

```bash
# Use Context7 for modern Python packaging patterns
use context7 for library /pdm-project/pdm topic "pyproject.toml configuration"

# Use Context7 for environment management
use context7 for python packaging topic "environment variables and .env files"

# Use Context7 for CLI frameworks
use context7 for library /tiangolo/typer topic "CLI applications and entry points"
```

**Why Context7 Enhances This PRP:**
- **PDM Documentation**: Latest pyproject.toml patterns, build-system configuration, and dependency management
- **Python Packaging**: Current best practices for project structure, entry points, and environment handling
- **Typer Patterns**: Modern CLI application patterns and command organization

## Core Architecture & Data Contracts

### Job State Contract

A new `JobState` contract is introduced to manage the state of pausable tasks within the workflow. This will be the source of truth for the Human-in-the-Loop (HITL) system, stored in Redis.

```json
{
  "JobState": {
    "description": "The state of a single, pausable task within the narrative factory workflow, stored in Redis.",
    "job_id": "string (e.g., 'd-a4b8c1f7')",
    "agent": "string (e.g., 'Director', 'Tactician')",
    "status": "string (enum: 'processing', 'pending_approval', 'approved', 'rejected', 'complete')",
    "input_payload": "object",
    "output_payload": "object",
    "feedback_history": "array[object]",
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
}
```

## Implementation Blueprint

### Task Zero: Bootstrap Data Creation

Before implementing any code, create the `/memory_bootstrap` directory with sample test data:

1. **CREATE** `/memory_bootstrap` directory structure:
```
memory_bootstrap/
├── character_sheets/
│   ├── char_protagonist.json
│   ├── char_mentor.json
│   └── char_antagonist.json
├── style_guides/
│   └── primary_style.json
└── lore_documents/
    ├── world_setting.json
    └── magic_system.json
```

2. **POPULATE** sample JSON files following these schemas:
```json
// character_sheets/char_protagonist.json
{
  "id": "char_protagonist",
  "name": "Kaelen Drakemoor", 
  "role": "protagonist",
  "arc": "reluctant hero discovering hidden powers",
  "goals": ["master forbidden magic", "save the realm"],
  "flaws": ["impulsive", "distrusts authority"],
  "voice_tone": "determined but conflicted",
  "relationships": ["mentor_eldara", "rival_thorne"]
}

// style_guides/primary_style.json  
{
  "id": "primary_style",
  "genre": "epic fantasy",
  "tone": "serious with moments of hope",
  "voice_patterns": "third person limited, vivid imagery",
  "example_passages": ["The shadows writhed..."],
  "pov_style": "close third person"
}

// lore_documents/world_setting.json
{
  "id": "world_setting", 
  "title": "The Sundered Realms",
  "content": "A world where magic is forbidden...",
  "category": "worldbuilding",
  "importance_level": "high"
}
```

### Agent Prompt Integration

3. **CREATE** `src/narrative_factory/agents/prompts/` directory with agent prompt files:
```
src/narrative_factory/agents/prompts/
├── director.txt
├── tactician.txt  
├── weaver.txt
└── canonist.txt
```

4. **COPY** persona content from `/workspaces/PRPs-agentic-eng/.personas/` to corresponding prompt files.

### List of tasks to be completed

1.  **CREATE** the primary directory structure: `src/narrative_factory`, `scripts`, `tests`.
2.  **CREATE** sub-packages within `src/narrative_factory`: `agents`, `memory`, `workflows`, `cli`.
3.  **CREATE** empty `__init__.py` files in all Python packages and sub-packages to make them importable.
4.  **CREATE** the new, empty files for our defined contracts and services:
    - `src/narrative_factory/agents/models.py`
    - `src/narrative_factory/workflows/jobs.py`
5.  **CREATE** the main project files: `pyproject.toml`, `.gitignore`, `.env.template`, `factory.py`.
6.  **POPULATE** `.gitignore` with standard Python and environment ignores.
7.  **POPULATE** `pyproject.toml` with initial dependencies: `prefect`, `qdrant-client`, `pydantic`, `python-dotenv`, `typer`, `google-generativeai`, `openai`, `redis`.
8.  **POPULATE** `factory.py` with boilerplate to run the Typer CLI application defined in `src/narrative_factory/cli/commands.py`.

## Validation Loop

### Level 1: Structural Validation

```bash
# Verify the directory and file structure from the project root
tree -L 4 .

# Expected: The output of the tree command should exactly match the "Desired Codebase Tree" specified above.
# If there are discrepancies, create or move files as needed to match the blueprint.
```

### Level 2: Dependency Validation

```bash
# Install the dependencies defined in pyproject.toml
# (Assuming 'uv' or 'pip' is the project's package manager)
uv pip install -e .

# Expected: Successful installation with no dependency resolution errors.
# If errors occur, check pyproject.toml for typos or version conflicts.
```

### Level 3: CLI Entrypoint Validation

```bash
# Run the factory.py entry point
python factory.py --help

# Expected: The Typer-generated help message for the CLI should be displayed, indicating that the entry point is correctly wired to the CLI command module.
# If it fails, check the import paths and boilerplate in factory.py and src/narrative_factory/cli/commands.py.
```
