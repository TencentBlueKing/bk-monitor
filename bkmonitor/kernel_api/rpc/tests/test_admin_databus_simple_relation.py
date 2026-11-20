from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import datalink

TARGET = {"bk_tenant_id": "tenant-a", "namespace": "bkmonitor", "name": "sample"}


@pytest.mark.parametrize("dry_run", [True, False])
def test_simple_relation_uses_target_and_propagates_skip_reason(dry_run):
    model = datalink.COMPONENT_CLASS_MAP["Databus"]
    with (
        patch.object(model, "objects") as objects,
        patch.object(datalink.transaction, "atomic", return_value=nullcontext()),
        patch.object(datalink, "rebuild_simple_databus_relation") as rebuild,
    ):
        lookup = objects if dry_run else objects.select_for_update.return_value
        target = SimpleNamespace(**TARGET, data_link_name="")
        lookup.get.return_value = target
        rebuild.side_effect = datalink.SimpleDatabusRelationError("missing storage for example.cpu")
        operation = datalink.preview_simple_relation if dry_run else datalink.rebuild_simple_relation
        with pytest.raises(CustomException, match="missing storage for example.cpu"):
            operation(TARGET)
        lookup.get.assert_called_once_with(**TARGET)
        rebuild.assert_called_once_with(target, dry_run=dry_run, raise_on_skip=True)
        target.data_link_name = "existing-link"
        with pytest.raises(CustomException, match="existing-link"):
            operation(TARGET)
        rebuild.assert_called_once()
