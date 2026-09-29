#!/bin/bash
# NEXUS (Codename) - Dev Script - Scaffold
# Starts infra (postgres, redis) and api + web

set -e

echo "NEXUS (Codename) - Dev Setup - Scaffold Phase"
echo "Temporary codename, public name TBD"
echo ""

# Check .env
if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
  echo "Please edit .env if needed, then rerun"
fi

# Check pnpm
if ! command -v pnpm &> /dev/null; then
  echo "pnpm not found, enabling via corepack..."
  corepack enable
  corepack prepare pnpm@9.12.3 --activate
fi

# Check python
if ! command -v python3 &> /dev/null; then
  echo "python3 not found, please install Python 3.12"
  exit 1
fi

echo "Starting infra (postgres + redis) via Docker Compose..."
docker compose -f infra/docker-compose.yml up -d postgres redis

echo "Waiting for postgres and redis to be healthy..."
sleep 5

echo "Installing frontend deps (if needed)..."
if [ ! -d "apps/web/node_modules" ]; then
  pnpm install
fi

echo "Installing backend deps (if needed)..."
if [ ! -d "apps/api/.venv" ]; then
  cd apps/api
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cd ../..
fi

echo ""
echo "Dev setup complete - scaffold phase"
echo ""
echo "To start API:"
echo "  cd apps/api && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "To start Web:"
echo "  pnpm dev:web  # http://localhost:3000"
echo ""
echo "To check health:"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:8000/version"
echo ""
echo "Docker Compose all services:"
echo "  docker compose -f infra/docker-compose.yml up -d"
echo ""
echo "Scaffold limitations: No real agents, MCP, RAG, LLM calls yet"
