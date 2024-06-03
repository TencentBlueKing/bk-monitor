# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import binascii
import gzip
import json
import os
import typing
import urllib.parse

import six
import tenacity
from ddtrace.internal import agent
from ddtrace.profiling import exporter
from ddtrace.profiling.collector import _lock  # noqa
from ddtrace.profiling.collector import memalloc, stack_event
from ddtrace.profiling.exporter.http import UploadFailed
from ddtrace.profiling.exporter.pprof import HashableStackTraceType  # noqa
from ddtrace.profiling.exporter.pprof import PprofExporter  # noqa
from ddtrace.profiling.exporter.pprof import _get_thread_name  # noqa
from ddtrace.profiling.exporter.pprof import _none_to_str  # noqa
from ddtrace.profiling.exporter.pprof import _PprofConverter  # noqa; noqa
from django.conf import settings
from six.moves import http_client

SAMPLE_TYPE_CONFIG = {
    "cpu-time": {
        "units": "samples",
        "aggregation": "sum",
        "display-name": "cpu_time",
        "sampled": True,
    },
    "wall-time": {
        "units": "samples",
        "aggregation": "sum",
        "display-name": "wall_time",
        "sampled": True,
    },
    # missing, leave it alone
    # "exception-samples": {
    #     "units": "samples",
    #     "aggregation": "sum",
    #     "display-name": "exception_samples",
    #     "sampled": True,
    # },
    # no proper units
    # "alloc-samples": {
    #     "units": "goroutines",
    #     "aggregation": "sum",
    #     "display-name": "alloc_samples",
    #     "sampled": True,
    # },
    "alloc-space": {
        "units": "bytes",
        "aggregation": "sum",
        "display-name": "alloc_space",
        "sampled": True,
    },
    "heap-space": {
        "units": "bytes",
        "aggregation": "average",
        "display-name": "heap_space",
        "sampled": False,
    },
}

SAMPLE_TYPE_CONFIG_JSON = json.dumps(SAMPLE_TYPE_CONFIG).encode()


class ProfileTypes:
    CPU = "cpu"
    MEM = "mem"


def convert_stack_event(
    self,
    thread_id,  # type: str
    thread_native_id,  # type: str
    thread_name,  # type: str
    task_id,  # type: str
    task_name,  # type: str
    local_root_span_id,  # type: str
    span_id,  # type: str
    trace_resource,  # type: str
    trace_type,  # type: str
    frames,  # type: HashableStackTraceType
    nframes,  # type: int
    samples,  # type: typing.List[stack_event.StackSampleEvent]
):
    # type: (...) -> None
    location_key = (
        self._to_locations(frames, nframes),
        (
            ("thread_id", thread_id),
            ("thread_native_id", thread_native_id),
            ("thread_name", thread_name),
            ("task_id", task_id),
            ("task_name", task_name),
            ("local_root_span_id", local_root_span_id),
            ("span_id", span_id),
            ("trace_endpoint", trace_resource),
            ("trace_type", trace_type),
            ("class_name", frames[0][3]),
        ),
    )

    self._location_values[location_key]["cpu-samples"] = len(samples)
    self._location_values[location_key]["cpu-time"] = sum(s.cpu_time_ns for s in samples)
    self._location_values[location_key]["wall-time"] = sum(s.wall_time_ns for s in samples)


def convert_memalloc_event(
    self,
    thread_id,  # type: str
    thread_native_id,  # type: str
    thread_name,  # type: str
    frames,  # type: HashableStackTraceType
    nframes,  # type: int
    events,  # type: typing.List[memalloc.MemoryAllocSampleEvent]
):
    # type: (...) -> None
    location_key = (
        self._to_locations(frames, nframes),
        (
            ("thread_id", thread_id),
            ("thread_native_id", thread_native_id),
            ("thread_name", thread_name),
        ),
    )

    self._location_values[location_key]["alloc-samples"] = round(
        sum(event.nevents * (event.capture_pct / 100.0) for event in events)
    )
    self._location_values[location_key]["alloc-space"] = round(
        sum(event.size / event.capture_pct * 100.0 for event in events)
    )


def convert_memalloc_heap_event(self, event: memalloc.MemoryHeapSampleEvent) -> None:
    location_key = (
        self._to_locations(tuple(event.frames), event.nframes),
        (
            ("thread_id", _none_to_str(event.thread_id)),
            ("thread_native_id", _none_to_str(event.thread_native_id)),
            ("thread_name", _get_thread_name(event.thread_id, event.thread_name)),
        ),
    )

    self._location_values[location_key]["heap-space"] += event.size


