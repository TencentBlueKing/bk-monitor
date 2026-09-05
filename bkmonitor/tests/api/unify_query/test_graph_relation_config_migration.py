import importlib


migration = importlib.import_module("bkmonitor.migrations.0204_migrate_graph_relation_v4_biz_id_white_list")


class FakeConfig:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.saved_update_fields = None

    def save(self, update_fields):
        self.saved_update_fields = update_fields


class FakeManager:
    def __init__(self, configs):
        self.configs = {config.key: config for config in configs}

    def filter(self, key__in):
        return [self.configs[key] for key in key__in if key in self.configs]

    def create(self, key, value):
        config = FakeConfig(key, value)
        self.configs[key] = config
        return config


class FakeApps:
    def __init__(self, configs):
        self.model = type("GlobalConfig", (), {"objects": FakeManager(configs)})

    def get_model(self, app_label, model_name):
        assert (app_label, model_name) == ("bkmonitor", "GlobalConfig")
        return self.model


def test_migrate_graph_relation_whitelists_intersects_old_values():
    apps = FakeApps(
        [
            FakeConfig(migration.OLD_SYNC_KEY, [2, "3", "invalid"]),
            FakeConfig(migration.OLD_QUERY_KEY, "3,4"),
            FakeConfig(migration.NEW_KEY, [5]),
        ]
    )

    migration.migrate_graph_relation_v4_biz_id_white_list(apps, None)

    new_config = apps.model.objects.configs[migration.NEW_KEY]
    assert new_config.value == [3]
    assert new_config.saved_update_fields == ["value"]


def test_migrate_graph_relation_whitelists_creates_empty_new_config_when_one_old_config_is_missing():
    apps = FakeApps([FakeConfig(migration.OLD_SYNC_KEY, [2])])

    migration.migrate_graph_relation_v4_biz_id_white_list(apps, None)

    assert apps.model.objects.configs[migration.NEW_KEY].value == []
