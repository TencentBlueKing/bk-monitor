from typing import List

from apps.api import CCApi
from bkm_space.utils import space_uid_to_bk_biz_id


def get_maintainers(space_uid: str) -> List[str]:
    bk_biz_id = space_uid_to_bk_biz_id(space_uid)
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
    }
    app_list = CCApi.get_app_list(params)
    if app_list and app_list["info"]:
        for maintainer in app_list["info"][0].get("bk_biz_maintainer", "").split(","):
            if not maintainer:
                continue
            maintainers.add(maintainer)
    return list(maintainers)
