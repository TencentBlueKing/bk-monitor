import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.metadata import config
from bk_monitor_base.metadata.config import settings


class Command(BaseCommand):
    help = "delete spec gse router"

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=int, help="数据源ID")
        parser.add_argument("--router_names", help="要删除的路由名称，多个以半角逗号分隔")

    def handle(self, *args, **options):
        bk_data_id = options["bk_data_id"]
        router_names = options["router_names"]
        if not (bk_data_id and router_names):
            raise CommandError("params [bk_data_id] and [router_names] are required")
        router_name_list = router_names.split(",")
        # 处理路由名称
        params: dict[str, dict[str, Any]] = {
            "condition": {"channel_id": bk_data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.blueking.common_username, "method": "specification"},
            "specification": {"route": router_name_list},
        }

        try:
            api.gse.delete_route(
                bk_tenant_id=DEFAULT_TENANT_ID,
                condition=params["condition"],
                operation=params["operation"],
                specification=params["specification"],
            )
        except BkApiError as e:
            raise CommandError(f"delete spec gse router failed, params: {params}, error: {e}")

        # 返回剩余的路由
        params = {
            "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": bk_data_id},
            "operation": {"operator_name": settings.blueking.common_username},
        }
        try:
            remained_router = api.gse.query_route(bk_tenant_id=DEFAULT_TENANT_ID, **params)
        except BkApiError as e:
            # 当已经不存在时，正常返回
            if "not found" in e.message or e.code in [1014505, 1014003]:
                self.stdout.write("no spec gse router remained")
                return
            raise CommandError(f"get spec gse router failed, params: {params}, error: {e}")

        self.stdout.write(self.style.SUCCESS("delete spec gse router success"))
        self.stdout.write(f"remained router: {json.dumps(remained_router)}")
