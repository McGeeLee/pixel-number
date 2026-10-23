"""Run explicitly on a desktop: .venv/bin/python tests/gui_smoke.py."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pixel_number.gui import App
from pixel_number import codec


def main():
    root = tk.Tk()
    app = App(root)
    failures = []
    root.report_callback_exception = lambda *args: failures.append(args)
    def wait(predicate, timeout=15):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            root.update()
            if failures:
                raise AssertionError(failures)
            if predicate():
                return
            time.sleep(.01)
        raise AssertionError("GUI did not reach expected state: " + app.status_var.get())
    def idle():
        return app.busy is None and app.pending is None and app.timer is None and not app.dirty
    try:
        wait(idle)
        assert app.image.size == (1920, 1080)
        assert app.number == 0
        app.number_var.set("65535")
        wait(idle)
        assert app.image.getpixel((1919, 1079)) == (255, 255, 255)
        app.advance(1)
        wait(idle)
        assert app.number == 65536
        assert app.image.getpixel((1918, 1079)) == (0, 0, 8)
        app.offset_var.set(5)
        app._slide("5")
        wait(idle)
        assert app.number == 65541
        # A newer edit must survive an older asynchronous render response.
        app._render_value(2, True)
        app.number_var.set("12345")
        wait(idle)
        assert app.number == 12345
        app.order_var.set("低位在左上 · 首像素先变")
        wait(idle)
        assert codec.image_to_number(app.image, "lsb") == 12345
        app.preset("random")
        wait(idle)
        assert app.compact and len(app.number_var.get()) < 160
        original = app.number
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.png"
            app._enqueue("save_png", {"path": str(path), **app.frame})
            wait(idle)
            assert codec.load_image(path)[0] == original
            app._enqueue("load_image", {"path": str(path), "order": "msb"}, reanchor=True)
            wait(idle)
            assert app.number == original
        root.geometry("1000x760")
        wait(lambda: app.canvas.winfo_width() < 850)
        app._redraw()
        assert app.photo.width() > 0
        for widget, state in app.inputs:
            assert widget.winfo_ismapped(), str(widget)
            assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width() + 1, (str(widget), 'right edge clipped')
            assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height() + 1, (str(widget), 'bottom edge clipped')
        assert not failures
        print("GUI smoke passed: entry, step, slider, stale response, order, random, PNG reload, resize.")
    finally:
        app._destroy()


if __name__ == "__main__":
    main()
