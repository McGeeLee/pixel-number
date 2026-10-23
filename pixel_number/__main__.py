from __future__ import annotations

import argparse
import multiprocessing
from pathlib import Path
import sys

from . import codec


def main():
    parser = argparse.ArgumentParser(description="Pixel Number · 数字与 RGB565 图片互转；无参数启动图形界面。")
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (("render", "指定编号生成 PNG"), ("batch", "按起点、步长和张数导出")):
        command = sub.add_parser(name, help=help_text)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--number", help="图像编号，批量时为起点")
        source.add_argument("--number-file", type=Path, help="纯数字 TXT，使用 --base 指定进制")
        command.add_argument("--base", type=int, choices=(10, 16), default=10)
        command.add_argument("--width", type=int, default=1920)
        command.add_argument("--height", type=int, default=1080)
        command.add_argument("--order", choices=codec.ORDERS, default="msb")
        command.add_argument("--output", type=Path, required=True, help="PNG 路径，或批量时的新文件夹路径")
        if name == "batch":
            command.add_argument("--step", default="1", help="正整数、0x 十六进制或 2^n / 65536^n")
            command.add_argument("--count", type=int, required=True)
    decode = sub.add_parser("decode", help="图片量化为 RGB565 并保存编号 JSON")
    decode.add_argument("image", type=Path)
    decode.add_argument("--output", type=Path, required=True)
    decode.add_argument("--order", choices=codec.ORDERS, default="msb")
    restore = sub.add_parser("restore", help="编号 JSON 还原成 PNG")
    restore.add_argument("session", type=Path)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command is None:
        from .gui import main as gui_main
        gui_main()
        return
    try:
        if args.command in ("render", "batch"):
            bits = codec.dimensions(args.width, args.height) * 16
            if args.number_file:
                if args.number_file.stat().st_size > int(bits * .302 + 1) * 4 + 4096:
                    raise ValueError("编号文件超过当前分辨率的输入容量。")
                text = args.number_file.read_text(encoding="utf-8-sig")
            else:
                text = args.number
            number = codec.parse_number(text, args.base, bits)
            if args.command == "render":
                codec.save_png(args.output, number, args.width, args.height, args.order)
            else:
                codec.export_range(args.output, number, codec.parse_step(args.step, bits), args.count,
                                   args.width, args.height, args.order)
        elif args.command == "decode":
            number, width, height, order = codec.load_image(args.image, args.order)
            codec.save_session(args.output, number, width, height, order)
        elif args.command == "restore":
            state = codec.load_session(args.session)
            state.pop("step")
            codec.save_png(args.output, **state)
        print(f"已保存：{args.output.resolve()}")
    except (ValueError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
