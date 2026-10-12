from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bkmonitor", "0205_shield_end_policy")]

    operations = [
        migrations.AddField(
            model_name="itemmodel",
            name="access_lookback_periods",
            field=models.IntegerField("Access 回看周期数", null=True, blank=True, default=None),
        ),
    ]
