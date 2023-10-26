# -*- coding: utf-8 -*-
import logging

from django.core.management.base import BaseCommand

from metadata.models.space import SpaceType
from metadata.models.space.constants import SYSTEM_USERNAME, SpaceTypes

logger = logging.getLogger("metadata")

# 初始化的类型，包含 bkcc、bcs、bkdevops
INIT_DATA = [
    {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "type_id": SpaceTypes.BKCC.value,
        "type_name": "业务",
        "description": "蓝鲸业务空间",
        "allow_merge": False,
        "allow_bind": False,
        "dimension_fields": ["bk_biz_id"],
    },
    {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "type_id": SpaceTypes.BCS.value,
        "type_name": "容器项目",
        "description": "容器项目空间",
        "allow_merge": True,
        "allow_bind": True,
        "dimension_fields": ["bcs_cluster_id", "namespace"],
    },
    {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "type_id": SpaceTypes.BKCI.value,
        "type_name": "研发项目",
        "description": "蓝盾研发项目空间",
        "allow_merge": True,
        "allow_bind": True,
        "dimension_fields": ["project_code"],
    },
    {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "type_id": SpaceTypes.BKSAAS.value,
        "type_name": "蓝鲸应用",
        "description": "蓝鲸应用空间",
        "allow_merge": True,
        "allow_bind": True,
        "dimension_fields": ["bk_app_code"],
    },
    {
        "creator": SYSTEM_USERNAME,
        "updater": SYSTEM_USERNAME,
        "type_id": SpaceTypes.DEFAULT.value,
        "type_name": "监控空间",
        "description": "监控空间",
        "allow_merge": True,
        "allow_bind": True,
        "dimension_fields": [],
    },
]


class Command(BaseCommand):
    help = "init the space type"

    def handle(self, *args, **options):
        print("start init space type")

        created = updated = 0
        for data in INIT_DATA:
            type_id = data.pop("type_id")
            _, new = SpaceType.objects.update_or_create(type_id=type_id, defaults=data)
            if new:
                created += 1
            else:
                updated += 1
        print(f"space created:[{created}], updated:[{updated}]")
