"""Install optional AI agent runtime packages into the locked monitor venv at build time."""

from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
from urllib.parse import urlsplit

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

DEFAULT_PYPROJECT_PATH = Path("/run/monitor-pyproject.toml")
DEFAULT_PIP_CONFIG_SECRET = Path("/run/secrets/python_package_config")
EXCLUDED_HOST_PACKAGES = {"bk-monitor-base", "bkmonitor"}
SHA256_FRAGMENT_RE = re.compile(r"sha256=[0-9a-f]{64}")


def validate_index_url(url: str, variable: str) -> str:
    value = url.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or any(char.isspace() for char in value)
    ):
        raise ValueError(f"{variable} must be a credential-free HTTPS index URL without query or fragment")
    return value


def validate_wheel_url(url: str, variable: str) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or not parts.path.endswith(".whl")
        or not SHA256_FRAGMENT_RE.fullmatch(parts.fragment)
        or any(char.isspace() for char in url)
    ):
        raise ValueError(f"{variable} requires a credential-free HTTPS wheel URL with a SHA256 fragment")
    return url


def parse_packages(raw: str, variable: str = "AI_AGENT_HERMES_PACKAGES") -> list[str]:
    tokens = shlex.split(raw or "")
    if not tokens:
        raise ValueError(f"{variable} must specify at least one runtime package")

    packages: list[str] = []
    for token in tokens:
        if token.startswith("-"):
            raise ValueError(f"{variable} must not contain pip CLI options: {token}")
        if "://" in token and "@" not in token:
            validate_wheel_url(token, variable)
            packages.append(token)
            continue
        req = Requirement(token)
        if req.url:
            validate_wheel_url(req.url, variable)
        packages.append(token)
    return packages


def collect_host_constraints(pyproject_path: Path) -> dict[str, str]:
    """Pin all direct monitor dependencies (main + aidev group) to their currently installed versions."""
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    raw_specs: list[str] = []
    raw_specs.extend(data.get("project", {}).get("dependencies", []))
    raw_specs.extend(data.get("dependency-groups", {}).get("aidev", []))

    constraints: dict[str, str] = {}
    for spec in raw_specs:
        name = canonicalize_name(Requirement(spec).name)
        if name in EXCLUDED_HOST_PACKAGES or name in constraints:
            continue
        try:
            constraints[name] = version(name)
        except PackageNotFoundError:
            continue
    return dict(sorted(constraints.items()))


def verify_host_constraints_unchanged(expected: dict[str, str]) -> None:
    drifted: list[str] = []
    for name, expected_version in expected.items():
        try:
            actual_version = version(name)
        except PackageNotFoundError:
            drifted.append(f"{name}: expected {expected_version}, now missing")
            continue
        if actual_version != expected_version:
            drifted.append(f"{name}: expected {expected_version}, got {actual_version}")
    if drifted:
        raise RuntimeError("Direct host dependencies changed during runtime installation: " + "; ".join(drifted))


def build_pip_command(
    packages: list[str],
    constraints_file: Path,
    *,
    pip_config_secret: Path = DEFAULT_PIP_CONFIG_SECRET,
    index_url: str = "",
    extra_index_url: str = "",
) -> tuple[list[str], dict[str, str]]:
    has_pip_config = pip_config_secret.is_file() and pip_config_secret.stat().st_size > 0
    validated_index = validate_index_url(index_url, "pypi_index_url")
    validated_extra = validate_index_url(extra_index_url, "AI_AGENT_PIP_EXTRA_INDEX_URL")

    cmd = [sys.executable, "-m", "pip"]
    env = dict(os.environ)
    if has_pip_config:
        env["PIP_CONFIG_FILE"] = str(pip_config_secret)
    else:
        cmd.append("--isolated")
        env["PIP_CONFIG_FILE"] = os.devnull

    cmd.extend(
        [
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-binary=pillow",
            "--upgrade-strategy=only-if-needed",
            "-c",
            str(constraints_file),
        ]
    )

    if not has_pip_config and validated_index:
        cmd.extend(["--index-url", validated_index])
    if validated_extra:
        cmd.extend(["--extra-index-url", validated_extra])

    cmd.extend(packages)
    return cmd, env


def main() -> None:
    packages = parse_packages(os.environ.get("AI_AGENT_HERMES_PACKAGES", ""))
    pyproject_path = Path(os.environ.get("MONITOR_PYPROJECT_PATH", str(DEFAULT_PYPROJECT_PATH)))
    pip_config_secret = Path(os.environ.get("AI_AGENT_PIP_CONFIG_PATH", str(DEFAULT_PIP_CONFIG_SECRET)))

    host_constraints = collect_host_constraints(pyproject_path)
    if not host_constraints:
        raise RuntimeError(f"No installed host dependencies resolved from {pyproject_path}")

    with TemporaryDirectory() as tmp:
        constraints_file = Path(tmp) / "host-constraints.txt"
        constraints_file.write_text(
            "\n".join(f"{name}=={ver}" for name, ver in host_constraints.items()) + "\n",
            encoding="utf-8",
        )
        cmd, env = build_pip_command(
            packages,
            constraints_file,
            pip_config_secret=pip_config_secret,
            index_url=os.environ.get("pypi_index_url", ""),
            extra_index_url=os.environ.get("AI_AGENT_PIP_EXTRA_INDEX_URL", ""),
        )
        subprocess.run(cmd, check=True, env=env)

    verify_host_constraints_unchanged(host_constraints)


if __name__ == "__main__":
    main()
