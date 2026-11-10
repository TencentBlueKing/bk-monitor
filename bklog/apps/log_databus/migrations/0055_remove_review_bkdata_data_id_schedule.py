from django.db import migrations


def remove_data_id_review_schedule(apps, schema_editor):
    periodic_task = apps.get_model("django_celery_beat", "PeriodicTask")
    periodic_task.objects.using(schema_editor.connection.alias).filter(
        task="apps.log_databus.tasks.bkdata.review_bkdata_data_id"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("log_databus", "0054_merge_nodeman_v3_and_expand_collector_name"),
        ("django_celery_beat", "0001_initial"),
    ]

    operations = [migrations.RunPython(remove_data_id_review_schedule, migrations.RunPython.noop)]
