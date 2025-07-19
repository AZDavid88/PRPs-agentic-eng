# CLI Reference - Universal Patterns

## Core Commands (Working)
- `uv run factory generate <seed>` - Basic generation
- `uv run factory generate-enhanced <story_seed>` - Enhanced generation with catalyst support
- `uv run factory inspect-memory <query>` - Memory inspection
- `uv run factory inspect-state` - State inspection
- `uv run factory catalyst-add <description>` - Add catalyst

## Common Parameter Patterns
- **Positional arguments**: Direct values (e.g., `"story seed"`)
- **Options**: Use double hyphens (`--dry-run`, `--details`, `--catalyst`)
- **Help**: Available for all commands (`--help`)

## Tool Execution Patterns
- **Linting**: `uv run ruff check <path> --fix`
- **Type checking**: `uv run mypy <path> --strict`
- **Testing**: `uv run pytest <path>/`
- **CLI tools**: `uv run <cli-name> <command>`

## Validation Commands (Tested)
```bash
# Static Analysis
uv run ruff check src/ --fix
uv run mypy src/ --strict

# CLI Testing
uv run factory --help
uv run factory inspect-memory --help
uv run factory generate-enhanced --help
uv run factory catalyst-add --help
```

## Error Prevention
- ✅ Always use `uv run` prefix for tools
- ✅ Use hyphens for multi-word commands
- ✅ Use positional args for main inputs
- ✅ Use `--flags` for options
- ❌ Don't use bare tool commands (`ruff`, `mypy`)
- ❌ Don't use underscores in command names
- ❌ Don't use flags for required arguments