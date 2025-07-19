#!/bin/bash
# Development Environment Setup Script

echo "🚀 Setting up Narrative Factory development environment..."

# Install dependencies
echo "📦 Installing Python dependencies..."
if ! command -v uv &> /dev/null; then
    echo "❌ UV not found. Please install UV first: https://docs.astral.sh/uv/"
    exit 1
fi

uv sync

# Set up pre-commit hooks (if available)
echo "🔧 Setting up pre-commit hooks..."
if uv run pre-commit install 2>/dev/null; then
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  Pre-commit not configured (optional)"
fi

# Verify tool availability
echo "🔍 Verifying tool availability..."
echo -n "  Ruff: "
if uv run ruff --version &>/dev/null; then
    echo "✅ $(uv run ruff --version)"
else
    echo "❌ Not available"
fi

echo -n "  MyPy: "
if uv run mypy --version &>/dev/null; then
    echo "✅ $(uv run mypy --version)"
else
    echo "❌ Not available"
fi

echo -n "  Pytest: "
if uv run pytest --version &>/dev/null; then
    echo "✅ $(uv run pytest --version | head -1)"
else
    echo "❌ Not available"
fi

# Test basic functionality
echo "🧪 Testing basic CLI functionality..."
if uv run factory --help > /dev/null 2>&1; then
    echo "✅ CLI working"
else
    echo "❌ CLI failed"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs
mkdir -p outputs/state
mkdir -p outputs/chapters

echo "✅ Development environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Run validation: ./validate_tool_standards.sh"
echo "  2. Run tests: uv run pytest tests/ -v"
echo "  3. Check types: uv run mypy src/"
echo "  4. Format code: uv run ruff check src/ --fix"