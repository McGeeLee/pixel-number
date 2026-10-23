from __future__ import annotations

import json
from pathlib import Path
import random
import tempfile
import unittest

from PIL import Image

from pixel_number import codec


class CodecTests(unittest.TestCase):
    def test_known_colors_and_order(self):
        # Four explicit 16-bit words, independent of implementation.
        number = 0xF80007E0001FFFFF
        image = codec.number_to_image(number, 2, 2)
        self.assertEqual(list(image.getdata()), [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])
        reverse = codec.number_to_image(number, 2, 2, "lsb")
        self.assertEqual(list(reverse.getdata()), list(image.getdata())[::-1])
        self.assertEqual(codec.image_to_number(reverse, "lsb"), number)

    def test_increment_carries_to_next_pixel(self):
        self.assertEqual(list(codec.number_to_image(1, 2, 1).getdata()), [(0, 0, 0), (0, 0, 8)])
        self.assertEqual(list(codec.number_to_image(65536, 2, 1).getdata()), [(0, 0, 8), (0, 0, 0)])
        self.assertEqual(list(codec.number_to_image(1, 2, 1, "lsb").getdata()), [(0, 0, 8), (0, 0, 0)])

    def test_all_65536_codes_expand_and_round_trip(self):
        packed = b"".join(i.to_bytes(2, "big") for i in range(65536))
        number = int.from_bytes(packed, "big")
        image = codec.number_to_image(number, 256, 256)
        for value, pixel in enumerate(image.getdata()):
            r, g, b = (value >> 11), (value >> 5) & 63, value & 31
            expected = (r * 8 + r // 4, g * 4 + g // 16, b * 8 + b // 4)
            self.assertEqual(pixel, expected)
        self.assertEqual(len(set(image.getdata())), 65536)
        self.assertEqual(codec.image_to_number(image), number)

    def test_full_hd_random_round_trip(self):
        number = random.Random(565).getrandbits(1920 * 1080 * 16)
        for order in codec.ORDERS:
            image = codec.number_to_image(number, 1920, 1080, order)
            self.assertEqual(image.size, (1920, 1080))
            self.assertEqual(codec.image_to_number(image, order), number)

    def test_black_white_and_bounds(self):
        self.assertEqual(codec.number_to_image(0, 3, 2).getextrema(), ((0, 0),) * 3)
        self.assertEqual(codec.number_to_image((1 << 96) - 1, 3, 2).getextrema(), ((255, 255),) * 3)
        for number in (-1, 1 << 96):
            with self.assertRaises(ValueError):
                codec.number_to_image(number, 3, 2)
        for size in ((0, 1080), (-1, 2), (codec.MAX_PIXELS + 1, 1)):
            with self.assertRaises(ValueError):
                codec.number_to_image(0, *size)

    def test_large_decimal_and_input_validation(self):
        text = "1234567890" * 1000
        number = codec.parse_number(text, 10, 40000)
        self.assertEqual(codec.number_text(number), text)
        self.assertEqual(codec.parse_number(" 0xF800_07E0\n", 16, 32), 0xF80007E0)
        self.assertEqual(codec.parse_number("0" * 10000, 10, 16), 0)
        for text in ("", "-1", "1.0", "1e3", "NaN", "65536"):
            with self.assertRaises(ValueError):
                codec.parse_number(text, 10, 16)
        with self.assertRaises(ValueError):
            codec.parse_number("10000", 16, 16)
        with self.assertRaises(ValueError):
            codec.parse_number("１２３", 10, 16)

    def test_step_and_slider_exactness(self):
        self.assertEqual(codec.parse_step("65536^1000", 20000), 1 << 16000)
        self.assertEqual(codec.parse_step("0x10000", 32), 65536)
        for text in ("0", "-1", "2^32", "65536^2", "__import__('os')"):
            with self.assertRaises(ValueError):
                codec.parse_step(text, 32)
        anchor = (1 << 10000) + 7
        low, high = codec.slider_bounds(anchor, 3, 10001)
        self.assertEqual((low, high), (-1000, 1000))
        self.assertEqual(anchor + 1000 * 3 - anchor, 3000)
        self.assertEqual(codec.slider_bounds(0, 1, 16), (0, 1000))
        self.assertEqual(codec.slider_bounds(65535, 1, 16), (-1000, 0))

    def test_quantization_and_transparency(self):
        image = Image.new("RGBA", (2, 1))
        image.putdata([(255, 255, 255, 0), (123, 234, 45, 255)])
        value = codec.image_to_number(image)
        self.assertEqual(value, ((123 >> 3) << 11) | ((234 >> 2) << 5) | (45 >> 3))

    def test_png_and_session_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            number = 0xF80007E0001FFFFF
            codec.save_png(path / "image.png", number, 2, 2, "lsb")
            self.assertEqual(codec.load_image(path / "image.png"), (number, 2, 2, "lsb"))
            with self.assertRaises(FileExistsError):
                codec.save_png(path / "image.png", 0, 2, 2)
            codec.save_session(path / "state.json", number, 2, 2, "lsb", 65536)
            self.assertEqual(codec.load_session(path / "state.json"),
                             dict(number=number, width=2, height=2, order="lsb", step=65536))
            data = json.loads((path / "state.json").read_text())
            data["order"] = "invalid"
            (path / "bad.json").write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                codec.load_session(path / "bad.json")

    def test_range_selection_overflow_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            result = codec.export_range(path / "range", 7, 3, 4, 2, 2)
            self.assertEqual(result["completed"], 4)
            self.assertEqual([codec.load_image(p)[0] for p in sorted((path / "range").glob("*.png"))], [7, 10, 13, 16])
            with self.assertRaises(ValueError):
                codec.export_range(path / "invalid", 65535, 1, 2, 1, 1)
            self.assertFalse((path / "invalid").exists())
            completed = []
            result = codec.export_range(path / "cancel", 0, 1, 5, 1, 1,
                cancelled=lambda: len(completed) == 2, progress=lambda n, total: completed.append(n))
            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(result["completed"], 2)
            self.assertEqual(len(list((path / "cancel").glob("*.png"))), 2)
            manifest = json.loads((path / "cancel" / "manifest.json").read_text())
            self.assertEqual(manifest["completed"], 2)
            with self.assertRaises(FileExistsError):
                codec.export_range(path / "range", 0, 1, 1, 1, 1)


if __name__ == "__main__":
    unittest.main()
