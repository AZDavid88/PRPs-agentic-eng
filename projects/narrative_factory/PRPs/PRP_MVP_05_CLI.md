name: "MVP Phase 5: CLI Implementation & Finalization"
description: "Implements the user-facing Command-Line Interface (CLI) and finalizes the MVP by tying all components together."

---

## Goal

To create the primary user **command and control interface** for the MVP. This will be a `factory.py` CLI that allows a user to initiate, monitor, and manage the stateful, pausable narrative generation workflow.

## Why

- **User Interface:** A CLI is the simplest and most effective way to interact with the narrative engine for the MVP.
- **Workflow Management:** The CLI is the user's tool to interact with the Redis job store, allowing them to approve, reject, and monitor the status of generation tasks.
- **Entry Point:** It provides a single, unified entry point for all major operations, making the system easy to use.

## What

### Success Criteria

- [ ] A `factory.py` file exists at the project root.
- [ ] The CLI is built using `Typer`.
- [ ] A `generate` command is implemented that triggers the *start* of the Prefect `generation_flow`.
- [ ] An `ingest` command is implemented to populate the Qdrant database.
- [ ] New commands `review`, `approve`, `reject`, and `status` are implemented to manage the HITL workflow.
- [ ] The CLI interacts with the Redis job store to update and query the state of jobs.

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

# Use Context7 for multi-command CLI applications
use context7 for library /fastapi/typer topic "CLI applications with multiple subcommands"

# Use Context7 for CLI testing with CliRunner
use context7 for library /fastapi/typer topic "testing CLI applications with CliRunner"

# Use Context7 for advanced CLI patterns
use context7 for library /fastapi/typer topic "CLI callbacks, contexts, and rich integration"
```

**Why Context7 Enhances This PRP:**
- **Typer Framework**: Latest command patterns, argument handling, and rich integration for modern CLIs
- **CLI Testing**: Advanced testing patterns for command-line applications using CliRunner
- **Entry Points**: Current best practices for Python script execution and entry point configuration
- **User Experience**: Modern CLI patterns for progress indicators, error handling, and user feedback
- **Multi-Command Apps**: Advanced patterns for creating complex CLI applications with multiple subcommands
- **Testing Frameworks**: Comprehensive testing strategies using `CliRunner` for robust CLI validation
- **Rich Integration**: Modern CLI UX patterns with progress bars, colored output, and interactive elements

**Critical Context7 Patterns for CLI:**
- **Command Structure**: Use `typer.Typer()` with `@app.command()` decorators for clean command organization
- **Argument Validation**: Implement proper type hints and validation for CLI arguments and options
- **Error Handling**: Use `typer.echo()` and `typer.Exit()` for consistent error reporting and graceful exits
- **Testing Patterns**: Leverage `CliRunner` for comprehensive CLI testing with mocked dependencies
- **Help Generation**: Use docstrings and `typer.Option()` descriptions for auto-generated help text
- **Command Grouping**: Organize related commands into logical groups for better user experience
- **Progress Indicators**: Implement progress bars and status updates for long-running operations
- **Configuration Management**: Handle configuration files and environment variables for CLI settings

## Implementation Blueprint

## Implementation Blueprint

1.  **MODIFY** `src/narrative_factory/cli/commands.py`.
2.  **IMPORT** `typer`, the Prefect `generation_flow`, and the `JobStore` service.
3.  **CREATE** a Typer app instance and an instance of the `JobStore`.
4.  **IMPLEMENT** the `generate` command to start the workflow.
5.  **IMPLEMENT** the `ingest` command for data population.
6.  **IMPLEMENT** the new workflow management commands:
    -   `status [--agent <name>]`: Lists jobs from the `JobStore`.
    -   `review <job_id>`: Fetches a job's output from the `JobStore` and prints it.
    -   `approve <job_id>`: Updates the job status to `approved` in the `JobStore` and triggers the event to resume the Prefect flow.
    -   `reject <job_id> --feedback "<text>"`: Updates status to `rejected`, saves the feedback, and triggers the re-run event.
7.  **MODIFY** the root `factory.py` to run the Typer app.

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
