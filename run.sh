#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Java 11 → 21 Migration Agent  |  run.sh
#  Usage: ./run.sh <github-repo-url>
# ─────────────────────────────────────────────────────────

set -e

# ── Check Docker ──
if ! docker info > /dev/null 2>&1; then
    echo ""
    echo "❌  Docker is not running."
    echo "    Please open Docker Desktop and wait for the whale icon to appear."
    exit 1
fi

# ── Check API key ──
if [ -z "$GEMINI_API_KEY" ]; then
    echo ""
    echo "❌  GEMINI_API_KEY is not set."
    echo ""
    echo "    Run this first:"
    echo "      export GEMINI_API_KEY=sk-ant-YOUR-KEY-HERE"
    echo ""
    echo "    Then run:"
    echo "      ./run.sh <github-repo-url>"
    exit 1
fi

# ── Check repo URL ──
if [ -z "$1" ]; then
    echo ""
    echo "Usage:   ./run.sh <github-repo-url>"
    echo ""
    echo "Example:"
    echo "  ./run.sh https://github.com/spring-projects/spring-petclinic"
    exit 1
fi

REPO_URL="$1"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ☕  Java 11 → 21 Migration Agent           ║"
echo "║   A: Build Config  B: Code  C: Dependencies  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Repo: $REPO_URL"
echo ""

# ── Build Docker image ──
echo "🐳  Building Docker image (first time takes ~2 min)..."
docker build -t java-migration-agent . 2>&1 | tail -5
echo ""

# ── Create output folder ──
mkdir -p ./output

# ── Run the agent ──
echo "🚀  Starting migration..."
echo ""
docker run --rm \
    -e GEMINI_API_KEY="$GEMINI_API_KEY" \
    -v "$(pwd)/output:/workspace/output" \
    java-migration-agent "$REPO_URL"
