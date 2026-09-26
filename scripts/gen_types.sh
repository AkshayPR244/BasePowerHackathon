#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
pnpm exec openapi-typescript ../contracts/openapi.json -o src/api/generated.ts
