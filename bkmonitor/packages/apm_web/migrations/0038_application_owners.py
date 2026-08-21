# Generated for apm application owners

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm_web", "0037_logservicerelation_addition"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="owners",
            field=models.JSONField(blank=True, default=list, verbose_name="负责人列表"),
        ),
    ]
