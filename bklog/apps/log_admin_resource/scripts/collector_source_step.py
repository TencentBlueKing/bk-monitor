"""Fixed Linux collector probe. Keep compatible with Python 2.7 in CentOS collector images."""

# ruff: noqa: UP024, UP031 -- the deployed helper also runs on Python 2.7

import base64
import datetime
import errno
import fnmatch
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time


def parts(path):
    return [part for part in path.split("/") if part]


def matches(path, patterns, ancestors=False):
    # The server expands recursive globs up to the collector's configured depth.
    names = parts(path)
    for pattern in patterns:
        globs = parts(pattern)
        if len(names) == len(globs) or (ancestors and len(names) < len(globs)):
            if all(fnmatch.fnmatchcase(name, glob) for name, glob in zip(names, globs)):
                return True
    return False


def inside(path, directory):
    return path == directory or path.startswith(directory.rstrip("/") + "/")


def descend(name):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchdir(fd)
    finally:
        os.close(fd)


def open_parent(path, policy, follow_leaf, reading_content):
    # cwd is private to this short-lived helper. Pin each directory before inspecting its
    # children. Never ask the collector kernel to follow a business-container symlink.
    links = []
    boundary = None
    original = path
    source_leaf = reading_content and matches(original, policy["patterns"])
    while len(links) <= 32:
        base = max((key for key in policy["mounts"] if inside(path, key)), key=len)
        root = policy["mounts"][base]
        if not root:
            raise ValueError("mount_unavailable_or_outside_scope")
        os.chdir("/")
        root_parts = parts(root)
        for index, name in enumerate(root_parts):
            if path == base and index == len(root_parts) - 1 and stat.S_ISREG(os.lstat(name).st_mode):
                return name, base, links
            descend(name)
        tail = parts(path[len(base) :])
        parent = base
        for index, name in enumerate(tail):
            last = index == len(tail) - 1
            logical = os.path.join(parent, name)
            if last and not follow_leaf:
                return name, logical, links
            if stat.S_ISLNK(os.lstat(name).st_mode):
                target = os.readlink(name)
                target_path = os.path.normpath(os.path.join(parent, target))
                path = os.path.join(target_path, *tail[index + 1 :])
                if boundary is not None and not inside(path, boundary):
                    raise ValueError("link_outside_source_directory")
                if last and source_leaf and not matches(path, policy["patterns"]):
                    # When moving into a data mount retain the configured filename constraint.
                    renamed = os.path.join(os.path.dirname(original), os.path.basename(path))
                    if not matches(renamed, policy["patterns"]):
                        raise ValueError("link_target_outside_configured_sources")
                if reading_content and not matches(path, policy["patterns"], ancestors=True):
                    volumes = [key for key in policy["mounts"] if key != "/" and inside(target_path, key)]
                    if not volumes or not policy["mounts"][max(volumes, key=len)]:
                        raise ValueError("link_target_outside_allowed_volume")
                    boundary = boundary or target_path
                links.append({"path": logical, "target": target})
                break
            if last:
                return name, logical, links
            descend(name)
            parent = logical
        else:
            return ".", base, links
    raise ValueError("too_many_symlinks")


def timestamp(seconds):
    return datetime.datetime.utcfromtimestamp(seconds).isoformat() + "Z"


def reader_positions(pid, info):
    # fdinfo.pos is a kernel read cursor. A registrar checkpoint can trail it until ACK/flush.
    # Multiple handles can belong to different inputs. Keep the ambiguity visible.
    if not pid:
        return None
    root = "/proc/%d" % pid
    try:
        if os.path.basename(os.readlink(root + "/exe")).split(" ")[0] != "bkunifylogbeat":
            return None
        entries = os.listdir(root + "/fd")
        if len(entries) > 4096:
            return None
        positions = []
        for fd in entries:
            path = root + "/fd/" + fd
            try:
                identity = os.stat(path)
                if (identity.st_dev, identity.st_ino) != (info.st_dev, info.st_ino):
                    continue
                with open(root + "/fdinfo/" + fd) as stream:
                    fields = dict(line.strip().split(":", 1) for line in stream if ":" in line)
                again = os.stat(path)
                if (again.st_dev, again.st_ino) != (identity.st_dev, identity.st_ino):
                    return None
                flags = int(fields["flags"], 8)
                if not flags & getattr(os, "O_PATH", 0o10000000) and flags & os.O_ACCMODE == os.O_RDONLY:
                    positions.append(int(fields["pos"]))
            except OSError as error:
                if error.errno != errno.ENOENT:
                    raise
        return positions
    except (OSError, IOError, KeyError, ValueError):
        return None


