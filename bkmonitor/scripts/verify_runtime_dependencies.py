"""Verify the pinned system Brotli libraries and the report browser in the final image."""

import asyncio
import ctypes
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path

from PIL import Image
from pyppeteer.launcher import Launcher

BROTLI_VERSION = "1.0.9-2+deb11u1"
# File digests from the verified Bullseye ELTS amd64 package.
BROTLI_SHA256 = {
    "libbrotlicommon.so.1": "af18a24ea48250487ec8a6b8f829d7375ed3d1967dbe343758c6bec111d8483d",
    "libbrotlidec.so.1": "41901739fa42390df644d15ad04401893a8672482b4059df5e3b5d8bdab37dbc",
    "libbrotlienc.so.1": "a4c9681a1fe99d8b03158a1ff2200ea8516b93a030eb8e5f1dddc34efdc082b2",
}
CHROME_VERSION = "157.0.8103.78"
CHROME_DIR = Path("/opt/google/chrome")
CHROME_SHA256 = "91e519ce83eac12740d54398364583b3131116055eca863d0a240d6062e84053"
REPORT_FONT = Path("/usr/share/fonts/truetype/SourceHanSansSC-VF.ttf")
REPORT_TEXT = "BlueKing 蓝鲸监控"
REPORT_SIZE = (320, 120)
REPORT_HTML = (
    "<!doctype html><meta charset=utf-8><link rel=icon href=data:,>"
    "<style>@font-face{font-family:ReportSmoke;src:url(/report-font.ttf)}"
    "body{margin:0}#report{width:320px;height:120px;display:grid;place-items:center;"
    "color:#111;background:#fff;font:24px ReportSmoke}</style>"
    f"<div id=report>{REPORT_TEXT}</div>"
).encode("utf-8")


def verify_package(name, version):
    status = subprocess.check_output(["dpkg-query", "-W", "-f=${Status} ${Version}", name], universal_newlines=True)
    if status.strip() != f"install ok installed {version}":
        raise RuntimeError(f"{name} must be installed at {version}, got {status.strip()!r}")


def verify_sha256(path, expected):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise RuntimeError(f"{path} differs from the audited package")


def verify_brotli():
    verify_package("libbrotli1", BROTLI_VERSION)
    files = subprocess.check_output(["dpkg-query", "-L", "libbrotli1"], universal_newlines=True)
    paths = {Path(name).name: Path(name).resolve() for name in files.splitlines() if Path(name).name in BROTLI_SHA256}
    if paths.keys() != BROTLI_SHA256.keys():
        raise RuntimeError("libbrotli1 must provide all three Brotli SONAMEs")

    libraries = {}
    for name, expected in BROTLI_SHA256.items():
        verify_sha256(paths[name], expected)
        libraries[name] = ctypes.CDLL(name)
    mapped_paths = (line.split(maxsplit=5)[-1] for line in Path("/proc/self/maps").read_text().splitlines())
    loaded = {
        Path(path).resolve()
        for path in mapped_paths
        if path.startswith("/") and Path(path).name.startswith("libbrotli")
    }
    if loaded != set(paths.values()):
        raise RuntimeError(f"Brotli must load only the audited system libraries, got {sorted(map(str, loaded))}")
    print(f"System libbrotli1 {BROTLI_VERSION}: verified all three loaded libraries")
    return libraries["libbrotlienc.so.1"]


def compress_report(encoder):
    max_size = encoder.BrotliEncoderMaxCompressedSize
    max_size.argtypes = [ctypes.c_size_t]
    max_size.restype = ctypes.c_size_t
    output_size = ctypes.c_size_t(max_size(len(REPORT_HTML)))
    output = ctypes.create_string_buffer(output_size.value)
    compress = encoder.BrotliEncoderCompress
    compress.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_size_t,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
    ]
    compress.restype = ctypes.c_int
    if not compress(5, 22, 1, len(REPORT_HTML), REPORT_HTML, ctypes.byref(output_size), output):
        raise RuntimeError("Could not Brotli-compress the report fixture")
    return output.raw[: output_size.value]


