from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def example_ping_task(self, payload: str = "ok"):
    """Minimal Celery task scaffold for background jobs."""
    logger.info("celery_example_ping payload=%s task_id=%s", payload, self.request.id)
    return {"status": "ok", "payload": payload, "task_id": self.request.id}
