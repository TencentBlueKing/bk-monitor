# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2023-05-19 09:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitor', '0099_uptimechecknode_ip_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uptimechecknode',
            name='ip',
            field=models.CharField(blank=True, default='', max_length=64, null=True, verbose_name='IP地址'),
        ),
        migrations.AlterField(
            model_name='uptimechecknode',
            name='ip_type',
            field=models.IntegerField(choices=[(0, 'all'), (4, 'IPv4'), (6, 'IPv6')], default=4, verbose_name='IP类型'),
        ),
        migrations.AlterField(
            model_name='uptimechecknode',
            name='plat_id',
            field=models.IntegerField(blank=True, default=0, null=True, verbose_name='云区域ID'),
        ),
    ]
