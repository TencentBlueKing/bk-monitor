import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import quote

from pyppeteer.browser import Browser, Page
from pyppeteer.errors import TimeoutError

from alarm_backends.service.report.utils import get_browser
from core.errors.common import CustomError

logger = logging.getLogger("alarm_backends")


@dataclass
class RenderDashboardConfig:
    """
    渲染仪表盘配置
    """

    bk_biz_id: int
    dashboard_uid: str
    width: int
    height: int
    panel_id: Optional[str] = None
    variables: Dict[str, List[str]] = field(default_factory=dict)
    start_time: int = field(default_factory=lambda: int(time.time() - 10800))
    end_time: int = field(default_factory=lambda: int(time.time()))
    # 是否需要标题，仅单个图表渲染时需要
    with_panel_title: bool = True
    # 像素比，默认为2，越大越清晰，但是图片大小也越大，最大值为4
    scale: int = 2


async def render_dashboard_panel(config: RenderDashboardConfig, timeout: int = 60) -> bytes:
    """
    渲染仪表盘面板
    :param timeout: 等待仪表盘加载完成的时间，单位秒
    """
    # 检查像素比
    if config.scale > 4:
        config.scale = 4

    # 生成变量url参数
    variables = []
    for key, value in config.variables.items():
        variables.append(f"var-{key}={quote(value)}")
    variables_str = "&".join(variables)
    if variables_str:
        variables_str = f"&{variables_str}"

    # 生成时间url参数
    time_str = f"&from={config.start_time*1000}&to={config.end_time*1000}"

    # 生成仪表盘链接
    prefix = "http://bk-monitor-api/grafana/"
    if config.panel_id:
        url = (
            f"{prefix}d-solo/{config.dashboard_uid}/?orgName={config.bk_biz_id}"
            f"{variables_str}&panelId={config.panel_id}{time_str}"
        )
    else:
        url = f"{prefix}d/{config.dashboard_uid}/?orgName={config.bk_biz_id}{variables_str}{time_str}&kiosk"

    # 获取浏览器
    browser: Browser = await get_browser()
    # 打开仪表盘链接，等待网络请求完成
    page = await browser.newPage()
    try:
        await page.goto(url, {"waitUntil": "networkidle0", "timeout": timeout * 1000})
    except TimeoutError:
        raise TimeoutError("wait for dashboard navigation timeout")

    # 判断是否是单个图表渲染
    if config.panel_id:
        content_selector = "div.panel-solo" if config.with_panel_title else "div.css-kuoxoh-panel-content"
        await page.setViewport({"width": config.width, "height": config.height, "deviceScaleFactor": config.scale})
    else:
        # 获取仪表盘高度
        scroll_div_selector = '[class="scrollbar-view"]'
        await page.waitForSelector(scroll_div_selector)
        heights = await page.evaluate(
            """
        (scrollDivSelector) => {
            const dashboardDiv = document.querySelector(scrollDivSelector);
            return { scroll: dashboardDiv.scrollHeight, client: dashboardDiv.clientHeight }
        }
        """,
            scroll_div_selector,
        )
        # 设置仪表盘大小
        await page.setViewport({"width": config.width, "height": heights["scroll"], "deviceScaleFactor": config.scale})
        content_selector = "div.react-grid-layout"

    # 等待2秒，等待图表渲染动画完成
    time.sleep(2)

    # 等待图表渲染动画完成
    await wait_for_panel_render(page, timeout=timeout)

    # 截图
    target = await page.querySelector(content_selector)
    if not target:
        raise CustomError(message="screenshot target not found")
    image = await target.screenshot(type="jpeg", quality=85)

    # 关闭页面
    try:
        await page.close()
    except Exception as e:
        logger.exception(f"close page error: {e}")

    # 关闭浏览器
    try:
        await browser.close()
    except Exception as e:
        logger.exception(f"close browser error: {e}")

    return image


async def wait_for_panel_render(page: Page, timeout: int = 60):
    """
    等待仪表盘加载完成
    """
    start_time = time.time()
    while True:
        # 获取等待加载的panel数量
        waiting_panel_count = await page.evaluate(
            "() => { return document.querySelectorAll('[aria-label=\"Panel loading bar\"]').length }"
        )
        if waiting_panel_count == 0:
            break

        if time.time() - start_time > timeout:
            raise TimeoutError("wait for dashboard panel render timeout")

        # 等待图表渲染动画完成
        time.sleep(1)
