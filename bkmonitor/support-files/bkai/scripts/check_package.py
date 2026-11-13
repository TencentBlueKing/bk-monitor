"""Check the distributable Skill package before previewing or synchronizing it."""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path, PurePosixPath
from posixpath import normpath
import re
import sys
from zipfile import BadZipFile, ZipFile

import yaml


SKILLS = frozenset(
    {
        "bkm-grafana-dashboard",
        "bklog-query",
        "bklog-ingest",
        "bkm-alert-assign",
        "bkm-alert-create-verify",
        "bkm-data-fetcher",
    }
)
PUBLIC_DOMAINS = frozenset({"github.com", "pypi.org", "opensource.org", "bkai.tencent.com", "kubernetes.io"})
DOMAIN = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|net|org|cn|io|dev|cloud|internal|local)\b")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6 = re.compile(r"(?i)(?<![\w:])(?:[a-f0-9]{0,4}:){2,}[a-f0-9:.]*(?![\w:])")
IDENTIFIER = re.compile(r"(?i)\b[a-f0-9]{16,}\b|/Users/[^\s`]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}")
SECRET = re.compile(r"""(?i)\b[A-Z_]*(?:APP_SECRET|ACCESS_TOKEN|API_KEY|PASSWORD)['"]?\s*[:=]\s*['"]?[^\s'"#},]+""")
ACCOUNT_EXAMPLE = re.compile(r"""(?i)把\s+[`'"]?[a-z][a-z0-9_.-]{2,}[`'"]?\s+加入""")
RESOURCE_ID_EXAMPLE = re.compile(
    r'"(?:bk_biz_id|bk_host_id|index_set_id|strategy_id|action_config_id)"\s*:\s*"?\d+'
    r"|strategy_id:\d+|(?:策略|套餐)\s+\d{3,}|\d{3,}\s+(?:HTTP\s+回调套餐|套餐)"
)
FORBIDDEN_NAMES = frozenset(
    {
        ".git",
        ".env",
        ".bkai-meta.json",
        ".DS_Store",
        "__pycache__",
        "tests",
        "node_modules",
        "bkmonitor-files",
        ".storage",
        ".venv",
        ".ruff_cache",
    }
)


def check_text(name: str, content: str) -> list[str]:
    errors = []
    for number, line in enumerate(content.splitlines(), 1):
        if any(
            domain.lower() not in PUBLIC_DOMAINS
            and domain.lower() != "example.com"
            and not domain.lower().endswith(".example.com")
            for domain in DOMAIN.findall(line)
        ):
            errors.append(f"{name}:{number}: unapproved domain")
        for candidate in IPV4.findall(line) + IPV6.findall(line):
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            errors.append(f"{name}:{number}: replace literal network addresses with placeholders")
        if IDENTIFIER.search(line):
            errors.append(f"{name}:{number}: identity, machine path, or fixed environment identifier")
        if SECRET.search(line):
            errors.append(f"{name}:{number}: nonempty credential assignment")
        if ACCOUNT_EXAMPLE.search(line):
            errors.append(f"{name}:{number}: use a placeholder for an account example")
        if name.endswith(".md") and RESOURCE_ID_EXAMPLE.search(line):
            errors.append(f"{name}:{number}: use placeholders for business resource IDs in documentation")
    return errors


def check_entry(name: str, data: bytes) -> list[str]:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return [f"{name}: entry escapes the package"]
    if (
        FORBIDDEN_NAMES.intersection(path.parts)
        or path.name.startswith("test_")
        or path.suffix in {".pyc", ".pyo", ".zip", ".pem", ".key"}
    ):
        return [f"{name}: local, generated, or credential file"]
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{name}: binary files require a separate publication review"]
    errors = check_text(name, content)
    if "-----BEGIN " in content and "PRIVATE KEY-----" in content:
        errors.append(f"{name}: private key material")
    return errors


