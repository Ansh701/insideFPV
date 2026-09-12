from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.db import get_session
from app.models import MonitorRun

router = APIRouter(tags=["monitoring"])


@router.get("/api/monitor/runs")
async def list_monitor_runs(
    limit: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    rows = list(
        (
            await session.scalars(
                select(MonitorRun).order_by(MonitorRun.started_at.desc()).limit(limit)
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "status": row.status,
                "trigger": row.trigger,
                "products_checked": row.products_checked,
                "products_changed": row.products_changed,
                "alerts_created": row.alerts_created,
                "errors_count": row.errors_count,
                "error_summary": row.error_summary,
            }
            for row in rows
        ]
    }


@router.post("/api/admin/monitor/run", dependencies=[Depends(require_admin)])
async def run_monitor(request: Request) -> dict[str, object]:
    result = await request.app.state.monitor.run(trigger="admin")
    return {
        "id": result.id,
        "status": result.status,
        "products_checked": result.products_checked,
        "products_changed": result.products_changed,
        "alerts_created": result.alerts_created,
        "errors_count": result.errors_count,
        "error_summary": result.error_summary,
    }
