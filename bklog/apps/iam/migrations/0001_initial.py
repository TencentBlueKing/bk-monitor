from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="IAMAuthorizationGrant",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("logical_key", models.CharField(max_length=64)),
                ("target_version", models.CharField(choices=[("v3", "V3"), ("v4", "V4")], max_length=8)),
                ("grant_type", models.CharField(default="creator_action", max_length=32)),
                ("intent_version", models.PositiveSmallIntegerField(default=1)),
                ("tenant_id", models.CharField(max_length=64)),
                ("subject_type", models.CharField(default="user", max_length=32)),
                ("subject_id", models.CharField(max_length=255)),
                ("operator", models.CharField(max_length=255)),
                ("resource_system", models.CharField(max_length=64)),
                ("resource_type", models.CharField(max_length=64)),
                ("resource_id", models.CharField(max_length=255)),
                ("semantic_role", models.CharField(max_length=64)),
                ("role_id", models.CharField(blank=True, default="", max_length=64)),
                ("payload", models.JSONField(default=dict)),
                ("expired_at", models.BigIntegerField(blank=True, null=True)),
                ("result", models.JSONField(blank=True, null=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("succeeded", "Succeeded"),
                            ("retry_wait", "Retry wait"),
                            ("unknown", "Unknown"),
                            ("failed_final", "Failed final"),
                        ],
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("next_retry_at", models.DateTimeField(blank=True, null=True)),
                ("lease_owner", models.CharField(blank=True, default="", max_length=64)),
                ("lease_until", models.DateTimeField(blank=True, null=True)),
                ("last_error_type", models.CharField(blank=True, default="", max_length=64)),
                ("last_error_code", models.CharField(blank=True, default="", max_length=64)),
                ("last_error_message", models.CharField(blank=True, default="", max_length=512)),
                ("succeeded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="iamauthorizationgrant",
            constraint=models.UniqueConstraint(
                fields=("logical_key", "target_version"), name="uniq_iam_grant_logical_target"
            ),
        ),
        migrations.AddIndex(
            model_name="iamauthorizationgrant",
            index=models.Index(fields=["state", "next_retry_at"], name="iam_grant_retry_idx"),
        ),
        migrations.AddIndex(
            model_name="iamauthorizationgrant",
            index=models.Index(fields=["state", "lease_until"], name="iam_grant_lease_idx"),
        ),
    ]
