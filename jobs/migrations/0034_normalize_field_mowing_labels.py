from django.db import migrations


def normalize_job_service_item_labels(apps, schema_editor):
    JobServiceItem = apps.get_model("jobs", "JobServiceItem")
    for item in JobServiceItem.objects.filter(description__icontains="field mowing"):
        description = (item.description or "").strip()
        normalized = " ".join(description.lower().split())
        if normalized == "field mowing":
            item.description = "Mowing"
            item.save(update_fields=["description"])


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0033_jobserviceitem_detail_description"),
    ]

    operations = [
        migrations.RunPython(normalize_job_service_item_labels, migrations.RunPython.noop),
    ]
