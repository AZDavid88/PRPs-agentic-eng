# Narrative Factory

AI-powered storytelling engine with Human-in-the-Loop workflow.

## Quick Start

### Development Setup

```bash
# Clone and setup
git clone <repository>
cd narrative_factory
./scripts/dev_setup.sh
```

### Manual Setup

```bash
# Install dependencies
uv sync

# Verify installation
uv run factory --help
```

## Usage

### Basic Generation
```bash
# Start basic generation
uv run factory generate "A mysterious letter arrives"

# Check status
uv run factory status

# Review output
uv run factory review <job_id>

# Approve and continue
uv run factory approve <job_id>
```

### Enhanced Generation (Phase 4)
```bash
# Enhanced generation with catalyst
uv run factory generate-enhanced "A storm approaches" --catalyst "Ancient magic awakens"

# Dry run mode
uv run factory generate-enhanced "The hero's journey begins" --dry-run

# Inspect memory
uv run factory inspect-memory "Elara" --limit 5

# Inspect story state
uv run factory inspect-state --details

# Manage catalysts
uv run factory catalyst-add "A mysterious stranger arrives" --priority 8
uv run factory catalyst-list --summary
```

## Development

### Running Validation

```bash
# Run all validation commands
./validate_tool_standards.sh

# Run specific validation
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest tests/ -v
```

### Project Structure

```
narrative_factory/
├── src/                 # Source code
│   ├── agents/         # AI agents (Director, Tactician, Weaver, Canonist)
│   ├── cli/           # Command-line interface
│   ├── memory/        # Vector database and memory management
│   ├── models/        # Pydantic models
│   ├── services/      # Business logic services
│   └── workflows/     # Prefect workflows
├── scripts/           # Development scripts
├── tests/            # Test suites
├── PRPs/             # Product Requirement Prompts
└── outputs/          # Generated content
```

### Configuration

- `mypy.ini` - MyPy type checking configuration
- `pyproject.toml` - Project dependencies and settings
- `TOOL_EXECUTION_STANDARDS.md` - Tool usage standards
- `CLI_REFERENCE.md` - Command reference guide

## Architecture

The Narrative Factory uses a multi-agent architecture:

1. **Director**: Strategic narrative planning
2. **Tactician**: Detailed chapter planning
3. **Weaver**: Prose generation
4. **Canonist**: Continuity validation

Each agent can pause for human review, enabling Human-in-the-Loop storytelling.

## Requirements

- Python 3.12+
- UV package manager
- Redis (for job state)
- Qdrant (for vector storage)
- OpenAI API key or Google Gemini API key