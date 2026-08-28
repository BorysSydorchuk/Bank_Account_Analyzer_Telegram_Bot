"""POST /api/feedback (S8-07) — beta testers' one channel to reach Borys."""
import logging
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth.dependency import get_current_user
from ..email_service import send_templated_email
from ..models import User
from ..schemas import FeedbackRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", status_code=204)
def send_feedback(body: FeedbackRequest, current_user: User = Depends(get_current_user)):
    """Email current_user's message to FEEDBACK_RECIPIENT_EMAIL via Resend.

    Unlike verify/reset emails (routers/user_auth.py), a send failure here
    IS the whole point of the request — there's no separate action for it
    to be a best-effort side effect of, and nothing else records the
    message if the send fails. So this surfaces the failure to the caller
    as a clean 502, instead of swallowing it, so the beta tester knows to
    retry rather than believing their feedback went through.
    """
    try:
        send_templated_email(
            os.environ["FEEDBACK_RECIPIENT_EMAIL"],
            "feedback",
            sender_email=current_user.email,
            message=body.message,
        )
    except Exception:
        logger.exception("Failed to send feedback email from user %s", current_user.id)
        return JSONResponse(
            status_code=502,
            content={"message": "Couldn't send your feedback right now. Please try again in a moment."},
        )
