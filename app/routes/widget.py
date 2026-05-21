import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_admin, get_session
from app.db.models import User
from app.repositories import widget as widget_repo
from app.schemas.widget import WidgetRead, WidgetUpdate

router = APIRouter(prefix="/widget", tags=["widget"])


@router.get("/config/{widget_id}", response_model=WidgetRead)
async def get_widget_config(
    widget_id: uuid.UUID,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> WidgetRead:
    """Public — returns widget config and sets CSP frame-ancestors header."""
    widget = await widget_repo.get_by_id(session, widget_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")
    origins = " ".join(widget.allowed_origins) if widget.allowed_origins else "'none'"
    response.headers["Content-Security-Policy"] = f"frame-ancestors {origins}"
    return WidgetRead.model_validate(widget)


@router.patch("/config/{widget_id}", response_model=WidgetRead)
async def update_widget_config(
    widget_id: uuid.UUID,
    body: WidgetUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_admin),
) -> WidgetRead:
    """Admin only — update widget config from Streamlit admin page."""
    widget = await widget_repo.update(
        session, widget_id, **{k: v for k, v in body.model_dump().items() if v is not None}
    )
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")
    await session.commit()
    await session.refresh(widget)
    return WidgetRead.model_validate(widget)
