"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from semconv.rum.attributes import (
    action_attributes,
    blank_screen_attributes,
    browser_attributes,
    common_attributes,
    device_attributes,
    error_attributes,
    http_attributes,
    longtask_attributes,
    network_attributes,
    resource_attributes,
    session_attributes,
    view_attributes,
    vital_attributes,
)
from semconv.rum.field import FieldSpec


class Attributes(FieldSpec):
    """attributes.*（Span attributes 字段）

    原子字段仅在此定义一次，直接引用 ``semconv.rum.attributes`` 下各模块导出的
    ``FieldSpec`` 实例；其 ``field_name`` 携带完整点分路径（如 ``"user.id"``），
    ``FieldRegistry`` 据此自动注册为 ``attributes.user.id`` 等嵌套路径。

    ``service.*`` / ``deployment.*`` / ``telemetry.*`` 属于 ``resource.*`` 顶层支柱，
    不在此处展开。
    """

    # ── 基础字段 ──────────────────────────────────────────────────────────
    USER_ID = common_attributes.USER_ID
    SPAN_TYPE = common_attributes.SPAN_TYPE
    OUTCOME_TYPE = common_attributes.OUTCOME_TYPE

    # ── error ──────────────────────────────────────────────────────
    ERROR_MESSAGE = error_attributes.ERROR_MESSAGE
    ERROR_HANDLED = error_attributes.ERROR_HANDLED
    ERROR_SOURCE = error_attributes.ERROR_SOURCE
    ERROR_COLUMN = error_attributes.ERROR_COLUMN
    ERROR_FILEPATH = error_attributes.ERROR_FILEPATH
    ERROR_LINENO = error_attributes.ERROR_LINENO

    # ── browser ─────────────────────────────────────────────────────────────
    BROWSER_SCREEN_HEIGHT = browser_attributes.BROWSER_SCREEN_HEIGHT
    BROWSER_SCREEN_WIDTH = browser_attributes.BROWSER_SCREEN_WIDTH
    BROWSER_VIEWPORT_HEIGHT = browser_attributes.BROWSER_VIEWPORT_HEIGHT
    BROWSER_VIEWPORT_WIDTH = browser_attributes.BROWSER_VIEWPORT_WIDTH

    # ── device ──────────────────────────────────────────────────────────────
    DEVICE_ID = device_attributes.DEVICE_ID

    # ── network ─────────────────────────────────────────────────────────────
    NETWORK_CONNECTION_TYPE = network_attributes.NETWORK_CONNECTION_TYPE
    NETWORK_EFFECTIVE_TYPE = network_attributes.NETWORK_EFFECTIVE_TYPE
    NETWORK_STATUS = network_attributes.NETWORK_STATUS
    NETWORK_PROTOCOL_NAME = network_attributes.NETWORK_PROTOCOL_NAME

    # ── session ─────────────────────────────────────────────────────────────
    SESSION_HAS_REPLAY = session_attributes.SESSION_HAS_REPLAY
    SESSION_ID = session_attributes.SESSION_ID
    SESSION_TYPE = session_attributes.SESSION_TYPE
    SESSION_PHASE = session_attributes.SESSION_PHASE

    # ── view ────────────────────────────────────────────────────────────────
    VIEW_ID = view_attributes.VIEW_ID
    VIEW_NAME = view_attributes.VIEW_NAME
    VIEW_LOADING_TYPE = view_attributes.VIEW_LOADING_TYPE
    VIEW_URL = view_attributes.VIEW_URL
    VIEW_PREVIOUS = view_attributes.VIEW_PREVIOUS
    VIEW_PREVIOUS_URL_TEMPLATE = view_attributes.VIEW_PREVIOUS_URL_TEMPLATE
    VIEW_REFERRER = view_attributes.VIEW_REFERRER
    VIEW_URL_TEMPLATE = view_attributes.VIEW_URL_TEMPLATE
    VIEW_LOADING_TIME = view_attributes.VIEW_LOADING_TIME
    VIEW_LOADING_TIME_SOURCE = view_attributes.VIEW_LOADING_TIME_SOURCE
    VIEW_FIRST_BYTE = view_attributes.VIEW_FIRST_BYTE
    VIEW_DOM_INTERACTIVE = view_attributes.VIEW_DOM_INTERACTIVE
    VIEW_DOM_CONTENT_LOADED = view_attributes.VIEW_DOM_CONTENT_LOADED
    VIEW_DOM_COMPLETE = view_attributes.VIEW_DOM_COMPLETE
    VIEW_LOAD_EVENT = view_attributes.VIEW_LOAD_EVENT
    VIEW_PHASE = view_attributes.VIEW_PHASE
    VIEW_STARTED_AT = view_attributes.VIEW_STARTED_AT
    VIEW_VERSION = view_attributes.VIEW_VERSION
    VIEW_END_REASON = view_attributes.VIEW_END_REASON

    # ── resource ────────────────────────────────────────────────────────────────
    RESOURCE_TYPE = resource_attributes.RESOURCE_TYPE
    RESOURCE_SIZE = resource_attributes.RESOURCE_SIZE
    RESOURCE_TRANSFER_SIZE = resource_attributes.RESOURCE_TRANSFER_SIZE
    RESOURCE_DECODED_BODY_SIZE = resource_attributes.RESOURCE_DECODED_BODY_SIZE
    RESOURCE_ENCODED_BODY_SIZE = resource_attributes.RESOURCE_ENCODED_BODY_SIZE
    RESOURCE_PROTOCOL = resource_attributes.RESOURCE_PROTOCOL
    RESOURCE_CACHE_HIT = resource_attributes.RESOURCE_CACHE_HIT
    RESOURCE_DELIVERY_TYPE = resource_attributes.RESOURCE_DELIVERY_TYPE
    RESOURCE_RENDER_BLOCKING_STATUS = resource_attributes.RESOURCE_RENDER_BLOCKING_STATUS
    RESOURCE_REDIRECT_START = resource_attributes.RESOURCE_REDIRECT_START
    RESOURCE_REDIRECT_DURATION = resource_attributes.RESOURCE_REDIRECT_DURATION
    RESOURCE_WORKER_START = resource_attributes.RESOURCE_WORKER_START
    RESOURCE_WORKER_DURATION = resource_attributes.RESOURCE_WORKER_DURATION
    RESOURCE_DNS_START = resource_attributes.RESOURCE_DNS_START
    RESOURCE_DNS_DURATION = resource_attributes.RESOURCE_DNS_DURATION
    RESOURCE_CONNECT_START = resource_attributes.RESOURCE_CONNECT_START
    RESOURCE_CONNECT_DURATION = resource_attributes.RESOURCE_CONNECT_DURATION
    RESOURCE_SSL_START = resource_attributes.RESOURCE_SSL_START
    RESOURCE_SSL_DURATION = resource_attributes.RESOURCE_SSL_DURATION
    RESOURCE_FIRST_BYTE_START = resource_attributes.RESOURCE_FIRST_BYTE_START
    RESOURCE_FIRST_BYTE_DURATION = resource_attributes.RESOURCE_FIRST_BYTE_DURATION
    RESOURCE_DOWNLOAD_START = resource_attributes.RESOURCE_DOWNLOAD_START
    RESOURCE_DOWNLOAD_DURATION = resource_attributes.RESOURCE_DOWNLOAD_DURATION

    # ── action ──────────────────────────────────────────────────────────────
    ACTION_ID = action_attributes.ACTION_ID
    ACTION_TYPE = action_attributes.ACTION_TYPE
    ACTION_TARGET_NAME = action_attributes.ACTION_TARGET_NAME
    ACTION_TARGET_TAG = action_attributes.ACTION_TARGET_TAG
    ACTION_FRUSTRATION_TYPE = action_attributes.ACTION_FRUSTRATION_TYPE

    # ── http ──────────────────────────────────────────────────────────────
    URL_FULL = http_attributes.URL_FULL
    URL_SCHEME = http_attributes.URL_SCHEME
    URL_TEMPLATE = http_attributes.URL_TEMPLATE
    HTTP_REQUEST_METHOD = http_attributes.HTTP_REQUEST_METHOD
    HTTP_RESPONSE_STATUS_CODE = http_attributes.HTTP_RESPONSE_STATUS_CODE
    SERVER_ADDRESS = http_attributes.SERVER_ADDRESS
    SERVER_PORT = http_attributes.SERVER_PORT

    # ── vital ───────────────────────────────────────────────────────────────
    VITAL_ID = vital_attributes.VITAL_ID
    VITAL_METRIC = vital_attributes.VITAL_METRIC
    VITAL_VALUE = vital_attributes.VITAL_VALUE
    VITAL_INP_INPUT_DELAY = vital_attributes.VITAL_INP_INPUT_DELAY
    VITAL_INP_INTERACTION_TARGET = vital_attributes.VITAL_INP_INTERACTION_TARGET
    VITAL_INP_INTERACTION_TYPE = vital_attributes.VITAL_INP_INTERACTION_TYPE
    VITAL_INP_PROCESSING_DURATION = vital_attributes.VITAL_INP_PROCESSING_DURATION
    VITAL_INP_PRESENTATION_DELAY = vital_attributes.VITAL_INP_PRESENTATION_DELAY
    VITAL_LCP_TARGET = vital_attributes.VITAL_LCP_TARGET
    VITAL_LCP_URL = vital_attributes.VITAL_LCP_URL
    VITAL_LCP_RESOURCE_LOAD_DURATION = vital_attributes.VITAL_LCP_RESOURCE_LOAD_DURATION
    VITAL_LCP_ELEMENT_RENDER_DELAY = vital_attributes.VITAL_LCP_ELEMENT_RENDER_DELAY
    VITAL_TTFB_WAITING_DURATION = vital_attributes.VITAL_TTFB_WAITING_DURATION
    VITAL_TTFB_DNS_DURATION = vital_attributes.VITAL_TTFB_DNS_DURATION
    VITAL_TTFB_CONNECTION_DURATION = vital_attributes.VITAL_TTFB_CONNECTION_DURATION
    VITAL_TTFB_REQUEST_DURATION = vital_attributes.VITAL_TTFB_REQUEST_DURATION

    # ── blank_screen ────────────────────────────────────────────────────────
    BLANK_SCREEN_REASON = blank_screen_attributes.BLANK_SCREEN_REASON
    BLANK_SCREEN_EMPTY_RATIO = blank_screen_attributes.BLANK_SCREEN_EMPTY_RATIO
    BLANK_SCREEN_EMPTY_SAMPLE_COUNT = blank_screen_attributes.BLANK_SCREEN_EMPTY_SAMPLE_COUNT

    # ── long_task ───────────────────────────────────────────────────────────
    LONG_TASK_ID = longtask_attributes.LONG_TASK_ID
    LONG_TASK_NAME = longtask_attributes.LONG_TASK_NAME
    LONG_TASK_ENTRY_TYPE = longtask_attributes.LONG_TASK_ENTRY_TYPE
    LONG_TASK_BLOCKING_DURATION = longtask_attributes.LONG_TASK_BLOCKING_DURATION
    LONG_TASK_FIRST_UI_EVENT_TIMESTAMP = longtask_attributes.LONG_TASK_FIRST_UI_EVENT_TIMESTAMP
    LONG_TASK_RENDER_START = longtask_attributes.LONG_TASK_RENDER_START
    LONG_TASK_STYLE_AND_LAYOUT_START = longtask_attributes.LONG_TASK_STYLE_AND_LAYOUT_START
