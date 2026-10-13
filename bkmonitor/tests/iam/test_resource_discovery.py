"""Real resource discovery must register nested IAM apps only once."""

from types import SimpleNamespace

from core.drf_resource.management import finder


def test_nested_app_is_discovered_by_parent_only(monkeypatch, tmp_path):
    parent = SimpleNamespace(name="parent", path=str(tmp_path / "parent"))
    child = SimpleNamespace(name="parent.iam", path=str(tmp_path / "parent/iam"))
    unrelated = SimpleNamespace(name="other", path=str(tmp_path / "other"))
    calls = []
    monkeypatch.setattr(finder.apps, "get_app_configs", lambda: [child, unrelated, parent])
    monkeypatch.setattr(finder, "RESOURCE_DIRS", [])
    monkeypatch.setattr(finder.ResourceFinder, "find", lambda self, path, **kwargs: calls.append(path) or [])
    finder.ResourceFinder()
    assert calls == [unrelated.path, parent.path]


def test_explicit_child_selection_still_discovers_child(monkeypatch, tmp_path):
    parent = SimpleNamespace(name="parent", path=str(tmp_path / "parent"))
    child = SimpleNamespace(name="parent.iam", path=str(tmp_path / "parent/iam"))
    calls = []
    monkeypatch.setattr(finder.apps, "get_app_configs", lambda: [parent, child])
    monkeypatch.setattr(finder, "RESOURCE_DIRS", [])
    monkeypatch.setattr(finder.ResourceFinder, "find", lambda self, path, **kwargs: calls.append(path) or [])
    finder.ResourceFinder(app_names=["parent.iam"])
    assert calls == [child.path]
