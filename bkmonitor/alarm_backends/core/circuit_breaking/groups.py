"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import math
import re
from uuid import UUID

from alarm_backends.core.circuit_breaking.matcher import CircuitBreakingMatcher, gen_circuit_breaking_matcher

MAX_GROUPS = 100
MAX_CONDITIONS = 20
MAX_VALUES = 100
MAX_TTL_SECONDS = 86400
MAX_REASON_LENGTH = 512
MAX_OPERATOR_LENGTH = 32
MAX_VALUE_LENGTH = 1024
MAX_REVISION = 2**31 - 1
MAX_TIMESTAMP_MS = 2**53 - 1
MAX_GROUP_BYTES = 16 * 1024
MAX_MODULE_BYTES = 256 * 1024

BASE_DIMENSIONS = ("strategy_id", "bk_biz_id", "data_source_label", "data_type_label", "strategy_source")
EVALUATION_CONTEXTS = {
    "access.data": (
        ("scheduler_refresh", BASE_DIMENSIONS[1:]),
        ("before_pull", ("strategy_id",)),
        ("nodata", BASE_DIMENSIONS),
    ),
    "alert.builder": (("alert_builder", BASE_DIMENSIONS),),
    "alert.manager": (("alert_manager", BASE_DIMENSIONS),),
    "action": (
        ("message_queue_creation", (*BASE_DIMENSIONS, "plugin_type")),
        ("action_execution", (*BASE_DIMENSIONS, "plugin_type")),
        ("notice", (*BASE_DIMENSIONS, "plugin_type")),
    ),
}


class CircuitBreakingGroupError(ValueError):
    def __init__(self, message: str, code: str = "validation_error"):
        self.code = code
        super().__init__(message)


def _validate_module(module):
    if not isinstance(module, str) or module not in EVALUATION_CONTEXTS:
        raise CircuitBreakingGroupError("unsupported circuit breaking module")


def capabilities(module: str) -> dict:
    """Describe dimensions available at the existing evaluation call sites.

    Source dimensions depend on a strategy being present. A missing dimension
    never matches, including negative methods. Contexts do not add call sites.
    """
    _validate_module(module)
    contexts = EVALUATION_CONTEXTS[module]
    return {
        "module": module,
        "dimensions": sorted({dimension for _, dimensions in contexts for dimension in dimensions}),
        "methods": sorted(CircuitBreakingMatcher.SUPPORTED_METHODS),
        "connectors": ["and", "or"],
        "operations": ["create", "update", "extend", "revoke"],
        "evaluation_contexts": [{"name": name, "dimensions": list(dimensions)} for name, dimensions in contexts],
        "missing_dimension_matches": False,
        "limits": {
            "groups_per_module": MAX_GROUPS,
            "conditions_per_group": MAX_CONDITIONS,
            "values_per_condition": MAX_VALUES,
            "value_length": MAX_VALUE_LENGTH,
            "group_bytes": MAX_GROUP_BYTES,
            "module_bytes": MAX_MODULE_BYTES,
            "reason_length": MAX_REASON_LENGTH,
            "operator_length": MAX_OPERATOR_LENGTH,
            "ttl_seconds": MAX_TTL_SECONDS,
        },
    }


def _positive_integer(value, name, maximum):
    if type(value) is not int or not 0 < value <= maximum:
        raise CircuitBreakingGroupError(f"{name} must be an integer between 1 and {maximum}")
    return value


def _text(value, name, maximum):
    if not isinstance(value, str) or len(value) > maximum or not value.strip():
        raise CircuitBreakingGroupError(f"{name} must be a string of at most {maximum} characters")
    return value


def _group_id(value):
    if not isinstance(value, str):
        raise CircuitBreakingGroupError("group_id must be a canonical UUID")
    try:
        if str(UUID(value)) == value:
            return value
    except ValueError:
        pass
    raise CircuitBreakingGroupError("group_id must be a canonical UUID")


