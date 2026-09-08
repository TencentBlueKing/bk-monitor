# Generated manually for Issues merge group reparent

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0202_fix_system_proc_cpu_time_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="issuemergerelation",
            name="via_issue_id",
            field=models.CharField(
                blank=True, default=None, max_length=64, null=True, verbose_name="上一跳主 Issue ID"
            ),
        ),
    ]
