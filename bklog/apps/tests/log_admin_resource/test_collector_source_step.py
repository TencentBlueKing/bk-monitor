"""Filesystem regressions for the standalone program executed inside the collector."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copyfile, which
from unittest.mock import patch

from apps.log_admin_resource.scripts import collector_source_step as probe


class SourceStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        parent = Path(self.tmp.name).resolve()
        self.root = parent / "container"
        self.volume = self.root / "data"
        self.root.mkdir()
        self.directory = self.volume / "service"
        self.directory.mkdir(parents=True)
        (self.root / "logs").symlink_to("/data/service")
        self.file = self.directory / "app.log"
        self.file.write_bytes(b"old\n")
        self.policy = {
            "directories": ["/logs"],
            "mounts": {"/data": True, "/data/secret": False},
            "runtime_id": "c" * 64,
            "interval": 0,
            "pid": 0,
        }

        proc = parent / "host-proc"
        self.process = proc / "27"
        self.process.mkdir(parents=True)
        (self.process / "root").symlink_to(self.root)
        (self.process / "cgroup").write_text("0::/docker-" + self.policy["runtime_id"] + ".scope\n")
        (self.process / "status").write_text("NSpid:\t27\t1\n")
        self.mountinfo = self.process / "mountinfo"
        self.mountinfo.write_text("1 2 0:3 / /data rw - tmpfs tmpfs rw\n")
        proc_patch = patch.object(probe, "HOST_PROC", str(proc))
        proc_patch.start()
        self.addCleanup(proc_patch.stop)

    def run_step(self, operation, path, **kwargs):
        return probe.inspect_source(self.policy, {"operation": operation, "path": path, **kwargs})

    def test_follow_directory_link_and_continue_using_discovered_target(self):
        link = self.run_step("readlink", "/logs")["observation"]
        self.assertEqual(link["target"], "/data/service")
        options = {"path_space": "target", "via": "/logs"}
        listing = self.run_step("list", link["target"], **options)["observation"]
        self.assertEqual(listing["entries"], ["/data/service/app.log"])
        observation = self.run_step("stat", listing["entries"][0], **options)
        self.assertEqual(observation["activity"], "no_growth_observed")
        self.assertEqual(observation["second"]["inode"], self.file.stat().st_ino)
        self.assertEqual(observation["second"]["device"], self.file.stat().st_dev)
        self.assertTrue(observation["second"]["mtime"].endswith("Z"))
        self.assertTrue(observation["second"]["sampled_at"].endswith("Z"))
        if sys.platform.startswith("linux"):
            row = self.run_step("read", listing["entries"][0], **options)["observation"]
            self.assertEqual(bytes.fromhex("".join(row["raw_hex_chunks"])), self.file.read_bytes())

    def test_link_target_with_directory_suffix_agrees_with_kernel(self):
        alias = self.directory / "alias"
        (self.directory / "subdir").mkdir()
        nested = self.directory / "nested"
        nested.symlink_to("alias")
        for suffix in ("/", "/.", "/./"):
            alias.symlink_to("app.log" + suffix)
            for link in (alias, nested):
                with self.assertRaises(NotADirectoryError):
                    link.stat()
                for operation in ("stat", "list", "read"):
                    with self.subTest(suffix=suffix, link=link.name, operation=operation):
                        with self.assertRaises(NotADirectoryError):
                            self.run_step(operation, "/logs/" + link.name)
            self.assertEqual(self.run_step("readlink", "/logs/alias")["observation"]["target"], "app.log" + suffix)
            alias.unlink()
            alias.symlink_to("subdir" + suffix)
            for link in (alias, nested):
                row = self.run_step("stat", "/logs/" + link.name)["observation"]
                self.assertEqual(row["inode"], link.stat().st_ino)
            alias.unlink()

    def test_list_distinguishes_undecodable_names_from_literal_replacement_character(self):
        invalid = [b"job-\xfe.log", b"job-\xff.log"]
        valid = "job-\ufffd.log"
        names = [valid.encode(), *invalid]
        with patch.object(probe.subprocess, "Popen") as popen:
            proc = popen.return_value
            proc.wait.return_value = 0
            for path, space in (("/logs", "target"), (str(self.directory), "collector")):
                proc.stdout = io.BytesIO(b"".join(b"./" + name + b"\0" for name in names))
                row = self.run_step("list", path, path_space=space)["observation"]
                self.assertEqual(row["entries"], [path + "/" + valid])
                self.assertEqual(row["non_utf8_names_hex"], [name.hex() for name in invalid])
                self.assertFalse(row["truncated"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "byte filenames on Linux")
    def test_byte_filenames_in_a_mounted_log_directory(self):
        raw_names = [b"job-\xfe.log", b"job-\xff.log"]
        for name in raw_names:
            with open(os.path.join(os.fsencode(self.directory), name), "wb") as stream:
                stream.write(name)
        valid = self.directory / "job-\ufffd.log"
        valid.write_bytes(b"valid")
        options = {"via": "/logs", "path_space": "target"}
        directory = self.run_step("readlink", "/logs")["observation"]["target"]
        listing = self.run_step("list", directory, **options)["observation"]
        self.assertEqual(listing["non_utf8_names_hex"], [name.hex() for name in raw_names])
        self.assertEqual(listing["entries"], [directory + "/app.log", directory + "/" + valid.name])
        row = self.run_step("read", listing["entries"][-1], **options)["observation"]
        self.assertEqual(row["inode"], valid.stat().st_ino)
        self.assertEqual(bytes.fromhex("".join(row["raw_hex_chunks"])), b"valid")
        alias = self.directory / "alias"
        os.symlink(raw_names[0], os.fsencode(alias))
        for path, space in ((str(alias), "collector"), ("/logs/alias", "target")):
            with self.assertRaisesRegex(ValueError, "non_utf8_link_target_hex=" + raw_names[0].hex()):
                self.run_step("readlink", path, path_space=space)
        self.assertEqual(
            self.run_step("stat", str(alias), path_space="collector")["second"]["inode"], alias.stat().st_ino
        )

    def test_mount_with_symlinked_parent_matches_the_kernel_path(self):
        (self.root / "var").mkdir()
        (self.root / "var" / "run").symlink_to("../run")
        self.directory.rename(self.root / "run")
        mounted = self.root / "run" / "service"
        mounted.mkdir()
        log = mounted / "app.log"
        log.write_bytes(b"mounted")
        logical = "/var/run/service"
        self.policy.update(
            mounts={logical: True}, mount_sources={logical: "/container/run/service"}, directories=[logical]
        )
        self.mountinfo.write_text("1 0 0:2 / /run rw - tmpfs tmpfs rw\n2 1 0:4 / /run/service rw - tmpfs tmpfs rw\n")
        self.assertEqual(self.run_step("stat", logical + "/app.log")["second"]["inode"], log.stat().st_ino)
        if sys.platform.startswith("linux"):
            for path, options in [
                (logical + "/app.log", {}),
                (str(log), {"path_space": "collector", "via": logical}),
            ]:
                row = self.run_step("read", path, **options)["observation"]
                self.assertEqual(bytes.fromhex("".join(row["raw_hex_chunks"])), log.read_bytes())
        for path in ("/run", "/run/app.log"):
            with self.assertRaisesRegex(ValueError, "outside_scope"):
                self.run_step("list", path)
        alias = self.root / "var/run"
        other = self.root / "other/service"
        other.mkdir(parents=True)
        (other / "app.log").write_bytes(b"second fixture")
        with self.mountinfo.open("a") as stream:
            stream.write("3 0 0:5 / /other/service rw - tmpfs tmpfs rw\n")
        with patch.dict(self.policy, host_path_mounts=[logical]):
            with self.assertRaisesRegex(ValueError, "identity_unverified"):
                self.run_step("stat", logical + "/app.log")
        alias.unlink()
        alias.symlink_to("../other")
        for path in (logical + "/app.log", "/other/service/app.log"):
            with self.assertRaisesRegex(ValueError, "identity_unverified"):
                self.run_step("stat", path)
        alias.unlink()
        alias.symlink_to("../run")
        with patch.dict(self.policy, mount_sources={}):
            with self.assertRaisesRegex(ValueError, "identity_unverified"):
                self.run_step("read", logical + "/app.log")
        self.policy["mounts"]["/run"] = False
        with self.assertRaisesRegex(ValueError, "outside_scope"):
            self.run_step("stat", logical + "/app.log")
        del self.policy["mounts"]["/run"]
        self.policy["mounts"]["/run/service"] = False
        with self.assertRaisesRegex(ValueError, "outside_scope"):
            self.run_step("stat", logical + "/app.log")
        del self.policy["mounts"]["/run/service"]
        self.mountinfo.write_text("")
        with self.assertRaisesRegex(ValueError, "target_volume_mount_unavailable"):
            self.run_step("stat", logical + "/app.log")

    def test_empty_directory_is_distinct_from_missing_target(self):
        self.file.unlink()
        self.assertEqual(self.run_step("list", "/logs")["observation"]["entries"], [])
        self.directory.rmdir()
        with self.assertRaises(FileNotFoundError):
            self.run_step("list", "/logs")

    def test_list_uses_one_directory_when_the_entry_is_replaced(self):
        for space in ("collector", "target"):
            with self.subTest(space=space):
                old = self.directory / ("old-" + space)
                new = self.directory / ("new-" + space)
                old.mkdir()
                new.mkdir()
                (old / "old.log").touch()
                (new / "new.log").touch()
                current = self.directory / ("current-" + space)
                current.symlink_to(old.name)
                replacement = self.directory / ("next-" + space)
                replacement.symlink_to(new.name)
                popen = subprocess.Popen

                def switch_directory(*args, **kwargs):
                    os.replace(replacement, current)
                    return popen(*args, **kwargs)

                path = str(current) if space == "collector" else "/logs/" + current.name
                with patch.object(probe.subprocess, "Popen", side_effect=switch_directory):
                    row = self.run_step("list", path, path_space=space)["observation"]
                self.assertEqual(row["inode"], old.stat().st_ino)
                self.assertEqual(row["entries"], [path + "/old.log"])
                self.assertEqual(current.stat().st_ino, new.stat().st_ino)

    def test_readlink_reports_rotation_during_observation(self):
        current = self.directory / "current"
        current.symlink_to("old")
        replacement = self.directory / "next"
        replacement.symlink_to("new")
        read_link = probe.read_link

        def rotate_and_read(name):
            os.replace(replacement, current)
            return read_link(name)

        with patch.object(probe, "read_link", side_effect=rotate_and_read):
            with self.assertRaisesRegex(ValueError, "source_changed_during_readlink"):
                self.run_step("readlink", str(current), path_space="collector")

    def test_unauthorized_paths_and_nested_mounts(self):
        (self.volume / "secret").mkdir()
        (self.root / "logs").unlink()
        (self.root / "logs").symlink_to("/data/secret")
        with self.assertRaisesRegex(ValueError, "allowed_volume|outside_scope"):
            self.run_step("list", "/logs")
        result = self.run_step("stat", "/data/service/app.log")
        self.assertEqual(result["first"]["inode"], self.file.stat().st_ino)

    def test_alias_does_not_authorize_a_sibling_and_leaf_link_cannot_escape(self):
        with self.assertRaisesRegex(ValueError, "outside_source_anchor"):
            self.run_step("read", "/data/other/app.log", via="/logs")
        (self.directory / "other.log").symlink_to("../secret/key")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.run_step("read", "/logs/other.log")

    def test_rotation_truncation_and_growth_without_a_reader(self):
        with patch.object(probe.time, "sleep", side_effect=lambda _: self.file.write_bytes(b"longer\n")):
            result = self.run_step("stat", "/logs/app.log")
        self.assertEqual((result["activity"], result["growth_bytes"], result["read_progress"]), ("grew", 3, "unknown"))
        with patch.object(probe.time, "sleep", side_effect=lambda _: self.file.write_bytes(b"")):
            self.assertEqual(self.run_step("stat", "/logs/app.log")["activity"], "truncated")

        def rotate(_):
            self.file.rename(self.file.with_suffix(".old"))
            self.file.touch()

        with patch.object(probe.time, "sleep", side_effect=rotate):
            self.assertEqual(self.run_step("stat", "/logs/app.log")["activity"], "replaced")

    @unittest.skipUnless(sys.platform.startswith("linux"), "collector descriptor operations require Linux procfs")
    def test_log_directory_allows_unmatched_and_excluded_files_verbatim(self):
        self.policy["exclude"] = [r"fd.*"]
        payload = b"token=fixture-only\x00\xff\n"
        (self.directory / "fd.log").write_bytes(payload)
        for path, options in [("/logs/fd.log", {}), ("/data/service/fd.log", {"via": "/logs"})]:
            result = self.run_step("read", path, **options)["observation"]
            self.assertEqual(bytes.fromhex("".join(result["raw_hex_chunks"])), payload)

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux tmpfs and O_PATH")
    def test_logical_and_collector_reads_across_mounts(self):
        with tempfile.TemporaryDirectory(dir="/dev/shm") as mounted:
            self.assertNotEqual(os.stat(mounted).st_dev, self.root.stat().st_dev)
            (self.process / "root").unlink()
            (self.process / "root").symlink_to("/")
            self.mountinfo.write_bytes(Path("/proc/self/mountinfo").read_bytes())
            self.policy["mounts"] = {line.split()[4]: True for line in self.mountinfo.read_text().splitlines()}
            logical_dir = self.root / "logs"
            logical_dir.unlink()
            logical_dir.symlink_to(Path(mounted) / "service")
            self.policy["directories"] = [str(logical_dir)]
            directory = Path(mounted) / "service"
            directory.mkdir()
            log = directory / "debug.txt"
            log.write_bytes(b"before\x00\xffafter")
            alias = directory / "rotated"
            alias.symlink_to(log)
            logical = self.run_step("stat", str(logical_dir / "debug.txt"))["second"]
            for path, options in [
                (str(logical_dir / "debug.txt"), {}),
                (logical["collector_path"], {"path_space": "collector", "via": str(logical_dir)}),
                (str(alias), {"path_space": "collector", "via": str(logical_dir)}),
            ]:
                result = self.run_step("read", path, offset=6, length=2, **options)["observation"]
                self.assertEqual((result["device"], result["inode"]), (log.stat().st_dev, log.stat().st_ino))
                self.assertEqual(result["raw_hex_chunks"], ["00ff"])
            alias.unlink()
            alias.symlink_to(self.file)
            with self.assertRaisesRegex(ValueError, "outside_target_log_directory"):
                self.run_step("read", str(alias), path_space="collector", via=str(logical_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux procfs")
    def test_runtime_root_directory_link_and_process_membership(self):
        runtime_id = "a" * 64
        os.chdir(f"/proc/{os.getpid()}")
        with patch(
            "builtins.open", side_effect=[io.StringIO("0::/cri-containerd-" + runtime_id + ".scope\n"), io.BytesIO(b"")]
        ):
            probe.enter_process_root(runtime_id)
        self.assertTrue(os.path.samefile(".", "/"))
        os.chdir(f"/proc/{os.getpid()}")
        with patch("builtins.open", return_value=io.StringIO("0::/another.scope\n")):
            with self.assertRaisesRegex(ValueError, "target_process_identity_unverified"):
                probe.enter_process_root(runtime_id)
        (self.root / "logs").unlink()
        (self.root / "logs").symlink_to("local")
        local = self.root / "local"
        local.mkdir()
        (local / "test.log").write_bytes(b"log")
        result = self.run_step("read", "/logs/test.log")["observation"]
        self.assertEqual(result["raw_hex_chunks"], ["6c6f67"])

    def test_expired_rendered_pid_falls_back_only_to_verified_init(self):
        self.policy["runtime_pid"] = "19"
        unrelated = self.process.with_name("19")
        unrelated.mkdir()
        (unrelated / "cgroup").write_text("0::/other.scope\n")
        row = self.run_step("stat", "/logs/app.log")["second"]
        self.assertEqual(row["inode"], self.file.stat().st_ino)
        self.assertEqual(self.policy["namespace_init_pid"], "27")
        (self.process / "status").write_text("NSpid:\t27\t2\n")
        with self.assertRaisesRegex(ValueError, "target_process_identity_unverified"):
            self.run_step("stat", "/logs/app.log")

    def test_mount_source_alias_uses_target_mount_and_refuses_unverified_mount(self):
        self.mountinfo.write_text("1 2 0:3 / /mounted rw - tmpfs tmpfs rw\n")
        mounted = self.root / "mounted"
        mounted.mkdir()
        (mounted / "a.log").write_bytes(b"bound mount")
        node_alias = self.root.parent / "node-alias"
        node_alias.symlink_to(self.volume)
        (self.volume / "a.log").write_bytes(b"different volume")
        self.policy.update(directories=["/mounted"])
        self.policy["mounts"]["/mounted"] = True
        meta = self.run_step("stat", "/mounted/a.log")["second"]
        self.assertEqual(meta["inode"], (mounted / "a.log").stat().st_ino)
        if sys.platform.startswith("linux"):
            row = self.run_step("read", meta["collector_path"], path_space="collector", via="/mounted")["observation"]
            self.assertEqual(bytes.fromhex("".join(row["raw_hex_chunks"])), b"bound mount")
            with self.assertRaisesRegex(ValueError, "outside_target_log_directory|identity_mismatch"):
                self.run_step("read", str(node_alias / "a.log"), path_space="collector", via="/mounted")
        self.mountinfo.write_text("")
        with self.assertRaises(ValueError):
            self.run_step("stat", "/mounted/a.log")

    @unittest.skipUnless(sys.platform.startswith("linux") and which("unshare"), "requires Linux mount namespaces")
    def test_recreated_node_directory_does_not_replace_live_bind_mount(self):
        node_source = self.root.parent / "node-source"
        (node_source / "service").mkdir(parents=True)
        log = node_source / "service/app.log"
        log.write_bytes(b"original mounted file")
        # Keep the bind mount private to this child. The parent can observe it through
        # the process root, just as a collector with a host procfs mount would.
        child = subprocess.Popen(
            [
                "unshare",
                "--mount",
                "--propagation",
                "private",
                "sh",
                "-ec",
                'mount --bind "$1" "$2"; echo ready; read -r done',
                "sh",
                str(node_source),
                str(self.volume),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            if child.stdout.readline() != b"ready\n":
                error = child.stderr.read().decode()
                if "Operation not permitted" in error or "Permission denied" in error:
                    self.skipTest("private bind mounts are unavailable to this test process")
                self.fail(error)
            target_root = Path(f"/proc/{child.pid}/root") / self.root.relative_to("/")
            mounted = target_root / "data/service/app.log"
            original = mounted.stat()
            archived = node_source.with_name("original")
            node_source.rename(archived)
            log.parent.mkdir(parents=True)
            log.write_bytes(b"replacement at the old name")
            self.assertFalse(os.path.samestat(original, log.stat()))
            (self.process / "root").unlink()
            (self.process / "root").symlink_to(target_root)
            for hint in ({}, {"runtime_pid": "27"}):
                with self.subTest(hint=hint):
                    self.policy.update(hint)
                    meta = self.run_step("stat", "/logs/app.log")["second"]
                    self.assertEqual((meta["device"], meta["inode"]), (original.st_dev, original.st_ino))
                    for path, options in [
                        ("/logs/app.log", {}),
                        (str(archived / "service/app.log"), {"path_space": "collector", "via": "/logs"}),
                    ]:
                        row = self.run_step("read", path, **options)["observation"]
                        self.assertEqual((row["size_bytes"], row["mtime_epoch"]), (original.st_size, original.st_mtime))
                        self.assertEqual(bytes.fromhex("".join(row["raw_hex_chunks"])), mounted.read_bytes())
                    with self.assertRaisesRegex(ValueError, "outside_target_log_directory|identity_mismatch"):
                        self.run_step("read", str(log), path_space="collector", via="/logs")
        finally:
            child.communicate(input=b"done\n", timeout=10)

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux O_PATH")
    def test_nested_mount_raw_read_uses_child_volume_and_rejects_sibling_link(self):
        nested = self.directory / "archive"
        nested.mkdir()
        self.policy["mounts"]["/data/service/archive"] = True
        with self.mountinfo.open("a") as stream:
            stream.write("2 1 0:4 / /data/service/archive rw - tmpfs tmpfs rw\n")
        file = nested / "app.log"
        file.write_bytes(b"mounted")
        for path, args in [
            ("/logs/archive/app.log", {}),
            (str(file), {"path_space": "collector", "via": "/logs"}),
        ]:
            row = self.run_step("read", path, **args)["observation"]
            self.assertEqual((row["device"], row["inode"]), (file.stat().st_dev, file.stat().st_ino))
            self.assertEqual(bytes.fromhex("".join(row["raw_hex_chunks"])), b"mounted")
        (nested / "other").symlink_to("../app.log")
        with self.assertRaisesRegex(ValueError, "outside_target_log_directory"):
            self.run_step("read", "/logs/archive/other")

    def test_special_files_and_unresolved_paths_have_no_content(self):
        os.mkfifo(self.directory / "pipe")
        with self.assertRaisesRegex(ValueError, "source_not_regular"):
            self.run_step("read", "/logs/pipe")
        (self.directory / "gone").symlink_to("missing")
        with self.assertRaises(FileNotFoundError):
            self.run_step("read", "/logs/gone")
        self.assertEqual(self.policy["resolving_path"], "/data/service/missing")

    def test_parent_of_intermediate_link_uses_resolved_directory(self):
        (self.directory / "nested" / "child").mkdir(parents=True)
        (self.directory / "nested" / "app.log").write_bytes(b"nested")
        (self.directory / "alias").symlink_to("nested/child")
        (self.directory / "latest").symlink_to("alias/../app.log")
        result = self.run_step("stat", "/logs/latest")["second"]
        self.assertEqual(result["inode"], (self.directory / "nested/app.log").stat().st_ino)
        (self.directory / "alias").unlink()
        (self.directory / "alias").symlink_to("latest")
        with self.assertRaisesRegex(ValueError, "too_many_symlinks"):
            self.run_step("stat", "/logs/latest")

    def test_file_link_cannot_leave_resolved_log_directory_within_same_volume(self):
        (self.volume / "other").mkdir()
        (self.volume / "other" / "elsewhere.log").touch()
        (self.directory / "redirect.log").symlink_to("../other/elsewhere.log")
        with self.assertRaisesRegex(ValueError, "outside_target_log_directory"):
            self.run_step("read", "/logs/redirect.log")

    def test_leaf_link_can_point_to_a_matching_log_in_a_data_mount(self):
        self.policy["directories"] = []
        source = self.root / "service.log"
        source.symlink_to("/data/service/service.log")
        self.file.rename(self.directory / "service.log")
        result = self.run_step("stat", "/service.log")
        self.assertEqual(result["first"]["resolved_path"], "/data/service/service.log")
        source.unlink()
        source.symlink_to("/data/service/private.key")
        with self.assertRaisesRegex(ValueError, "outside_target_log_directory"):
            self.run_step("read", "/service.log")

    def test_direct_mount_and_listing_limit(self):
        self.policy["directories"] = ["/data/service"]
        for n in range(50):
            (self.directory / f"{n}.log").touch()
        listing = self.run_step("list", "/data/service")["observation"]
        self.assertTrue(listing["truncated"])
        self.assertEqual(len(listing["entries"]), 50)
        self.assertEqual(self.run_step("stat", "/data/service/app.log")["activity"], "no_growth_observed")
        direct = self.run_step("list", "/data/service", via="/data/service")["observation"]
        self.assertEqual(direct["entries"], listing["entries"])

    def test_unmatched_file_and_link_to_sibling_directory(self):
        archive = self.volume / "archive"
        archive.mkdir()
        missed = archive / "fd.log"
        missed.write_text("hello")
        (self.directory / "old").symlink_to("../archive")
        listing = self.run_step("list", "/logs/old")["observation"]
        self.assertEqual(listing["entries"], ["/logs/old/fd.log"])
        self.assertEqual(self.run_step("readlink", "/logs/old")["observation"]["target"], "../archive")
        with patch.object(probe.time, "sleep", side_effect=lambda _: missed.write_text("hello again")):
            stat = self.run_step("stat", listing["entries"][0])
        self.assertEqual(stat["growth_bytes"], 6)
        native = self.run_step("stat", stat["second"]["collector_path"], path_space="collector")
        self.assertEqual(native["second"]["inode"], missed.stat().st_ino)
        with self.assertRaisesRegex(ValueError, "outside_target_log_directory"):
            self.run_step("read", listing["entries"][0])

    def test_native_metadata_uses_the_collector_namespace_without_a_mount_map(self):
        self.policy = {"pid": 0, "interval": 0}
        alias = self.root / "outside"
        alias.symlink_to("data/service")
        native = {"path_space": "collector"}
        self.assertEqual(self.run_step("readlink", str(alias), **native)["observation"]["target"], "data/service")
        result = self.run_step("list", str(alias), **native)["observation"]
        child = str(alias / "app.log")
        self.assertEqual(result["entries"], [child])
        observed = self.run_step("stat", child, **native)["second"]
        self.assertEqual((observed["collector_path"], observed["inode"]), (child, self.file.stat().st_ino))
        with self.assertRaisesRegex(ValueError, "requires_target_directory"):
            self.run_step("read", child, **native)
        alias.unlink()
        alias.symlink_to("missing")
        self.assertEqual(self.run_step("readlink", str(alias), **native)["observation"]["target"], "missing")
        with self.assertRaises(FileNotFoundError):
            self.run_step("stat", str(alias), **native)

    @unittest.skipUnless(sys.platform.startswith("linux") and os.path.isdir("/dev/shm"), "requires Linux tmpfs")
    def test_native_metadata_follows_link_across_mounts(self):
        with tempfile.TemporaryDirectory(dir="/dev/shm") as mounted:
            destination = Path(mounted)
            self.assertNotEqual(self.root.stat().st_dev, destination.stat().st_dev)
            link = self.root / "mounted"
            link.symlink_to(destination)
            log = destination / "new.log"
            log.touch()
            listing = self.run_step("list", str(link), path_space="collector")["observation"]
            self.assertEqual(listing["entries"], [str(link / "new.log")])
            with patch.object(probe.time, "sleep", side_effect=lambda _: log.write_bytes(b"new")):
                result = self.run_step("stat", listing["entries"][0], path_space="collector")
            self.assertEqual((result["growth_bytes"], result["second"]["inode"]), (3, log.stat().st_ino))
            self.assertEqual(result["second"]["device"], destination.stat().st_dev)

    def test_single_file_mount_metadata(self):
        self.policy["mounts"]["/single"] = True
        os.link(self.file, self.root / "single")
        with self.mountinfo.open("a") as stream:
            stream.write("2 1 0:4 / /single rw - tmpfs tmpfs rw\n")
        self.assertEqual(self.run_step("stat", "/single")["first"]["inode"], self.file.stat().st_ino)

    def test_shared_readers_do_not_identify_one_position(self):
        with patch.object(probe, "reader_positions", return_value=[2, 7]):
            with patch.object(probe.time, "sleep", side_effect=lambda _: self.file.write_bytes(b"longer\n")):
                result = self.run_step("stat", "/logs/app.log")
        self.assertEqual(result["read_progress"], "unknown")
        self.assertNotIn("unread_bytes", result)

    @unittest.skipUnless(sys.platform.startswith("linux"), "collector descriptor operations require Linux procfs")
    def test_reads_a_bounded_byte_range(self):
        result = self.run_step("read", "/logs/app.log", offset=1, length=2)["observation"]
        self.assertEqual((bytes.fromhex("".join(result["raw_hex_chunks"])), result["returned_bytes"]), (b"ld", 2))

    @unittest.skipUnless(sys.platform.startswith("linux"), "collector descriptor operations require Linux procfs")
    def test_observed_cursor_before_and_after_append(self):
        executable = self.volume / "bkunifylogbeat"
        copyfile(sys.executable, executable)
        executable.chmod(0o700)
        with subprocess.Popen(
            [
                str(executable),
                "-u",
                "-c",
                "import sys; f=open(sys.argv[1],'rb',0); f.read(); print('ready'); "
                "sys.stdin.readline(); f.read(); print('caught up'); sys.stdin.readline()",
                str(self.file),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as reader:
            try:
                self.assertEqual(reader.stdout.readline(), b"ready\n")
                self.policy["pid"] = reader.pid

                def append(_):
                    with self.file.open("ab") as output:
                        output.write(b"new\n")

                with patch.object(probe.time, "sleep", side_effect=append):
                    result = self.run_step("stat", "/logs/app.log")
                self.assertEqual((result["read_progress"], result["unread_bytes"]), ("open_reader_behind", 4))

                def catch_up(_):
                    append(0)
                    reader.stdin.write(b"read\n")
                    reader.stdin.flush()
                    self.assertEqual(reader.stdout.readline(), b"caught up\n")

                with patch.object(probe.time, "sleep", side_effect=catch_up):
                    result = self.run_step("stat", "/logs/app.log")
                self.assertEqual((result["read_progress"], result["unread_bytes"]), ("open_reader_at_eof", 0))
            finally:
                reader.terminate()
