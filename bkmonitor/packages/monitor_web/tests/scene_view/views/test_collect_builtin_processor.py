import pytest

from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin.collect import CollectBuiltinProcessor


class TestCollectBuiltinProcessor:
    @pytest.mark.django_db
    def test_get_view_config_only_simple_info_skips_full_render(self, monkeypatch):
        view = SceneViewModel(
            bk_biz_id=2,
            scene_id="collect_1",
            id="default",
            name="Default",
            mode="auto",
            variables=[],
            options={"show_panel_count": True},
        )

        monkeypatch.setattr(
            CollectBuiltinProcessor,
            "get_default_view_config",
            classmethod(
                lambda cls, bk_biz_id, scene_id: {
                    "mode": "auto",
                    "options": {"show_panel_count": False},
                }
            ),
        )
        monkeypatch.setattr(
            "monitor_web.scene_view.builtin.collect.get_simple_panel_count",
            lambda _view: 3,
        )

        def _raise_if_called(*args, **kwargs):
            raise AssertionError("full panel rendering should be skipped for only_simple_info")

        monkeypatch.setattr(CollectBuiltinProcessor, "get_auto_view_panels", classmethod(_raise_if_called))

        result = CollectBuiltinProcessor.get_view_config(view, {"only_simple_info": True})

        assert result["mode"] == "auto"
        assert len(result["panels"]) == 3
        assert result["options"]["show_panel_count"] is True
