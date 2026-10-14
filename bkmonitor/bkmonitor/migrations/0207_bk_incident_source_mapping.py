"""补齐已有标准排障插件的来源映射，不依赖插件初次注册开关。"""

import logging
from copy import deepcopy

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

SOURCE_INPUT = {
    "key": "source",
    "value": "execute_config.source || 'bk_monitor'",
    "type": "string",
    "format": "jmespath",
}


def add_source_mapping(apps, schema_editor):
    action_plugin = apps.get_model("bkmonitor", "ActionPlugin")
    alias = schema_editor.connection.alias
    plugins = action_plugin._base_manager.using(alias).filter(
        id=110, plugin_key="bk_incident", plugin_type="bk_incident", is_builtin=True, is_deleted=False
    )
    with transaction.atomic(using=alias):
        plugin = plugins.select_for_update().first()
        if plugin is None:
            return
        config = deepcopy(plugin.backend_config)
        if not isinstance(config, list) or any(not isinstance(node, dict) for node in config):
            raise RuntimeError("bk_incident plugin 110: invalid backend_config")
        nodes = [node for node in config if node.get("function") == "create_task"]
        if len(nodes) != 1:
            raise RuntimeError("bk_incident plugin 110: expected one create_task node")
        node = nodes[0]
        if (
            node.get("resource_module") != "api.bk_incident.default"
            or node.get("resource_class") != "CreateTaskResource"
        ):
            raise RuntimeError("bk_incident plugin 110: unexpected create_task resource")
        inputs = node.get("inputs")
        if not isinstance(inputs, list) or any(not isinstance(item, dict) for item in inputs):
            raise RuntimeError("bk_incident plugin 110: invalid create_task inputs")
        existing = [item for item in inputs if item.get("key") == "source"]
        if len(existing) > 1:
            raise RuntimeError("bk_incident plugin 110: duplicate source mappings")
        if existing:
            if existing[0] != SOURCE_INPUT:
                logger.warning("bk_incident plugin 110: preserve existing custom source mapping")
            return
        inputs.append(deepcopy(SOURCE_INPUT))
        # 仅更新这一列，保留运行环境中的其他配置及元数据。
        plugins.update(backend_config=config)


class Migration(migrations.Migration):
    dependencies = [("bkmonitor", "0206_item_access_lookback_periods")]

    # 无法区分预先存在或后续修改的映射，反向迁移不能无条件删除 source。
    operations = [migrations.RunPython(add_source_mapping, migrations.RunPython.noop)]
