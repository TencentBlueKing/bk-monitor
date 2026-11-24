"""Filesystem regressions for the standalone program executed inside the collector."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copyfile
from unittest.mock import patch

from apps.log_admin_resource.scripts import collector_source_step as probe


class SourceStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        parent = Path(self.tmp.name).resolve()
        self.root = parent / "container"
        self.volume = parent / "volume"
        self.root.mkdir()
        self.directory = self.volume / "service"
        self.directory.mkdir(parents=True)
        (self.root / "logs").symlink_to("/data/service")
        self.file = self.directory / "app.log"
        self.file.write_bytes(b"old\n")
        self.policy = {
            "patterns": ["/logs/*.log"],
            "mounts": {"/": str(self.root), "/data": str(self.volume), "/data/secret": None},
            "interval": 0,
            "pid": 0,
        }

    def run_step(self, operation, path, **kwargs):
        return probe.inspect_source(self.policy, {"operation": operation, "path": path, **kwargs})

    def test_follow_directory_link_and_continue_using_discovered_target(self):
        link = self.run_step("readlink", "/logs")["observation"]
        self.assertEqual(link["target"], "/data/service")
        listing = self.run_step("list", link["target"], via="/logs")["observation"]
        self.assertEqual(listing["entries"], ["/logs/app.log"])
        observation = self.run_step("stat", listing["entries"][0])
        self.assertEqual(observation["activity"], "no_growth_observed")
        self.assertEqual(observation["second"]["inode"], self.file.stat().st_ino)
        self.assertEqual(observation["second"]["device"], self.file.stat().st_dev)
        self.assertTrue(observation["second"]["mtime"].endswith("Z"))
        self.assertTrue(observation["second"]["sampled_at"].endswith("Z"))

    def test_empty_directory_is_distinct_from_missing_target(self):
        self.file.unlink()
        self.assertEqual(self.run_step("list", "/logs")["observation"]["entries"], [])
        self.directory.rmdir()
        with self.assertRaises(FileNotFoundError):
            self.run_step("list", "/logs")

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

    def test_excluded_files_can_be_listed_and_statted(self):
        self.policy["exclude"] = [r"app\.log$"]
        self.assertEqual(self.run_step("list", "/logs")["observation"]["entries"], ["/logs/app.log"])
        self.assertEqual(self.run_step("stat", "/logs/app.log")["activity"], "no_growth_observed")
        with self.assertRaisesRegex(ValueError, "excluded"):
            self.run_step("read", "/logs/app.log")

    def test_leaf_link_can_point_to_a_matching_log_in_a_data_mount(self):
        self.policy["patterns"] = ["/service.log"]
        source = self.root / "service.log"
        source.symlink_to("/data/service/service.log")
        self.file.rename(self.directory / "service.log")
        result = self.run_step("stat", "/service.log")
        self.assertEqual(result["first"]["resolved_path"], "/data/service/service.log")
        source.unlink()
        source.symlink_to("/data/service/private.key")
        with self.assertRaisesRegex(ValueError, "outside_configured"):
            self.run_step("read", "/service.log")

    def test_direct_mount_and_listing_limit(self):
        self.policy["patterns"] = ["/data/service/*.log"]
        for n in range(50):
            (self.directory / f"{n}.log").touch()
        listing = self.run_step("list", "/data/service")["observation"]
        self.assertTrue(listing["truncated"])
        self.assertEqual(len(listing["entries"]), 50)
        self.assertEqual(self.run_step("stat", "/data/service/app.log")["activity"], "no_growth_observed")

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
        with self.assertRaisesRegex(ValueError, "outside_configured"):
            self.run_step("read", listing["entries"][0])

    def test_collector_metadata_requires_a_mapped_path_and_respects_nested_mounts(self):
        with self.assertRaisesRegex(ValueError, "outside_target_mounts"):
            self.run_step("list", "/unmapped", path_space="collector")
        with self.assertRaisesRegex(ValueError, "outside_scope"):
            self.run_step("list", str(self.volume / "secret"), path_space="collector")
        self.policy["mounts"]["/another"] = str(self.volume)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.run_step("stat", str(self.file), path_space="collector")

    def test_single_file_mount_metadata(self):
        self.policy["mounts"]["/single"] = str(self.file)
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
        self.assertEqual((result["content"], result["returned_bytes"]), ("ld", 2))

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
