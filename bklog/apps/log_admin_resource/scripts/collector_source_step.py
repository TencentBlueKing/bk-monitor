"""Fixed Linux collector probe. Keep compatible with Python 2.7 in CentOS collector images."""

# ruff: noqa: UP024, UP031 -- the deployed helper also runs on Python 2.7

import base64
import binascii
import datetime
import errno
import fnmatch
import itertools
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time


HOST_PROC = "/var/host/proc"


def parts(path):
    return [part for part in path.split("/") if part]


def matches(path, patterns):
    # The server expands recursive globs up to the collector's configured depth.
    names = parts(path)
    for pattern in patterns:
        globs = parts(pattern)
        if len(names) == len(globs):
            if all(fnmatch.fnmatchcase(name, glob) for name, glob in zip(names, globs)):
                return True
    return False


def read_directory(request, patterns):
    directory = request.get("via") or os.path.dirname(request["path"])
    while directory != "/" and not matches(directory, patterns):
        directory = os.path.dirname(directory)
    if directory == "/" or (request.get("via") and request["via"] != directory):
        raise ValueError("outside_target_log_directory")
    return directory


def inside(path, directory):
    return path == directory or path.startswith(directory.rstrip("/") + "/")


def descend(name):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchdir(fd)
    finally:
        os.close(fd)


def mount_for(path, policy):
    return max(["/"] + [key for key in policy["mounts"] if inside(path, key)], key=len)


def collector_location(path, policy):
    return os.path.join(policy["root_path"], path.lstrip("/"))


