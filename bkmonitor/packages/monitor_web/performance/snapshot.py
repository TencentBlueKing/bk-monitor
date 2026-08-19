"""Shared Redis state for progressive host metric snapshots."""

import hashlib
import json
import time
import zlib
from dataclasses import dataclass
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches


CACHE_ALIAS = "redis"
LIVE_END_TOLERANCE = 300
LIVE_TIME_BUCKET = 60
RESERVATION_TTL = 15
RUNNING_TTL = 120
READY_TTL = 120
SECTION_TTL = 180
FAILED_TTL = 15
SNAPSHOT_DEADLINE = 60
SNAPSHOT_SECTIONS = ("agent_status", "performance_data", "process_status", "alarm_count")

CLAIM_SNAPSHOT_SCRIPT = """
-- host-metric-snapshot-claim
local current = redis.call('get', KEYS[1])
if current then
    return {current, 0}
end
redis.call('zremrangebyscore', KEYS[2], '-inf', ARGV[1])
if redis.call('zcard', KEYS[2]) >= tonumber(ARGV[3]) then
    return {'', -1}
end
redis.call('set', KEYS[1], ARGV[4], 'EX', ARGV[5])
redis.call('zadd', KEYS[2], ARGV[2], ARGV[4])
redis.call('expire', KEYS[2], ARGV[6])
return {ARGV[4], 1}
"""
RENEW_CAPACITY_SCRIPT = """
-- host-metric-snapshot-renew
if redis.call('get', KEYS[1]) ~= ARGV[1] then
    return 0
end
local score = redis.call('zscore', KEYS[2], ARGV[1])
if not score or tonumber(score) <= tonumber(ARGV[2]) then
    return 0
end
redis.call('expire', KEYS[1], ARGV[4])
redis.call('zadd', KEYS[2], ARGV[3], ARGV[1])
redis.call('expire', KEYS[2], ARGV[4])
return 1
"""
RELEASE_CAPACITY_SCRIPT = """
-- host-metric-snapshot-terminal-claim
local score = redis.call('zscore', KEYS[1], ARGV[1])
if not score then
    return 0
end
if tonumber(score) <= tonumber(ARGV[2]) or tonumber(ARGV[3]) < tonumber(ARGV[2]) then
    redis.call('zrem', KEYS[1], ARGV[1])
    return -1
end
return redis.call('zrem', KEYS[1], ARGV[1])
"""
DELETE_POINTER_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""
TOUCH_POINTER_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


class SnapshotState:
    RUNNING = "RUNNING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    UNAVAILABLE = "UNAVAILABLE"


class SnapshotUnavailable(RuntimeError):
    pass


class SnapshotCapacityExceeded(SnapshotUnavailable):
    pass


@dataclass(frozen=True)
class CanonicalSnapshotTime:
    start_time: int
    end_time: int
    time_key: dict


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def build_host_ids_hash(host_ids) -> str:
    normalized = ",".join(str(host_id) for host_id in sorted({int(host_id) for host_id in host_ids}))
    return hashlib.sha256(normalized.encode()).hexdigest()


def canonicalize_snapshot_time(
    start_time: int,
    end_time: int,
    *,
    now: int | None = None,
    is_share: bool,
) -> CanonicalSnapshotTime:
    start_time = int(start_time)
    end_time = int(end_time)
    if end_time <= start_time:
        raise ValueError("end_time must be greater than start_time")

    now = int(time.time()) if now is None else int(now)
    if not is_share and abs(now - end_time) <= LIVE_END_TOLERANCE:
        duration = end_time - start_time
        end_time = end_time // LIVE_TIME_BUCKET * LIVE_TIME_BUCKET
        start_time = end_time - duration
        time_key = {"end_time": end_time, "mode": "live", "start_time": start_time}
    else:
        time_key = {"end_time": end_time, "mode": "historical", "start_time": start_time}
    return CanonicalSnapshotTime(start_time=start_time, end_time=end_time, time_key=time_key)


