"""Batch-local matching for alerts owned by a close-on-end shield."""

import logging

import arrow
from django.utils import timezone

from alarm_backends.core.cache.shield import ShieldCacheManager
from alarm_backends.service.alert.enricher.strategy import StrategySnapshotEnricher
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.converge.shield.window import business_timezone, matching_window

logger = logging.getLogger("alert")


class CloseShieldMatcher:
    def __init__(self):
        self.now = arrow.now()
        self.by_business = {}
        self.timezones = {}

    def take_over(self, alert):
        if alert.shield_end_close or not alert.is_abnormal():
            return
        try:
            self._take_over(alert)
        except Exception:
            # A failed match must not prevent unrelated alerts from being saved.
            logger.exception("Close shield matching failed for alert(%s), strategy(%s)", alert.id, alert.strategy_id)

    def _take_over(self, alert):
        business = alert.bk_biz_id
        if business not in self.by_business:
            configs = [
                config
                for config in ShieldCacheManager.get_shields_by_biz_id(business)
                if config.get("end_policy") == "close"
                and config.get("is_enabled", True)
                and not config.get("is_deleted", False)
                and config.get("category") not in ("alert", "event")
                and not config.get("is_quick", False)
            ]
            if configs:
                if business not in self.timezones:
                    self.timezones[business] = business_timezone(business)
                self.by_business[business] = [
                    AlertShieldObj(config, business_timezone_name=self.timezones[business]) for config in configs
                ]
            else:
                self.by_business[business] = []
        if not self.by_business[business]:
            return
        if business not in self.timezones:
            self.timezones[business] = business_timezone(business)
        with timezone.override(self.timezones[business]):
            self._match(alert, self.by_business[business])

    def _match(self, alert, shields):
        candidates = []
        # Matching precedes the normal enrichment stage in the builder.
        if alert.strategy_id and not alert.get_extra_info("strategy"):
            StrategySnapshotEnricher([alert]).enrich_alert(alert)
        document = alert.to_document()
        for shield in shields:
            if shield.is_match(document, self.now):
                begin, end = matching_window(shield.time_check, self.now)
                candidates.append((end, -int(shield.id), begin, shield.id))
        if not candidates:
            return
        end, _, begin, shield_id = max(candidates)
        alert.set("shield_end_close", True)
        alert.set("is_shielded", True)
        alert.set("shield_id", [shield_id])
        alert.update_extra_info(
            "shield_end_close_config", {"shield_id": shield_id, "window_begin": begin, "window_end": end}
        )
        alert.clear_next_status()
