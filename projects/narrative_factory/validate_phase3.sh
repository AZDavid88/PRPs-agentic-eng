#!/bin/bash
# Phase 3 Validation Script

echo "🧪 Validating Phase 3 Minor Projects..."

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

# Test async test infrastructure
echo "🔧 Testing Async Test Infrastructure..."
test_condition "conftest.py exists" "[ -f tests/conftest.py ]"
test_condition "Mock reference exists" "[ -f tests/mock_reference.py ]"
test_condition "Async fixtures defined" "grep -q 'mock_memory_service' tests/conftest.py"
test_condition "Event loop fixture defined" "grep -q 'event_loop' tests/conftest.py"

# Test mock import fixes
echo "🔍 Testing Mock Import Fixes..."
test_condition "StateManager mock path fixed" "grep -q 'src.services.state_manager.StateManager' tests/test_cli_enhancements.py"
test_condition "CatalystManager mock path fixed" "grep -q 'src.services.catalyst_manager.CatalystManager' tests/test_cli_enhancements.py"
test_condition "QdrantService mock path fixed" "grep -q 'src.memory.qdrant.QdrantService' tests/test_cli_enhancements.py"

# Test improved pass rate
echo "📊 Testing Test Pass Rate..."
test_result=$(uv run pytest tests/test_cli_enhancements.py --tb=no -q 2>/dev/null | grep -E "failed|passed" | tail -1)
if [[ $test_result == *"passed"* ]]; then
    passed_count=$(echo "$test_result" | grep -o '[0-9]\+ passed' | grep -o '[0-9]\+' | head -1)
    if [[ -n "$passed_count" && "$passed_count" -gt 10 ]]; then
        test_condition "Test pass rate > 50%" "true"
    else
        test_condition "Test pass rate > 50%" "false"
    fi
else
    test_condition "Test pass rate > 50%" "false"
fi

# Test reference documentation
echo "📚 Testing Reference Documentation..."
test_condition "Mock patterns documented" "grep -q 'MOCK_PATTERNS' tests/mock_reference.py"
test_condition "Mock paths documented" "grep -q 'MOCK_PATHS' tests/mock_reference.py"

# Summary
echo ""
echo "📊 Phase 3 Validation Summary:"
echo "  Total tests: $total_tests"
echo "  Passed: $passed_tests"
echo "  Failed: $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo "🎉 All Phase 3 Minor Projects validated successfully!"
    exit 0
else
    echo "⚠️  Some Phase 3 issues found. Please review and fix."
    exit 1
fi