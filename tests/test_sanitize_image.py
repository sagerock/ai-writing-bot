"""main.sanitize_image_data_uri: the only Pillow code path (resize + re-encode)."""

import base64
import io
import os
import unittest

os.environ.setdefault("ROMALUME_SKIP_STARTUP", "1")

from PIL import Image


def _data_uri(image: Image.Image, fmt: str, mime: str) -> str:
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def _decode(data_uri: str) -> tuple[str, Image.Image]:
    header, b64 = data_uri.split(",", 1)
    image = Image.open(io.BytesIO(base64.b64decode(b64)))
    image.load()
    return header, image


class SanitizeImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def test_large_rgb_is_resized_to_jpeg(self):
        source = Image.new("RGB", (4000, 2000), (200, 30, 30))
        header, out = _decode(self.main.sanitize_image_data_uri(_data_uri(source, "PNG", "image/png")))
        self.assertEqual(header, "data:image/jpeg;base64")
        self.assertEqual(out.format, "JPEG")
        self.assertEqual(max(out.size), self.main.IMAGE_MAX_EDGE)
        self.assertEqual(out.size, (self.main.IMAGE_MAX_EDGE, self.main.IMAGE_MAX_EDGE // 2))

    def test_transparency_stays_png(self):
        source = Image.new("RGBA", (300, 200), (0, 0, 255, 128))
        header, out = _decode(self.main.sanitize_image_data_uri(_data_uri(source, "PNG", "image/png")))
        self.assertEqual(header, "data:image/png;base64")
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((10, 10)), (0, 0, 255, 128))

    def test_palette_image_becomes_rgba_png(self):
        source = Image.new("P", (64, 64), 3)
        header, out = _decode(self.main.sanitize_image_data_uri(_data_uri(source, "GIF", "image/gif")))
        self.assertEqual(header, "data:image/png;base64")
        self.assertEqual(out.mode, "RGBA")

    def test_garbage_is_dropped(self):
        self.assertIsNone(self.main.sanitize_image_data_uri("data:image/png;base64,bm90IGFuIGltYWdl"))


if __name__ == "__main__":
    unittest.main()
