import asyncio
import subprocess
import time
from unittest import mock

import pytest
from pyppeteer.connection import Connection
from pyppeteer.util import get_free_port

from alarm_backends.core.context import chart
from bkmonitor.browser import browser


async def hang(_):
    await asyncio.sleep(60)


async def boom(_):
    raise RuntimeError("Browser closed unexpectedly")


@pytest.mark.parametrize("render", [hang, boom])
def test_get_chart_image_kills_browser_when_render_fails(render):
    with (
        mock.patch.object(chart, "RENDER_TIMEOUT", 0.1),
        mock.patch.object(chart, "render_html", render),
        mock.patch.object(chart, "kill_browser") as kill,
    ):
        start = time.monotonic()
        assert chart.get_chart_image({"series": []}) == ""

    assert time.monotonic() - start < 5
    kill.assert_called_once_with()


class HangingLauncher:
    """chrome 已拉起但调试 WebSocket 建连失败，pyppeteer 卡在首个 CDP 请求上"""

    def __init__(self, *args, **kwargs):
        self.chromeClosed = False
        self._cleanup_tmp_user_data_dir = mock.Mock()

    async def launch(self):
        self.proc = subprocess.Popen(["sleep", "60"])
        self.connection = Connection(f"ws://127.0.0.1:{get_free_port()}", asyncio.get_running_loop())
        await self.connection.send("Target.setDiscoverTargets", {"discover": True})


def test_kill_browser_cleans_up_when_launch_times_out():
    loop = asyncio.new_event_loop()
    with (
        mock.patch.object(browser, "Launcher", HangingLauncher),
        mock.patch.object(browser, "get_browser_path", return_value="chromium"),
        mock.patch.multiple(browser, _launcher=None, _browser=None, _browser_connected=False, _browser_start_time=0),
    ):
        try:
            for _ in range(3):
                with pytest.raises(asyncio.TimeoutError):
                    loop.run_until_complete(asyncio.wait_for(browser.get_browser(), 0.1))
                launcher = browser._launcher
                try:
                    browser.kill_browser()
                    returncode = launcher.proc.poll()
                finally:
                    launcher.proc.kill()
                    launcher.proc.wait()

                assert returncode is not None
                assert launcher.chromeClosed is True
                launcher._cleanup_tmp_user_data_dir.assert_called_once_with()
                assert browser._launcher is None
                assert browser._browser is None
                assert not asyncio.all_tasks(loop)
                assert browser._browser_lock.acquire(blocking=False)
                browser._browser_lock.release()
        finally:
            loop.close()