def enter_process_root(container_id, namespace_init=False):
    # cwd is the pinned proc PID directory. Check membership and open root relative to
    # that handle, so PID reuse cannot switch the container between those operations.
    if not re.match(r"^[0-9a-f]{64}\Z", container_id):
        raise ValueError("target_process_identity_unverified")
    if namespace_init:
        with open("status") as stream:
            if not any(
                line.startswith("NSpid:") and len(line.split()) > 2 and line.split()[-1] == "1" for line in stream
            ):
                raise ValueError("target_process_identity_unverified")
    scope = re.compile(r"^(?:(?:cri-containerd|docker|crio)-)?%s(?:\.scope)?$" % container_id)
    with open("cgroup") as stream:
        for line in stream:
            fields = line.rstrip("\n").split(":", 2)
            if len(fields) == 3 and any(
                scope.match(part) for part in (parts(fields[2])[-1:] if namespace_init else parts(fields[2]))
            ):
                break
        else:
            raise ValueError("target_process_identity_unverified")
    with open("mountinfo", "rb") as stream:
        mounts = {line.split()[4] for line in stream}
    fd = os.open("root", os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fchdir(fd)
    finally:
        os.close(fd)

    return mounts


def enter_target_root(policy):
    # A node alias may have changed since kubelet mounted it. Use the mount pinned
    # by the target's mount namespace, never the current destination of the alias.
    container_id = policy.get("runtime_id", "")
    if not re.match(r"^[0-9a-f]{64}\Z", container_id):
        raise ValueError("target_process_identity_unverified")
    os.chdir("/")
    for part in parts(HOST_PROC):
        descend(part)
    proc_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        # A rendered PID can expire between config rendering and inspection. Prefer a
        # known PID, then look for a namespace init with this exact container cgroup.
        rendered_pid = policy.get("runtime_pid")
        known_pid = policy.get("namespace_init_pid") or rendered_pid

        def other_pids():
            os.fchdir(proc_fd)
            for entry in os.listdir("."):
                if entry.isdigit() and entry != known_pid:
                    yield entry

        for pid in itertools.chain([known_pid] if known_pid else [], other_pids()):
            os.fchdir(proc_fd)
            try:
                descend(pid)
                mounts = enter_process_root(container_id, namespace_init=pid != rendered_pid)
            except (OSError, IOError, ValueError):
                continue
            if pid != rendered_pid:
                policy["namespace_init_pid"] = pid
            return os.path.join(HOST_PROC, pid, "root"), mounts
        raise ValueError("target_process_identity_unverified")
    finally:
        os.close(proc_fd)


def link_destination(parent, target, policy, links):
    current = "/" if target.startswith("/") else parent
    pending = []
    for part in parts(target):
        if part == "..":
            if pending:
                # In link/../file, the kernel follows link before taking its parent.
                name, current, _ = open_parent(os.path.join(current, *pending), policy, True, links)
                descend(name)
                pending = []
            current = os.path.dirname(current)
        elif part != ".":
            pending.append(part)
    return os.path.join(current, *pending)


def is_mountpoint(path, policy):
    escaped = path.replace("\\", "\\134").replace(" ", "\\040").replace("\t", "\\011").replace("\n", "\\012")
    return escaped.encode("utf-8") in policy["active_mounts"]


def bind_mount_paths(policy):
    # mountinfo uses the actual mount destination. A Pod may spell its parent
    # through an image symlink. Resolve parents inside the pinned target root;
    # the leaf must still be a mount in the kernel table on every observation.
    declared = policy["mounts"]
    resolved = dict(declared)
    # Resolve declaration names independently. An alias for a nested mount may
    # be shorter than its parent alias. Enforce the completed table for all I/O.
    lookup = dict(policy, mounts={}, active_mounts=frozenset())
    for path, allowed in declared.items():
        if path == "/" or is_mountpoint(path, policy):
            continue
        try:
            _, parent, _ = open_parent(os.path.dirname(path), lookup, True)
        except (IOError, OSError, ValueError):
            continue
        destination = os.path.join(parent, os.path.basename(path))
        resolved[destination] = allowed and resolved.get(destination, True)
    policy["mounts"] = resolved


def open_parent(path, policy, follow_leaf, links=None):
    # cwd is private to this short-lived helper. Pin each directory before inspecting its
    # children. Never ask the collector kernel to follow a business-container symlink.
    if links is None:
        links = []
    while len(links) <= 32:
        policy["resolving_path"] = path
        os.fchdir(policy["root_fd"])
        if policy["mounts"].get("/") is False:
            raise ValueError("mount_unavailable_or_outside_scope: /")
        tail = parts(path)
        parent = "/"
        for index, name in enumerate(tail):
            last = index == len(tail) - 1
            logical = os.path.join(parent, name)
            policy["resolving_path"] = logical
            allowed = policy["mounts"].get(logical)
            mounted = is_mountpoint(logical, policy)
            if allowed is False or (mounted and not allowed):
                raise ValueError("mount_unavailable_or_outside_scope: " + logical)
            if allowed and not mounted:
                raise ValueError("target_volume_mount_unavailable: " + logical)
            if last and not follow_leaf:
                return name, logical, links
            if stat.S_ISLNK(os.lstat(name).st_mode):
                target = os.readlink(name)
                hop = {"path": logical, "target": target}
                links.append(hop)
                target_path = link_destination(parent, target, policy, links)
                hop["resolved_path"] = target_path
                path = os.path.join(target_path, *tail[index + 1 :])
                break
            if last:
                return name, logical, links
            descend(name)
            parent = logical
        else:
            return ".", "/", links
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
    path = request["path"]
    via = request.get("via")
    if via:
        _, anchor, hops = open_parent(via, policy, True)
        if not hops or not inside(path, anchor):
            raise ValueError("path_outside_source_anchor")
        path = os.path.normpath(os.path.join(via, os.path.relpath(path, anchor)))
    name, resolved, links = open_parent(path, policy, request["operation"] != "readlink")
    return name, path, resolved, links, collector_location(resolved, policy)


def logical_collector_file(path, anchor, policy):
    # Match actual directory identities, including aliases and mount roots that
    # have unrelated path prefixes on the node. Raw I/O always uses target fds.
    observed = os.stat(path)
    canonical = os.path.realpath(path)
    try:
        if not os.path.samestat(observed, os.stat(canonical)):
            canonical = path
    except OSError:
        canonical = path  # Kernel magic links can lack a usable canonical pathname.
    ancestors = {}
    parent = canonical
    while parent != "/":
        info = os.stat(parent)
        ancestors[(info.st_dev, info.st_ino)] = os.path.relpath(canonical, parent)
        parent = os.path.dirname(parent)
    scopes = [key for key, root in policy["mounts"].items() if root and inside(key, anchor) and key != anchor]
    for scope in sorted(scopes, key=len, reverse=True) + [anchor]:
        try:
            name, _, _ = open_parent(scope, policy, True)
            info = os.lstat(name)
        except (OSError, IOError, ValueError):
            if scope == anchor:
                raise
            continue
        suffix = ancestors.get((info.st_dev, info.st_ino))
        if suffix is not None:
            return os.path.normpath(os.path.join(scope, suffix))
    raise ValueError("outside_target_log_directory")


def read_target_file(policy, request):
    # Identify a concrete directory from target-bound directory patterns. Never authorize
    # the caller-supplied parent, the host root, or a sibling of the resolved directory.
    path = request["path"]
    native = request.get("path_space") == "collector"
    directory = read_directory(request, policy["directories"])
    name, anchor, hops = open_parent(directory, policy, True)
    base = mount_for(anchor, policy)
    if base == "/" and any(inside(anchor, fs) for fs in ("/proc", "/sys", "/dev")):
        raise ValueError("outside_target_log_directory")
    if anchor == "/":
        raise ValueError("unverified_log_directory_link")
    descend(name)
    root_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        if native:
            actual = logical_collector_file(path, anchor, policy)
        elif request.get("via"):
            if not inside(path, anchor):
                raise ValueError("path_outside_source_anchor")
            actual = path
        else:
            actual = os.path.normpath(os.path.join(anchor, os.path.relpath(path, directory)))
        name, resolved, links = open_parent(actual, policy, True)
        physical = collector_location(resolved, policy)
        if not inside(resolved, anchor):
            raise ValueError("outside_target_log_directory")
        for link in links:
            link_mount = mount_for(link["path"], policy)
            if inside(link_mount, anchor) and not inside(link["resolved_path"], link_mount):
                raise ValueError("outside_target_log_directory")
        # The pinned log directory sees the same nested mounts as the target.
        observed = os.lstat(name)
        os.fchdir(root_fd)
        components = parts(os.path.relpath(resolved, anchor))
        if not components or components == ["."]:
            raise ValueError("source_not_regular")
        for component in components[:-1]:
            descend(component)
        if not os.path.samestat(observed, os.lstat(components[-1])):
            raise ValueError("source_changed_before_read")
        return components[-1], path, resolved, hops + links, physical
    finally:
        os.close(root_fd)


def snapshot(policy, request):
    if request.get("path_space") == "collector" and request["operation"] != "read":
        return observe_path(policy, request)
    if request.get("path_space") == "collector" and not request.get("via"):
        raise ValueError("collector_read_requires_target_directory")
    policy["resolving_path"] = request["path"]
    root_path, mounts = enter_target_root(policy)
    observation_policy = dict(policy, root_path=root_path, active_mounts=mounts)
    root_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        observation_policy["root_fd"] = root_fd
        bind_mount_paths(observation_policy)
        return observe_path(observation_policy, request)
    finally:
        policy["resolving_path"] = observation_policy.get("resolving_path", request["path"])
        os.close(root_fd)


def observe_path(policy, request):
    path, operation = request["path"], request["operation"]
    native = request.get("path_space") == "collector"
    native_metadata = native and operation != "read"
    if native_metadata:
        if operation not in ("list", "readlink", "stat") or "via" in request:
            raise ValueError("collector_paths_support_metadata_only")
        # Keep the original path for follow-ups. Kernel magic links may have no equivalent
        # canonical pathname (for instance a mounted process root or a deleted file).
        name = collector_path = path
        info = os.lstat(path) if operation == "readlink" else os.stat(path)
    else:
        resolve = read_target_file if operation == "read" else target_source_path
        name, path, resolved, links, collector_path = resolve(policy, request)
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
    if not native_metadata:
        result.update(resolved_path=resolved, links=links)
    if operation == "readlink":
        result["target"] = os.readlink(name)
        result["follow_path"] = path
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
            if native:
                observed = os.stat(path)
                if (observed.st_dev, observed.st_ino) != (bound.st_dev, bound.st_ino):
                    raise ValueError("collector_path_identity_mismatch")
            result.update(
                device=bound.st_dev,
                inode=bound.st_ino,
                mode=bound.st_mode,
                size_bytes=bound.st_size,
                mtime=timestamp(bound.st_mtime),
                mtime_epoch=bound.st_mtime,
            )
            with open("/proc/self/fd/%d" % pinned, "rb") as stream:
                offset = request.get("offset", 0)
                stream.seek(offset)
                data = stream.read(request.get("length", 1024))
            # Carry exact bytes through the generic evidence sanitization and compaction.
            # Each encoded chunk is within the evidence store's 4096-character string limit.
            chunks = [binascii.hexlify(data[i : i + 2048]).decode("ascii") for i in range(0, len(data), 2048)]
            result.update(offset=offset, returned_bytes=len(data), raw_hex_chunks=chunks)
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
        return {
            "first": first,
            "activity": "second_sample_unavailable",
            "error": str(error),
            "failed_path": policy.get("resolving_path", request["path"]),
        }
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
        print(
            json.dumps(
                {
                    "error": str(error),
                    "errno": getattr(error, "errno", None),
                    "failed_path": policy.get("resolving_path", request["path"]),
                }
            )
        )
