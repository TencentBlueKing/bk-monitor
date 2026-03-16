# Generated manually for Admin field optimization

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0253_merge_0252_0249_resourcedefinition"),
    ]

    operations = [
        # EntityMeta.namespace: 添加 blank=True (影响 ResourceDefinition, RelationDefinition, CustomRelationStatus)
        migrations.AlterField(
            model_name="resourcedefinition",
            name="namespace",
            field=models.CharField(blank=True, db_index=True, max_length=128, verbose_name="命名空间"),
        ),
        migrations.AlterField(
            model_name="relationdefinition",
            name="namespace",
            field=models.CharField(blank=True, db_index=True, max_length=128, verbose_name="命名空间"),
        ),
        migrations.AlterField(
            model_name="customrelationstatus",
            name="namespace",
            field=models.CharField(blank=True, db_index=True, max_length=128, verbose_name="命名空间"),
        ),
        # EntityMeta.labels: 添加 blank=True (影响 ResourceDefinition, RelationDefinition, CustomRelationStatus)
        migrations.AlterField(
            model_name="resourcedefinition",
            name="labels",
            field=models.JSONField(blank=True, default=dict, verbose_name="资源标签"),
        ),
        migrations.AlterField(
            model_name="relationdefinition",
            name="labels",
            field=models.JSONField(blank=True, default=dict, verbose_name="资源标签"),
        ),
        migrations.AlterField(
            model_name="customrelationstatus",
            name="labels",
            field=models.JSONField(blank=True, default=dict, verbose_name="资源标签"),
        ),
        # EntityMeta.generation: verbose_name 改为 "generation"
        migrations.AlterField(
            model_name="resourcedefinition",
            name="generation",
            field=models.BigIntegerField(default=1, help_text="跟踪资源规格变更次数", verbose_name="generation"),
        ),
        migrations.AlterField(
            model_name="relationdefinition",
            name="generation",
            field=models.BigIntegerField(default=1, help_text="跟踪资源规格变更次数", verbose_name="generation"),
        ),
        migrations.AlterField(
            model_name="customrelationstatus",
            name="generation",
            field=models.BigIntegerField(default=1, help_text="跟踪资源规格变更次数", verbose_name="generation"),
        ),
        # ResourceDefinition.fields: 添加 blank=True
        migrations.AlterField(
            model_name="resourcedefinition",
            name="fields",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="资源的字段定义，每个字段包含 namespace, name, required",
                verbose_name="字段定义列表",
            ),
        ),
    ]
