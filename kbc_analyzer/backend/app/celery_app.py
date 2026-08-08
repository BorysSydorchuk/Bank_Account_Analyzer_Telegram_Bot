"""Celery instance — the background-job counterpart to FastAPI's app in
main.py. The celery_worker container runs this module directly
(`celery -A app.celery_app worker`); the backend container will later enqueue
tasks against the same broker/backend (S3-04), so both read the connection
strings from the same env vars rather than each hardcoding Redis URLs.
"""
import os

from celery import Celery

celery_app = Celery(
    "kbc_analyzer",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    # Explicit rather than Celery's Django-style autodiscover_tasks(), which
    # expects an installed-apps list this project doesn't have. One entry per
    # module under app/tasks/ — add the next one here when S3-04 or later adds it.
    include=["app.tasks.analysis", "app.tasks.auth"],
)
