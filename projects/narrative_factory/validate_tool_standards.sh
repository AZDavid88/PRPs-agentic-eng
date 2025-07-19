#!/bin/bash
# Universal Tool Standards Validation Script
# Tests that all tool invocations follow standard patterns

set -e

echo "🧪 Validating Tool Execution Standards..."

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

# Function to test a pattern
test_pattern() {
    local description="$1"
    local pattern="$2"
    local should_find="$3"  # true if pattern should be found, false if it shouldn't
    
    echo -n "  Testing: $description... "
    total_tests=$((total_tests + 1))
    
    if find . -name "*.md" -o -name "*.sh" | xargs grep -l "$pattern" >/dev/null 2>&1; then
        if [ "$should_find" = "true" ]; then
            echo "✅ PASS"
            passed_tests=$((passed_tests + 1))
        else
            echo "❌ FAIL (found unwanted pattern)"
            failed_tests=$((failed_tests + 1))
        fi
    else
        if [ "$should_find" = "false" ]; then
            echo "✅ PASS"
            passed_tests=$((passed_tests + 1))
        else
            echo "❌ FAIL (pattern not found)"
            failed_tests=$((failed_tests + 1))
        fi
    fi
}

# Test for good patterns (should exist)
echo "🟢 Testing for correct patterns..."
test_pattern "UV prefix for ruff" "uv run ruff" "true"
test_pattern "UV prefix for mypy" "uv run mypy" "true"

# Test for bad patterns (should not exist)
echo "🔴 Testing for incorrect patterns..."
test_pattern "Bare ruff commands" "^ruff check" "false"
test_pattern "Bare mypy commands" "^mypy " "false"

# Test CLI command naming
echo "🔧 Testing CLI command naming..."
if command -v uv >/dev/null 2>&1; then
    # Only test if uv is available
    echo "  UV available - testing CLI commands..."
    # Add specific CLI tests here based on project
else
    echo "  UV not available - skipping CLI tests"
fi

# Summary
echo ""
echo "📊 Validation Summary:"
echo "  Total tests: $total_tests"
echo "  Passed: $passed_tests"
echo "  Failed: $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo "🎉 All tool execution standards validated successfully!"
    exit 0
else
    echo "⚠️  Some standards violations found. Please review and fix."
    exit 1
fi