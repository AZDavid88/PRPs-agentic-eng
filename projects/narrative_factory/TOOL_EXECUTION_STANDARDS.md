# Tool Execution Standards - Universal Patterns

## Required Prefixes for UV-based Projects
- `uv run <tool> <args>` (NOT `<tool> <args>`)
- `uv run ruff check <path> --fix` (NOT `ruff check <path>`)
- `uv run mypy <path> --strict` (NOT `mypy <path> --strict`)
- `uv run pytest <path>/` (NOT `pytest <path>/`)
- `uv run <cli-tool> <command>` (NOT `<cli-tool> <command>`)

## CLI Command Naming Convention
- Use hyphens for multi-word commands: `command-name` (NOT `command-name`)
- Use consistent verb-noun patterns: `inspect-memory`, `generate-enhanced`
- Maintain command consistency across all subcommands

## Validation Command Template
```bash
# Static Analysis Pattern
uv run ruff check <source-path> --fix
uv run mypy <source-path> --strict

# Functional Testing Pattern
uv run <cli-tool> <command> <positional-args> --flag-args
```

## CLI Parameter Patterns
- Positional arguments: Direct values (NOT --flag-name)
- Options: Use double hyphens (--dry-run, --details, --verbose)
- Help: Available for all commands (--help)

## Error Pattern Recognition
- **Command not found**: Missing `uv run` prefix
- **Invalid option**: Using flags for positional arguments
- **Wrong command name**: Using underscores instead of hyphens

## Correction Strategy
1. **Audit**: Find all tool invocations in documentation
2. **Standardize**: Apply consistent prefixing and naming
3. **Validate**: Test each corrected command
4. **Document**: Create reference for future use