def validate_conditions(module: str, conditions: list) -> list[dict]:
    """Validate the entire flat AND/OR expression before using the legacy matcher.

    Every value becomes a nonempty list, so the range loader cannot discard a
    falsy scalar and accidentally turn an AND branch into an empty conjunction.
    """
    _validate_module(module)
    if not isinstance(conditions, list) or not 0 < len(conditions) <= MAX_CONDITIONS:
        raise CircuitBreakingGroupError(f"conditions must contain between 1 and {MAX_CONDITIONS} entries")
    contexts = [set(dimensions) for _, dimensions in EVALUATION_CONTEXTS[module]]
    dimensions = set().union(*contexts)
    result, branches, branch = [], [], set()
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) - {"key", "method", "value", "condition"}:
            raise CircuitBreakingGroupError("condition contains unknown fields or is not an object")
        if not {"key", "method", "value"}.issubset(condition):
            raise CircuitBreakingGroupError("condition requires key, method and value")
        key, method = condition["key"], condition["method"]
        if not isinstance(key, str) or key not in dimensions:
            raise CircuitBreakingGroupError("condition key is unavailable for this module")
        if not isinstance(method, str) or method not in CircuitBreakingMatcher.SUPPORTED_METHODS:
            raise CircuitBreakingGroupError("unsupported condition method")
        connector = condition.get("condition", "and")
        if not isinstance(connector, str) or connector.lower() not in {"and", "or"}:
            raise CircuitBreakingGroupError("condition connector must be and or or")
        connector = connector.lower()
        if connector == "or" and branch:
            branches.append(branch)
            branch = set()
        branch.add(key)
        values = condition["value"]
        if not isinstance(values, list):
            values = [values]
        if not 0 < len(values) <= MAX_VALUES:
            raise CircuitBreakingGroupError(f"condition value must contain between 1 and {MAX_VALUES} entries")
        for value in values:
            if type(value) not in (str, int, float):
                raise CircuitBreakingGroupError("condition values must be strings or finite numbers")
            if isinstance(value, str):
                _text(value, "condition value", MAX_VALUE_LENGTH)
            else:
                try:
                    finite = math.isfinite(value)
                except OverflowError:
                    finite = False
                if not finite:
                    raise CircuitBreakingGroupError("condition values must be finite")
            if method in {"gt", "gte", "lt", "lte"}:
                try:
                    valid_number = math.isfinite(float(value))
                except (ValueError, OverflowError):
                    valid_number = False
                if not valid_number:
                    raise CircuitBreakingGroupError("numeric comparison requires finite numeric values")
            if method in {"reg", "nreg"}:
                try:
                    re.compile(str(value).strip())
                except re.error as error:
                    raise CircuitBreakingGroupError("invalid regular expression") from error
        # Matchers already convert values to strings. Doing it before Lua also
        # avoids cjson rounding numeric identifiers or comparison thresholds.
        result.append({"key": key, "method": method, "value": [str(value) for value in values], "condition": connector})
    try:
        conditions_size = len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except UnicodeEncodeError as error:
        raise CircuitBreakingGroupError("condition values must contain valid UTF-8 text") from error
    if conditions_size > MAX_GROUP_BYTES:
        raise CircuitBreakingGroupError("rule group byte limit exceeded")
    branches.append(branch)
    if any(not any(branch <= context for context in contexts) for branch in branches):
        raise CircuitBreakingGroupError("each AND branch must be evaluable at an existing context")
    matcher = gen_circuit_breaking_matcher(result)
    if matcher is None or matcher.condition_matcher is None:
        raise CircuitBreakingGroupError("conditions cannot be compiled")
    return result


# Bound reads before materializing values or decoding JSON inside Redis.
_BOUNDED_READ_SCRIPT = """
local function bounded_entries(key, max_groups, max_group_bytes, max_module_bytes)
    if redis.call('HLEN', key) > max_groups then return nil end
    local fields, total = redis.call('HKEYS', key), 0
    for _, field in ipairs(fields) do
        if #field ~= 36 then return nil end
        local size = redis.call('HSTRLEN', key, field)
        if size > max_group_bytes then return nil end
        total = total + #field + size
        if total > max_module_bytes then return nil end
    end
    return redis.call('HGETALL', key)
end
"""

