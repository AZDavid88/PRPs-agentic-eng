# Material Ingestion CLI Reference

This document provides comprehensive reference for the Phase 1B Material Ingestion CLI commands.

## Overview

The Material Ingestion CLI provides a user-friendly interface to the Narrative Factory Material Ingestion Pipeline, enabling efficient processing of story materials through LLM classification, embedding generation, and Qdrant storage with temporal gating.

## Commands

### `factory ingest-materials`

Ingest materials using the Material Ingestion Pipeline.

```bash
factory ingest-materials [FILES...] [OPTIONS]
```

**Arguments:**
- `FILES...` - Material files or directories to ingest (required)

**Options:**
- `--genre, -g` - Primary genre context for classification (default: unknown)
- `--additional-genres` - Comma-separated additional genres
- `--custom-categories` - Comma-separated custom categories
- `--mode, -m` - Processing mode: pipeline, agent, or hybrid (default: pipeline)
- `--batch-size, -b` - Batch size for processing (1-100, default: 10)
- `--confidence, -c` - Minimum confidence threshold (0.0-1.0, default: 0.7)
- `--dry-run` - Validate inputs without processing
- `--async/--sync` - Run in background (async) or foreground (sync, default: async)
- `--output, -o` - Output format: table, json, or stream (default: table)
- `--story-id` - Associate with specific story
- `--overwrite` - Overwrite existing materials with same content hash

**Examples:**
```bash
# Ingest a single story file
factory ingest-materials story.txt --genre fantasy

# Ingest multiple files with additional options
factory ingest-materials *.txt --genre romance --mode agent --batch-size 5

# Ingest a directory with custom categories
factory ingest-materials lore/ --genre fantasy --custom-categories "unique_magic,custom_creature"

# Dry run to validate before processing
factory ingest-materials materials/ --genre mystery --dry-run

# JSON output for programmatic use
factory ingest-materials story.txt --genre fantasy --output json
```

### `factory ingest-validate`

Validate materials before ingestion without processing.

```bash
factory ingest-validate [FILES...] [OPTIONS]
```

**Arguments:**
- `FILES...` - Files or directories to validate (required)

**Options:**
- `--genre, -g` - Genre context for validation (default: unknown)
- `--check-duplicates` - Check for duplicate content (default: true)
- `--estimate-cost` - Estimate processing costs (default: true)
- `--verbose, -v` - Show detailed validation results

**Examples:**
```bash
# Basic validation
factory ingest-validate story.txt

# Detailed validation with cost estimation
factory ingest-validate *.txt --verbose --estimate-cost

# Check for duplicates in a directory
factory ingest-validate lore/ --check-duplicates
```

### `factory ingest-status`

Check the status of material ingestion jobs.

```bash
factory ingest-status [JOB_ID] [OPTIONS]
```

**Arguments:**
- `JOB_ID` - Specific job ID to check (optional)

**Options:**
- `--all` - Show all ingestion jobs
- `--watch, -w` - Watch job progress in real-time
- `--interval` - Refresh interval for watch mode (seconds, default: 2)

**Examples:**
```bash
# Show pending ingestion jobs
factory ingest-status

# Check specific job
factory ingest-status ingest_abc12345

# Watch job progress
factory ingest-status ingest_abc12345 --watch

# Show all jobs
factory ingest-status --all
```

### `factory ingest-config`

Configure and test the material ingestion pipeline.

```bash
factory ingest-config [OPTIONS]
```

**Options:**
- `--test-connections` - Test service connections (default: true)
- `--setup` - Run interactive setup wizard
- `--show` - Show current configuration
- `--validate-keys` - Validate API keys (default: true)

**Examples:**
```bash
# Test current setup
factory ingest-config

# Show configuration
factory ingest-config --show

# Run setup wizard
factory ingest-config --setup

# Test connections only
factory ingest-config --test-connections --no-validate-keys
```

## Processing Modes

### Pipeline Mode (default)
- **Purpose**: Fast, efficient bulk processing
- **Cost**: Optimized for <$0.005 per material
- **Use case**: Large volumes of similar materials
- **Features**: Batch processing, cost optimization

### Agent Mode
- **Purpose**: Comprehensive analysis with detailed relationship mapping
- **Cost**: Higher cost but more thorough analysis
- **Use case**: Complex materials requiring detailed classification
- **Features**: Full agent integration, advanced cross-referencing

### Hybrid Mode
- **Purpose**: Automatic routing based on material complexity
- **Cost**: Balanced approach
- **Use case**: Mixed material types
- **Features**: Smart routing, adaptive processing

## Genre Support

