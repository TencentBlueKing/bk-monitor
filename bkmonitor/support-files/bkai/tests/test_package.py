"""Exercise real Skill archives and package synchronization with an in-memory client."""

from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

try:
    from bkai_init import BkaiInit
    from bkai_init.utils.archive import build_skill_zip
    from bkai_init.utils.manifest import load_package, load_skill
except ModuleNotFoundError as error:
    if error.name != "bkai_init":
        raise
    BkaiInit = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_package  # noqa: E402
import run_bkai  # noqa: E402


class RecordingClient:
    def __init__(self):
        self.uploads = []
        self.writes = []
        self.reads = []

    def list_skills(self, space_id, code):
        self.reads.append((space_id, code))
        return []

    def upload_skill(self, archive, space_id):
        errors = check_package.check_archive(archive)
        if errors:
            raise AssertionError(errors)
        with ZipFile(archive) as content:
            self.uploads.append((space_id, set(content.namelist())))
        return {"url": "https://files.example.com/skill.zip", "file_name": archive.name}

    def upsert_skill(self, payload):
        self.writes.append(payload)
        return {"id": len(self.writes), "created": True, "version": "0.0.1"}

    def __getattr__(self, name):
        raise AssertionError(f"Unexpected platform operation: {name}")


@unittest.skipIf(BkaiInit is None, "Install bkai-init 0.1.6 for the standalone delivery tests")
class PackageTests(unittest.TestCase):
    def test_local_validation_needs_no_credentials_or_remote_client(self):
        report = BkaiInit(space="example-space").validate(ROOT / "package/bkai.yaml")
        self.assertEqual(len(report.events), 6)
        self.assertEqual(check_package.check_directory(ROOT / "package"), [])

    def test_sync_uploads_only_six_clean_skills_to_explicit_space(self):
        client = RecordingClient()
        BkaiInit(space="example-space", client=client).sync(ROOT / "package/bkai.yaml")
        self.assertEqual(len(client.uploads), 6)
        self.assertEqual({item["skill_code"] for item in client.writes}, check_package.SKILLS)
        for payload in client.writes:
            self.assertEqual(payload["space_id"], "example-space")
            self.assertNotIn("version", payload)
            self.assertIs(payload["is_public"], False)
        for space, names in client.uploads:
            self.assertEqual(space, "example-space")
            self.assertIn("SKILL.md", names)
            self.assertIn("skill.yaml", names)
        dashboard = next(names for _, names in client.uploads if "scripts/dashboard_tools.py" in names)
        self.assertIn("skills/dash-create/SKILL.md", dashboard)
        self.assertIn("skills/dash-edit/SKILL.md", dashboard)

    def test_plan_reads_without_uploading_or_writing(self):
        client = RecordingClient()
        BkaiInit(space="example-space", client=client).plan(ROOT / "package/bkai.yaml")
        self.assertEqual(len(client.reads), 6)
        self.assertEqual(client.writes, [])
        self.assertEqual(client.uploads, [])

    def test_selected_resource_does_not_update_other_skills(self):
        client = RecordingClient()
        BkaiInit(space="example-space", client=client).sync(
            ROOT / "package/bkai.yaml", resources={"skill/bk-log-query"}
        )
        self.assertEqual([payload["skill_code"] for payload in client.writes], ["bk-log-query"])

    def test_actual_archives_are_deterministic_and_include_references(self):
        package = load_package(ROOT / "package/bkai.yaml")
        with tempfile.TemporaryDirectory() as temporary:
            for resource in package.resources:
                skill = load_skill(resource, package.version)
                first = build_skill_zip(skill, Path(temporary) / "first.zip")
                second = build_skill_zip(skill, Path(temporary) / "second.zip")
                self.assertEqual(first.read_bytes(), second.read_bytes())
                self.assertEqual(check_package.check_archive(first), [])
                with ZipFile(first) as content:
                    self.assertTrue(any(name.startswith("references/") for name in content.namelist()))


class PublicationCheckTests(unittest.TestCase):
    def test_rejects_domains_network_addresses_identities_and_credentials(self):
        samples = [
            "https://" + "private" + ".internal",
            "10" + ".1.2.3",
            "fd00" + ":" + ":1",
            "a" * 24,
            "ACCESS_TOKEN" + ": 'synthetic-value'",
            "把 example_user 加入示例告警组A",
            "把 `example_user` 加入示例告警组A",
            '{"bk_biz_id": 7}',
            '{"index_set_id": "8"}',
            '{"bk_host_id": 9}',
            "给策略绑定 123 HTTP 回调套餐",
            "strategy_id:123",
        ]
        for sample in samples:
            with self.subTest(sample_type=samples.index(sample)):
                errors = check_package.check_text("example.md", sample)
                self.assertTrue(errors)
                self.assertNotIn(sample, "\n".join(errors))
        self.assertEqual(check_package.check_text("example.md", "把 `<user-name>` 加入示例告警组A"), [])

    def test_rejects_credential_files_and_outside_archive_entries(self):
        for name in [".env", "credentials.key", "../outside.md", "/outside.md"]:
            self.assertTrue(check_package.check_entry(name, b"synthetic"))

    def test_rejects_symlinks_before_reading_their_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bkai.yaml").symlink_to(root / "unreadable-target")
            with patch.object(Path, "read_text", side_effect=AssertionError("must not follow the link")):
                self.assertTrue(check_package.check_directory(root))

    def test_rejects_links_leaving_the_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            shutil.copytree(ROOT / "package", root)
            (root / "example.md").write_text("[outside](../outside.md)")
            self.assertTrue(any("out-of-package" in error for error in check_package.check_directory(root)))

    def test_skill_references_cannot_depend_on_another_skill_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            shutil.copytree(ROOT / "package", root)
            reference = root / "skills/bk-log-query/references/cross.md"
            reference.write_text("[other](../../bk-log-ingest/SKILL.md)")
            self.assertTrue(any("out-of-package" in error for error in check_package.check_directory(root)))

    def test_archive_checks_references_inside_each_individual_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "skill.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("SKILL.md", "[missing](references/missing.md)")
            self.assertTrue(any("Markdown reference" in error for error in check_package.check_archive(path)))


class RunnerTests(unittest.TestCase):
    def test_missing_space_and_tenant_fail_before_platform_execution(self):
        scenarios = [({}, ["plan"]), ({"BKPAAS_MULTI_TENANT_MODE": "true"}, ["sync", "--space", "example-space"])]
        for environment, arguments in scenarios:
            with patch.dict(os.environ, environment, clear=True), patch.object(run_bkai.subprocess, "run") as run:
                with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                    run_bkai.main(arguments)
                run.assert_not_called()

    def test_sync_binds_explicit_space_and_tenant_with_confirmation(self):
        with patch.dict(os.environ, {"BKPAAS_MULTI_TENANT_MODE": "true"}, clear=True):
            with patch.object(run_bkai.subprocess, "run") as run:
                run.return_value.returncode = 0
                self.assertEqual(run_bkai.main(["sync", "--space", "example-space", "--tenant-id", "example"]), 0)
                command = run.call_args.args[0]
                self.assertEqual(command[command.index("--space") + 1], "example-space")
                self.assertEqual(command[command.index("--tenant-id") + 1], "example")
                self.assertIn("--confirm", command)

    def test_manifest_override_fails_before_platform_execution(self):
        for override in ["-f/another/package.yaml", "--file=/another/package.yaml", "--fi=/another/package.yaml"]:
            with patch.dict(os.environ, {}, clear=True), patch.object(run_bkai.subprocess, "run") as run:
                with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                    run_bkai.main(["sync", "--space", "example-space", override])
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
