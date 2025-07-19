#!/bin/bash
# Phase 4 Validation Script - API Migration

echo "🧪 Validating Phase 4 API Migration..."

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

# Test API migration script existence
echo "🔧 Testing Migration Infrastructure..."
test_condition "Migration script exists" "[ -f scripts/migrate_apis.py ]"
test_condition "Migration script is executable" "[ -x scripts/migrate_apis.py ]"

# Test deprecated pattern removal
echo "🔍 Testing Deprecated Pattern Removal..."
test_condition "No @validator decorators remain" "! grep -r '@validator' src/ --include='*.py'"
test_condition "No datetime.utcnow() calls remain" "! grep -r 'datetime\.utcnow()' src/ --include='*.py'"
test_condition "No .dict() calls remain" "! grep -r '\.dict()' src/ --include='*.py'"
test_condition "No .json() calls remain" "! grep -r '\.json()' src/ --include='*.py'"
test_condition "No .copy() calls remain" "! grep -r '\.copy()' src/ --include='*.py'"

# Test modern API adoption
echo "🚀 Testing Modern API Adoption..."
test_condition "field_validator imports present" "grep -q 'field_validator' src/config.py"
test_condition "timezone import present" "grep -q 'timezone' src/logger.py || grep -q 'timezone' src/health.py"
test_condition "model_dump usage present" "grep -q 'model_dump' src/agents/communication.py"
test_condition "model_copy usage present" "grep -q 'model_copy' src/exceptions.py"

# Test syntax validation
echo "📋 Testing Syntax Validation..."
test_condition "Config file syntax valid" "uv run python -c 'from src.config import config; print(\"OK\")' > /dev/null 2>&1"
test_condition "Logger file syntax valid" "uv run python -c 'from src.logger import logger; print(\"OK\")' > /dev/null 2>&1"
test_condition "Health file syntax valid" "uv run python -c 'from src.health import HealthStatus; print(\"OK\")' > /dev/null 2>&1"

# Test static analysis
echo "🔍 Testing Static Analysis..."
test_condition "Ruff passes on migrated config" "uv run ruff check src/config.py > /dev/null 2>&1"
test_condition "MyPy passes on migrated config" "uv run mypy src/config.py > /dev/null 2>&1"

# Test functional validation
echo "🧪 Testing Functional Validation..."
test_condition "datetime.now(timezone.utc) works" "uv run python -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc))' > /dev/null 2>&1"
test_condition "field_validator works" "uv run python -c 'from src.config import ModelSettings; m = ModelSettings(); print(\"OK\")' > /dev/null 2>&1"

# Test deprecation warnings
echo "⚠️  Testing Deprecation Warnings..."
warning_output=$(uv run python -c "import warnings; warnings.simplefilter('always'); from src.config import config; print('No warnings')" 2>&1 | grep -v "INFO")
if [[ "$warning_output" == *"DeprecationWarning"* ]] || [[ "$warning_output" == *"deprecated"* ]]; then
    test_condition "No Pydantic deprecation warnings" "false"
else
    test_condition "No Pydantic deprecation warnings" "true"
fi

# Summary
echo ""
echo "📊 Phase 4 Validation Summary:"
echo "  Total tests: $total_tests"
echo "  Passed: $passed_tests"
echo "  Failed: $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo "🎉 All Phase 4 API migrations validated successfully!"
    exit 0
else
    echo "⚠️  Some Phase 4 issues found. Please review and fix."
    exit 1
fi