#!/bin/sh
set -eu

alembic upgrade head
python -m app.scripts.seed
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
