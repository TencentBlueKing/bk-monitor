"""Batch-local matching for alerts owned by a close-on-end shield."""

import arrow

from alarm_backends.core.cache.shield import ShieldCacheManager
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.converge.shield.window import matching_window


class CloseShieldMatcher:
    def __init__(self):
        self.now = arrow.now()
        self.by_business = {}

    def take_over(self, alert):
        if alert.shield_end_close or not alert.is_abnormal():
            return
        business = alert.bk_biz_id
        if business not in self.by_business:
            self.by_business[business] = [
                AlertShieldObj(config)
                for config in ShieldCacheManager.get_shields_by_biz_id(business)
                if config.get("end_policy") == "close"
                and config.get("is_enabled", True)
                and not config.get("is_deleted", False)
                and config.get("category") not in ("alert", "event")
                and not config.get("is_quick", False)
            ]
        candidates = []
        if not self.by_business[business]:
            return
        document = alert.to_document()
        for shield in self.by_business[business]:
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
