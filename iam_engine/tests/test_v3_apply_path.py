"""Path serialization is independent of product authorization and IAM I/O."""

from types import SimpleNamespace

import pytest

from iam_engine.v3.apply import application_resource_path


@pytest.mark.parametrize("path", [None, ""])
def test_root_and_missing_ancestors_remain_leaf_only(path):
    resource = SimpleNamespace(system="product", type="space", id="-12", attribute={"_bk_iam_path_": path})
    assert application_resource_path(resource, leaf_name="Space") == [
        {"system": "product", "type": "space", "id": "-12", "name": "Space"}
    ]


@pytest.mark.parametrize("path", ["/space,-12/folder,3/", "/owner,space,-12/product,folder,3/"])
def test_multi_level_cross_system_paths_are_ordered_without_mutation(path):
    attrs = {"_bk_iam_path_": path}
    resource = SimpleNamespace(system="product", type="dashboard", id="leaf", attribute=attrs)
    nodes = application_resource_path(resource, leaf_name="Dashboard", resource_systems={"space": "owner"})
    assert nodes == [
        {"system": "owner", "type": "space", "id": "-12", "name": "space,-12"},
        {"system": "product", "type": "folder", "id": "3", "name": "folder,3"},
        {"system": "product", "type": "dashboard", "id": "leaf", "name": "Dashboard"},
    ]
    assert attrs == {"_bk_iam_path_": path}


def test_explicit_system_is_not_replaced_by_legacy_type_mapping():
    resource = SimpleNamespace(
        system="product", type="child", id="leaf", attribute={"_bk_iam_path_": "/other,space,2/"}
    )
    assert (
        application_resource_path(resource, leaf_name="", resource_systems={"space": "owner"})[0]["system"] == "other"
    )


def test_invalid_path_is_not_silently_converted_to_leaf_only():
    resource = SimpleNamespace(system="product", type="child", id="leaf", attribute={"_bk_iam_path_": "/invalid/"})
    with pytest.raises(ValueError, match="Invalid _bk_iam_path_"):
        application_resource_path(resource, leaf_name="")
