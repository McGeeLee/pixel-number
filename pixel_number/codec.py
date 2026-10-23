"""Exact integer ↔ RGB565 mapping. No floating-point image identifiers."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Callable

import gmpy2
from PIL import Image, ImageChops, ImageOps, PngImagePlugin

MAX_PIXELS = 16_777_216
ORDERS = ("msb", "lsb")
SCHEMA = "pixel-number/v1"


def dimensions(width: int, height: int) -> int:
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("宽度和高度必须是整数。")
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError(f"宽高必须为正数，总像素不能超过 {MAX_PIXELS:,}。")
    return width * height


def validate_number(number: int, width: int, height: int, order: str = "msb") -> None:
    pixels = dimensions(width, height)
    if order not in ORDERS:
        raise ValueError("像素顺序必须是 msb 或 lsb。")
    if not isinstance(number, int) or number < 0:
        raise ValueError("编号必须是非负整数。")
    if number.bit_length() > pixels * 16:
        raise ValueError(f"编号超出 {width} × {height} 的容量；请减小编号或增加分辨率。")


def parse_number(text: str, base: int, bits: int) -> int:
    """Bound input before GMP conversion; never disable Python's global safety limit."""
    if base not in (10, 16):
        raise ValueError("仅支持十进制或十六进制。")
    compact = re.sub(r"[\s_]", "", text)
    if compact.startswith("+"):
        compact = compact[1:]
    if base == 16 and compact.lower().startswith("0x"):
        compact = compact[2:]
    pattern = r"[0-9]+" if base == 10 else r"[0-9a-fA-F]+"
    if not re.fullmatch(pattern, compact):
        raise ValueError("请输入非负整数；可用空格、换行或下划线分隔数字。")
    compact = compact.lstrip("0") or "0"
    max_digits = math.floor(bits * math.log10(2)) + 1 if base == 10 else (bits + 3) // 4
    if len(compact) > max_digits:
        raise ValueError("输入数字超过当前分辨率的容量。")
    value = int(gmpy2.mpz(compact, base))
    if value.bit_length() > bits:
        raise ValueError("输入数字超过当前分辨率的容量。")
    return value


def parse_step(text: str, bits: int) -> int:
    compact = re.sub(r"\s", "", text)
    power = re.fullmatch(r"(2|65536)\^(\d{1,10})", compact)
    if power:
        exponent = int(power[2]) * (16 if power[1] == "65536" else 1)
        if exponent >= bits:
            raise ValueError("步长过大，已经超出整张图的编号范围。")
        value = 1 << exponent
    else:
        value = parse_number(compact, 16 if compact.lower().startswith("0x") else 10, bits)
    if value < 1:
        raise ValueError("步长必须大于零。")
    return value


def number_text(number: int, base: int = 10) -> str:
    if base == 16:
        return "0x" + format(number, "x")
    return gmpy2.mpz(number).digits(10)


def short_number(number: int, base: int = 10, limit: int = 160) -> tuple[str, bool]:
    """Never put a multi-million-digit string into a Tk Entry."""
    if number.bit_length() <= (limit - 2) * (3 if base == 10 else 4):
        value = number_text(number, base)
        if len(value) <= limit:
            return value, False
    bits = number.bit_length()
    head = number >> max(0, bits - 48)
    tail = number & ((1 << 48) - 1)
    return f"已载入大数 · {bits:,} bit · 0x{head:012x}…{tail:012x}（可直接输入新数字替换）", True