def target_source_path(policy, request):
    path, operation = request["path"], request["operation"]
    reading_content = operation == "read"
    if request.get("via"):
        via = request["via"]
        if reading_content and not matches(via, policy["patterns"], ancestors=True):
            raise ValueError("source_anchor_outside_configured_paths")
        _, anchor, hops = open_parent(via, policy, True, reading_content)
        if not hops or not inside(path, anchor):
            raise ValueError("path_outside_source_anchor")
        path = os.path.normpath(os.path.join(via, os.path.relpath(path, anchor)))
    if reading_content and not matches(path, policy["patterns"]):
        raise ValueError("source_outside_configured_paths")
    name, resolved, links = open_parent(path, policy, operation != "readlink", reading_content)

    collector_path = os.path.normpath(os.path.join(os.getcwd(), name))
    if reading_content and any(
        re.search(rule, value) for rule in policy.get("exclude", []) for value in (path, resolved, collector_path)
    ):
        raise ValueError("source_excluded_by_input")
    return name, path, resolved, links, collector_path


def snapshot(policy, request):
    path, operation = request["path"], request["operation"]
    native = request.get("path_space") == "collector"
    if native:
        if operation not in ("list", "readlink", "stat") or "via" in request:
            raise ValueError("collector_paths_support_metadata_only")
        # Keep the original path for follow-ups. Kernel magic links may have no equivalent
        # canonical pathname (for instance a mounted process root or a deleted file).
        name = collector_path = path
        info = os.lstat(path) if operation == "readlink" else os.stat(path)
    else:
        name, path, resolved, links, collector_path = target_source_path(policy, request)
        info = os.lstat(name)
    result = {
        "path": path,
        "path_space": "collector" if native else "target",
        "collector_path": collector_path,
        "sampled_at": timestamp(time.time()),
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": info.st_mode,
        "size_bytes": info.st_size,
        "mtime": timestamp(info.st_mtime),
        "mtime_epoch": info.st_mtime,
    }
    if not native:
        result.update(resolved_path=resolved, links=links)
    if operation == "readlink":
        result["target"] = os.readlink(name)
    elif operation == "list":
        if not native:
            descend(name)
        # Include every observed name so a misconfigured pattern can be diagnosed.
        find = "/usr/bin/find" if os.path.isfile("/usr/bin/find") else "/bin/find"
        proc = subprocess.Popen(
            [find, ".", "-mindepth", "1", "-maxdepth", "1", "-print0"],
            cwd=path if native else None,
            stdout=subprocess.PIPE,
        )
        try:
            raw = proc.stdout.read(65537)
        finally:
            proc.stdout.close()
            rc = proc.wait()
        truncated = len(raw) > 65536
        if rc and not truncated:
            raise ValueError("directory_listing_failed")
        names = [line[2:].decode("utf-8", "replace") for line in raw[:65536].split(b"\0")[:-1]]
        children = sorted(os.path.join(path, child) for child in names)
        result.update(entries=children[:50], truncated=truncated or len(children) > 50)
    elif operation == "read":
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("source_not_regular")
        # Pin the inode with O_PATH before opening it for I/O. A swapped link/device cannot
        # redirect the read. Linux exposes O_PATH even on older Python builds without the constant.
        pinned = os.open(name, getattr(os, "O_PATH", 0o10000000) | os.O_NOFOLLOW)
        try:
            bound = os.fstat(pinned)
            if not stat.S_ISREG(bound.st_mode) or (bound.st_dev, bound.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError("source_changed_before_read")
            with open("/proc/self/fd/%d" % pinned, "rb") as stream:
                offset = request.get("offset", 0)
                stream.seek(offset)
                data = stream.read(request.get("length", 1024))
            result.update(offset=offset, returned_bytes=len(data), content=data.decode("utf-8", "replace"))
        finally:
            os.close(pinned)
    elif operation == "stat" and stat.S_ISREG(info.st_mode):
        result["collector_read_positions"] = reader_positions(policy["pid"], info)
    return result


def inspect_source(policy, request):
    first = snapshot(policy, request)
    if request["operation"] != "stat" or "collector_read_positions" not in first:
        return {"observation": first}
    time.sleep(policy["interval"])
    try:
        second = snapshot(policy, request)
    except (OSError, IOError, ValueError) as error:
        return {"first": first, "activity": "second_sample_unavailable", "error": str(error)}
    growth = second["size_bytes"] - first["size_bytes"]
    result = {"first": first, "second": second, "reader_scope": "collector_process", "data_id_attribution": "unknown"}
    if (first["device"], first["inode"]) != (second["device"], second["inode"]):
        result["activity"] = "replaced"
    elif growth < 0:
        result["activity"] = "truncated"
    elif not growth:
        result["activity"] = "modified_same_size" if first["mtime"] != second["mtime"] else "no_growth_observed"
    else:
        result.update(activity="grew", growth_bytes=growth, read_progress="unknown")
        positions = second.get("collector_read_positions")
        if positions and len(positions) == 1 and 0 <= positions[0] <= second["size_bytes"]:
            lag = second["size_bytes"] - positions[0]
            result.update(read_progress="open_reader_behind" if lag else "open_reader_at_eof", unread_bytes=lag)
    return result


if __name__ == "__main__":
    signal.alarm(20)
    policy, request = json.loads(base64.b64decode(sys.argv[1]))
    try:
        print(json.dumps(inspect_source(policy, request)))
    except (OSError, IOError, ValueError) as error:
        print(json.dumps({"error": str(error), "errno": getattr(error, "errno", None)}))
