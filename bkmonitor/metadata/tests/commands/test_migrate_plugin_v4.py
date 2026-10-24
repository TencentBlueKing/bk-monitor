import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from metadata import models
from metadata.management.commands import migrate_plugin_v4 as migration
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.constants import DATA_LABEL_TO_RESULT_TABLE_KEY, RESULT_TABLE_DETAIL_KEY

pytestmark = pytest.mark.django_db(databases="__all__")
TENANT = "plugin_migration"
DATA_ID = 50010
NAME = "pushgateway_migration_plugin"
TABLE_ID = f"{NAME}.__default__"


@pytest.fixture
def plugin(settings):
    settings.ENABLE_V2_VM_DATA_LINK = True
    kafka = models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT,
        cluster_name="plugin-kafka",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name="localhost",
        port=9092,
        is_default_cluster=False,
    )
    vm = models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT,
        cluster_name="plugin-vm",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="localhost",
        port=8481,
        is_default_cluster=False,
    )
    topic = models.KafkaTopicInfo.objects.create(bk_data_id=DATA_ID, topic="0bkmonitor_500100", partition=1)
    source = models.DataSource.objects.create(
        bk_tenant_id=TENANT,
        bk_data_id=DATA_ID,
        data_name=NAME,
        etl_config="bk_exporter",
        mq_cluster_id=kafka.cluster_id,
        mq_config_id=topic.id,
        is_custom_source=False,
        created_from=DataIdCreatedFromSystem.BKGSE.value,
    )
    table = models.ResultTable.objects.create(
        bk_tenant_id=TENANT,
        table_id=TABLE_ID,
        is_custom_table=False,
        data_label=NAME,
        default_storage=models.ClusterInfo.TYPE_VM,
    )
    models.DataSourceResultTable.objects.create(bk_tenant_id=TENANT, bk_data_id=DATA_ID, table_id=TABLE_ID)
    models.ResultTableOption.objects.create(
        bk_tenant_id=TENANT,
        table_id=TABLE_ID,
        name=models.ResultTableOption.OPTION_IS_SPLIT_MEASUREMENT,
        value="true",
        value_type="bool",
    )
    models.AccessVMRecord.objects.create(
        bk_tenant_id=TENANT,
        result_table_id=TABLE_ID,
        vm_cluster_id=vm.cluster_id,
        vm_result_table_id="100147_vm_legacy",
        bk_base_data_id=DATA_ID,
    )
    legacy = [f"{NAME}.group{i}" for i in range(1, 8)]
    for table_id in legacy:
        models.ResultTable.objects.create(bk_tenant_id=TENANT, table_id=table_id, is_custom_table=False)
    models.ResultTable.objects.create(bk_tenant_id=TENANT, table_id=f"{NAME}.group1_cmdb_level", is_custom_table=False)
    models.ResultTable.objects.create(bk_tenant_id="other", table_id=f"{NAME}.foreign", is_custom_table=False)
    return source, table, legacy


def command():
    cmd = migration.Command(stdout=io.StringIO())
    cmd.tenant, cmd.biz_id, cmd.namespace, cmd.operator = TENANT, 2, "bkmonitor", "admin"
    cmd.load_context(DATA_ID, None)
    return cmd


@pytest.mark.parametrize("phase", ["precheck", "pre-run"])
def test_preparation_is_read_only_and_supports_long_aliases(plugin, mocker, phase):
    source, table, legacy = plugin
    register = mocker.patch.object(models.DataSource, "register_to_bkbase")
    apply = mocker.patch.object(migration, "create_bkbase_data_link")
    redis = mocker.patch.object(migration.RedisTools, "hmset_to_redis")
    consul = mocker.patch.object(models.DataSource, "delete_consul_config")
    output = io.StringIO()
    call_command("migrate_plugin_v4", phase, bk_tenant_id=TENANT, bk_data_id=DATA_ID, bk_biz_id=2, stdout=output)
    report = json.loads(output.getvalue())
    assert report["errors"] == []
    assert report["plan"]["data_labels"] == [NAME, *legacy]
    assert report["plan"]["sync_data_label"] is False
    for external in [register, apply, redis, consul]:
        external.assert_not_called()
    source.refresh_from_db()
    table.refresh_from_db()
    assert source.created_from == DataIdCreatedFromSystem.BKGSE.value
    assert table.data_labels == [NAME]


