#!/bin/bash
# Phase 2 Validation Script

echo "🧪 Validating Phase 2 Easy Fixes..."

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

# Function to test a condition
test_condition() {
    local description="$1"
    local condition="$2"
    
    echo -n "  Testing: $description... "
    total_tests=$((total_tests + 1))
    
    if eval "$condition"; then
        echo "✅ PASS"
        passed_tests=$((passed_tests + 1))
    else
        echo "❌ FAIL"
        failed_tests=$((failed_tests + 1))
    fi
}

# Test MyPy configuration
echo "🔧 Testing MyPy Configuration..."
test_condition "MyPy config file exists" "[ -f mypy.ini ]"
test_condition "MyPy runs without module conflicts" "uv run mypy src/exceptions.py --config-file mypy.ini &>/dev/null"
test_condition "MyPy explicit package bases enabled" "grep -q 'explicit_package_bases = True' mypy.ini"

# Test development environment
echo "🚀 Testing Development Environment..."
test_condition "Dev setup script exists" "[ -f scripts/dev_setup.sh ]"
test_condition "Dev setup script is executable" "[ -x scripts/dev_setup.sh ]"
test_condition "Required directories exist" "[ -d logs ] && [ -d outputs/state ] && [ -d outputs/chapters ]"

# Test documentation
echo "📚 Testing Documentation..."
test_condition "README exists" "[ -f README.md ]"
test_condition "README has Quick Start section" "grep -q 'Quick Start' README.md"
test_condition "README has Development Setup" "grep -q 'Development Setup' README.md"

# Test tools availability
echo "🔍 Testing Tools Availability..."
test_condition "UV available" "command -v uv &>/dev/null"
test_condition "Ruff available via UV" "uv run ruff --version &>/dev/null"
test_condition "MyPy available via UV" "uv run mypy --version &>/dev/null"
test_condition "CLI available via UV" "uv run factory --help &>/dev/null"

# Summary
echo ""
echo "📊 Phase 2 Validation Summary:"
echo "  Total tests: $total_tests"
echo "  Passed: $passed_tests"
echo "  Failed: $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo "🎉 All Phase 2 Easy Fixes validated successfully!"
    exit 0
else
    echo "⚠️  Some Phase 2 issues found. Please review and fix."
    exit 1
fi