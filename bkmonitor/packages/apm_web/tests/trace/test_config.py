import pytest

from apm_web.trace.diagram.config import DiagramConfigController


class TestDiagramConfigController:
    @pytest.mark.parametrize(
        "raw_config,expected",
        [
            (
                {
                    "topo": {
                        "tree_building_config": {
                            "min_group_members": 7,
                            "with_group": True,
                            "group_ignore_sequence": True,
                        }
                    }
                },
                {
                    "topo": {
                        "tree_building_config": {
                            "min_group_members": 7,
                            "with_group": True,
                            "group_ignore_sequence": True,
                        }
                    },
                    "flamegraph": None,
                    "sequence": None,
                    "statistics": None,
                },
            ),
        ],
    )
    def test_load(self, raw_config, expected):
        controller = DiagramConfigController.read(raw_config)
        for k, v in expected.items():
            if v is None:
                assert getattr(controller, k) is None
                continue

            for config_key, config_value in v["tree_building_config"].items():  # noqa
                assert getattr(getattr(controller, k).tree_building_config, config_key) == config_value
