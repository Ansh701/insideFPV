FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend
COPY backend/ ./
RUN pip install --no-cache-dir .

COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN chmod 0555 scripts/start-production.sh \
    && addgroup --system rotorwatch \
    && adduser --system --ingroup rotorwatch rotorwatch \
    && chown -R rotorwatch:rotorwatch /app

USER rotorwatch
EXPOSE 10000

CMD ["./scripts/start-production.sh"]
