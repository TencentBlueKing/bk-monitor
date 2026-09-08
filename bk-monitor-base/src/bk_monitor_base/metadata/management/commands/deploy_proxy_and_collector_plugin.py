from django.core.management import BaseCommand

from bk_monitor_base.metadata.task.auto_deploy_proxy import AutoDeployProxy


class Command(BaseCommand):
    """通过节点管理，部署 proxy 和 collector 插件

    1. 用户在监控平台`全局配置`中设置需要`自定义上报默认服务器`的 IP
    2. 如果有对应的域名，可以填写上域名信息，此后页面将屏蔽具体IP的展示
    3. 执行命令，部署 proxy 和 collector 插件
    """

    def handle(self, *args, **options):
        AutoDeployProxy.refresh("bk-collector")

        print("bkmonitorproxy and bk-collector deployed successfully!")