def test_execute_publishes_full_aliases_before_cutover(plugin, mocker):
    source, table, legacy = plugin
    cmd = command()
    register = mocker.patch.object(models.DataSource, "register_to_bkbase")
    mocker.patch.object(migration, "create_bkbase_data_link")
    mocker.patch.object(cmd, "component_status", return_value=[{"phase": "Ok"}])
    router = mocker.patch.object(migration, "SpaceTableIDRedis").return_value
    events = []

    def delete_consul(instance):
        assert router.push_data_label_table_ids.called
        table.refresh_from_db()
        instance.refresh_from_db()
        assert table.data_labels == [NAME, *legacy]
        assert instance.created_from == DataIdCreatedFromSystem.BKDATA.value
        events.append("cutover")

    mocker.patch.object(models.DataSource, "delete_consul_config", autospec=True, side_effect=delete_consul)
    cmd.execute_migration()
    register.assert_called_once_with(bk_biz_id=2, namespace="bkmonitor", update_created_from=False)
    assert events == ["cutover"]
    table.refresh_from_db()
    assert table.data_label == NAME
    assert table.data_labels == [NAME, *legacy]


def test_pending_components_do_not_change_aliases_or_transfer(plugin, mocker):
    source, table, _ = plugin
    cmd = command()
    mocker.patch.object(models.DataSource, "register_to_bkbase")
    mocker.patch.object(migration, "create_bkbase_data_link")
    mocker.patch.object(cmd, "component_status", return_value=[{"phase": "Pending"}])
    delete = mocker.patch.object(models.DataSource, "delete_consul_config")
    router = mocker.patch.object(migration, "SpaceTableIDRedis")
    with pytest.raises(CommandError, match="尚未就绪"):
        cmd.execute_migration()
    source.refresh_from_db()
    table.refresh_from_db()
    assert source.created_from == DataIdCreatedFromSystem.BKGSE.value
    assert table.data_labels == [NAME]
    delete.assert_not_called()
    router.assert_not_called()


def test_status_checks_arrays_instead_of_legacy_field(plugin, mocker):
    source, table, legacy = plugin
    table.data_labels = [NAME, *legacy]
    table.save(update_fields=["data_labels"])
    source.created_from = DataIdCreatedFromSystem.BKDATA.value
    source.save(update_fields=["created_from"])
    cmd = command()
    mocker.patch.object(cmd, "component_status", return_value=[{"phase": "Ok"}])
    mocker.patch.object(migration, "HashConsul").return_value.get.return_value = (None, None)

    def values(key, fields):
        if key == DATA_LABEL_TO_RESULT_TABLE_KEY:
            return {field: [TABLE_ID] for field in fields}
        if key == RESULT_TABLE_DETAIL_KEY:
            return {field: {"vm_rt": "100147_vm_legacy"} for field in fields}
        return {}

    mocker.patch.object(cmd, "redis_values", side_effect=values)
    report = cmd.check_status()
    assert report["ready"] is True
    assert report["data_label"] == NAME
    assert report["data_labels"] == [NAME, *legacy]


def test_plugin_edit_preserves_migrated_aliases(plugin, mocker):
    source, table, legacy = plugin
    source.created_from = DataIdCreatedFromSystem.BKDATA.value
    source.save(update_fields=["created_from"])
    table.data_labels = [NAME, *legacy]
    table.save(update_fields=["data_labels"])
    mocker.patch.object(models.ResultTable, "apply_datalink")
    mocker.patch.object(models.DataSource, "refresh_consul_config")
    table.modify(operator="admin", data_label=NAME)
    table.refresh_from_db()
    assert table.data_labels == [NAME, *legacy]
    assert table.data_label == NAME
    table.modify(operator="admin", data_labels=[])
    table.refresh_from_db()
    assert table.data_labels == []
    assert table.data_label == ""


def test_registration_can_delay_source_mark_until_cutover(plugin, mocker):
    source, _, _ = plugin
    mocker.patch.object(models.DataIdConfig, "compose_predefined_config", return_value={})
    mocker.patch.object(models.DataIdConfig, "compose_data_source_config", return_value={})
    mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    mocker.patch("metadata.models.data_link.service.apply_data_source_config")
    source.register_to_bkbase(2, update_created_from=False)
    source.refresh_from_db()
    assert source.created_from == DataIdCreatedFromSystem.BKGSE.value
    source.register_to_bkbase(2)
    source.refresh_from_db()
    assert source.created_from == DataIdCreatedFromSystem.BKDATA.value
