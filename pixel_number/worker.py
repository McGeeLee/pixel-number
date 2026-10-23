"""All parsing, image conversion and export happens outside the Tk process."""
from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import queue
import secrets
import time

from . import codec


def _loop(requests, replies, cancelled):
    while True:
        task = requests.get()
        if task is None:
            return
        serial, kind, payload = task
        started = time.perf_counter()
        try:
            p = dict(payload)
            if kind in ("render", "preset", "load_image", "load_session", "load_text"):
                step = None
                if kind == "load_image":
                    number, width, height, order = codec.load_image(p["path"], p["order"])
                elif kind == "load_session":
                    loaded = codec.load_session(p["path"])
                    number, width, height, order, step = (loaded[key] for key in ("number", "width", "height", "order", "step"))
                else:
                    width, height, order = p["width"], p["height"], p["order"]
                    bits = codec.dimensions(width, height) * 16
                    if kind == "preset":
                        number = {"black": lambda: 0, "white": lambda: (1 << bits) - 1,
                                  "random": lambda: secrets.randbits(bits)}[p["preset"]]()
                    else:
                        if kind == "load_text":
                            source = Path(p["path"])
                            if source.stat().st_size > int(bits * 0.302 + 1) * 4 + 4096:
                                raise ValueError("文本文件超过当前分辨率的输入容量。")
                            p["text"] = source.read_text(encoding="utf-8-sig")
                        number = (codec.parse_number(p["text"], p["base"], bits)
                                  if "text" in p else p["number"])
                frame = codec.number_to_image(number, width, height, order)
                result = {"number": number, "width": width, "height": height, "order": order,
                          "rgb": frame.tobytes(), "step": step}
            elif kind == "save_png":
                codec.save_png(**p)
                result = {"path": str(p["path"])}
            elif kind == "save_session":
                codec.save_session(**p)
                result = {"path": str(p["path"])}
            elif kind == "save_text":
                value = codec.number_text(p["number"], p["base"]).encode("ascii") + b"\n"
                codec._atomic_write(Path(p["path"]), lambda stream: stream.write(value), True)
                result = {"path": str(p["path"])}
            elif kind == "batch":
                result = codec.export_range(**p, cancelled=cancelled.is_set,
                    progress=lambda done, total: replies.put((serial, "progress", (done, total))))
                result["path"] = str(p["directory"])
            else:
                raise ValueError("未知任务。")
            result["elapsed"] = time.perf_counter() - started
            replies.put((serial, "ok", result))
        except Exception as exc:
            replies.put((serial, "error", f"{type(exc).__name__}: {exc}"))


class Worker:
    def __init__(self):
        context = mp.get_context("spawn")
        self.requests = context.Queue()
        self.replies = context.Queue()
        self.cancelled = context.Event()
        self.process = context.Process(target=_loop, args=(self.requests, self.replies, self.cancelled), daemon=True)
        self.process.start()

    def submit(self, serial: int, kind: str, payload: dict):
        self.cancelled.clear()
        self.requests.put((serial, kind, payload))

    def receive(self):
        try:
            return self.replies.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.cancelled.set()
        self.process.terminate()
        self.process.join(timeout=1)
        self.requests.cancel_join_thread()
        self.replies.cancel_join_thread()
        self.requests.close()
        self.replies.close()