# One module is one Redis key. All preconditions are checked before any HDEL,
# HSET or expiry change, including cleanup of logically expired groups.
_MUTATE_SCRIPT = (
    _BOUNDED_READ_SCRIPT
    + """
local key, operation, id = KEYS[1], ARGV[1], ARGV[2]
local expected, patch, delta = tonumber(ARGV[3]), cjson.decode(ARGV[4]), tonumber(ARGV[5])
local max_groups, max_remaining, module = tonumber(ARGV[6]), tonumber(ARGV[7]), ARGV[8]
local max_revision = tonumber(ARGV[9])
local max_group_bytes, max_module_bytes = tonumber(ARGV[10]), tonumber(ARGV[11])
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local entries = bounded_entries(key, max_groups, max_group_bytes, max_module_bytes)
if not entries then return {0, 'corrupt_state', 'stored rule groups exceed byte or count limits'} end
local active, expired, count, current, active_bytes, current_bytes = {}, {}, 0, nil, 0, 0
for i = 1, #entries, 2 do
    local ok, group = pcall(cjson.decode, entries[i + 1])
    if not ok or type(group) ~= 'table' or group.group_id ~= entries[i] or group.module ~= module
        or type(group.expires_at_ms) ~= 'number' or type(group.revision) ~= 'number'
        or group.revision < 1 or group.revision > max_revision or group.revision % 1 ~= 0
        or type(group.created_at_ms) ~= 'number' or type(group.updated_at_ms) ~= 'number'
        or type(group.conditions) ~= 'table' or #group.conditions < 1
        or type(group.reason) ~= 'string' or type(group.operator) ~= 'string' then
        return {0, 'corrupt_state', 'stored rule group is invalid'}
    end
    if group.expires_at_ms > now then
        active[entries[i]], count = group, count + 1
        active_bytes = active_bytes + #entries[i] + #entries[i + 1]
        if entries[i] == id then
            current, current_bytes = group, #entries[i] + #entries[i + 1]
        end
    else
        table.insert(expired, entries[i])
    end
end
if operation == 'create' then
    if current then return {0, 'already_exists', 'group_id already exists'} end
    if count >= max_groups then return {0, 'capacity_exceeded', 'module rule group limit reached'} end
    current = patch
    current.group_id, current.module, current.revision = id, module, 1
    current.created_at_ms, current.updated_at_ms, current.expires_at_ms = now, now, now + delta
else
    if not current then return {0, 'not_found', 'rule group does not exist or has expired'} end
    if current.revision ~= expected then return {0, 'revision_conflict', 'rule group revision changed'} end
    if operation ~= 'revoke' and current.revision >= max_revision then
        return {0, 'revision_conflict', 'rule group revision limit reached'}
    end
    if operation == 'extend' then
        if current.expires_at_ms + delta - now > max_remaining then
            return {0, 'validation_error', 'extended remaining lifetime exceeds the limit'}
        end
        current.expires_at_ms = current.expires_at_ms + delta
    elseif operation == 'update' then
        if patch.conditions then current.conditions = patch.conditions end
        if patch.reason then current.reason = patch.reason end
    elseif operation ~= 'revoke' then
        return {0, 'validation_error', 'unsupported rule group operation'}
    end
    if operation ~= 'revoke' then
        current.revision, current.updated_at_ms, current.operator = current.revision + 1, now, patch.operator
    end
end
local encoded = cjson.encode(current)
local resulting_bytes = active_bytes - current_bytes
if operation ~= 'revoke' then
    if #encoded > max_group_bytes then
        return {0, 'validation_error', 'rule group byte limit exceeded'}
    end
    resulting_bytes = resulting_bytes + #id + #encoded
end
if resulting_bytes > max_module_bytes then
    return {0, 'capacity_exceeded', 'module rule group byte limit exceeded'}
end
local latest = 0
for group_id, group in pairs(active) do
    if group_id ~= id then latest = math.max(latest, group.expires_at_ms) end
end
if operation ~= 'revoke' then latest = math.max(latest, current.expires_at_ms) end
-- No operation after this point can fail a domain precondition.
for _, group_id in ipairs(expired) do redis.call('HDEL', key, group_id) end
if operation == 'revoke' then redis.call('HDEL', key, id)
else redis.call('HSET', key, id, encoded) end
if latest > 0 then redis.call('PEXPIREAT', key, latest) end
return {1, encoded}
"""
)

_SNAPSHOT_SCRIPT = (
    _BOUNDED_READ_SCRIPT
    + """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local entries = bounded_entries(KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3]))
if not entries then return {0, 'corrupt_state', 'stored rule groups exceed byte or count limits'} end
return {now, entries}
"""
)


