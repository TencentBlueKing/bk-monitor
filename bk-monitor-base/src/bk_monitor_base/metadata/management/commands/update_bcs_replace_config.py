import yaml
from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from bk_monitor_base.metadata import config
from bk_monitor_base.metadata.models.bcs.replace import ReplaceConfig
from bk_monitor_base.metadata.task.bcs import refresh_bcs_monitor_info


class Command(BaseCommand):
    """
    根据配置文件，将replace_config相关的信息刷入mysql
    """

    def add_arguments(self, parser):
        parser.add_argument("-g", type=str, default="true", help="generate yaml")
        parser.add_argument("-f", type=str, help="yaml file to change replace config")

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        file_path = options.get("f")
        if not file_path:
            print("file_path should not be empty")
            return
        generate = options.get("g")
        # 如果传入generate，则生成配置文件
        if generate == "true":
            replace_configs = ReplaceConfig.export_data()
            data = {
                "replace_configs": replace_configs,
            }
            with open(file_path, mode="w+") as f:
                yaml.dump(data, f, default_flow_style=False)
            return
        # 否则从配置文件写入
        with open(file_path) as f:
            data = yaml.safe_load(f)
            replace_configs = data.get("replace_configs", None)
            if replace_configs is not None and isinstance(replace_configs, list):
                ReplaceConfig.import_data(replace_configs)
            refresh_bcs_monitor_info()
