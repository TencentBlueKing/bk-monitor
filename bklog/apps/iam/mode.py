from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from functools import lru_cache

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import IAM_V3_PERMISSION_TOGGLE, IAM_V4_PERMISSION_TOGGLE
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.requests import ResourceInstance, to_definition_id

_BIZ_PATH_PATTERN = re.compile(r"(?:^|/)space,(-?\d+)(?:/|$)")


class FeatureToggleModeProvider:
    """根据两个可独立灰度的 Feature Toggle 解析 IAM 鉴权模式。"""

    def __init__(
        self,
        switch: Callable[..., bool] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.switch = switch or FeatureToggleObject.switch
        self.logger = logger or logging.getLogger("iam.mode")

    def get_mode(self, resources: tuple[ResourceInstance, ...] = ()) -> AuthMode:
        biz_id = self._get_biz_id(resources)
        return self._load_mode(biz_id)

    def _load_mode(self, biz_id: int | None) -> AuthMode:
        try:
            v3_enabled = self.switch(name=IAM_V3_PERMISSION_TOGGLE, biz_id=biz_id, default=True)
            v4_enabled = self.switch(name=IAM_V4_PERMISSION_TOGGLE, biz_id=biz_id, default=False)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("failed to load IAM permission feature toggles, fallback to v3")
            return AuthMode.V3

        if v3_enabled and v4_enabled:
            return AuthMode.UNION
        if v4_enabled:
            return AuthMode.V4
        if v3_enabled:
            return AuthMode.V3

        self.logger.error(
            "both IAM permission feature toggles are disabled, fallback to v3, biz_id=%s",
            biz_id,
        )
        return AuthMode.V3

    def _get_biz_id(self, resources: Iterable[ResourceInstance]) -> int | None:
        biz_ids = set(_iter_biz_ids(resources))
        if len(biz_ids) == 1:
            return biz_ids.pop()
        if len(biz_ids) > 1:
            self.logger.warning("multiple business IDs found in IAM request, use global feature toggle: %s", biz_ids)
        return None


def _iter_biz_ids(resources: Iterable[ResourceInstance]):
    for resource in resources:
        attribute_biz_id = _normalize_biz_id(resource.attributes.get("bk_biz_id"))
        if attribute_biz_id is not None:
            yield attribute_biz_id

        if to_definition_id(resource.type) == "space":
            resource_biz_id = _normalize_biz_id(resource.id)
            if resource_biz_id is not None:
                yield resource_biz_id

        iam_paths = resource.attributes.get("_bk_iam_path_", ())
        if isinstance(iam_paths, str):
            iam_paths = (iam_paths,)
        elif not isinstance(iam_paths, list | tuple | set):
            iam_paths = ()
        for iam_path in iam_paths:
            for match in _BIZ_PATH_PATTERN.finditer(str(iam_path)):
                yield int(match.group(1))

        yield from _iter_biz_ids(resource.ancestor_chain)


def _normalize_biz_id(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def get_mode_provider() -> FeatureToggleModeProvider:
    return FeatureToggleModeProvider()
