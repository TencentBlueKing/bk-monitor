import pytest

from . import install_ai_agent_runtime as runtime


def test_parse_packages_accepts_pinned_specs_and_verified_direct_urls():
    url = "https://packages.example.org/pkg-1.0-py3-none-any.whl#sha256=" + "a" * 64
    specs = runtime.parse_packages(f'bkai-hermes-core==0.8.2.dev1 "bkai-otel-hermes @ {url}"')
    assert specs == ["bkai-hermes-core==0.8.2.dev1", f"bkai-otel-hermes @ {url}"]


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "--extra-index-url https://packages.example.org/simple/",
        "bkai-hermes-core==0.8.2.dev1 --no-deps",
        "https://packages.example.org/pkg.whl",
        "https://user:pass@packages.example.org/pkg.whl#sha256=" + "a" * 64,
        "bkai-hermes-core @ https://packages.example.org/pkg.whl?token=x#sha256=" + "a" * 64,
        "bkai-hermes-core @ http://packages.example.org/pkg.whl#sha256=" + "a" * 64,
    ],
)
def test_parse_packages_rejects_empty_options_or_unsafe_urls(raw):
    with pytest.raises(ValueError):
        runtime.parse_packages(raw)


@pytest.mark.parametrize(
    "url",
    [
        "http://packages.example.org/simple/",
        "https://user:secret@packages.example.org/simple/",
        "https://packages.example.org/simple/?token=abc",
        "https://packages.example.org/simple/#frag",
    ],
)
def test_validate_index_url_rejects_credentials_query_or_non_https(url):
    with pytest.raises(ValueError, match="AI_AGENT_PIP_EXTRA_INDEX_URL"):
        runtime.validate_index_url(url, "AI_AGENT_PIP_EXTRA_INDEX_URL")


def test_collect_host_constraints_pins_installed_direct_deps_only(monkeypatch, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "bkmonitor"
dependencies = [
    "Django==4.2.27",
    "pillow==11.2.1",
    "bk-audit[opentelemetry]==1.2.2",
    "bk-monitor-base",
]

[dependency-groups]
aidev = [
    "openai==2.38.0",
    "missing-optional-pkg>=1.0",
]
""",
        encoding="utf-8",
    )
    installed = {
        "django": "4.2.27",
        "pillow": "11.2.1",
        "bk-audit": "1.2.2",
        "bk-monitor-base": "0.1.0",
        "openai": "2.38.0",
    }

    def fake_version(name):
        if name not in installed:
            raise runtime.PackageNotFoundError(name)
        return installed[name]

    monkeypatch.setattr(runtime, "version", fake_version)
    assert runtime.collect_host_constraints(pyproject) == {
        "bk-audit": "1.2.2",
        "django": "4.2.27",
        "openai": "2.38.0",
        "pillow": "11.2.1",
    }


def test_verify_host_constraints_unchanged_detects_drift(monkeypatch):
    monkeypatch.setattr(runtime, "version", lambda name: {"pillow": "12.0.0", "django": "4.2.27"}[name])
    with pytest.raises(RuntimeError, match="pillow: expected 11.2.1, got 12.0.0"):
        runtime.verify_host_constraints_unchanged({"django": "4.2.27", "pillow": "11.2.1"})


def test_build_pip_command_uses_pip_config_secret_without_isolated(tmp_path):
    pip_conf = tmp_path / "pip.conf"
    pip_conf.write_text("[global]\nindex-url = https://mirrors.example.org/simple/\n", encoding="utf-8")
    constraints = tmp_path / "host-constraints.txt"

    cmd, env = runtime.build_pip_command(
        ["bkai-hermes-core==0.8.2.dev1", "bkai-otel-hermes==1.3.0"],
        constraints,
        pip_config_secret=pip_conf,
        index_url="https://pypi.org/simple/",
        extra_index_url="https://internal.example.org/simple/",
    )

    assert "--isolated" not in cmd
    assert "--index-url" not in cmd
    assert "--extra-index-url" in cmd
    assert "https://internal.example.org/simple/" in cmd
    assert "--no-binary=pillow" in cmd
    assert "--upgrade-strategy=only-if-needed" in cmd
    assert env["PIP_CONFIG_FILE"] == str(pip_conf)


def test_build_pip_command_uses_index_args_when_no_secret(tmp_path):
    constraints = tmp_path / "host-constraints.txt"
    cmd, env = runtime.build_pip_command(
        ["bkai-hermes-core==0.8.2.dev1", "bkai-otel-hermes==1.3.0"],
        constraints,
        pip_config_secret=tmp_path / "missing.conf",
        index_url="https://mirrors.example.org/pypi/simple/",
        extra_index_url="https://internal.example.org/simple/",
    )

    assert "--isolated" in cmd
    assert "--index-url" in cmd
    assert "https://mirrors.example.org/pypi/simple/" in cmd
    assert "--extra-index-url" in cmd
    assert "https://internal.example.org/simple/" in cmd
    assert env["PIP_CONFIG_FILE"] == runtime.os.devnull
