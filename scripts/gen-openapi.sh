#!/bin/bash
# Generate OpenAPI spec from FastAPI - scaffold placeholder

set -e

echo "Generating OpenAPI spec from FastAPI scaffold..."

cd apps/api
source .venv/bin/activate 2>/dev/null || true

python -c "
from app.main import app
import json
openapi = app.openapi()
with open('../../docs/api-spec.json', 'w') as f:
    json.dump(openapi, f, indent=2)
print('OpenAPI spec written to docs/api-spec.json')
" || echo "Failed - ensure backend deps installed and API starts"

echo "Done - scaffold placeholder"
