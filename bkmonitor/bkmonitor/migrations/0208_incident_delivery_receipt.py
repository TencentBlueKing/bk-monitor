from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bkmonitor", "0207_bk_incident_source_mapping")]

    operations = [
        migrations.CreateModel(
            name="IncidentDeliveryReceipt",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delivery_key", models.CharField(max_length=64, unique=True)),
                ("event_id", models.CharField(max_length=128)),
                ("bk_tenant_id", models.CharField(max_length=128)),
                ("scope_id", models.CharField(max_length=128)),
                ("payload_digest", models.CharField(max_length=64)),
                ("payload", models.JSONField(default=dict)),
                ("status", models.CharField(default="processing", max_length=32)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("error_type", models.CharField(blank=True, default="", max_length=128)),
            ],
            options={"db_table": "incident_delivery_receipt"},
        )
    ]
