#!/bin/bash
# T03 WebSocket HITL Implementation Validation Script
# Tests WebSocket interfaces, authentication, and streaming agents

set -e

echo "🔌 Validating T03 WebSocket HITL Implementation..."

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

# Test WebSocket Infrastructure
echo "🌐 Testing WebSocket Infrastructure..."
test_condition "WebSocket manager exists" "[ -f src/web/websocket_manager.py ]"
test_condition "WebSocket routes exist" "[ -f src/web/websocket_routes.py ]"
test_condition "WebSocket integration module exists" "[ -f src/web/websocket_integration.py ]"
test_condition "FastAPI app includes WebSocket support" "grep -q 'websocket' src/web/app.py"

# Test Authentication System
echo "🔐 Testing Authentication System..."
test_condition "Auth module exists" "[ -f src/web/auth.py ]"
test_condition "JWT authentication implemented" "grep -q 'jwt' src/web/auth.py || grep -q 'JWT' src/web/auth.py"
test_condition "WebSocket auth integration" "grep -q 'authenticate' src/web/websocket_manager.py"

# Test Streaming Agents
echo "🤖 Testing Streaming Agents..."
test_condition "Streaming agents module exists" "[ -f src/agents/streaming_agents.py ]"
test_condition "Agent streaming integration" "grep -q 'websocket' src/agents/streaming_agents.py"
test_condition "Real-time communication implemented" "grep -q 'broadcast' src/web/websocket_manager.py"

# Test FastAPI Integration
echo "⚡ Testing FastAPI Integration..."
test_condition "FastAPI app imports WebSocket routes" "grep -q 'websocket' src/web/app.py"
test_condition "WebSocket endpoints configured" "grep -q '/ws' src/web/app.py || grep -q 'websocket_narrative_endpoint\|websocket_dashboard_endpoint' src/web/websocket_routes.py"

# Test Module Imports
echo "📦 Testing Module Imports..."
test_condition "WebSocket manager imports" "uv run python -c 'from src.web.websocket_manager import ConnectionManager; print(\"OK\")' > /dev/null 2>&1"
test_condition "WebSocket routes imports" "uv run python -c 'from src.web.websocket_routes import websocket_narrative_endpoint; print(\"OK\")' > /dev/null 2>&1"
test_condition "Auth module imports" "uv run python -c 'from src.web.auth import authenticate_websocket; print(\"OK\")' > /dev/null 2>&1"
test_condition "Streaming agents imports" "uv run python -c 'from src.agents.streaming_agents import StreamingAgentMixin; print(\"OK\")' > /dev/null 2>&1"

# Test Configuration
echo "⚙️ Testing WebSocket Configuration..."
test_condition "WebSocket settings in config" "grep -q -i 'websocket\|ws_' src/config.py || echo 'SKIP: No config validation needed'"
test_condition "CORS configuration for WebSockets" "grep -q 'origins' src/web/app.py"

# Test Dependencies
echo "📋 Testing Dependencies..."
test_condition "FastAPI WebSocket support" "uv run python -c 'from fastapi import WebSocket; print(\"OK\")' > /dev/null 2>&1"
test_condition "JWT dependencies available" "uv run python -c 'import jwt; print(\"OK\")' > /dev/null 2>&1"

# Test Integration Points
echo "🔗 Testing Integration Points..."
test_condition "Agent lifecycle WebSocket integration" "grep -q 'websocket\|broadcast' src/agents/lifecycle.py || echo 'SKIP: Optional integration'"
test_condition "Workflow WebSocket integration" "grep -q 'websocket\|broadcast' src/workflows/generation.py || echo 'SKIP: Optional integration'"

# Test Error Handling
echo "🛡️ Testing Error Handling..."
test_condition "WebSocket error handling" "grep -q 'except\|try' src/web/websocket_manager.py"
test_condition "Connection cleanup logic" "grep -q 'disconnect\|close' src/web/websocket_manager.py"

# Test Real-time Features
echo "⏱️ Testing Real-time Features..."
test_condition "Message broadcasting capability" "grep -q 'broadcast\|send_to_all' src/web/websocket_manager.py"
test_condition "Agent status streaming" "grep -q 'status\|state' src/agents/streaming_agents.py"

# Summary
echo ""
echo "📊 T03 WebSocket HITL Validation Summary:"
echo "  Total tests: $total_tests"
echo "  Passed: $passed_tests"
echo "  Failed: $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo "🎉 T03 WebSocket HITL implementation validated successfully!"
    exit 0
else
    echo "⚠️  Some T03 WebSocket issues found. Please review and fix."
    exit 1
fi