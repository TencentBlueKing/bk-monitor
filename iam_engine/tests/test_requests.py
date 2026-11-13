from collections import UserDict
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from iam_engine.core import requests
from iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject


def test_default_resource_attributes_share_an_immutable_empty_mapping():
    first = ResourceInstance(type="space", id="1")
    second = ResourceInstance(type="space", id="2")

    assert first.attributes == {}
    assert second.attributes is first.attributes
    with pytest.raises(TypeError):
        first.attributes["extra"] = "value"
    assert second.attributes == {}


def test_default_resource_attributes_do_not_allocate_mapping_proxies(monkeypatch):
    def unexpected_allocation(*args, **kwargs):
        raise AssertionError("default resource attributes must reuse the empty mapping")

    monkeypatch.setattr(requests, "MappingProxyType", unexpected_allocation)

    assert ResourceInstance(type="space", id="1").attributes == {}
    assert ResourceInstance(type="space", id="2").attributes == {}


@pytest.mark.parametrize("values", [{}, {"key": "original"}])
@pytest.mark.parametrize("wrap", [dict, MappingProxyType, UserDict])
def test_explicit_resource_attributes_keep_a_readonly_snapshot(values, wrap):
    source = dict(values)
    attributes = wrap(source)
    resource = ResourceInstance(type="space", id="1", attributes=attributes)
    expected = dict(attributes)

    source["key"] = "changed"
    source["added"] = "later"
    if isinstance(attributes, UserDict | dict):
        attributes["key"] = "changed"
        attributes["added"] = "later"

    assert dict(resource.attributes) == expected
    assert resource.attributes is not attributes
    with pytest.raises(TypeError):
        resource.attributes["key"] = "changed"


def test_resource_attributes_preserve_shallow_copy_semantics():
    nested = ["original"]
    source = {"nested": nested}
    resource = ResourceInstance(type="space", id="1", attributes=source)

    source["replacement"] = "not copied"
    nested.append("changed")

    assert dict(resource.attributes) == {"nested": ["original", "changed"]}
    assert resource.attributes["nested"] is nested


def test_falsy_explicit_mapping_is_still_snapshotted():
    class FalsyMapping(UserDict):
        def __bool__(self):
            return False

    source = FalsyMapping({"key": "original"})
    resource = ResourceInstance(type="space", id="1", attributes=source)
    source["key"] = "changed"

    assert dict(resource.attributes) == {"key": "original"}


def test_resource_identity_ancestors_and_frozen_fields_are_unchanged():
    parent = ResourceInstance(type="space", id="1")
    ancestors = (parent,)
    resource = ResourceInstance(
        type="dashboard", id="example", system="monitor", name="Example", ancestor_chain=ancestors
    )

    assert (resource.type, resource.id, resource.system, resource.name) == (
        "dashboard",
        "example",
        "monitor",
        "Example",
    )
    assert resource.ancestor_chain is ancestors
    assert resource == ResourceInstance(
        type="dashboard", id="example", system="monitor", name="Example", ancestor_chain=ancestors, attributes={}
    )
    with pytest.raises(FrozenInstanceError):
        resource.id = "changed"


@pytest.mark.parametrize("attributes", [None, 1])
def test_invalid_resource_attributes_keep_failing(attributes):
    with pytest.raises(TypeError):
        ResourceInstance(type="space", id="1", attributes=attributes)


@pytest.mark.parametrize(
    "factory,field",
    [
        (lambda **kwargs: Subject(id="alice", **kwargs), "attributes"),
        (lambda **kwargs: AuthRequest(Subject(id="alice"), "view_business", **kwargs), "environment"),
        (lambda **kwargs: BatchAuthRequest(Subject(id="alice"), ("view_business",), (), **kwargs), "environment"),
    ],
)
def test_other_request_mappings_keep_default_and_explicit_snapshot_contract(factory, field):
    default = factory()
    source = {}
    explicit = factory(**{field: source})
    source["extra"] = "later"

    assert getattr(default, field) == {}
    assert getattr(explicit, field) == {}
    with pytest.raises(TypeError):
        getattr(default, field)["extra"] = "changed"
