from typing import final

from django.apps import AppConfig, apps


@final
class MetaDataAppConfig(AppConfig):
    name = "bk_monitor_base.metadata"
    label = "old_metadata"

    def ready(self):
        # 使得信号配置生效
        from bk_monitor_base.metadata import signals  # noqa

        # 进行一些赋值，防止在app没有准备好时就赋值
        from bk_monitor_base.metadata.models import data_source

        data_source.ResultTable = apps.get_model("old_metadata", "ResultTable")
        data_source.ResultTableField = apps.get_model("old_metadata", "ResultTableField")
        data_source.ResultTableRecordFormat = apps.get_model("old_metadata", "ResultTableRecordFormat")
        data_source.ResultTableOption = apps.get_model("old_metadata", "ResultTableOption")

        from bk_monitor_base.metadata.models import storage

        storage.ResultTableField = apps.get_model("old_metadata", "ResultTableField")
        storage.ResultTableFieldOption = apps.get_model("old_metadata", "ResultTableFieldOption")
        storage.ResultTable = apps.get_model("old_metadata", "ResultTable")
        storage.EventGroup = apps.get_model("old_metadata", "EventGroup")

        from bk_monitor_base.metadata.models import custom_report

        custom_report.DataSource = apps.get_model("old_metadata", "DataSource")
