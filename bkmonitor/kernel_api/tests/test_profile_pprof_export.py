import gzip
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml
from django.conf import settings
from jsonschema import Draft7Validator
from requests import Request, Response
from rest_framework.exceptions import ValidationError

from apm_web.profile.constants import PROFILE_MCP_EXPORT_PATH
from apm_web.profile.models import Profile, Sample, ValueType
from apm_web.profile.views import ProfileQueryViewSet
from apm_web.models import ProfileUploadRecord
from kernel_api.adapters import ApiRenderer
from kernel_api.resource import apm, unified_mcp


@pytest.fixture
def export_args():
    return {
        "bk_biz_id": 2,
        "app_name": "demo",
        "service_name": "checkout",
        "start_time": 1710000000,
        "end_time": 1710000060,
        "confirm": True,
    }


@pytest.fixture
def storage(monkeypatch):
    client = Mock(endpoint_url="https://artifacts.example.com", project="demo", bucket="private")
    client.get_client.return_value.hooks = {"response": []}
    client.get_bucket_metadata.return_value = {"public": False}
    client.generate_presigned_url.return_value = "https://artifacts.example.com/download?token=synthetic"
    monkeypatch.setattr(
        apm, "ProfilingFileHandler", Mock(return_value=SimpleNamespace(bk_repo_storage=SimpleNamespace(client=client)))
    )
    return client


def test_storage_logging_cannot_include_credentials_or_profile_bytes():
    request = Request(
        "PUT", "https://artifacts.example.com/profile", headers={"Authorization": "Basic synthetic"}, data=b"profile"
    ).prepare()
    response = Response()
    response.request = request

    apm.ExportProfilePprofResource._redact_storage_request(response)

    assert "Authorization" not in response.request.headers
    assert response.request.body is None
    assert request.body == b"profile"


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"confirm": False}, "confirm"),
        ({"end_time": 1710000000}, "time_span"),
        ({"end_time": 1710001801}, "time_span"),
        ({"app_name": "ebpf-demo"}, "app_name"),
        ({"global_query": True}, "profile_id"),
    ],
)
def test_pprof_export_serializer_rejects_invalid_requests(export_args, changes, field):
    serializer = apm.ExportProfilePprofResource.RequestSerializer(data={**export_args, **changes})
    assert not serializer.is_valid()
    assert field in serializer.errors


def test_export_uploads_original_gzip_pprof_and_returns_download_metadata(monkeypatch, export_args, storage):
    profile = Profile(
        sample_type=[ValueType(type=1, unit=2)],
        sample=[Sample(value=[7])],
        string_table=["", "cpu", "nanoseconds"],
    )
    essentials = {"bk_biz_id": 2, "app_name": "demo", "service_name": "checkout", "result_table_id": "demo_profile"}
    monkeypatch.setattr(ProfileQueryViewSet, "get_essentials", Mock(return_value=essentials))
    monkeypatch.setattr(ProfileQueryViewSet, "get_query_limit_params", Mock(return_value={"limit": {"rows": 5000}}))
    query = Mock(return_value=SimpleNamespace(profile=profile))
    monkeypatch.setattr(ProfileQueryViewSet, "query", query)

    result = apm.ExportProfilePprofResource().request(export_args)

    assert query.call_args.kwargs["start"] == export_args["start_time"] * 1000
    assert query.call_args.kwargs["end"] == export_args["end_time"] * 1000
    assert query.call_args.kwargs["service_name"] == "checkout"
    assert query.call_args.kwargs["sample_type"] == "cpu/nanoseconds"
    uploaded = storage.upload_fileobj.call_args.args[0]
    assert gzip.decompress(uploaded) == profile.SerializeToString()
    assert result["filename"].endswith(".pprof")
    assert result["size_bytes"] == len(uploaded)
    assert result["download_url"] == storage.generate_presigned_url.return_value
    assert result["expires_in_seconds"] == 900
    key = f"{PROFILE_MCP_EXPORT_PATH}{result['filename']}"
    storage.upload_fileobj.assert_called_once_with(uploaded, key=key, allow_overwrite=False)
    storage.generate_presigned_url.assert_called_once_with(key=key, expires_in=900)

    contract = unified_mcp.LookupToolSchemaResource().request(tool_name="export_profile_pprof")
    resource_file = Path(settings.BASE_DIR) / "support-files/apigw/resources/internal/user/apm_mcp.yaml"
    operation = yaml.safe_load(resource_file.read_text())["paths"]["/mcp/export_profile_pprof/"]["post"]
    envelope_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert contract["output_schema"] == envelope_schema["properties"]["data"]
    assert set(contract["output_schema"]["required"]) == set(result)
    envelope = ApiRenderer().get_result(result, renderer_context={"response": SimpleNamespace(status_code=200)})
    Draft7Validator(envelope_schema, format_checker=Draft7Validator.FORMAT_CHECKER).validate(envelope)


def test_uploaded_profile_cannot_be_exported_from_another_business(monkeypatch, export_args, storage):
    scoped_records = Mock()
    scoped_records.return_value.exists.return_value = False
    monkeypatch.setattr(ProfileUploadRecord.objects, "filter", scoped_records)
    query = Mock()
    monkeypatch.setattr(ProfileQueryViewSet, "query", query)
    args = {key: value for key, value in export_args.items() if key not in {"app_name", "service_name"}}
    args.update(global_query=True, profile_id="synthetic-profile")

    with pytest.raises(ValidationError) as error:
        apm.ExportProfilePprofResource().request(args)

    assert error.value.get_codes() == {"profile_id": "invalid_profile_scope"}
    scoped_records.assert_called_once_with(bk_biz_id=2, profile_id="synthetic-profile")
    query.assert_not_called()
    storage.upload_fileobj.assert_not_called()


@pytest.mark.parametrize("metadata", [{"public": True}, {}])
def test_export_never_uploads_to_a_repository_without_private_visibility(monkeypatch, export_args, storage, metadata):
    storage.get_bucket_metadata.return_value = metadata
    monkeypatch.setattr(ProfileQueryViewSet, "query_export", Mock(return_value=SimpleNamespace(content=b"profile")))

    with pytest.raises(apm.ProfileExportUnavailable):
        apm.ExportProfilePprofResource().perform_request(export_args)

    storage.upload_fileobj.assert_not_called()
    storage.generate_presigned_url.assert_not_called()


def test_empty_profile_does_not_create_download(monkeypatch, export_args, storage):
    empty_profile = SimpleNamespace(profile=Profile())
    with pytest.raises(ValueError) as err:
        ProfileQueryViewSet.build_export_response(empty_profile, "demo", "cpu/nanoseconds", "pprof")
    monkeypatch.setattr(ProfileQueryViewSet, "query_export", Mock(side_effect=err.value))

    with pytest.raises(ValidationError) as error:
        apm.ExportProfilePprofResource().perform_request(export_args)

    assert error.value.get_codes() == {"profile": "empty_profile"}
    storage.upload_fileobj.assert_not_called()


def test_missing_artifact_cannot_return_an_unsigned_download(monkeypatch, export_args, storage):
    storage.endpoint_url = "https://artifacts.example.com/api"
    storage.generate_presigned_url.side_effect = lambda key, expires_in: (
        f"{storage.endpoint_url}/generic/temporary/token/download/demo/private/{key}"
    )
    monkeypatch.setattr(ProfileQueryViewSet, "query_export", Mock(return_value=SimpleNamespace(content=b"profile")))

    with pytest.raises(apm.ProfileExportUnavailable):
        apm.ExportProfilePprofResource().perform_request(export_args)