def check_directory(root: Path) -> list[str]:
    if root.is_symlink():
        return ["package: symbolic links are not distributable"]
    errors = []
    links = [path for path in root.rglob("*") if path.is_symlink()]
    if links:
        return [f"{path.relative_to(root)}: symbolic links are not distributable" for path in links]
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_file():
            errors.extend(check_entry(name, path.read_bytes()))
            if path.suffix == ".md":
                content = path.read_text(encoding="utf-8")
                for target in re.findall(r"\]\(([^)]+)\)", content):
                    if target.startswith(("https://", "http://", "mailto:", "#")):
                        continue
                    relative = target.split("#", 1)[0]
                    resolved = (path.parent / relative).resolve()
                    parts = path.relative_to(root).parts
                    boundary = root / "skills" / parts[1] if len(parts) > 2 and parts[0] == "skills" else root
                    if not resolved.is_relative_to(boundary.resolve()) or not resolved.exists():
                        errors.append(f"{name}: missing or out-of-package Markdown reference")
    manifest = yaml.safe_load((root / "bkai.yaml").read_text(encoding="utf-8"))
    expected = {f"skills/{name}" for name in SKILLS}
    resources = manifest.get("resources", [])
    if len(resources) != len(expected) or set(resources) != expected:
        errors.append(f"bkai.yaml: declare exactly the {len(SKILLS)} supported Skills")
        return errors
    for name in sorted(SKILLS):
        skill = root / "skills" / name
        declaration = yaml.safe_load((skill / "skill.yaml").read_text(encoding="utf-8"))
        metadata = declaration.get("metadata", {})
        options = declaration.get("spec", {})
        if declaration.get("kind") != "Skill" or metadata.get("code") != name:
            errors.append(f"{name}: mismatched Skill declaration")
        if metadata.keys() - {"code", "name", "description"}:
            errors.append(f"{name}: deployment identity and version belong outside the distributable metadata")
        if options.get("generate_type") != "global" or options.get("is_public") is not True:
            errors.append(f"{name}: official Skills must declare global visibility")
        if not metadata.get("name", "").startswith(("监控平台-", "日志平台-")):
            errors.append(f"{name}: use the product name followed by a Chinese resource name")
        content = (skill / "SKILL.md").read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            errors.append(f"{name}: missing Skill frontmatter")
            continue
        frontmatter = yaml.safe_load(content.split("---", 2)[1])
        if frontmatter.get("name") != name or not frontmatter.get("description"):
            errors.append(f"{name}: invalid name or description")
        if frontmatter.keys() - {"name", "description"}:
            errors.append(f"{name}: remove environment-specific Skill frontmatter")
    return errors


def check_archive(path: Path) -> list[str]:
    errors = []
    with ZipFile(path) as archive:
        names = archive.namelist()
        if "SKILL.md" not in names or len(names) != len(set(names)):
            errors.append(f"{path.name}: missing root SKILL.md or duplicate entries")
        for entry in archive.infolist():
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                errors.append(f"{entry.filename}: symbolic link in archive")
            if not entry.is_dir():
                data = archive.read(entry)
                errors.extend(check_entry(entry.filename, data))
                if entry.filename.endswith(".md"):
                    content = data.decode("utf-8", errors="replace")
                    for target in re.findall(r"\]\(([^)]+)\)", content):
                        if target.startswith(("https://", "http://", "mailto:", "#")):
                            continue
                        relative = target.split("#", 1)[0]
                        resolved = normpath(str(PurePosixPath(entry.filename).parent / relative))
                        if resolved not in names:
                            errors.append(f"{entry.filename}: missing or out-of-package Markdown reference in ZIP")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1] / "package")
    parser.add_argument("--archive", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        errors = check_directory(args.package)
        for archive in args.archive:
            errors.extend(check_archive(archive))
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, yaml.YAMLError) as error:
        print(f"Package check failed: {type(error).__name__}", file=sys.stderr)
        return 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Checked {len(SKILLS)} Skills and {len(args.archive)} archives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
