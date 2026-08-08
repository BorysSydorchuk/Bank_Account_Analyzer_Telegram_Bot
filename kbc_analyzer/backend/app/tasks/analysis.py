"""Background version of analysis_service's work (S3-03 wires up the queue
itself; S3-04 makes this task do the real categorization + insight
generation instead of just confirming receipt).
"""
import logging

from ..celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def categorize_and_analyze() -> None:
    """Stub for S3-04 — proves the API-to-broker-to-worker pipeline works
    end to end before any real work runs inside it.
    """
    logger.info("task received")
