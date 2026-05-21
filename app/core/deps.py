"""Central dependency registry for FastAPI routes.

Import all Depends() callables from here rather than from individual service
or db modules. Internal auth plumbing (get_user_db, get_user_manager) stays
in its own module and is not re-exported here.
"""

from app.db.session import get_session
from app.services.auth import current_active_user, current_admin

__all__ = ["get_session", "current_active_user", "current_admin"]
