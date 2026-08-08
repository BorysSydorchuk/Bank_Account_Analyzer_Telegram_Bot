"""Background task that waits for Enable Banking's OAuth redirect (S3-07
Item 2), so the reconnect flow no longer needs the user to copy-paste it.
"""
import logging

from ..celery_app import celery_app
from ..eb_callback_server import CallbackPortBusyError, wait_for_callback
from ..eb_service import EnableBankingService

logger = logging.getLogger(__name__)


@celery_app.task
def catch_enable_banking_callback() -> None:
    """Blocks on this worker (never on the API process) until Enable
    Banking's redirect hits the local catcher server, then completes
    re-authorization. The frontend never talks to this task directly — it
    just polls GET /api/auth/enable-banking/status until it reports "active".
    """
    try:
        result = wait_for_callback()
    except TimeoutError:
        logger.warning("No Enable Banking callback received before timeout.")
        return
    except CallbackPortBusyError as exc:
        # Confirmed live: a page refresh mid-reconnect followed by a second
        # "Reconnect" click fires this task again while the first is still
        # waiting. Not a crash — the first attempt is still valid and will
        # either complete or time out on its own.
        logger.warning(str(exc))
        return

    code = result.get("code")
    if not code:
        logger.warning("Enable Banking callback had no authorization code: %s", result)
        return

    try:
        EnableBankingService().complete_reauthorization(code)
    except Exception:
        logger.exception("Failed to complete Enable Banking re-authorization.")
