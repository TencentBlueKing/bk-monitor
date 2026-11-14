from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0284_federation_reconcile_status")]

    operations = [
        migrations.AddField(
            model_name="dorisstorage",
            name="doris_storage_config",
            field=models.JSONField("Doris Binding 存储配置", default=dict),
        ),
    ]
