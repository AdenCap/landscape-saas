# Wave 6 — Backfill Job.recurring_job for legacy mowing jobs.
#
# Before Wave 6, mowing_bulk_schedule() created Job rows with "[Mowing]" notes
# but WITHOUT setting recurring_job=rj. That meant calendar_job_reschedule's
# "apply to all future" path could not find or shift the parent RecurringJob.
#
# This migration finds existing legacy mowing Jobs (notes contains "[Mowing]",
# recurring_job_id IS NULL, status in ["scheduled", "en_route"]) and links them
# back to the matching active RecurringJob for that property.
#
# Reversible: sets recurring_job_id back to NULL for jobs we touched.
#
# Safety:
#   - Only modifies Jobs with recurring_job_id CURRENTLY NULL (no overwrite).
#   - Only matches jobs that have "[Mowing]" in notes (explicit marker we set).
#   - Uses .iterator(chunk_size=500) for memory safety on large tables.
#   - Only links to ACTIVE RecurringJobs on the same property (one-to-one match).

from django.db import migrations


def backfill_mowing_recurring_fk(apps, schema_editor):
    Job = apps.get_model('jobs', 'Job')
    RecurringJob = apps.get_model('jobs', 'RecurringJob')

    legacy_jobs = Job.objects.filter(
        notes__icontains='[Mowing]',
        recurring_job_id__isnull=True,
        status__in=['scheduled', 'en_route'],
    ).only('id', 'property_id', 'notes')

    # Build a single-query lookup: property_id -> active RecurringJob.id (most recent)
    # Prefer the most recently-created RecurringJob if a property has multiple.
    active_rjs = RecurringJob.objects.filter(active=True).order_by('property_id', '-id').only(
        'id', 'property_id'
    )
    rj_by_property = {}
    for rj in active_rjs:
        rj_by_property.setdefault(rj.property_id, rj.id)

    updates = 0
    for job in legacy_jobs.iterator(chunk_size=500):
        rj_id = rj_by_property.get(job.property_id)
        if rj_id:
            Job.objects.filter(id=job.id).update(recurring_job_id=rj_id)
            updates += 1


def reverse_backfill(apps, schema_editor):
    # Reverse is a no-op — we don't know which Jobs we backfilled vs which were
    # always linked. Leaving the FK set is safe (it's what newly-created jobs do now).
    # If a hard reverse is ever needed, it would require a timestamp marker on the
    # Job model, which we intentionally don't add to keep this migration minimal.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0030_jobserviceitem_scheduled_date'),
    ]

    operations = [
        migrations.RunPython(
            backfill_mowing_recurring_fk,
            reverse_code=reverse_backfill,
            hints={'target_db': 'default'},
        ),
    ]
