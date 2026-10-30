"""Verify the audited Pillow 8.4.0 Linux x86_64 wheel and its image support."""

import hashlib
from io import BytesIO
from pathlib import Path

import PIL
from PIL import Image, ImageDraw, ImageFont


def verify_native_libraries():
    if PIL.__version__ != "8.4.0":
        raise RuntimeError("Reaudit the native libraries before changing Pillow 8.4.0")

    loaded = {Path(line.split()[-1]) for line in Path("/proc/self/maps").read_text().splitlines()}
    matches = {library.resolve() for library in loaded if library.name.startswith("libfreetype")}
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one audited FreeType library to be loaded")
    library = matches.pop()
    wheel_libraries = Path(PIL.__file__).resolve().parent.parent / "Pillow.libs"
    if library.parent != wheel_libraries:
        raise RuntimeError("Pillow must load the audited wheel's FreeType library")

    # This exact wheel has WOFF2/Brotli disabled, including the static decoder path.
    expected = "75e772cc57f768dd30be6ec249d0c9013f34ab6bdd7ebb1b912cb1c77b068ad1"
    if hashlib.sha256(library.read_bytes()).hexdigest() != expected:
        raise RuntimeError("FreeType differs from the audited build without Brotli")
    if any("brotli" in library.name.lower() for library in loaded):
        raise RuntimeError("Pillow must not load a Brotli decoder in this image")
    print("Pillow 8.4.0: audited FreeType without Brotli verified")


def verify_image_support(font_dir=Path("/usr/share/fonts/truetype")):
    for name in ("SourceHanSansSC-VF.ttf", "SourceHanSerifSC-VF.ttf"):
        font = ImageFont.truetype(str(font_dir / name), 24)
        image = Image.new("RGB", (256, 64), "black")
        ImageDraw.Draw(image).text((4, 4), "BlueKing 蓝鲸监控", font=font, fill="white")
        if image.getbbox() is None:
            raise RuntimeError("Font did not render text: " + name)
        encoded = BytesIO()
        image.save(encoded, format="PNG")
        encoded.seek(0)
        with Image.open(encoded) as decoded:
            decoded.load()
            if decoded.size != image.size or decoded.tobytes() != image.tobytes():
                raise RuntimeError("PNG round trip failed: " + name)
        print("Chinese/Latin text and PNG round trip: " + name)


if __name__ == "__main__":
    verify_image_support()
    verify_native_libraries()
