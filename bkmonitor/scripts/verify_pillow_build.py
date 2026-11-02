"""Check the source-built Pillow environment during the runtime image build."""

import subprocess
from io import BytesIO
from pathlib import Path

import PIL
from PIL import Image, ImageDraw, ImageFont, features


def verify_native_libraries():
    # The manylinux wheel carries its own FreeType/Brotli in pillow.libs.
    if (Path(PIL.__file__).resolve().parent.parent / "pillow.libs").exists():
        raise RuntimeError("Pillow must use system libraries, not bundled wheel libraries")

    loaded = {Path(line.split()[-1]) for line in Path("/proc/self/maps").read_text().splitlines()}
    for soname, package in (
        ("libfreetype.so.6", "freetype"),
        ("libbrotlidec.so.1", "libbrotli"),
        ("libbrotlicommon.so.1", "libbrotli"),
    ):
        matches = {library for library in loaded if library.name == soname or library.name.startswith(f"{soname}.")}
        if len(matches) != 1:
            raise RuntimeError(f"Expected one system {soname} to be loaded, got {matches}")
        library = str(matches.pop().resolve(strict=True))
        owner = subprocess.check_output(["rpm", "-qf", "--qf", "%{NAME}", library], text=True)
        if owner != package:
            raise RuntimeError(f"{library} must come from the {package} system package, got {owner}")
        print(f"{soname}: {library}")

    # Check the patched RPM release: its upstream Brotli version remains 1.1.0.
    subprocess.check_call(["rpm", "-q", "freetype", "libbrotli-1.1.0-4.tl4.2"])


def verify_image_support(font_dir=Path("/usr/share/fonts/truetype")):
    required = (
        "freetype2",
        "jpg",
        "zlib",
        "libtiff",
        "jpg_2000",
        "littlecms2",
        "webp",
        "webp_anim",
        "webp_mux",
        "raqm",
        "xcb",
    )
    missing = [feature for feature in required if not features.check(feature)]
    if missing:
        raise RuntimeError(f"Pillow is missing image features: {', '.join(missing)}")

    for name in ("SourceHanSansSC-VF.ttf", "SourceHanSerifSC-VF.ttf"):
        font = ImageFont.truetype(str(font_dir / name), 24)
        image = Image.new("RGB", (256, 64), "black")
        ImageDraw.Draw(image).text((4, 4), "BlueKing 蓝鲸监控", font=font, fill="white")
        if image.getbbox() is None:
            raise RuntimeError(f"Font did not render text: {name}")
        encoded = BytesIO()
        image.save(encoded, format="PNG")
        encoded.seek(0)
        with Image.open(encoded) as decoded:
            decoded.load()
            if decoded.size != image.size or decoded.tobytes() != image.tobytes():
                raise RuntimeError(f"PNG round trip failed: {name}")
        print(f"Chinese/Latin text and PNG round trip: {name}")


if __name__ == "__main__":
    verify_image_support()
    verify_native_libraries()
    print(f"Pillow {PIL.__version__}: system libraries and image support verified")
