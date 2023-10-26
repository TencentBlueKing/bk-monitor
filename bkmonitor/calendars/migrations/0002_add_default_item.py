# -*- coding: utf-8 -*-
import datetime

from django.db import migrations


def add_default_item(apps, *args, **kwargs):
    CalendarItemModel = apps.get_model("calendars", "CalendarItemModel")
    CalendarModel = apps.get_model("calendars", "CalendarModel")
    calendar = CalendarModel.objects.create(
        name="周末",
        color="#00FF00",
        classify="default",
        create_user="admin",
        update_user="admin",
        create_time=datetime.datetime.now().timestamp(),
        update_time=datetime.datetime.now().timestamp()
    )
    CalendarItemModel.objects.create(
        name="周末",
        calendar_id=calendar.id,
        start_time=1640966400,
        end_time=1641052799,
        repeat={
            "freq": "week",
            "every": [0, 6],
            "until": None,
            "exclude_date": [],
            "interval": 1,
        },
        time_zone="Asia/Shanghai",
        create_user="admin",
        update_user="admin",
        create_time=datetime.datetime.now().timestamp(),
        update_time=datetime.datetime.now().timestamp()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("calendars", "0001_initial"),
    ]

    operations = [migrations.RunPython(add_default_item)]
