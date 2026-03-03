import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_scheduled_monthly_invoices_task(self):
    """Run the scheduled monthly invoice sender command.

    Intended to run daily from Celery beat.
    """
    logger.info("monthly_invoice_automation started task_id=%s", self.request.id)
    call_command("send_scheduled_monthly_invoices")
    logger.info("monthly_invoice_automation completed task_id=%s", self.request.id)
    return {"status": "ok", "task_id": self.request.id}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_invoice_reminders_task(self):
    logger.info("invoice_reminder_automation started task_id=%s", self.request.id)
    call_command("send_invoice_reminders")
    logger.info("invoice_reminder_automation completed task_id=%s", self.request.id)
    return {"status": "ok", "task_id": self.request.id}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_estimate_followups_task(self):
    logger.info("estimate_followup_automation started task_id=%s", self.request.id)
    call_command("send_estimate_followups")
    logger.info("estimate_followup_automation completed task_id=%s", self.request.id)
    return {"status": "ok", "task_id": self.request.id}