### Built-in Genres
- `fantasy` - Magic systems, world-building, mythology, creatures
- `romance` - Relationship dynamics, emotional beats, romantic tension
- `mystery` - Clues, evidence, red herrings, investigative methods
- `thriller` - Tension mechanisms, chase elements, threat profiles
- `sci_fi` - Technology, scientific principles, future society
- `historical` - Period details, cultural norms, historical events
- `horror` - Threat entities, fear mechanisms, atmospheric elements
- `adventure` - Journey elements, obstacles, discoveries
- `literary` - Symbolic elements, thematic devices, literary techniques

### Multi-Genre Support
```bash
# Fantasy-Romance hybrid
factory ingest-materials story.txt --genre fantasy --additional-genres romance

# Custom categories for unique story elements
factory ingest-materials lore.txt --genre fantasy --custom-categories "time_magic,portal_system"
```

## Output Formats

### Table Format (default)
Rich-formatted tables with color coding and progress indicators.

### JSON Format
Machine-readable output for integration with other tools:
```json
{
  "job_id": "ingest_abc12345",
  "status": "completed",
  "materials_processed": 15,
  "processing_time": 45.2,
  "cost_estimate": 0.075,
  "average_confidence": 0.89,
  "category_distribution": {
    "character": 5,
    "magic_system": 3,
    "setting": 7
  }
}
```

### Stream Format
Real-time progress updates for long-running operations.

## File Support

### Supported Formats
- `.txt` - Plain text files
- `.md` - Markdown files

### File Requirements
- UTF-8 encoding
- Minimum 10 characters of content
- Maximum 10MB per file
- Regular file (not directories, symlinks, etc.)

### Directory Processing
When a directory is specified, the system automatically:
1. Recursively finds all `.txt` and `.md` files
2. Validates each file
3. Processes in batches for efficiency

## Error Handling

### Common Errors
- **File not found**: Check file paths and permissions
- **File too large**: Files must be <10MB
- **Invalid UTF-8**: Ensure text files are properly encoded
- **Rate limits**: Reduce batch size or wait before retrying
- **API key issues**: Check configuration with `factory ingest-config`

### Graceful Degradation
The system provides fallback processing for failed materials:
- Automatic retries with exponential backoff
- Fallback classification for LLM failures
- Partial processing completion for batch errors
- Detailed error reporting with suggested fixes

## Integration

### Story Association
```bash
# Associate materials with a specific story
factory ingest-materials lore/ --story-id "story_123" --genre fantasy
```

### Overwrite Protection
```bash
# Overwrite existing materials (use with caution)
factory ingest-materials updated_lore.txt --overwrite
```

### Cost Management
- Use `--dry-run` to estimate costs before processing
- Monitor costs with `factory ingest-status`
- Pipeline mode optimizes for cost efficiency
- Batch size tuning can reduce API costs

## Best Practices

### File Organization
```
project/
├── characters/           # Character descriptions
├── world_building/       # Settings and lore
├── magic_systems/        # Magic and technology
└── plot_elements/        # Story events and conflicts
```

### Batch Processing
- Start with small batches (5-10 materials) to test
- Increase batch size for efficiency once validated
- Use dry-run mode for large batches
- Monitor processing costs

### Genre Selection
- Choose the most dominant genre as primary
- Add secondary genres for hybrid stories
- Use custom categories for unique story elements
- Validate genre-specific categories with dry-run

### Quality Control
- Set appropriate confidence thresholds (0.7-0.9)
- Review failed materials for quality issues
- Use validation command before processing
- Check for duplicate content to avoid waste

## Troubleshooting

### Configuration Issues
```bash
# Check current configuration
factory ingest-config --show

# Test all connections
factory ingest-config --test-connections

# Validate API keys
factory ingest-config --validate-keys
```

### Processing Issues
```bash
# Validate files before processing
factory ingest-validate your_files/ --verbose

# Use dry-run to check setup
factory ingest-materials your_files/ --dry-run

# Reduce batch size for rate limit issues
factory ingest-materials your_files/ --batch-size 3
```

### Performance Optimization
```bash
# Use pipeline mode for bulk processing
factory ingest-materials large_batch/ --mode pipeline --batch-size 20

# Use agent mode for complex materials
factory ingest-materials complex_lore/ --mode agent --batch-size 5

# Use hybrid mode for mixed content
factory ingest-materials mixed_content/ --mode hybrid
```

## Advanced Usage

### Programmatic Integration
```bash
# JSON output for scripts
factory ingest-materials data/ --output json > results.json

# Batch processing with error handling
for file in *.txt; do
    factory ingest-materials "$file" --genre fantasy || echo "Failed: $file"
done
```

### Monitoring and Logging
- Check logs in `outputs/logs/` for detailed information
- Use `--watch` mode for real-time progress monitoring
- Monitor costs and performance with status commands

---

For more information about the Material Ingestion Pipeline architecture, see the [PRP Phase 1 documentation](PRPs/PRP_NF_PHASE_01_FOUNDATION.md).