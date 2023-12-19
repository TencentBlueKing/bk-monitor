# -*- coding: utf-8 -*-
from copy import deepcopy
from typing import List

from celery.schedules import crontab

from apps.api import TransferApi
from apps.constants import BATCH_SYNC_SPACE_COUNT
from apps.log_search.models import Space, SpaceApi, SpaceType
from apps.utils.lock import share_lock
from apps.utils.log import logger
from apps.utils.task import high_priority_periodic_task
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import space_uid_to_bk_biz_id


@high_priority_periodic_task(run_every=crontab(minute="*/5"))
@share_lock()
def sync():
    """
    同步空间配置
    """
    sync_space_types()
    sync_spaces()


def sync_space_types():
    """
    同步空间类型信息
    """
    space_types = TransferApi.list_space_types()
    all_space_types = []

    for space_type in space_types:
        type_id = space_type.pop("type_id")
        type_name = space_type.pop("type_name")

        type_obj = SpaceType(type_id=type_id, type_name=type_name, properties=space_type, is_deleted=False)
        type_obj.save()

        all_space_types.append(type_obj)

    # 删除不存在的空间类型
    deleted_rows = SpaceType.origin_objects.exclude(type_id__in=[t.type_id for t in all_space_types]).delete()
    logger.info("[sync_space_types] sync ({}), delete ({})".format(len(all_space_types), deleted_rows))


def get_page_numbers(total: int, page_size: int):
    total_pages = (total + page_size - 1) // page_size
    return list(range(1, total_pages + 1))


def sync_spaces():
    """
    同步空间信息
    """
    # 获取类型ID到类型名称的映射
    type_names = {t["type_id"]: t["type_name"] for t in TransferApi.list_space_types()}
    # 记录本地同步所有的space_id, 用于删除不存在的空间
    space_id_list: List[int] = []
    # 有关联的空间
    have_related_space_id_list: List[int] = []
    total: int = TransferApi.list_spaces({"page": 1, "page_size": 1})["count"]
    for i in get_page_numbers(total=total, page_size=BATCH_SYNC_SPACE_COUNT):
        spaces = TransferApi.list_spaces(
            {"is_detail": True, "page": i, "page_size": BATCH_SYNC_SPACE_COUNT, "include_resource_id": True}
        )["list"]
        for space in spaces:
            space_pk = space.pop("id")
            space_type_id = space.pop("space_type_id")
            space_type_name = type_names.get(space_type_id, space_type_id)
            space_id = space.pop("space_id")
            space_name = space.pop("space_name")
            space_code = space.pop("space_code") or space_id
            space_uid = space.pop("space_uid")
            bk_biz_id = space_uid_to_bk_biz_id(space_uid=space_uid, id=space_pk)

            space_obj = Space(
                id=space_pk,
                space_uid=space_uid,
                bk_biz_id=bk_biz_id,
                space_type_id=space_type_id,
                space_type_name=space_type_name,
                space_id=space_id,
                space_name=space_name,
                space_code=space_code,
                properties=space,
                is_deleted=False,
            )

            space_obj.save()
            space_id_list.append(space_pk)
            # 记录存在关联的空间, 因为只有非BKCC的业务会关联其他空间, 但是BKCC的业务不会知道他关联了哪些非BKCC业务, 所以需要记录
            if space_type_id == SpaceTypeEnum.BKCC.value or not space.get("resources", []):
                continue
            have_related_space_id_list.append(space_obj.id)

    # 将BKCC的业务的resources里也添加上其他空间类型的resource, 这样就可以通过BKCC的业务找到其他空间类型的业务
    for _space_id in have_related_space_id_list:
        _space = Space.objects.get(pk=_space_id)
        for resource in _space.properties["resources"]:
            need_relate_space_uid: str = SpaceApi.gen_space_uid(
                space_type=resource["resource_type"], space_id=resource["resource_id"]
            )
            need_relate_space_obj: Space = Space.objects.filter(space_uid=need_relate_space_uid).first()
            if not need_relate_space_obj:
                continue
            properties = deepcopy(need_relate_space_obj.properties)
            properties["resources"].append({'resource_id': _space.space_id, 'resource_type': _space.space_type_id})
            need_relate_space_obj.properties = properties
            need_relate_space_obj.save()

    # 删除不存在的空间
    deleted_rows = Space.origin_objects.exclude(id__in=space_id_list).delete()
    logger.info("[sync_spaces] sync ({}), delete ({})".format(len(space_id_list), deleted_rows))
