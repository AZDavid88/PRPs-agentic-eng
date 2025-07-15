name: "MVP Phase 5: CLI Implementation & Finalization"
description: "Implements the user-facing Command-Line Interface (CLI) and finalizes the MVP by tying all components together."

---

## Goal

To create the primary user interface for the MVP: a `factory.py` CLI with `ingest` and `generate` commands. This PRP also includes notes on the project's future evolution, bridging the gap between the MVP and the full vision.

## Why

- **User Interface:** A CLI is the simplest and most effective way to interact with the narrative engine for the MVP.
- **Entry Point:** It provides a single, unified entry point for all major operations, making the system easy to use.
- **Automation:** A CLI is easily scriptable, allowing for future automation and integration with other tools.

## What

### Success Criteria

- [ ] A `factory.py` file exists at the project root.
- [ ] The CLI is built using `Typer`.
- [ ] A `generate` command is implemented that accepts a `--seed` and triggers the Prefect `generation_flow`.
- [ ] An `ingest` command is implemented that runs the `scripts/ingest.py` logic to populate the Qdrant database.
- [ ] The CLI provides helpful feedback to the user (e.g., "Generation complete," "Ingestion started...").

## Context7 Documentation Injection

Before implementation, inject real-time documentation for key libraries:

```bash
# Use Context7 for Typer CLI framework
use context7 for library /fastapi/typer topic "CLI applications and command definition"

# Use Context7 for CLI testing patterns
use context7 for typer topic "testing CLI applications with CliRunner"

# Use Context7 for Python entry points
use context7 for python topic "setuptools entry points and executable scripts"

# Use Context7 for CLI argument handling
use context7 for typer topic "command options, arguments, and rich integration"
```

**Why Context7 Enhances This PRP:**
- **Typer Framework**: Latest command patterns, argument handling, and rich integration for modern CLIs
- **CLI Testing**: Advanced testing patterns for command-line applications using CliRunner
- **Entry Points**: Current best practices for Python script execution and entry point configuration
- **User Experience**: Modern CLI patterns for progress indicators, error handling, and user feedback

## Implementation Blueprint

### List of tasks to be completed

1.  **MODIFY** `src/narrative_factory/cli/commands.py`.
2.  **IMPORT** `typer`, and the Prefect `generation_flow`.
3.  **CREATE** a Typer app instance: `app = typer.Typer()`.
4.  **IMPLEMENT** the `generate` command:
    -   Use the `@app.command()` decorator.
    -   Accept a `seed: str` as an argument.
    -   Inside the function, call `generation_flow(seed)`.
    -   Print the result to the console.
5.  **IMPLEMENT** the `ingest` command:
    -   Use the `@app.command()` decorator.
    -   Inside the function, import and run the logic from `scripts/ingest.py`.
6.  **MODIFY** the root `factory.py` file.
    -   Import the `app` object from `src/narrative_factory/cli/commands.py`.
    -   In an `if __name__ == "__main__":` block, call `app()`. This makes the script executable.

## Validation Loop

### Level 1: CLI Command Validation

```bash
# Test the help message for the generate command
python factory.py generate --help

# Expected: Should display the help text for the generate command, including the --seed option.

# Test the help message for the ingest command
python factory.py ingest --help

# Expected: Should display the help text for the ingest command.
```

### Level 2: End-to-End Test (Mocked)

This test will invoke the CLI command but mock the Prefect flow itself, verifying that the CLI correctly calls the flow with the right parameters.

```python
# In a new file: tests/test_cli.py
from typer.testing import CliRunner
from narrative_factory.cli.commands import app

runner = CliRunner()

def test_generate_command(mocker):
    """Tests that the generate CLI command calls the Prefect flow."""
    # Mock the flow function
    mock_flow = mocker.patch('narrative_factory.cli.commands.generation_flow')
    mock_flow.return_value = "Mocked chapter text."

    result = runner.invoke(app, ["generate", "--seed", "My test seed"])

    # Assert the command ran successfully
    assert result.exit_code == 0
    assert "Mocked chapter text." in result.stdout

    # Assert the flow was called with the correct seed
    mock_flow.assert_called_once_with("My test seed")
```

```bash
# Run and iterate until passing:
uv run pytest tests/test_cli.py -v
```

---

## Path to Full Vision: The "Bridge" PRP

This MVP is the foundational engine. The `NARRATIVE_FACTORY_PRP_v3.md` document outlines the ultimate goal of a full-stack web application. Once this CLI-based MVP is complete and validated, the next step will be to create a **new "Bridge" PRP** using the `prp_planning.md` template.

This future PRP will not be written now, as it must be informed by the lessons learned during MVP development. However, its purpose will be to detail the following transition:

1.  **Project Restructuring:** Migrating the self-contained MVP structure into the `backend/` directory of a new monorepo.
2.  **API Layer Creation:** Building a FastAPI application in `backend/` that wraps the core narrative engine logic (`agents`, `memory`, `workflows`). The FastAPI endpoints will replace the CLI as the primary interface.
3.  **Frontend Scaffolding:** Initializing a React/TypeScript application in a new `frontend/` directory.
4.  **API Contract Definition:** Formally defining the REST API and WebSocket contract that the frontend will use to communicate with the backend.

By completing this MVP first, we ensure the core logic is sound before building the complex UI on top of it, making the "Bridge" phase significantly more likely to succeed.