def verify_chrome():
    verify_package("google-chrome-stable", f"{CHROME_VERSION}-1")
    if shutil.which("chromium"):
        raise RuntimeError("The report launcher would pick Chromium ahead of Google Chrome")
    chrome = shutil.which("google-chrome")
    if not chrome or Path(chrome).resolve() != CHROME_DIR / "google-chrome":
        raise RuntimeError("The report launcher must find the audited Google Chrome wrapper")
    verify_sha256(CHROME_DIR / "chrome", CHROME_SHA256)
    version = subprocess.check_output([chrome, "--version"], universal_newlines=True, timeout=15).strip()
    if version != f"Google Chrome {CHROME_VERSION}":
        raise RuntimeError(f"Unexpected report browser version: {version!r}")
    return chrome


async def verify_screenshot(browser, url):
    page = await browser.newPage()
    response = await page.goto(url, {"waitUntil": "networkidle0", "timeout": 30000})
    if response is None or response.status != 200 or response.headers.get("content-encoding") != "br":
        raise RuntimeError("The report page did not receive the Brotli HTTP response")

    await page.setViewport({"width": 640, "height": 480, "deviceScaleFactor": 1})
    target = await page.querySelector("#report")
    if target is None or await page.evaluate("(element) => element.textContent", target) != REPORT_TEXT:
        raise RuntimeError("Chrome did not decode the expected report text")
    font_count = await page.evaluate(
        "async (text) => (await document.fonts.load('24px ReportSmoke', text)).length",
        REPORT_TEXT,
    )
    if font_count != 1:
        raise RuntimeError("Chrome did not load the installed report font")
    with Image.open(BytesIO(await target.screenshot())) as image:
        image.load()
        non_uniform = any(low != high for low, high in image.convert("RGB").getextrema())
        if image.format != "PNG" or image.size != REPORT_SIZE or not non_uniform:
            raise RuntimeError(f"Unexpected report screenshot: {image.format}, {image.size}, non-uniform={non_uniform}")


async def run_browser(chrome, url, profile):
    # Use the same launcher as pyppeteer.launch, retaining its process for startup failure cleanup.
    launcher = Launcher(
        headless=True,
        executablePath=chrome,
        userDataDir=profile,
        args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox"],
        dumpio=True,
        autoClose=False,
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False,
    )
    browser = None
    try:
        browser = await asyncio.wait_for(launcher.launch(), timeout=40)
        await asyncio.wait_for(verify_screenshot(browser, url), timeout=45)
    finally:
        try:
            if browser is not None:
                await asyncio.wait_for(browser.close(), timeout=10)
        finally:
            proc = getattr(launcher, "proc", None)
            if proc is not None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


def verify_report(chrome, compressed):
    class ReportHandler(BaseHTTPRequestHandler):
        timeout = 10

        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Encoding", "br")
                self.send_header("Content-Length", str(len(compressed)))
                self.end_headers()
                self.wfile.write(compressed)
            elif self.path == "/report-font.ttf":
                self.send_response(200)
                self.send_header("Content-Type", "font/ttf")
                self.send_header("Content-Length", str(REPORT_FONT.stat().st_size))
                self.end_headers()
                with REPORT_FONT.open("rb") as font:
                    shutil.copyfileobj(font, self.wfile)
            else:
                self.send_error(404)

    server = HTTPServer(("127.0.0.1", 0), ReportHandler)
    with server, tempfile.TemporaryDirectory() as profile:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(run_browser(chrome, f"http://127.0.0.1:{server.server_port}/", profile))
        finally:
            server.shutdown()
            thread.join()
            loop.close()
    print(f"Google Chrome {CHROME_VERSION}: verified Brotli report, Chinese font, and PNG (no-sandbox smoke)")


if __name__ == "__main__":
    if os.geteuid() == 0:
        raise RuntimeError("Run the image check as the report runtime user")
    chrome_path = verify_chrome()
    verify_report(chrome_path, compress_report(verify_brotli()))
