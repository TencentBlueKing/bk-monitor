"""Decode the fixed shell probe's byte-preserving directory and symlink observations."""

import base64
import os
import re
import stat
from types import SimpleNamespace

from apps.log_admin_resource.scripts.collector_source_step import identity_guard, timestamp


def _metadata(metadata):
    fields, mtime, ctime = metadata.split("|")
    device, inode, mode, size, mtime_s, ctime_s = fields.split()

    def epoch_ns(seconds, formatted):
        fraction = re.search(r"\.(\d{9}) [+-]\d{4}$", formatted)
        if not fraction:
            raise ValueError("invalid_source_timestamp")
        return int(seconds) * 10**9 + int(fraction[1])

    mtime_ns = epoch_ns(mtime_s, mtime)
    ctime_ns = epoch_ns(ctime_s, ctime)
    return SimpleNamespace(
        st_mode=int(mode, 16),
        st_dev=int(device),
        st_ino=int(inode),
        st_size=int(size),
        st_mtime_ns=mtime_ns,
        st_ctime_ns=ctime_ns,
        st_mtime=int(mtime_s) + (mtime_ns % 10**9) / 10**9,
        st_ctime=int(ctime_s) + (ctime_ns % 10**9) / 10**9,
    )


def _guard(kind, policy, path, info, precision):
    if precision == "float":
        info = SimpleNamespace(**{k: v for k, v in vars(info).items() if not k.endswith("_ns")})
    return identity_guard(kind, policy, "collector", path, info)


def decode_directory_step(output, policy, request, sampled_at):
    path = request["path"]
    if "expect" in request:
        parent, output = output.split("\n", 1)
        parent_info = _metadata(parent)
        if request["expect"] not in {_guard("parent", policy, path, parent_info, p) for p in ("float", "ns")}:
            return {"error": "source_parent_identity_changed", "failed_path": path}
    if output.rstrip("\n") == "stat_unavailable":
        return {"error": "stat_unavailable", "failed_path": path}
    metadata, payload = output.split("\n", 1)
    info = _metadata(metadata)
    row = {
        "path": path,
        "collector_path": path,
        "path_space": "collector",
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": info.st_mode,
        "size_bytes": info.st_size,
        "sampled_at": sampled_at,
        "mtime_epoch": info.st_mtime_ns / 10**9,
        "mtime": timestamp(info.st_mtime_ns / 10**9),
    }
    if "expect" in request:
        row["verified_expectation"] = request["expect"]
    if request["operation"] == "stat":
        row["mtime_epoch_ns"] = str(info.st_mtime_ns)
        if payload.strip():
            raise ValueError("invalid_stat_response")
        result = {"observation": row}
        if stat.S_ISREG(info.st_mode) and "expect" in request:
            # The pinned sampler uses the timestamp representation of its own
            # runtime. Both expectations describe the same observed directory.
            result["parent_guards"] = {p: _guard("parent", policy, path, parent_info, p) for p in ("ns", "float")}
        return result
    raw = base64.b64decode("".join(payload.splitlines()), validate=True)
    if request["operation"] == "readlink":
        if not raw.endswith(b"\0") or b"\0" in raw[:-1] or not raw[:-1]:
            raise ValueError("readlink_incomplete")
        try:
            row["target"] = raw[:-1].decode("utf-8")
        except UnicodeDecodeError:
            return {"error": "non_utf8_link_target_hex=" + raw[:-1].hex(), "failed_path": path}
        row["follow_path"] = path
    else:
        truncated = len(raw) > 65536
        if not truncated and not (raw == b"\0" or raw.endswith(b"\0\0")):
            raise ValueError("directory_listing_incomplete")
        records = raw[:65536].split(b"\0")[:-1]
        names = []
        for entry in records:
            if not entry:
                continue
            if not entry.startswith(b"./") or b"/" in entry[2:] or not entry[2:]:
                raise ValueError("invalid_directory_entry")
            names.append(entry[2:])
        entries, non_utf8 = [], []
        for name in sorted(names)[:50]:
            try:
                entries.append(os.path.join(path, name.decode("utf-8")))
            except UnicodeDecodeError:
                non_utf8.append(name.hex())
        row.update(
            entries=entries,
            entry_guards=[identity_guard("parent", policy, "collector", entry, info) for entry in entries],
            directory_identity_verified=True,
            truncated=truncated or len(names) > 50,
        )
        if non_utf8:
            row["non_utf8_names_hex"] = non_utf8
    return {"observation": row}
