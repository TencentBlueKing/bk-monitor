from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0285_doris_storage_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="DorisJobConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "data_link",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="doris_jobs", to="metadata.datalink"
                    ),
                ),
                ("cluster_id", models.IntegerField()),
                ("database", models.CharField(max_length=255)),
                ("name", models.CharField(max_length=255)),
                ("interval_minutes", models.PositiveIntegerField()),
                ("insert_sql", models.TextField()),
                ("template_key", models.CharField(max_length=64, blank=True)),
                ("template_inputs", models.JSONField(default=dict)),
                ("remote_id", models.BigIntegerField(null=True)),
                ("reconcile_status", models.CharField(db_index=True, default="draft", max_length=16)),
                ("pending_action", models.CharField(blank=True, max_length=16)),
                ("status_reason", models.TextField(blank=True)),
                ("create_time", models.DateTimeField(auto_now_add=True)),
                ("last_modify_time", models.DateTimeField(auto_now=True)),
            ],
            options={
                "unique_together": {("cluster_id", "name")},
                "indexes": [],
                "constraints": [],
            },
        ),
        migrations.CreateModel(
            name="DorisJobTableRelation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="table_relations",
                        to="metadata.dorisjobconfig",
                    ),
                ),
                ("component_kind", models.CharField(blank=True, max_length=16)),
                ("direction", models.CharField(choices=[("source", "source"), ("target", "target")], max_length=8)),
                (
                    "result_table",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to="metadata.resulttableconfig"
                    ),
                ),
                (
                    "doris_binding",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL, to="metadata.dorisstoragebindingconfig"
                    ),
                ),
                ("database", models.CharField(blank=True, max_length=255)),
                ("table", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "indexes": [],
                "constraints": [],
            },
        ),
    ]