class CircuitBreakingRuleGroupStore:
    """Independent rule groups; legacy JSON keys and setters remain untouched."""

    def __init__(self, redis_client=None):
        if redis_client is None:
            from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

            redis_client = CircuitBreakingCacheManager.cache
        self.redis = redis_client

    @staticmethod
    def get_cache_key(module: str) -> str:
        _validate_module(module)
        from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager

        return f"{CircuitBreakingCacheManager.CACHE_KEY_PREFIX}.groups.{module}"

    def _eval(self, script, key, *arguments):
        # The cache wrapper retries ConnectionError, which could repeat a write
        # whose reply was lost. Use its current raw client once for this request.
        from alarm_backends.core.storage.redis import BaseRedisCache

        client = self.redis._instance if isinstance(self.redis, BaseRedisCache) else self.redis
        return client.eval(script, 1, key, *arguments)

    def snapshot(self, module: str) -> dict:
        result = self._eval(_SNAPSHOT_SCRIPT, self.get_cache_key(module), MAX_GROUPS, MAX_GROUP_BYTES, MAX_MODULE_BYTES)
        self._raise_script_error(result)
        server_time_ms, entries = result
        groups = []
        for index in range(0, len(entries), 2):
            try:
                group = json.loads(entries[index + 1])
                field = entries[index].decode() if isinstance(entries[index], bytes) else entries[index]
                self._validate_stored_group(module, field, group)
            except (ValueError, TypeError, KeyError, OverflowError) as error:
                raise CircuitBreakingGroupError("stored rule group is invalid", "corrupt_state") from error
            if group["expires_at_ms"] > server_time_ms:
                groups.append(group)
        return {
            "module": module,
            "server_time_ms": server_time_ms,
            "groups": sorted(groups, key=lambda g: g["group_id"]),
        }

    @staticmethod
    def _validate_stored_group(module, field, group):
        if not isinstance(group, dict) or set(group) != {
            "group_id",
            "module",
            "conditions",
            "reason",
            "operator",
            "revision",
            "created_at_ms",
            "updated_at_ms",
            "expires_at_ms",
        }:
            raise CircuitBreakingGroupError("invalid stored group fields")
        if _group_id(group["group_id"]) != field or group["module"] != module:
            raise CircuitBreakingGroupError("stored group identity is inconsistent")
        _positive_integer(group["revision"], "revision", MAX_REVISION)
        for field in ("created_at_ms", "updated_at_ms", "expires_at_ms"):
            _positive_integer(group[field], field, MAX_TIMESTAMP_MS)
        if not group["created_at_ms"] <= group["updated_at_ms"] <= group["expires_at_ms"]:
            raise CircuitBreakingGroupError("stored group deadlines are inconsistent")
        _text(group["reason"], "reason", MAX_REASON_LENGTH)
        _text(group["operator"], "operator", MAX_OPERATOR_LENGTH)
        group["conditions"] = validate_conditions(module, group["conditions"])

    def _mutate(self, operation, module, group_id, expected_revision, patch, seconds=0):
        key = self.get_cache_key(module)
        _group_id(group_id)
        if operation != "create":
            _positive_integer(expected_revision, "expected_revision", MAX_REVISION)
        result = self._eval(
            _MUTATE_SCRIPT,
            key,
            operation,
            group_id,
            expected_revision,
            json.dumps(patch, ensure_ascii=False, allow_nan=False),
            seconds * 1000,
            MAX_GROUPS,
            MAX_TTL_SECONDS * 1000,
            module,
            MAX_REVISION,
            MAX_GROUP_BYTES,
            MAX_MODULE_BYTES,
        )
        self._raise_script_error(result)
        return json.loads(result[1])

    @staticmethod
    def _raise_script_error(result):
        if not result[0]:
            code, message = result[1:]
            if isinstance(code, bytes):
                code, message = code.decode(), message.decode()
            raise CircuitBreakingGroupError(message, code)

    def create(self, module, group_id, conditions, ttl_seconds, reason, operator):
        conditions = validate_conditions(module, conditions)
        _positive_integer(ttl_seconds, "ttl_seconds", MAX_TTL_SECONDS)
        return self._mutate(
            "create",
            module,
            group_id,
            0,
            {
                "conditions": conditions,
                "reason": _text(reason, "reason", MAX_REASON_LENGTH),
                "operator": _text(operator, "operator", MAX_OPERATOR_LENGTH),
            },
            ttl_seconds,
        )

    def update(self, module, group_id, expected_revision, *, conditions=None, reason=None, operator):
        patch = {"operator": _text(operator, "operator", MAX_OPERATOR_LENGTH)}
        if conditions is not None:
            patch["conditions"] = validate_conditions(module, conditions)
        if reason is not None:
            patch["reason"] = _text(reason, "reason", MAX_REASON_LENGTH)
        if len(patch) == 1:
            raise CircuitBreakingGroupError("update requires conditions or reason")
        return self._mutate("update", module, group_id, expected_revision, patch)

    def extend(self, module, group_id, expected_revision, extend_seconds, operator):
        _positive_integer(extend_seconds, "extend_seconds", MAX_TTL_SECONDS)
        return self._mutate(
            "extend",
            module,
            group_id,
            expected_revision,
            {"operator": _text(operator, "operator", MAX_OPERATOR_LENGTH)},
            extend_seconds,
        )

    def revoke(self, module, group_id, expected_revision, operator):
        return self._mutate(
            "revoke",
            module,
            group_id,
            expected_revision,
            {"operator": _text(operator, "operator", MAX_OPERATOR_LENGTH)},
        )
