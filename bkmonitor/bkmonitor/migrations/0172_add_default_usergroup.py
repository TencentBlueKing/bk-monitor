from django.db import migrations, models


def add_user_group(apps, schema_editor):
    """
    新增 [内置]空通知组

    通知人员为空
    业务绑定在0下面
    名称: [内置]空通知组
    """
    UserGroup = apps.get_model('bkmonitor', 'UserGroup')
    UserGroup.objects.create(
        name="[内置]空通知组",
        bk_biz_id=0,
    )


class Migration(migrations.Migration):
    dependencies = [
        # ('bkmonitor', '0157_migrate_duty_groups'),
        ('bkmonitor', '0171_renderimagetask_start_time'),
    ]

    operations = [
        migrations.RunPython(add_user_group),
    ]
