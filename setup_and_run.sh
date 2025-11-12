#!/bin/bash
# Setup and run script for LiveKit Interrupt Handler
# This script sets up the environment and runs all tests

set -e  # Exit on error

echo "============================================================"
echo "LiveKit Interrupt Handler - Setup and Validation"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Found Python $python_version"

# Create virtual environment
echo ""
echo "🔧 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   ✅ Virtual environment created"
else
    echo "   ℹ️  Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate
echo "   ✅ Virtual environment activated"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q --upgrade pip
pip install -q pytest pytest-asyncio
echo "   ✅ Dependencies installed"

# Create directories
echo ""
echo "📁 Creating project directories..."
mkdir -p tests demo benchmarks logs
touch tests/__init__.py demo/__init__.py benchmarks/__init__.py
echo "   ✅ Directories created"

# Set environment variables
echo ""
echo "⚙️  Setting environment variables..."
export IGNORED_WORDS="uh,umm,hmm,haan"
export COMMAND_WORDS="wait,stop,no,hold"
export CONFIDENCE_THRESHOLD="0.3"
export LOG_FILE="logs/interrupts.jsonl"
export ENABLE_LOGGING="true"
echo "   ✅ Environment configured"

# Run configuration check
echo ""
echo "🔍 Checking configuration..."
python config.py
echo ""

# Run tests
echo "============================================================"
echo "🧪 Running Test Suite"
echo "============================================================"
echo ""
pytest tests/ -v --tb=short
test_result=$?

if [ $test_result -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests PASSED!${NC}"
else
    echo ""
    echo -e "${RED}❌ Some tests FAILED${NC}"
    exit 1
fi

# Run benchmarks
echo ""
echo "============================================================"
echo "⚡ Running Performance Benchmarks"
echo "============================================================"
echo ""
python benchmarks/run_benchmark.py
benchmark_result=$?

if [ $benchmark_result -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All benchmarks PASSED!${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠️  Some benchmarks did not meet targets${NC}"
fi

# Run demo
echo ""
echo "============================================================"
echo "🎬 Running Interactive Demo"
echo "============================================================"
echo ""
read -p "Run interactive demo? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python demo/simulate_agent.py
fi

# Show logs
echo ""
echo "============================================================"
echo "📊 Log File Summary"
echo "============================================================"
if [ -f "logs/interrupts.jsonl" ]; then
    echo ""
    echo "Total events logged:"
    wc -l logs/interrupts.jsonl
    echo ""
    echo "Events by action:"
    grep -o '"action":"[^"]*"' logs/interrupts.jsonl | sort | uniq -c
    echo ""
    echo "Log file location: logs/interrupts.jsonl"
else
    echo "No log file generated yet"
fi

# Final summary
echo ""
echo "============================================================"
echo "✅ Setup and Validation Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "1. Review the logs in logs/interrupts.jsonl"
echo "2. Check out README.md for detailed documentation"
echo "3. Integrate with your LiveKit agent using LiveKitAgentAdapter"
echo ""
echo "For manual testing:"
echo "  source venv/bin/activate"
echo "  python demo/simulate_agent.py"
echo ""
echo "For running tests again:"
echo "  pytest tests/ -v"
echo ""
echo "For benchmarks:"
echo "  python benchmarks/run_benchmark.py"
echo ""
echo "Happy coding! 🚀"
