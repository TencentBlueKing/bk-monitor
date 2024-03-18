"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import binascii
import datetime
import gzip
import logging
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Tuple

import requests
from rest_framework.status import HTTP_200_OK

from apm_web.profile.models import Profile
from core.drf_resource import api

logger = logging.getLogger("root")


def encode_multipart_form_data(data) -> Tuple[bytes, bytes]:
    boundary = binascii.hexlify(os.urandom(16))

    # The body that is generated is very sensitive and must perfectly match what the server expects.
    body = (
        b"".join(
            (
                b'--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                % (boundary, field_name, field_name)
            )
            + b"Content-Type: application/octet-stream\r\n\r\n"
            + field_data
            + b"\r\n"
            for field_name, field_data in data.items()
        )
        + b"--%s--" % boundary
    )

    content_type = b"multipart/form-data; boundary=%s" % boundary

    return content_type, body


@dataclass
class CollectorHandler:
    """Collector handler for profile"""

    @classmethod
    def send_to_builtin_datasource(cls, profile: Profile):
        """Send profile to collector"""
        builtin_profile_datasource = api.apm_api.query_builtin_profile_datasource()

        data_token = builtin_profile_datasource["bk_data_token"]
        app_name = builtin_profile_datasource["app_name"]

        pprof = BytesIO()
        with gzip.GzipFile(fileobj=pprof, mode="wb") as gz:
            gz.write(bytes(profile))

        data = {
            b"profile": pprof.getvalue(),
            # TODO: support other type in the future by specifying sample_type_config
            # b"sample_type_config": {},
        }
        content_type, body = encode_multipart_form_data(data=data)
        headers = {"Authorization": f"Bearer {data_token}", "Content-Type": content_type}

        # bk-collector already integrated with ingestion of pyroscope
        collector_http_host = os.getenv("BKAPP_PROFILING_COLLECTOR_HTTP_HOST")
        if collector_http_host is None:
            # if no profiling host set, use otel collector host
            otlp_host = os.getenv("BKAPP_OTLP_HTTP_HOST")
            if otlp_host is None:
                raise Exception("collector_http_host is not set")
            collector_http_host = otlp_host.split("/v1/traces")[0]

        server_url = f"{collector_http_host}/pyroscope/ingest"

        def _get_stamp_by_ns(time_ns: int) -> int:
            return int(datetime.datetime.utcfromtimestamp(time_ns / 1e9).timestamp())

        # simulating as pyroscope agent
        params = {
            "name": app_name,
            "from": _get_stamp_by_ns(profile.time_nanos),
            "until": _get_stamp_by_ns(int(profile.time_nanos) + int(profile.duration_nanos)),
            "spyName": "gospy",
            "sampleRate": 100,
            "units": profile.string_table[profile.sample_type[0].unit],
            "aggregationType": "",
        }

        try:
            result = requests.post(server_url, data=body, params=params, headers=headers)
        except Exception:
            logger.exception("send to collector failed")
            raise

        if result.status_code != HTTP_200_OK:
            logger.error("send to collector failed: %s", result.text)
            # TODO: retry?
            raise Exception("send to collector failed")
