# Generated by Django 3.2.5 on 2022-09-20 11:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0047_alter_logindexset_bcs_project_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="logindexset",
            name="is_editable",
            field=models.BooleanField(default=True, verbose_name="是否可以编辑"),
        ),
    ]
