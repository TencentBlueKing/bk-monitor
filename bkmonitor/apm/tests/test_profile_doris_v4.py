from types import SimpleNamespace

from apm.models.datasource import ProfileDataSource
from apm.models.doris import BkDataDorisV4Provider, compose_profile_data_id_name


def test_compose_profile_data_id_name_uses_biz_prefix_for_positive_biz():
    assert compose_profile_data_id_name(100, "same-app") == "profile_100_same_app"
    assert compose_profile_data_id_name(200, "same-app") == "profile_200_same_app"


def test_compose_profile_data_id_name_uses_space_prefix_for_negative_biz():
    assert compose_profile_data_id_name(-100, "same-app") == "profile_space_100_same_app"
    assert compose_profile_data_id_name(-200, "same-app") == "profile_space_200_same_app"


def test_v4_provider_separates_source_biz_from_bkbase_biz(settings):
    settings.APM_PROFILE_V4_DORIS_BINDING_CLUSTER = "doris-default"
    datasource = SimpleNamespace(
        bk_biz_id=-100,
        profile_bk_biz_id=9527,
        app_name="same-app",
        bkdata_datalink_config={},
    )

    provider = BkDataDorisV4Provider.from_datasource_instance(
        datasource,
        bk_tenant_id="tenant-a",
        maintainer="admin",
        operator="admin",
    )

    assert provider._data_id_name() == "profile_space_100_same_app"
    assert provider._metadata_labels() == {"bk_biz_id": "9527"}
    assert provider._build_data_id_config()["spec"]["bizId"] == 9527
    assert provider._build_result_table_config(123)["spec"]["bizId"] == 9527

    storage_config = provider._build_doris_binding_config(123)["spec"]["storage_config"]
    assert storage_config["db"] == "mapleleaf_9527"
    assert storage_config["sample_table_name"].endswith("_sample_9527")
    assert storage_config["label_table_name"].endswith("_label_9527")


def test_apply_profile_datasource_uses_tenant_default_biz_for_space(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.APM_APP_BKDATA_MAINTAINER = []
    settings.APM_PROFILE_V4_BIZ_WHITE_LIST = []
    settings.APM_PROFILING_DEFAULT_USE_BKDATA_V4 = False

    datasource = mocker.Mock()
    mocker.patch("apm.models.datasource.ProfileDataSource.objects.filter").return_value.first.return_value = None
    create = mocker.patch("apm.models.datasource.ProfileDataSource.objects.create", return_value=datasource)
    resolve_tenant = mocker.patch("apm.models.datasource.bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    get_default_biz = mocker.patch("apm.models.datasource.get_tenant_default_biz_id", return_value=9527)
    mocker.patch("apm.models.datasource.get_global_user", return_value="admin")
    legacy_provider = mocker.patch("apm.models.datasource.BkDataDorisProvider.from_datasource_instance")
    legacy_provider.return_value.provider.return_value = {
        "bk_data_id": 123,
        "result_table_id": "9527_profile_same_app_123",
        "retention": 3,
    }

    ProfileDataSource.apply_datasource(-100, "same-app", option=True)

    resolve_tenant.assert_called_once_with(-100)
    get_default_biz.assert_called_once_with("tenant-a")
    create.assert_called_once_with(bk_biz_id=-100, app_name="same-app", profile_bk_biz_id=9527)