def slider_bounds(anchor: int, step: int, bits: int, radius: int = 1000) -> tuple[int, int]:
    if anchor < 0 or anchor.bit_length() > bits or step <= 0:
        raise ValueError("滑条参数无效。")
    return -min(radius, anchor // step), min(radius, ((1 << bits) - 1 - anchor) // step)


def rgb565_color(value: int) -> tuple[int, int, int]:
    r, g, b = (value >> 11) & 31, (value >> 5) & 63, value & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


_R = [((h >> 3) << 3) | (h >> 5) for h in range(256)]
_GH = [((h & 7) << 5) | ((h & 7) >> 1) for h in range(256)]
_GL = [(low >> 5) << 2 for low in range(256)]
_B = [((low & 31) << 3) | ((low & 31) >> 2) for low in range(256)]


def number_to_image(number: int, width: int = 1920, height: int = 1080,
                    order: str = "msb") -> Image.Image:
    validate_number(number, width, height, order)
    raw = number.to_bytes(width * height * 2, "big")
    high, low = raw[0::2], raw[1::2]
    if order == "lsb":
        high, low = high[::-1], low[::-1]
    hi = Image.frombytes("L", (width, height), high)
    lo = Image.frombytes("L", (width, height), low)
    return Image.merge("RGB", (hi.point(_R), ImageChops.add(hi.point(_GH), lo.point(_GL)), lo.point(_B)))


def image_to_number(image: Image.Image, order: str = "msb") -> int:
    dimensions(*image.size)
    if order not in ORDERS:
        raise ValueError("像素顺序必须是 msb 或 lsb。")
    # Transparent input is composited onto black, consistently across PNG modes.
    rgba = image.convert("RGBA")
    rgb = Image.alpha_composite(Image.new("RGBA", image.size, (0, 0, 0, 255)), rgba).convert("RGB")
    r, g, b = rgb.split()
    high = ImageChops.add(r.point([v & 248 for v in range(256)]),
                         g.point([v >> 5 for v in range(256)])).tobytes()
    low = ImageChops.add(g.point([(v & 28) << 3 for v in range(256)]),
                        b.point([v >> 3 for v in range(256)])).tobytes()
    if order == "lsb":
        high, low = high[::-1], low[::-1]
    raw = bytearray(image.width * image.height * 2)
    raw[0::2], raw[1::2] = high, low
    return int.from_bytes(raw, "big")


def load_image(path: str | Path, order: str = "msb") -> tuple[int, int, int, str]:
    with Image.open(path) as source:
        dimensions(*source.size)
        stored_order = source.info.get("pixel_number.order", order)
        if stored_order not in ORDERS:
            stored_order = order
        image = ImageOps.exif_transpose(source)
        return image_to_number(image, stored_order), image.width, image.height, stored_order


def _atomic_write(path: Path, writer: Callable, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"文件已存在：{path}")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name + ".", suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temp, path)
        else:
            # An atomic no-clobber publish, including if another process created the destination.
            os.link(temp, path)
            temp.unlink()
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def save_png(path: str | Path, number: int, width: int, height: int,
             order: str = "msb", overwrite: bool = False) -> None:
    image = number_to_image(number, width, height, order)
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("pixel_number.schema", SCHEMA)
    metadata.add_text("pixel_number.order", order)
    metadata.add_text("pixel_number.format", "RGB565")
    _atomic_write(Path(path), lambda stream: image.save(stream, format="PNG", pnginfo=metadata), overwrite)


def save_session(path: str | Path, number: int, width: int, height: int,
                 order: str = "msb", step: int = 1, overwrite: bool = False) -> None:
    validate_number(number, width, height, order)
    if step <= 0 or step.bit_length() > width * height * 16:
        raise ValueError("步长超出当前分辨率的范围。")
    data = {"schema": SCHEMA, "width": width, "height": height, "order": order,
            "number_hex": format(number, "x"), "step_hex": format(step, "x")}
    encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    _atomic_write(Path(path), lambda stream: stream.write(encoded), overwrite)


def load_session(path: str | Path) -> dict:
    path = Path(path)
    if path.stat().st_size > MAX_PIXELS * 8 + 4096:
        raise ValueError("编号文件过大。")
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("不是 Pixel Number 的编号文件。")
    try:
        width, height, order = data["width"], data["height"], data["order"]
        bits = dimensions(width, height) * 16
        number = parse_number(data["number_hex"], 16, bits)
        step = parse_number(data.get("step_hex", "1"), 16, bits)
        validate_number(number, width, height, order)
        if step < 1:
            raise ValueError("编号文件中的步长必须大于零。")
    except (KeyError, TypeError) as exc:
        raise ValueError("编号文件字段不完整或格式无效。") from exc
    return {"number": number, "width": width, "height": height, "order": order, "step": step}


def export_range(directory: str | Path, start: int, step: int, count: int,
                 width: int, height: int, order: str = "msb",
                 cancelled: Callable[[], bool] = lambda: False,
                 progress: Callable[[int, int], None] = lambda done, total: None) -> dict:
    if not isinstance(count, int) or count < 1 or count > 1_000_000:
        raise ValueError("导出张数必须在 1 到 1,000,000 之间。")
    if not isinstance(step, int) or step < 1:
        raise ValueError("步长必须是正整数。")
    validate_number(start, width, height, order)
    validate_number(start + step * (count - 1), width, height, order)
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": "pixel-number/batch-v1", "width": width, "height": height,
                "order": order, "start_hex": format(start, "x"), "step_hex": format(step, "x"),
                "requested": count, "completed": 0, "status": "running"}
    # Large starting numbers are stored once, not rewritten for every frame.
    plan = {key: manifest[key] for key in ("schema", "width", "height", "order", "start_hex", "step_hex", "requested")}
    plan_bytes = (json.dumps(plan, indent=2) + "\n").encode()
    _atomic_write(path / "plan.json", lambda stream: stream.write(plan_bytes), False)
    def record():
        status = {key: value for key, value in manifest.items() if key not in ("start_hex", "step_hex")}
        status["plan"] = "plan.json"
        content = (json.dumps(status, indent=2) + "\n").encode()
        _atomic_write(path / "manifest.json", lambda stream: stream.write(content), True)
    record()
    try:
        for i in range(count):
            if cancelled():
                manifest["status"] = "cancelled"
                break
            save_png(path / f"{i:06d}.png", start + i * step, width, height, order)
            manifest["completed"] = i + 1
            record()
            progress(i + 1, count)
        else:
            manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        raise
    finally:
        record()
    return manifest
