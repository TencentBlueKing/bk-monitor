from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bkmonitor", "0212_metriclistcache_add_related_id_index")]

    operations = [
        migrations.CreateModel(
            name="IncidentNoticeDelivery",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("event_key", models.CharField(db_index=True, max_length=64)),
                ("channel", models.CharField(max_length=64)),
                ("recipient", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        db_index=True,
                        default="pending",
                        max_length=16,
                        choices=[
                            ("pending", "Pending"),
                            ("sending", "Sending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("uncertain", "Uncertain"),
                        ],
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "bkmonitor_incident_notice_delivery"},
        )
    ]
