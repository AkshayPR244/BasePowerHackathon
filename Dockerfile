# One service: FastAPI serves the API and the built UI on the same origin.
FROM node:22-slim AS ui
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY contracts/ /app/contracts/
RUN VITE_API_MODE=live pnpm exec vite build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY data/ /app/data/
COPY contracts/ /app/contracts/
COPY --from=ui /app/frontend/dist /app/frontend/dist
# Bake the battery value cache so the first request is fast (about 2 minutes at build).
RUN uv run --no-dev python -c "from app.api import warm; warm._run(); print(warm.status())"
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uv run --no-dev uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
