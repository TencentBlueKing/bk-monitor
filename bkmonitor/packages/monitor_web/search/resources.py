# -*- coding: utf-8 -*-
import logging

from monitor_web.search.handlers import INSTALLED_HANDLERS
from monitor_web.search.handlers.base import SearchScope
from rest_framework import serializers

from bkmonitor.utils.serializers import StringSplitListField
from core.drf_resource import Resource

logger = logging.getLogger("monitor_web")


class GlobalSearch(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        scope = serializers.ChoiceField(
            label="搜索范围", default=SearchScope.BIZ, choices=[SearchScope.BIZ, SearchScope.GLOBAL]
        )
        scene = StringSplitListField(
            label="搜索场景",
            required=True,
            allow_empty=False,
            sep=",",
            child=serializers.ChoiceField(choices=[h.SCENE for h in INSTALLED_HANDLERS]),
        )
        limit = serializers.IntegerField(label="限制条数", default=10, max_value=100)
        query = serializers.CharField(label="搜索关键字")

    def perform_request(self, params):
        results = []
        for handler_cls in INSTALLED_HANDLERS:
            if handler_cls.SCENE not in params["scene"]:
                continue
            handler = handler_cls(bk_biz_id=params["bk_biz_id"], scope=params["scope"])
            try:
                search_result = handler.handle(query=params["query"], limit=params["limit"])
                if search_result.results:
                    results.append(search_result.to_dict())
            except Exception as e:
                logger.exception(
                    "[GlobalSearch] error occurred when searching scene(%s), reason: %s, params: %s",
                    handler_cls.SCENE,
                    e,
                    params,
                )
        return results
