from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from core.drf_resource import api
from metadata import config
from metadata.models.data_source import DataSource
from metadata.models.space import Space
from metadata.models.space.constants import SpaceTypes
from metadata.models.space.space_data_source import (
    get_biz_data_id,
    get_real_zero_biz_data_id,
)
from metadata.models.space.utils import (
    create_bkcc_space_data_source,
    create_bkcc_spaces,
)


class Command(BaseCommand):
    help = "sync cmdb biz for space"
    type_id = SpaceTypes.BKCC.value

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, default="system", help="租户ID")

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        """同步业务空间"""
        print("start sync bkcc space")

        # 检测是否已经有业务空间数据，如果有也跳过执行
        if Space.objects.filter(space_type_id=self.type_id).exists():
            print("bkcc space type already exists, do nothing")
            return

        # 通过cmdb接口查询所有业务
        biz_list = api.cmdb.get_business(bk_tenant_id=options["bk_tenant_id"])
        # 获取业务及对应的数据源信息
        biz_data_id_dict = get_biz_data_id()
        # 针对 0 业务按照规则转换为所属业务
        real_biz_data_id_dict, zero_data_id_list = get_real_zero_biz_data_id()
        # 创建业务空间
        create_bkcc_spaces(
            [
                {
                    "bk_biz_id": str(biz.bk_biz_id),
                    "bk_biz_name": biz.bk_biz_name,
                    "bk_tenant_id": options["bk_tenant_id"],
                }
                for biz in biz_list
            ]
        )
        # 赋值空间级的数据源 ID
        DataSource.objects.filter(bk_data_id__in=zero_data_id_list).update(
            is_platform_data_id=True, space_type_id=self.type_id
        )
        # 创建空间和数据源的关联
        create_bkcc_space_data_source(biz_data_id_dict)
        create_bkcc_space_data_source(real_biz_data_id_dict)

        print("sync cmdb biz for space successfully")
