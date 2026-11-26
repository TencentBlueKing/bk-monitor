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
    error_attributes,
    http_attributes,
    longtask_attributes,
    network_attributes,
    resource_attributes,
    session_attributes,
    timing_attributes,
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
    TAB_ID = common_attributes.TAB_ID
    SPAN_TYPE = common_attributes.SPAN_TYPE
    OUTCOME_TYPE = common_attributes.OUTCOME_TYPE

    # ── error ──────────────────────────────────────────────────────
    ERROR_SOURCE = error_attributes.ERROR_SOURCE
    ERROR_COLUMN = error_attributes.ERROR_COLUMN
    ERROR_FILEPATH = error_attributes.ERROR_FILEPATH
    ERROR_LINENO = error_attributes.ERROR_LINENO

    # ── browser ─────────────────────────────────────────────────────────────
    BROWSER_SCREEN_HEIGHT = browser_attributes.BROWSER_SCREEN_HEIGHT
    BROWSER_SCREEN_WIDTH = browser_attributes.BROWSER_SCREEN_WIDTH
    BROWSER_VIEWPORT_HEIGHT = browser_attributes.BROWSER_VIEWPORT_HEIGHT
    BROWSER_VIEWPORT_WIDTH = browser_attributes.BROWSER_VIEWPORT_WIDTH

    # ── network ─────────────────────────────────────────────────────────────
    NETWORK_CONNECTION_TYPE = network_attributes.NETWORK_CONNECTION_TYPE
    NETWORK_EFFECTIVE_TYPE = network_attributes.NETWORK_EFFECTIVE_TYPE
    NETWORK_STATUS = network_attributes.NETWORK_STATUS

    # ── session ─────────────────────────────────────────────────────────────
    SESSION_ID = session_attributes.SESSION_ID
    SESSION_TYPE = session_attributes.SESSION_TYPE
    SESSION_PHASE = session_attributes.SESSION_PHASE

    # ── view ────────────────────────────────────────────────────────────────
    VIEW_ID = view_attributes.VIEW_ID
    VIEW_NAME = view_attributes.VIEW_NAME
    VIEW_LOADING_TYPE = view_attributes.VIEW_LOADING_TYPE
    VIEW_URL = view_attributes.VIEW_URL
    VIEW_PREVIOUS_URL_TEMPLATE = view_attributes.VIEW_PREVIOUS_URL_TEMPLATE
    VIEW_REFERRER = view_attributes.VIEW_REFERRER
    VIEW_URL_TEMPLATE = view_attributes.VIEW_URL_TEMPLATE
    VIEW_LOADING_TIME = view_attributes.VIEW_LOADING_TIME
    VIEW_LOADING_TIME_SOURCE = view_attributes.VIEW_LOADING_TIME_SOURCE
    VIEW_PHASE = view_attributes.VIEW_PHASE
    VIEW_STARTED_AT = view_attributes.VIEW_STARTED_AT
    VIEW_VERSION = view_attributes.VIEW_VERSION
    VIEW_END_REASON = view_attributes.VIEW_END_REASON

    # ── resource ────────────────────────────────────────────────────────────────
    RESOURCE_TYPE = resource_attributes.RESOURCE_TYPE
    RESOURCE_INITIATOR_TYPE = resource_attributes.RESOURCE_INITIATOR_TYPE
    RESOURCE_SIZE = resource_attributes.RESOURCE_SIZE
    RESOURCE_TRANSFER_SIZE = resource_attributes.RESOURCE_TRANSFER_SIZE
    RESOURCE_ENCODED_BODY_SIZE = resource_attributes.RESOURCE_ENCODED_BODY_SIZE
    RESOURCE_PROTOCOL = resource_attributes.RESOURCE_PROTOCOL
    RESOURCE_DELIVERY_TYPE = resource_attributes.RESOURCE_DELIVERY_TYPE
    RESOURCE_RENDER_BLOCKING_STATUS = resource_attributes.RESOURCE_RENDER_BLOCKING_STATUS

    # ── timing ─────────────────────────────────────────────────────────────────
    TIMING_START_TIME = timing_attributes.TIMING_START_TIME
    TIMING_REDIRECT_START = timing_attributes.TIMING_REDIRECT_START
    TIMING_REDIRECT_END = timing_attributes.TIMING_REDIRECT_END
    TIMING_FETCH_START = timing_attributes.TIMING_FETCH_START
    TIMING_WORKER_START = timing_attributes.TIMING_WORKER_START
    TIMING_WORKER_ROUTER_EVALUATION_START = timing_attributes.TIMING_WORKER_ROUTER_EVALUATION_START
    TIMING_WORKER_CACHE_LOOKUP_START = timing_attributes.TIMING_WORKER_CACHE_LOOKUP_START
    TIMING_DOMAIN_LOOKUP_START = timing_attributes.TIMING_DOMAIN_LOOKUP_START
    TIMING_DOMAIN_LOOKUP_END = timing_attributes.TIMING_DOMAIN_LOOKUP_END
    TIMING_CONNECT_START = timing_attributes.TIMING_CONNECT_START
    TIMING_SECURE_CONNECTION_START = timing_attributes.TIMING_SECURE_CONNECTION_START
    TIMING_CONNECT_END = timing_attributes.TIMING_CONNECT_END
    TIMING_REQUEST_START = timing_attributes.TIMING_REQUEST_START
    TIMING_RESPONSE_START = timing_attributes.TIMING_RESPONSE_START
    TIMING_FINAL_RESPONSE_HEADERS_START = timing_attributes.TIMING_FINAL_RESPONSE_HEADERS_START
    TIMING_RESPONSE_END = timing_attributes.TIMING_RESPONSE_END
    TIMING_UNLOAD_EVENT_START = timing_attributes.TIMING_UNLOAD_EVENT_START
    TIMING_UNLOAD_EVENT_END = timing_attributes.TIMING_UNLOAD_EVENT_END
    TIMING_DOM_INTERACTIVE = timing_attributes.TIMING_DOM_INTERACTIVE
    TIMING_DOM_CONTENT_LOADED_EVENT_START = timing_attributes.TIMING_DOM_CONTENT_LOADED_EVENT_START
    TIMING_DOM_CONTENT_LOADED_EVENT_END = timing_attributes.TIMING_DOM_CONTENT_LOADED_EVENT_END
    TIMING_DOM_COMPLETE = timing_attributes.TIMING_DOM_COMPLETE
    TIMING_LOAD_EVENT_START = timing_attributes.TIMING_LOAD_EVENT_START
    TIMING_LOAD_EVENT_END = timing_attributes.TIMING_LOAD_EVENT_END
    TIMING_ACTIVATION_START = timing_attributes.TIMING_ACTIVATION_START
    TIMING_WORKER_MATCHED_ROUTER_SOURCE = timing_attributes.TIMING_WORKER_MATCHED_ROUTER_SOURCE
    TIMING_WORKER_FINAL_ROUTER_SOURCE = timing_attributes.TIMING_WORKER_FINAL_ROUTER_SOURCE
    TIMING_INCOMPLETE = timing_attributes.TIMING_INCOMPLETE

    # ── action ──────────────────────────────────────────────────────────────
    ACTION_ID = action_attributes.ACTION_ID
    ACTION_NAME = action_attributes.ACTION_NAME
    ACTION_IDS = action_attributes.ACTION_IDS
    ACTION_TYPE = action_attributes.ACTION_TYPE
    ACTION_END_REASON = action_attributes.ACTION_END_REASON
    ACTION_TARGET_NAME = action_attributes.ACTION_TARGET_NAME
    ACTION_TARGET_TAG = action_attributes.ACTION_TARGET_TAG
    ACTION_TARGET_SELECTOR = action_attributes.ACTION_TARGET_SELECTOR
    ACTION_TARGET_PATH = action_attributes.ACTION_TARGET_PATH
    ACTION_TARGET_WIDTH = action_attributes.ACTION_TARGET_WIDTH
    ACTION_TARGET_HEIGHT = action_attributes.ACTION_TARGET_HEIGHT
    ACTION_POSITION_X = action_attributes.ACTION_POSITION_X
    ACTION_POSITION_Y = action_attributes.ACTION_POSITION_Y
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
    VITAL_VERSION = vital_attributes.VITAL_VERSION
    VITAL_METRIC = vital_attributes.VITAL_METRIC
    VITAL_VALUE = vital_attributes.VITAL_VALUE
    VITAL_INP_INTERACTION_TYPE = vital_attributes.VITAL_INP_INTERACTION_TYPE
    VITAL_INP_TARGET_SELECTOR = vital_attributes.VITAL_INP_TARGET_SELECTOR
    VITAL_LCP_TARGET = vital_attributes.VITAL_LCP_TARGET
    VITAL_LCP_URL = vital_attributes.VITAL_LCP_URL
    VITAL_CLS_TARGET_SELECTOR = vital_attributes.VITAL_CLS_TARGET_SELECTOR

    # ── blank_screen ────────────────────────────────────────────────────────
    BLANK_SCREEN_REASON = blank_screen_attributes.BLANK_SCREEN_REASON
    BLANK_SCREEN_EMPTY_RATIO = blank_screen_attributes.BLANK_SCREEN_EMPTY_RATIO
    BLANK_SCREEN_EMPTY_SAMPLE_COUNT = blank_screen_attributes.BLANK_SCREEN_EMPTY_SAMPLE_COUNT

    # ── long_task ───────────────────────────────────────────────────────────
    LONG_TASK_ENTRY_TYPE = longtask_attributes.LONG_TASK_ENTRY_TYPE
    LONG_TASK_BLOCKING_DURATION = longtask_attributes.LONG_TASK_BLOCKING_DURATION
    LONG_TASK_FIRST_UI_EVENT_TIMESTAMP = longtask_attributes.LONG_TASK_FIRST_UI_EVENT_TIMESTAMP
    LONG_TASK_RENDER_START = longtask_attributes.LONG_TASK_RENDER_START
    LONG_TASK_STYLE_AND_LAYOUT_START = longtask_attributes.LONG_TASK_STYLE_AND_LAYOUT_START
