from typing import List

from apps.api import CCApi
from apps.api.modules.utils import get_non_bkcc_space_related_bkcc_biz_id
from bkm_space.utils import space_uid_to_bk_biz_id


def get_maintainers(space_uid: str) -> List[str]:
    bk_biz_id = space_uid_to_bk_biz_id(space_uid)
    # 如果是非蓝鲸业务空间，先查询是否关联蓝鲸业务, 如果没有关联蓝鲸业务，直接返回空列表
    if bk_biz_id < 0:
        bk_biz_id = get_non_bkcc_space_related_bkcc_biz_id(bk_biz_id)
        if bk_biz_id < 0:
            return []
    maintainers = set()
    params = {
        "biz_property_filter": {
            "condition": "AND",
            "rules": [
                {
                    "field": "bk_biz_id",
                    "operator": "equal",
                    "value": bk_biz_id,
                },
            ],
        },
        "fields": ["bk_biz_maintainer"],
        "no_request": True,
    }
    app_list = CCApi.get_app_list(params, request_cookies=False)
    if app_list and app_list["info"]:
        for maintainer in app_list["info"][0].get("bk_biz_maintainer", "").split(","):
            if not maintainer:
                continue
            maintainers.add(maintainer)
    return list(maintainers)
