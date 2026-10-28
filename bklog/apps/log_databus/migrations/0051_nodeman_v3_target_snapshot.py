from django.db import migrations, models

import apps.models


class Migration(migrations.Migration):
    """
    BKL-3 目标动态收敛所需的 binding 字段。

    刻意新开一个迁移而不是改 0050：0050 已经在联调环境跑过，原地改会让已建库的环境与
    迁移记录对不上（Django 只按文件名判断是否已应用，内容变了也不会重跑）。
    """

    dependencies = [
        ("log_databus", "0050_nodeman_v3_control_plane"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodemanv3binding",
            name="sub_config_template_names",
            field=apps.models.JsonField(default=None, null=True, verbose_name="子配置模板名"),
        ),
        migrations.AddField(
            model_name="nodemanv3binding",
            name="target_snapshot_at",
            field=models.DateTimeField(default=None, null=True, verbose_name="目标快照时间"),
        ),
        migrations.AddField(
            model_name="nodemanv3binding",
            name="last_heal_at",
            field=models.DateTimeField(default=None, null=True, verbose_name="兜底重放时间"),
        ),
        # desired_md5 从来没被写过，也算不出来：list_config_files 回的 md5 是节点管理渲染完模板
        # 之后的文件内容摘要，渲染在对方侧，我们本地只有 custom_config_context。
        # 留着一个算不出来的期望值挨着 applied_md5，早晚会被写成
        # 「desired != applied 即未生效」而 100% 误判，不如现在删掉
        migrations.RemoveField(
            model_name="nodemanv3subconfigtarget",
            name="desired_md5",
        ),
    ]
