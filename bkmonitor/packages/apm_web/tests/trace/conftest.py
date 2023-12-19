import pytest

from apm_web.trace.diagram.base import TreeBuildingConfig


@pytest.fixture
def default_trace_tree_config() -> TreeBuildingConfig:
    return TreeBuildingConfig.default()


@pytest.fixture
def forced_group_trace_tree_config() -> TreeBuildingConfig:
    return TreeBuildingConfig(min_group_members=2, with_group=True)


@pytest.fixture
def group_and_parallel_trace_tree_config() -> TreeBuildingConfig:
    return TreeBuildingConfig(min_group_members=2, with_group=True, with_parallel_detection=True)


@pytest.fixture
def group_and_parallel_virtual_return_trace_tree_config() -> TreeBuildingConfig:
    return TreeBuildingConfig(
        min_group_members=2, with_group=True, with_parallel_detection=True, with_virtual_return=True
    )
