from types import SimpleNamespace

from bkmonitor.utils import dynamic_settings
from bkmonitor.utils.dynamic_settings import DynamicSettings


class _FakeCache:
    def __init__(self):
        self.store = {}

    def has_key(self, key):
        return key in self.store

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, timeout=None):
        self.store[key] = value


class _FallbackGlobalConfig:
    @classmethod
    def get(cls, key, defaults=None, raise_exception=False):
        if raise_exception:
            raise RuntimeError("db unavailable")
        return defaults


def test_dynamic_settings_does_not_cache_default_when_db_unavailable(monkeypatch):
    cache = _FakeCache()
    monkeypatch.setattr(dynamic_settings, "locmem_cache", cache)
    monkeypatch.setattr(dynamic_settings, "redis_cache", None)

    dynamic_settings_obj = object.__new__(DynamicSettings)
    dynamic_settings_obj._wrapped = SimpleNamespace(WXWORK_BOT_WEBHOOK_URL="")
    dynamic_settings_obj._global_config_model = _FallbackGlobalConfig
    dynamic_settings_obj.__name_list__ = {"WXWORK_BOT_WEBHOOK_URL"}
    dynamic_settings_obj.has_redis_cache = False

    assert dynamic_settings_obj.WXWORK_BOT_WEBHOOK_URL == ""
    assert "WXWORK_BOT_WEBHOOK_URL" not in cache.store