def convert_lock_acquire_event(
    self,
    lock_name,  # type: str
    thread_id,  # type: str
    thread_name,  # type: str
    task_id,  # type: str
    task_name,  # type: str
    local_root_span_id,  # type: str
    span_id,  # type: str
    trace_resource,  # type: str
    trace_type,  # type: str
    frames,  # type: HashableStackTraceType
    nframes,  # type: int
    events,  # type: typing.List[_lock.LockAcquireEvent]
    sampling_ratio,  # type: float
):
    # type: (...) -> None
    location_key = (
        self._to_locations(frames, nframes),
        (
            ("thread_id", thread_id),
            ("thread_name", thread_name),
            ("task_id", task_id),
            ("task_name", task_name),
            ("local_root_span_id", local_root_span_id),
            ("span_id", span_id),
            ("trace_endpoint", trace_resource),
            ("trace_type", trace_type),
            ("lock_name", lock_name),
            ("class_name", frames[0][3]),
        ),
    )

    self._location_values[location_key]["lock-acquire"] = len(events)
    self._location_values[location_key]["lock-acquire-wait"] = int(sum(e.wait_time_ns for e in events) / sampling_ratio)


def convert_lock_release_event(
    self,
    lock_name,  # type: str
    thread_id,  # type: str
    thread_name,  # type: str
    task_id,  # type: str
    task_name,  # type: str
    local_root_span_id,  # type: str
    span_id,  # type: str
    trace_resource,  # type: str
    trace_type,  # type: str
    frames,  # type: HashableStackTraceType
    nframes,  # type: int
    events,  # type: typing.List[_lock.LockReleaseEvent]
    sampling_ratio,  # type: float
):
    # type: (...) -> None
    location_key = (
        self._to_locations(frames, nframes),
        (
            ("thread_id", thread_id),
            ("thread_name", thread_name),
            ("task_id", task_id),
            ("task_name", task_name),
            ("local_root_span_id", local_root_span_id),
            ("span_id", span_id),
            ("trace_endpoint", trace_resource),
            ("trace_type", trace_type),
            ("lock_name", lock_name),
            ("class_name", frames[0][3]),
        ),
    )

    self._location_values[location_key]["lock-release"] = len(events)
    self._location_values[location_key]["lock-release-hold"] = int(
        sum(e.locked_for_ns for e in events) / sampling_ratio
    )


def convert_stack_exception_event(
    self,
    thread_id: str,
    thread_native_id: str,
    thread_name: str,
    local_root_span_id: str,
    span_id: str,
    trace_resource: str,
    trace_type: str,
    frames: HashableStackTraceType,
    nframes: int,
    exc_type_name: str,
    events: typing.List[stack_event.StackExceptionSampleEvent],
) -> None:
    location_key = (
        self._to_locations(frames, nframes),
        (
            ("thread_id", thread_id),
            ("thread_native_id", thread_native_id),
            ("thread_name", thread_name),
            ("local_root_span_id", local_root_span_id),
            ("span_id", span_id),
            ("trace_endpoint", trace_resource),
            ("trace_type", trace_type),
            ("exception_type", exc_type_name),
            ("class_name", frames[0][3]),
        ),
    )

    self._location_values[location_key]["exception-samples"] = len(events)


def patch_converter():
    _PprofConverter.convert_stack_exception_event = convert_stack_exception_event
    _PprofConverter.convert_stack_event = convert_stack_event
    _PprofConverter.convert_memalloc_event = convert_memalloc_event
    _PprofConverter.convert_lock_acquire_event = convert_lock_acquire_event
    _PprofConverter.convert_lock_release_event = convert_lock_release_event
    _PprofConverter.convert_memalloc_heap_event = convert_memalloc_heap_event


