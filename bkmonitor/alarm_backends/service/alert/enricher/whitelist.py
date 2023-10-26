# -*- coding: utf-8 -*-
from django.conf import settings

from alarm_backends.core.alert import Event
from alarm_backends.service.alert.enricher import BaseEventEnricher


class BizWhiteListFor3rdEvent(BaseEventEnricher):
    def enrich_event(self, event: Event):
        if event.is_dropped():
            return event

        if event.strategy_id:
            # 有策略ID的不处理
            return event

        white_list = [str(bk_biz_id) for bk_biz_id in settings.BIZ_WHITE_LIST_FOR_3RD_EVENT]

        if not white_list:
            return event

        if str(event.bk_biz_id) in white_list:
            return event

        # 如果不在业务白名单，则丢掉事件
        event.drop()
        return event
