# Generated manually for Issues merge/split feature

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0195_alter_renderimagetask_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="IssueMergeRelation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务 ID")),
                ("main_issue_id", models.CharField(max_length=64, verbose_name="主 Issue ID")),
                ("member_issue_id", models.CharField(max_length=64, verbose_name="并入 Issue ID")),
                ("status", models.CharField(default="active", max_length=16, verbose_name="关系状态")),
                (
                    "merge_reasons",
                    bkmonitor.utils.db.fields.JsonField(default=list, verbose_name="合并依据"),
                ),
                (
                    "split_reasons",
                    bkmonitor.utils.db.fields.JsonField(blank=True, default=None, null=True, verbose_name="拆分依据"),
                ),
                (
                    "split_kind",
                    models.CharField(blank=True, default=None, max_length=16, null=True, verbose_name="拆分触发类型"),
                ),
            ],
            options={
                "verbose_name": "Issue 合并关系",
                "db_table": "bkmonitor_issue_merge_relation",
            },
        ),
        migrations.AddIndex(
            model_name="issuemergerelation",
            index=models.Index(fields=["bk_biz_id", "status", "main_issue_id"], name="idx_imr_biz_status_main"),
        ),
        migrations.AddIndex(
            model_name="issuemergerelation",
            index=models.Index(fields=["main_issue_id", "status"], name="idx_imr_main_status"),
        ),
        migrations.AddIndex(
            model_name="issuemergerelation",
            index=models.Index(fields=["member_issue_id", "status"], name="idx_imr_member_status"),
        ),
        migrations.AddConstraint(
            model_name="issuemergerelation",
            constraint=models.CheckConstraint(
                check=models.Q(("main_issue_id", models.F("member_issue_id")), _negated=True),
                name="ck_imr_main_ne_member",
            ),
        ),
    ]