class PyroscopePprofHTTPExporter(PprofExporter):
    """Send profiles via pprof format to pyroscope server"""

    def __init__(
        self,
        endpoint: str,
        endpoint_path: str,
        max_retry_delay: int = 3,
        enable_code_provenance: bool = False,
    ):
        self.endpoint = endpoint
        self.endpoint_path = endpoint_path
        self.max_retry_delay = max_retry_delay
        # useless in pyroscope now
        self.enable_code_provenance = enable_code_provenance

        self._retry_upload = tenacity.Retrying(
            # Retry after 1s, 2s, 4s, 8s with some randomness
            wait=tenacity.wait_random_exponential(multiplier=0.5),
            stop=tenacity.stop_after_delay(self.max_retry_delay),
            retry_error_cls=UploadFailed,
            retry=tenacity.retry_if_exception_type((http_client.HTTPException, OSError, IOError)),
        )

    def export(self, events, start_time_ns, end_time_ns):
        """Export events to an HTTP endpoint.

        :param events: The event dictionary from a `ddtrace.profiling.recorder.Recorder`.
        :param start_time_ns: The start time of recording.
        :param end_time_ns: The end time of recording.
        """
        profile, libs = super().export(events, start_time_ns, end_time_ns)
        pprof = six.BytesIO()
        with gzip.GzipFile(fileobj=pprof, mode="wb") as gz:
            gz.write(profile.SerializeToString())
        data = {
            b"profile": pprof.getvalue(),
            b"sample_type_config": SAMPLE_TYPE_CONFIG_JSON,
        }

        # pyroscope ignores content-type if format=pprof is provided
        # which will cause Parser.Parse() failed
        # https://github.com/pyroscope-io/pyroscope/blob/c068c7c0db1550b85031d7df0b56c84ce63036f6/pkg/server/ingest.go#L163
        params = {
            "name": settings.SERVICE_NAME,
            "spyName": "ddtrace",
            "from": start_time_ns,
            "until": end_time_ns,
        }
        content_type, body = self._encode_multipart_formdata(data=data)

        headers = {"Content-Type": content_type}
        auth_token = os.getenv("BKAPP_CONTINUOUS_PROFILING_TOKEN") or os.getenv("BKAPP_OTLP_BK_DATA_TOKEN")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        self._retry_upload(self._upload_once, body, headers, params)

        return profile, libs

    @staticmethod
    def _encode_multipart_formdata(data) -> typing.Tuple[bytes, bytes]:
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

    def _assemble_url(self, params: dict) -> str:
        """Assemble url with path and params"""
        url = urllib.parse.urljoin(self.endpoint, self.endpoint_path)
        url += f"?{urllib.parse.urlencode(params)}"
        return url

    def _upload_once(self, body, headers: dict, params: dict):
        """Upload profile to target"""
        url = self._assemble_url(params)
        client = agent.get_connection(self.endpoint)

        client.request("POST", url, body=body, headers=headers)
        resp = client.getresponse()

        if 200 <= resp.status < 300:
            return

        if 500 <= resp.status:
            raise tenacity.TryAgain

        if resp.status == 400:
            raise exporter.ExportError("Server returned 400, check your API key.")
        elif resp.status == 404:
            raise exporter.ExportError("Server returned 404, check your endpoint path.")

        raise exporter.ExportError(f"POST to {url}, but got {resp.status}")


def _build_default_exporters(self):  # noqa
    """Patch. Only return custom httpExporter"""
    endpoint, endpoint_path = _get_endpoint_info_from_env()
    return [PyroscopePprofHTTPExporter(endpoint, endpoint_path)]


def _get_endpoint_info_from_env() -> typing.Tuple[str, str]:
    """Get endpoint url and path from environment variables"""
    endpoint = os.getenv("BKAPP_CONTINUOUS_PROFILING_ENDPOINT", "http://localhost:4040")
    endpoint_path = os.getenv("BKAPP_CONTINUOUS_PROFILING_PATH", "/pyroscope/ingest")

    return endpoint, endpoint_path


def patch_ddtrace_to_pyroscope(skip_converter: bool = False):
    """Patching entrance"""

    # converter use empty str in label key which causes exceptions in pyroscope
    # remaining params for future changes
    if not skip_converter:
        patch_converter()

    from ddtrace.profiling.profiler import _ProfilerInstance  # noqa

    # 'cpu' always open，but 'mem' is on demand
    profiling_types = str(os.getenv("BKAPP_CONTINUOUS_PROFILING_TYPES", ProfileTypes.CPU)).split(",")
    if ProfileTypes.MEM not in profiling_types:
        os.environ["DD_PROFILING_MEMORY_ENABLED"] = "False"

    _ProfilerInstance._build_default_exporters = _build_default_exporters
