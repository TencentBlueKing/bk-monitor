"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.conf import settings

from api.aiops_sdk.default import SasPredictResource


class FakeResponse:
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.request_kwargs = None

    def request(self, **kwargs):
        self.request_kwargs = kwargs
        return FakeResponse(self.payload)


def make_resource(payload):
    resource = SasPredictResource()
    resource.base_url = "http://sas.example"
    resource.session = FakeSession(payload)
    resource.get_headers = mock.Mock(return_value={})
    resource.record_request_data_to_span = mock.Mock()
    resource.report_api_request_count_metric = mock.Mock()
    resource.report_api_failure_metric = mock.Mock()
    return resource


def request_data():
    return {
        "data": [{"timestamp": 1_780_000_000_000, "value": 10.0, "is_anomaly": 1.0}],
        "dimensions": {"host": "host-a", "strategy_id": 101},
        "predict_args": {"predict_start_time": 1_780_000_000_000},
        "interval": 60,
        "extra_data": {},
        "serving_config": {"pre_service_name": "default", "serving_with_ts_depend": True},
        "bk_tenant_id": "tenant",
    }


def test_sas_resource_has_independent_contract():
    assert SasPredictResource.base_url == settings.AIOPS_SERVER_SAS_URL
    assert SasPredictResource.action == settings.AIOPS_SAS_PREDICT_SDK
    assert SasPredictResource.TIMEOUT == settings.AIOPS_SAS_TIMEOUT
    assert SasPredictResource.IS_STANDARD_FORMAT is False
    assert SasPredictResource.INSERT_BK_USERNAME_TO_REQUEST_DATA is False


def test_sas_resource_keeps_raw_list_and_exact_request_body():
    payload = [{"timestamp": 1_780_000_000_000, "severity_score": 0.9}]
    resource = make_resource(payload)

    result = resource.request(request_data())

    assert result == payload
    assert resource.session.request_kwargs["method"] == "POST"
    assert resource.session.request_kwargs["timeout"] == settings.AIOPS_SAS_TIMEOUT
    assert resource.session.request_kwargs["url"] == "http://sas.example/aiops/serving/default/"
    assert resource.session.request_kwargs["json"] == {
        key: value for key, value in request_data().items() if key != "bk_tenant_id"
    }


def test_sas_resource_does_not_unwrap_success_wrapper():
    payload = {"result": True, "code": 0, "data": [{"severity_score": 0.9}]}
    resource = make_resource(payload)

    result = resource.request(request_data())

    assert result == payload
