# Generated manually for ResourceDefinition and RelationDefinition models

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0248_auto_20260119_0334"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResourceDefinition",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=32, verbose_name="创建者")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=32, verbose_name="更新者")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "uid",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name="唯一标识符"
                    ),
                ),
                (
                    "generation",
                    models.BigIntegerField(default=1, help_text="跟踪资源规格变更次数", verbose_name="世代号"),
                ),
                ("namespace", models.CharField(db_index=True, max_length=128, verbose_name="命名空间")),
                ("name", models.CharField(max_length=128, verbose_name="资源名称")),
                ("labels", models.JSONField(default=dict, verbose_name="资源标签")),
                (
                    "fields",
                    models.JSONField(
                        default=list,
                        help_text="资源的字段定义，每个字段包含 namespace, name, required",
                        verbose_name="字段定义列表",
                    ),
                ),
            ],
            options={
                "verbose_name": "资源类型定义",
                "verbose_name_plural": "资源类型定义",
                "unique_together": {("namespace", "name")},
            },
        ),
        migrations.CreateModel(
            name="RelationDefinition",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=32, verbose_name="创建者")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=32, verbose_name="更新者")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "uid",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name="唯一标识符"
                    ),
                ),
                (
                    "generation",
                    models.BigIntegerField(default=1, help_text="跟踪资源规格变更次数", verbose_name="世代号"),
                ),
                ("namespace", models.CharField(db_index=True, max_length=128, verbose_name="命名空间")),
                ("name", models.CharField(max_length=128, verbose_name="资源名称")),
                ("labels", models.JSONField(default=dict, verbose_name="资源标签")),
                (
                    "from_resource",
                    models.CharField(help_text="关联的源资源类型名称", max_length=128, verbose_name="源资源类型"),
                ),
                (
                    "to_resource",
                    models.CharField(help_text="关联的目标资源类型名称", max_length=128, verbose_name="目标资源类型"),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[("static", "静态关联"), ("dynamic", "动态关联")],
                        default="static",
                        help_text="静态关联或动态关联",
                        max_length=32,
                        verbose_name="关联类别",
                    ),
                ),
                (
                    "is_directional",
                    models.BooleanField(
                        default=False, help_text="单向关系使用 from_to_to 格式命名", verbose_name="是否单向关系"
                    ),
                ),
                (
                    "is_belongs_to",
                    models.BooleanField(
                        default=False,
                        help_text="仅对双向关系有效，表示 from_resource 归属于 to_resource",
                        verbose_name="是否归属关系",
                    ),
                ),
            ],
            options={
                "verbose_name": "关联关系定义",
                "verbose_name_plural": "关联关系定义",
                "unique_together": {("namespace", "name")},
            },
        ),
    ]
