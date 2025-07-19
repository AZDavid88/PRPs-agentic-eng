#!/bin/bash
# Universal Tool Execution Standards Fix Script
# Applies standardized patterns to documentation and scripts

set -e

echo "🔧 Applying Universal Tool Execution Standards..."

# Function to apply fixes to a file
apply_standards() {
    local file="$1"
    echo "  📝 Processing: $file"
    
    # Add uv run prefix to common tools
    sed -i 's/^ruff check/uv run ruff check/g' "$file"
    sed -i 's/^mypy /uv run mypy /g' "$file"
    sed -i 's/^pytest /uv run pytest /g' "$file"
    
    # Fix CLI command patterns (only in markdown files)
    if [[ "$file" == *.md ]]; then
        sed -i 's/\b\([a-zA-Z_]*\)_\([a-zA-Z_]*\)\b/\1-\2/g' "$file"
    fi
    
    echo "  ✅ Standards applied to: $file"
}

# Find and process all relevant files
echo "🔍 Finding documentation files..."
find . -name "*.md" -type f | while read -r file; do
    if grep -q "ruff\|mypy\|pytest" "$file"; then
        apply_standards "$file"
    fi
done

echo "🔍 Finding shell scripts..."
find . -name "*.sh" -type f | while read -r file; do
    if grep -q "ruff\|mypy\|pytest" "$file"; then
        apply_standards "$file"
    fi
done

echo "✅ Tool execution standards applied successfully!"
echo "💡 Run validation script to verify changes..."