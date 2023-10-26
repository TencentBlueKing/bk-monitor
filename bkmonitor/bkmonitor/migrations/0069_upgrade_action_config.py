# -*- coding: utf-8 -*-


from django.db import migrations

from bkmonitor.action.converter import ActionConverter


def convert_actions(apps, *args, **kwargs):
    models = {
        "ActionConfig": apps.get_model("bkmonitor", "ActionConfig"),
        "StrategyActionConfigRelation": apps.get_model("bkmonitor", "StrategyActionConfigRelation"),
        "UserGroup": apps.get_model("bkmonitor", "UserGroup"),
        "NoticeTemplate": apps.get_model("bkmonitor", "NoticeTemplate"),
        "NoticeGroup": apps.get_model("bkmonitor", "NoticeGroup"),
        "StrategyModel": apps.get_model("bkmonitor", "StrategyModel"),
        "ItemModel": apps.get_model("bkmonitor", "ItemModel"),
        "ActionNoticeMapping": apps.get_model("bkmonitor", "ActionNoticeMapping"),
        "Action": apps.get_model("bkmonitor", "Action"),
        "DutyArrange": apps.get_model("bkmonitor", "DutyArrange"),
    }
    converter = ActionConverter(**models)
    result = converter.migrate()
    if any(result.values()):
        print("[ActionConverter] migrate result: %s" % result)


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0068_auto_20211110_2057"),
    ]

    operations = [
        migrations.RunPython(convert_actions),
    ]
