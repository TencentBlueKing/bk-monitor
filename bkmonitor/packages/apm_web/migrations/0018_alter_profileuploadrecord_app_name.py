# Generated by Django 3.2.15 on 2023-12-12 09:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('apm_web', '0017_profileuploadrecord'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profileuploadrecord',
            name='app_name',
            field=models.CharField(max_length=50, null=True, verbose_name='应用名称'),
        ),
    ]
