from django.core.cache import caches
from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from metadata import config

from metadata.models.space import Space
from metadata.models.space.constants import SpaceTypes

__doc__ = """
指定 cmdb 特定业务，为全局业务
示例:
python manage.py enable_global_biz --bk_tenant_id=system --bk_biz_id=1
取消:
python manage.py enable_global_biz --bk_tenant_id=system --bk_biz_id=1 --op=disable
"""

print(__doc__)


class Command(BaseCommand):
    help = __doc__.strip()
    type_id = SpaceTypes.BKCC.value

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, default="system", help="租户ID")
        parser.add_argument("--bk_biz_id", type=str, help="业务 id")
        parser.add_argument("--op", type=str, help="启用/禁用", default="enable", choices=["enable", "disable"])

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        bk_tenant_id: str = options.get("bk_tenant_id") or "system"
        bk_biz_id: str | None = options.get("bk_biz_id")
        op: str = options.get("op") or "enable"

        space_qs = Space.objects.filter(space_type_id=self.type_id, bk_tenant_id=bk_tenant_id)

        # 指定业务，仅操作该业务
        if bk_biz_id:
            space_qs = space_qs.filter(space_id=str(bk_biz_id))
        else:
            raise ValueError("必须指定业务ID")

        # 执行更新
        is_global = op == "enable"
        updated = space_qs.update(is_global=is_global)

        # 清理空间相关缓存，确保前台立即生效
        self._invalidate_space_cache(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

        self.stdout.write(
            self.style.SUCCESS(
                f"操作完成: tenant={bk_tenant_id}, biz={bk_biz_id or '[default/ALL]'}, op={op}, affected={updated}"
            )
        )

    def _invalidate_space_cache(self, bk_tenant_id: str, bk_biz_id: str | None = None) -> None:
        cache = caches["space"]
        # 列表缓存
        cache.delete("metadata:list_spaces_dict")
        cache.delete(f"metadata:list_spaces_dict:{bk_tenant_id}")
        cache.delete("metadata:list_spaces")
        cache.delete(f"metadata:list_spaces:{bk_tenant_id}")
        # 详情缓存（仅 BKCC 空间需要，因为该键仅对 BKCC 预热）
        if bk_biz_id:
            cache.delete(f"metadata:spaces_map:{SpaceTypes.BKCC.value}__{str(bk_biz_id)}")