def build_snapshot_fingerprint(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    scope: dict,
    time_key: dict,
) -> str:
    payload = {
        "bk_biz_id": int(bk_biz_id),
        "bk_tenant_id": bk_tenant_id,
        "scope": scope,
        "time": time_key,
    }
    return _sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())


class HostMetricSnapshotStore:
    key_prefix = "host_metric_snapshot:v1"

    def __init__(self, cache=None):
        if cache is None:
            try:
                cache = caches[CACHE_ALIAS]
            except Exception as error:
                raise SnapshotUnavailable("shared Redis cache is unavailable") from error
        self.cache = cache
        try:
            self.redis = cache.client.get_client(write=True)
        except Exception as error:
            raise SnapshotUnavailable("shared Redis client is unavailable") from error

    @classmethod
    def pointer_key(cls, fingerprint: str) -> str:
        return f"{cls.key_prefix}:pointer:{fingerprint}"

    @classmethod
    def manifest_key(cls, snapshot_id: str) -> str:
        return f"{cls.key_prefix}:manifest:{snapshot_id}"

    @classmethod
    def section_key(cls, snapshot_id: str, section: str) -> str:
        return f"{cls.key_prefix}:section:{snapshot_id}:{section}"

    @classmethod
    def repair_lock_key(cls, fingerprint: str) -> str:
        return f"{cls.key_prefix}:repair:{fingerprint}"

    @classmethod
    def capacity_lease_key(cls, *, bk_tenant_id: str, bk_biz_id: int) -> str:
        identity = json.dumps(
            {"bk_biz_id": int(bk_biz_id), "bk_tenant_id": bk_tenant_id},
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"{cls.key_prefix}:capacity:{hashlib.sha256(identity.encode()).hexdigest()}"

    def _get(self, key, default=None):
        try:
            return self.cache.get(key, default)
        except Exception as error:
            raise SnapshotUnavailable("shared Redis cache read failed") from error

    def _set(self, key, value, timeout):
        try:
            self.cache.set(key, value, timeout=timeout)
        except Exception as error:
            raise SnapshotUnavailable("shared Redis cache write failed") from error

    def _raw_key(self, key: str) -> str:
        try:
            return self.cache.make_key(key)
        except Exception as error:
            raise SnapshotUnavailable("shared Redis key generation failed") from error

    @staticmethod
    def _decode_redis_value(value):
        return value.decode() if isinstance(value, bytes) else value

    def _get_pointer(self, fingerprint: str) -> str | None:
        try:
            value = self.redis.get(self._raw_key(self.pointer_key(fingerprint)))
        except Exception as error:
            raise SnapshotUnavailable("shared Redis pointer read failed") from error
        return self._decode_redis_value(value) if value else None

    def _claim_snapshot(self, fingerprint: str, payload: dict, snapshot_id: str) -> tuple[str, int]:
        lease_key = self._raw_key(
            self.capacity_lease_key(
                bk_tenant_id=payload["bk_tenant_id"],
                bk_biz_id=payload["bk_biz_id"],
            )
        )
        pointer_key = self._raw_key(self.pointer_key(fingerprint))
        now = int(time.time())
        try:
            claimed_snapshot_id, claim_status = self.redis.eval(
                CLAIM_SNAPSHOT_SCRIPT,
                2,
                pointer_key,
                lease_key,
                now,
                now + RESERVATION_TTL,
                settings.HOST_METRIC_SNAPSHOT_MAX_CONCURRENT_PER_BIZ,
                snapshot_id,
                RESERVATION_TTL,
                RUNNING_TTL,
            )
        except Exception as error:
            raise SnapshotUnavailable("shared Redis snapshot claim failed") from error
        return self._decode_redis_value(claimed_snapshot_id), int(claim_status)

    def renew_capacity(self, manifest: dict, *, now: int | None = None) -> bool:
        now = time.time() if now is None else now
        try:
            return bool(
                self.redis.eval(
                    RENEW_CAPACITY_SCRIPT,
                    2,
                    self._raw_key(self.pointer_key(manifest["fingerprint"])),
                    manifest["capacity_lease_key"],
                    manifest["snapshot_id"],
                    now,
                    now + RUNNING_TTL,
                    RUNNING_TTL,
                )
            )
        except Exception as error:
            raise SnapshotUnavailable("shared Redis capacity renewal failed") from error

    def _delete_pointer(self, fingerprint: str, snapshot_id: str):
        try:
            self.redis.eval(
                DELETE_POINTER_SCRIPT,
                1,
                self._raw_key(self.pointer_key(fingerprint)),
                snapshot_id,
            )
        except Exception as error:
            raise SnapshotUnavailable("shared Redis pointer delete failed") from error

    def _touch_pointer(self, manifest: dict, timeout: int):
        try:
            self.redis.eval(
                TOUCH_POINTER_SCRIPT,
                1,
                self._raw_key(self.pointer_key(manifest["fingerprint"])),
                manifest["snapshot_id"],
                timeout,
            )
        except Exception as error:
            raise SnapshotUnavailable("shared Redis pointer touch failed") from error

    def _capacity_lease_key(self, payload: dict) -> str:
        return self._raw_key(
            self.capacity_lease_key(
                bk_tenant_id=payload["bk_tenant_id"],
                bk_biz_id=payload["bk_biz_id"],
            )
        )

    def owns_capacity(self, manifest: dict, *, now: int | None = None) -> bool:
        lease_key = manifest.get("capacity_lease_key")
        if not lease_key:
            return False
        try:
            expires_at = self.redis.zscore(lease_key, manifest["snapshot_id"])
        except Exception as error:
            raise SnapshotUnavailable("shared Redis capacity lease read failed") from error
        return expires_at is not None and float(expires_at) > (time.time() if now is None else now)

    def _claim_terminal(self, manifest: dict) -> int:
        lease_key = manifest.get("capacity_lease_key")
        if not lease_key:
            return 0
        try:
            return int(
                self.redis.eval(
                    RELEASE_CAPACITY_SCRIPT,
                    1,
                    lease_key,
                    manifest["snapshot_id"],
                    time.time(),
                    manifest["deadline_at"],
                )
            )
        except Exception as error:
            raise SnapshotUnavailable("shared Redis capacity release failed") from error

    def _force_expired_if_running(self, snapshot_id: str) -> dict | None:
        manifest = self.get_manifest(snapshot_id)
        if not manifest or manifest["state"] != SnapshotState.RUNNING:
            return manifest
        manifest["state"] = SnapshotState.EXPIRED
        self._set(self.manifest_key(snapshot_id), manifest, FAILED_TTL)
        self._touch_pointer(manifest, FAILED_TTL)
        return manifest

    def create_or_get(self, fingerprint: str, payload: dict) -> tuple[dict, bool]:
        current_snapshot_id = self._get_pointer(fingerprint)
        if current_snapshot_id:
            current = self.get_manifest(current_snapshot_id)
            if current:
                if current["state"] not in {SnapshotState.FAILED, SnapshotState.EXPIRED}:
                    return current, False
                self._delete_pointer(fingerprint, current_snapshot_id)
            else:
                repair_lock_key = self.repair_lock_key(fingerprint)
                try:
                    has_repair_lock = self.cache.add(repair_lock_key, True, timeout=5)
                except Exception as error:
                    raise SnapshotUnavailable("shared Redis singleflight repair failed") from error
                if has_repair_lock:
                    try:
                        if self._get_pointer(fingerprint) == current_snapshot_id and not self.get_manifest(
                            current_snapshot_id
                        ):
                            self._delete_pointer(fingerprint, current_snapshot_id)
                    except Exception as error:
                        raise SnapshotUnavailable("shared Redis stale pointer repair failed") from error
                    finally:
                        try:
                            self.cache.delete(repair_lock_key)
                        except Exception:
                            pass

        snapshot_id = uuid4().hex
        manifest = {
            **payload,
            "capacity_lease_key": self._capacity_lease_key(payload),
            "fingerprint": fingerprint,
            "revision": 0,
            "snapshot_id": snapshot_id,
            "state": SnapshotState.RUNNING,
        }
        self._set(self.manifest_key(snapshot_id), manifest, RUNNING_TTL)
        try:
            claimed_snapshot_id, claim_status = self._claim_snapshot(fingerprint, payload, snapshot_id)
        except Exception:
            self.cache.delete(self.manifest_key(snapshot_id))
            raise
        if claim_status == 1:
            return manifest, True

        self.cache.delete(self.manifest_key(snapshot_id))
        if claim_status == -1:
            raise SnapshotCapacityExceeded("host metric snapshot capacity exceeded")
        current = self.get_manifest(claimed_snapshot_id)
        if not current:
            raise SnapshotUnavailable("shared Redis singleflight manifest is unavailable")
        return current, False

    def get_current(self, fingerprint: str) -> dict | None:
        snapshot_id = self._get_pointer(fingerprint)
        return self.get_manifest(snapshot_id) if snapshot_id else None

    def get_manifest(self, snapshot_id: str) -> dict | None:
        return self._get(self.manifest_key(snapshot_id))

    def update_manifest(self, snapshot_id: str, **changes) -> dict | None:
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return None
        if "state" in changes and changes["state"] != manifest["state"]:
            raise ValueError("snapshot state transitions require a terminal capacity claim")
        if manifest["state"] != SnapshotState.RUNNING or not self.owns_capacity(manifest):
            return manifest
        manifest.update(changes)
        self._set(self.manifest_key(snapshot_id), manifest, RUNNING_TTL)
        if not self.owns_capacity(manifest):
            return self._force_expired_if_running(snapshot_id)
        return manifest

    def write_section(self, snapshot_id: str, section: str, data: dict):
        encoded = zlib.compress(json.dumps(data, separators=(",", ":"), sort_keys=True).encode())
        self._set(self.section_key(snapshot_id, section), encoded, SECTION_TTL)

    def mark_section_ready(self, snapshot_id: str, section: str, *, state: str = SnapshotState.READY) -> dict | None:
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return None
        revision = int(manifest.get("revision", 0)) + 1
        sections = dict(manifest.get("sections", {}))
        if state not in {SnapshotState.READY, SnapshotState.PARTIAL}:
            raise ValueError("invalid available section state")
        sections[section] = {"revision": revision, "state": state}
        return self.update_manifest(snapshot_id, revision=revision, sections=sections)

    def mark_ready(self, snapshot_id: str, *, expected_sections: set[str]) -> dict | None:
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return None
        ready_sections = {
            section
            for section, section_state in manifest.get("sections", {}).items()
            if section_state.get("state") == SnapshotState.READY
        }
        if ready_sections != expected_sections:
            raise ValueError("incomplete sections")
        terminal_claim = self._claim_terminal(manifest) if manifest["state"] == SnapshotState.RUNNING else 0
        if terminal_claim != 1:
            if terminal_claim == -1:
                return self.mark_deadline(snapshot_id, terminal_claimed=True)
            return self.get_manifest(snapshot_id)
        manifest = self.get_manifest(snapshot_id)
        if not manifest or manifest["state"] != SnapshotState.RUNNING:
            return manifest
        manifest["state"] = SnapshotState.READY
        self._set(self.manifest_key(snapshot_id), manifest, READY_TTL)
        self._touch_pointer(manifest, READY_TTL)
        return manifest

    def mark_degraded(
        self,
        snapshot_id: str,
        *,
        failed_sections: list[str],
        partial_sections: list[str] | None = None,
    ) -> dict | None:
        """结束不完整快照，同时保留已经成功发布的分区。"""
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return None
        ready_sections = {
            section
            for section, section_state in manifest.get("sections", {}).items()
            if section_state.get("state") in {SnapshotState.READY, SnapshotState.PARTIAL}
        }
        if not ready_sections:
            self.fail(snapshot_id, "section_failed", failed_sections=sorted(set(failed_sections)))
            return self.get_manifest(snapshot_id)
        terminal_claim = self._claim_terminal(manifest) if manifest["state"] == SnapshotState.RUNNING else 0
        if manifest["state"] == SnapshotState.RUNNING and terminal_claim != 1:
            if terminal_claim == -1:
                return self.mark_deadline(snapshot_id, terminal_claimed=True)
            return self.get_manifest(snapshot_id)
        manifest = self.get_manifest(snapshot_id)
        if not manifest or manifest["state"] not in {
            SnapshotState.RUNNING,
            SnapshotState.READY,
            SnapshotState.DEGRADED,
        }:
            return manifest
        sections = dict(manifest.get("sections", {}))
        for section in failed_sections:
            sections[section] = {"state": SnapshotState.FAILED}
        manifest.update(
            {
                "error_code": "section_failed",
                "failed_sections": sorted(set(manifest.get("failed_sections", [])) | set(failed_sections)),
                "partial_sections": sorted(set(manifest.get("partial_sections", [])) | set(partial_sections or [])),
                "sections": sections,
                "state": SnapshotState.DEGRADED,
            }
        )
        self._set(self.manifest_key(snapshot_id), manifest, READY_TTL)
        self._touch_pointer(manifest, READY_TTL)
        return manifest

    def mark_deadline(self, snapshot_id: str, *, terminal_claimed: bool = False) -> dict | None:
        """结束超时快照；有已发布分区时保留数据并降级，否则过期。"""
        manifest = self.get_manifest(snapshot_id)
        if not manifest or manifest["state"] != SnapshotState.RUNNING:
            return manifest
        if not terminal_claimed:
            terminal_claim = self._claim_terminal(manifest)
            if terminal_claim == 0:
                return self.get_manifest(snapshot_id)
        manifest = self.get_manifest(snapshot_id)
        if not manifest or manifest["state"] != SnapshotState.RUNNING:
            return manifest

        sections = dict(manifest.get("sections", {}))
        available_sections = {
            section
            for section, section_state in sections.items()
            if section_state.get("state") in {SnapshotState.READY, SnapshotState.PARTIAL}
        }
        if not available_sections:
            return self._force_expired_if_running(snapshot_id)

        failed_sections = sorted(set(SNAPSHOT_SECTIONS) - available_sections)
        partial_sections = sorted(
            section
            for section, section_state in sections.items()
            if section_state.get("state") == SnapshotState.PARTIAL
        )
        for section in failed_sections:
            sections[section] = {"state": SnapshotState.FAILED}
        manifest.update(
            {
                "error_code": "deadline_exceeded",
                "failed_sections": failed_sections,
                "partial_sections": partial_sections,
                "sections": sections,
                "state": SnapshotState.DEGRADED,
            }
        )
        self._set(self.manifest_key(snapshot_id), manifest, READY_TTL)
        self._touch_pointer(manifest, READY_TTL)
        return manifest

    def read_section(self, snapshot_id: str, section: str) -> dict | None:
        encoded = self._get(self.section_key(snapshot_id, section))
        if encoded is None:
            return None
        data = json.loads(zlib.decompress(encoded))
        return {int(key) if key.isdigit() else key: value for key, value in data.items()}

    def fail(
        self,
        snapshot_id: str,
        error_code: str,
        *,
        failed_sections: list[str] | None = None,
        allow_ready: bool = False,
    ):
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return
        if manifest["state"] == SnapshotState.RUNNING:
            terminal_claim = self._claim_terminal(manifest)
            if terminal_claim != 1:
                if terminal_claim == -1:
                    self.mark_deadline(snapshot_id, terminal_claimed=True)
                return
        elif manifest["state"] not in {SnapshotState.READY, SnapshotState.DEGRADED} or not allow_ready:
            return
        manifest.update(
            {
                "error_code": error_code,
                "failed_sections": failed_sections or [],
                "state": SnapshotState.FAILED,
            }
        )
        self._set(self.manifest_key(snapshot_id), manifest, FAILED_TTL)
        self._touch_pointer(manifest, FAILED_TTL)

    def expire(self, snapshot_id: str, *, allow_ready: bool = True):
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return
        if manifest["state"] == SnapshotState.RUNNING:
            terminal_claim = self._claim_terminal(manifest)
            if terminal_claim != 1:
                if terminal_claim == -1:
                    self._force_expired_if_running(snapshot_id)
                return
        elif manifest["state"] not in {SnapshotState.READY, SnapshotState.DEGRADED} or not allow_ready:
            return
        manifest["state"] = SnapshotState.EXPIRED
        self._set(self.manifest_key(snapshot_id), manifest, FAILED_TTL)
        self._touch_pointer(manifest, FAILED_TTL)

    def build_response(
        self,
        snapshot_id: str,
        *,
        since_revision: int = 0,
        now: int | None = None,
        include_data: bool = True,
    ) -> dict:
        manifest = self.get_manifest(snapshot_id)
        if not manifest:
            return {
                "data": {},
                "expired": True,
                "failed_sections": [],
                "retry_after": 0,
                "snapshot_id": snapshot_id,
                "state": SnapshotState.EXPIRED,
            }

        now = int(time.time()) if now is None else int(now)
        if manifest["state"] == SnapshotState.RUNNING and now > int(manifest["deadline_at"]):
            self.mark_deadline(snapshot_id)
            manifest = self.get_manifest(snapshot_id)

        response = {
            key: manifest[key]
            for key in (
                "canonical_end_time",
                "canonical_start_time",
                "host_count",
                "host_ids_hash",
                "revision",
                "sections",
                "snapshot_id",
                "state",
            )
            if key in manifest
        }
        response["data"] = {}
        response["expired"] = manifest["state"] == SnapshotState.EXPIRED
        response["failed_sections"] = manifest.get("failed_sections", [])
        response["partial_sections"] = manifest.get("partial_sections", [])
        if manifest["state"] == SnapshotState.RUNNING:
            response["retry_after"] = 1
        elif manifest["state"] in {SnapshotState.DEGRADED, SnapshotState.FAILED, SnapshotState.EXPIRED}:
            response["retry_after"] = 5
        else:
            response["retry_after"] = 0
        if manifest["state"] not in {SnapshotState.RUNNING, SnapshotState.READY, SnapshotState.DEGRADED}:
            return response
        if not include_data:
            return response

        broken_sections = []
        for section, section_state in manifest.get("sections", {}).items():
            if section_state.get("state") not in {SnapshotState.READY, SnapshotState.PARTIAL}:
                continue
            if int(section_state.get("revision", 0)) <= since_revision:
                continue
            try:
                data = self.read_section(snapshot_id, section)
            except SnapshotUnavailable:
                raise
            except Exception:
                broken_sections.append(section)
                continue
            if data is None:
                broken_sections.append(section)
                continue
            response["data"][section] = data
        if broken_sections:
            available_sections = {
                section
                for section, section_state in manifest.get("sections", {}).items()
                if section_state.get("state") in {SnapshotState.READY, SnapshotState.PARTIAL}
            }
            if response["data"] or available_sections.difference(broken_sections):
                manifest = self.mark_degraded(snapshot_id, failed_sections=broken_sections)
                response.update(
                    failed_sections=manifest.get("failed_sections", broken_sections),
                    retry_after=5,
                    sections=manifest.get("sections", {}),
                    state=SnapshotState.DEGRADED,
                )
            else:
                error_code = "section_corrupt"
                for section in broken_sections:
                    if self._get(self.section_key(snapshot_id, section)) is None:
                        error_code = "section_missing"
                        break
                self.fail(snapshot_id, error_code, failed_sections=broken_sections, allow_ready=True)
                response.update(
                    data={},
                    failed_sections=broken_sections,
                    retry_after=5,
                    state=SnapshotState.FAILED,
                )
        return response
