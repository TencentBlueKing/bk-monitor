from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.config import CONSUL_PATH
from bk_monitor_base.metadata.models import DataSource


class Command(BaseCommand):
    """
    清理老版本的consul路径，并将配置刷新到新的consul路径
    """

    def handle(self, *args, **options):
        self.stdout.write("[clean_old_consul_config] START.")
        # 获取全部数据源
        datasources = DataSource.objects.all()
        # 遍历类型，每种类型都要遍历datasource，更新key，且删除多余的consul key
        # 整个流程不save，model的改动都是临时的
        for datasource in datasources:
            # 需要将老版的consul路径的配置删除
            consul_config_path = f"{CONSUL_PATH}/data_id/{datasource.bk_data_id}"
            datasource.delete_consul_config(consul_config_path)

            # 然后把配置刷到新版consul路径
            datasource.refresh_consul_config()
            self.stdout.write(
                f"bk_data_id->[{datasource.bk_data_id}] clean old consul config ({consul_config_path}), and refresh new config ({datasource.consul_config_path})"
            )
        self.stdout.write("[clean_old_consul_config] DONE!")
