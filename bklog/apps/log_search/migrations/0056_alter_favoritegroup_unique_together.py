# Generated by Django 3.2.15 on 2022-10-28 02:27

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0055_auto_20221027_1718"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="favoritegroup",
            unique_together={("name", "space_uid", "created_by")},
        ),
    ]
