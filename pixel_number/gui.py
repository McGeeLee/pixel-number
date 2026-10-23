"""A small, local Tkinter explorer. The main process only handles the UI."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

from PIL import Image, ImageDraw, ImageTk

from . import codec
from .worker import Worker

BG = "#10151d"
PANEL = "#19222e"
TEXT = "#e5edf7"
MUTED = "#95a6bb"
ACCENT = "#66d9bd"
ORDER_LABELS = {"高位在左上 · 末像素先变": "msb", "低位在左上 · 首像素先变": "lsb"}


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Pixel Number · 数字像素实验室")
        root.geometry("1180x850")
        root.minsize(960, 740)
        root.configure(bg=BG)
        self.worker = Worker()
        self.serial = 0
        self.latest = 0
        self.busy = None
        self.pending = None
        self.locked = False
        self.closing = False
        self.dirty = True
        self.updating = False
        self.compact = False
        self.timer = None
        self.resize_timer = None
        self.photo = None
        self.loupe_photo = None
        self.image = None
        self.number = 0
        self.anchor = 0
        self.step = 1
        self.frame = {"number": 0, "width": 1920, "height": 1080, "order": "msb"}
        self.view_rect = (0, 0, 0, 0)
        self.pixel = (1919, 1079)
        self.inputs = []
        self.save_buttons = []
        self.number_var = tk.StringVar(value="0")
        self.base_var = tk.StringVar(value="十进制")
        self.width_var = tk.StringVar(value="1920")
        self.height_var = tk.StringVar(value="1080")
        self.order_var = tk.StringVar(value=next(iter(ORDER_LABELS)))
        self.step_var = tk.StringVar(value="1")
        self.offset_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="准备预览…")
        self.info_var = tk.StringVar(value="1920 × 1080  /  RGB565 · 65,536 色")
        self.range_var = tk.StringVar()
        self.pixel_var = tk.StringVar()
        self.loupe_mode = tk.StringVar(value="最后一个像素")
        self._style()
        self._build()
        self.number_var.trace_add("write", self._input_changed)
        for variable in (self.width_var, self.height_var, self.order_var):
            variable.trace_add("write", self._parameters_changed)
        self.root.bind("<Control-s>", lambda event: self.save_png())
        self.root.bind("<Command-s>", lambda event: self.save_png())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(30, self._poll)
        self.generate()

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Helvetica", 12))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Helvetica", 11))
        style.configure("Title.TLabel", foreground=TEXT, font=("Helvetica", 25, "bold"))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("TButton", background="#28374a", foreground=TEXT, borderwidth=0,
                        padding=(12, 9), font=("Helvetica", 11))
        style.map("TButton", background=[("active", "#364b62"), ("disabled", "#202934")],
                  foreground=[("disabled", "#69798c")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#0d2825", font=("Helvetica", 11, "bold"))
        style.map("Accent.TButton", background=[("active", "#90e8d1"), ("disabled", "#36544e")])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT,
                        padding=(8, 8), bordercolor="#344558")
        style.map("TEntry", fieldbackground=[("disabled", "#202934")], foreground=[("disabled", MUTED)])
        style.configure("TCombobox", fieldbackground=PANEL, background="#28374a", foreground=TEXT,
                        arrowcolor=ACCENT, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL, borderwidth=0)
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#36544e")

    def _input(self, widget, state="normal"):
        self.inputs.append((widget, state))
        return widget

    def _build(self):
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ttk.Label(header, text="Pixel Number", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="数字像素实验室  /  每一个整数，一幅确定的画面", style="Muted.TLabel").pack(side="left", padx=20)

        row = ttk.Frame(outer)
        row.grid(row=1, column=0, sticky="ew")
        row.columnconfigure(1, weight=1)
        base = self._input(ttk.Combobox(row, textvariable=self.base_var, values=("十进制", "十六进制"), width=9, state="readonly"), "readonly")
        base.grid(row=0, column=0, padx=(0, 8))
        base.bind("<<ComboboxSelected>>", self._change_base)
        validation = (self.root.register(self._validate_entry), "%P")
        self.entry = self._input(ttk.Entry(row, textvariable=self.number_var, font=("Menlo", 12),
                                           validate="key", validatecommand=validation))
        self.entry.grid(row=0, column=1, sticky="ew")
        self.entry.bind("<Return>", lambda event: self.generate())
        self.entry.bind("<FocusIn>", self._select_compact)
        self._input(ttk.Button(row, text="生成预览 ↵", style="Accent.TButton", command=self.generate)).grid(row=0, column=2, padx=(8, 0))

        settings = ttk.Frame(outer)
        settings.grid(row=2, column=0, sticky="ew", pady=(12, 8))
        ttk.Label(settings, text="尺寸", style="Muted.TLabel").pack(side="left")
        for variable in (self.width_var, self.height_var):
            field = self._input(ttk.Entry(settings, textvariable=variable, width=6))
            field.pack(side="left", padx=5)
            if variable is self.width_var:
                ttk.Label(settings, text="×", style="Muted.TLabel").pack(side="left")
        self._input(ttk.Button(settings, text="1080p", command=lambda: self._set_size(1920, 1080))).pack(side="left", padx=(0, 10))
        order = self._input(ttk.Combobox(settings, textvariable=self.order_var, values=tuple(ORDER_LABELS), state="readonly", width=26), "readonly")
        order.pack(side="left")
        for title, name in (("全黑", "black"), ("全白", "white"), ("随机跳转", "random")):
            self._input(ttk.Button(settings, text=title, command=lambda key=name: self.preset(key))).pack(side="right", padx=(6, 0))

        browser = ttk.Frame(outer)
        browser.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(browser, text="步长", style="Muted.TLabel").pack(side="left")
        step_entry = self._input(ttk.Entry(browser, textvariable=self.step_var, width=18))
        step_entry.pack(side="left", padx=8)
        step_entry.bind("<Return>", lambda event: self.apply_step())
        self._input(ttk.Button(browser, text="应用步长", command=self.apply_step)).pack(side="left")
        ttk.Label(browser, text="支持 1、65536、2^32、65536^100", style="Muted.TLabel").pack(side="left", padx=12)
        self.next_button = self._input(ttk.Button(browser, text="下一张 →", command=lambda: self.advance(1)))
        self.next_button.pack(side="right")
        self.prev_button = self._input(ttk.Button(browser, text="← 上一张", command=lambda: self.advance(-1)))
        self.prev_button.pack(side="right", padx=6)
        slider_row = ttk.Frame(outer)
        slider_row.grid(row=4, column=0, sticky="ew", pady=(2, 12))
        self.slider = self._input(tk.Scale(slider_row, from_=0, to=1000, resolution=1, orient="horizontal",
            showvalue=False, variable=self.offset_var, command=self._slide, bg=BG, fg=TEXT,
            troughcolor=PANEL, activebackground=ACCENT, highlightthickness=0, bd=0,
            sliderrelief="flat", sliderlength=20, width=12, repeatinterval=40))
        self.slider.pack(fill="x")
        ttk.Label(slider_row, textvariable=self.range_var, style="Muted.TLabel").pack(anchor="w")

        view = ttk.Frame(outer)
        view.grid(row=5, column=0, sticky="nsew")
        view.columnconfigure(0, weight=1)
        view.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(view, background="#080c12", highlightbackground="#2a394b", highlightthickness=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<Motion>", self._hover)
        sidebar = ttk.Frame(view, style="Panel.TFrame", padding=14, width=205)
        sidebar.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        ttk.Label(sidebar, text="像素放大镜", style="Panel.TLabel", font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(0, 10))
        modes = ttk.Combobox(sidebar, textvariable=self.loupe_mode,
                            values=("最后一个像素", "第一个像素", "跟随鼠标"), state="readonly", width=15)
        modes.pack(fill="x")
        modes.bind("<<ComboboxSelected>>", lambda event: self._update_loupe())
        self.loupe = tk.Canvas(sidebar, width=176, height=176, bg="#080c12", highlightthickness=0)
        self.loupe.pack(pady=12)
        ttk.Label(sidebar, textvariable=self.pixel_var, style="Panel.TLabel", justify="left", font=("Menlo", 10)).pack(anchor="w")
        ttk.Label(sidebar, text="每次 +1 通常只改变\n一个像素。放大镜显示\n原始颜色，不做平滑。", style="Panel.TLabel", foreground=MUTED,
                  justify="left", font=("Helvetica", 10)).pack(anchor="w", pady=(16, 0))

        ttk.Label(outer, textvariable=self.info_var, style="Muted.TLabel").grid(row=6, column=0, sticky="w", pady=(10, 12))
        actions = ttk.Frame(outer)
        actions.grid(row=7, column=0, sticky="ew")
        self._input(ttk.Button(actions, text="导入图片", command=self.open_image)).pack(side="left")
        self._input(ttk.Button(actions, text="打开编号", command=self.open_number)).pack(side="left", padx=6)
        for title, command, style in (("保存 PNG", self.save_png, "Accent.TButton"),
                                       ("保存编号", self.save_session, "TButton"),
                                       ("导出数字 TXT", self.save_text, "TButton"),
                                       ("批量导出", self.batch, "TButton")):
            button = self._input(ttk.Button(actions, text=title, command=command, style=style))
            button.pack(side="right", padx=(6, 0))
            self.save_buttons.append(button)
        footer = ttk.Frame(outer)
        footer.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel", wraplength=880).grid(row=0, column=0, sticky="w")
        self.cancel_button = ttk.Button(footer, text="停止批量", command=self.cancel_batch, state="disabled")
        self.cancel_button.grid(row=0, column=1, padx=(10, 0))

    def _validate_entry(self, proposed):
        if len(proposed) > 4096:
            self.status_var.set("超过 4096 个字符的编号请保存为 TXT，再用「打开编号」载入。")
            return False
        return True

    def _select_compact(self, event):
        if self.compact:
            self.root.after_idle(lambda: self.entry.selection_range(0, "end"))

    def _dimensions(self):
        try:
            width, height = int(self.width_var.get()), int(self.height_var.get())
        except ValueError as exc:
            raise ValueError("宽高请输入正整数。") from exc
        codec.dimensions(width, height)
        return width, height

    def _params(self):
        width, height = self._dimensions()
        return {"width": width, "height": height, "order": ORDER_LABELS[self.order_var.get()]}

    def _base(self):
        return 10 if self.base_var.get() == "十进制" else 16

    def _cancel_timer(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None

    def _schedule(self):
        self._cancel_timer()
        # An in-flight response must never overwrite a newer edit during debounce.
        self.serial += 1
        self.latest = self.serial
        self.pending = None
        self.dirty = True
        self._buttons()
        self.status_var.set("输入已修改，等待预览…")
        self.timer = self.root.after(350, self.generate)

    def _input_changed(self, *args):
        if not self.updating:
            self.compact = False
            self._schedule()

    def _parameters_changed(self, *args):
        if not self.updating:
            self._schedule()

    def _set_size(self, width, height):
        self.updating = True
        self.width_var.set(str(width))
        self.height_var.set(str(height))
        self.updating = False
        self.generate()

    def _write_number(self):
        value, self.compact = codec.short_number(self.number, self._base())
        self.updating = True
        self.number_var.set(value)
        self.updating = False

    def _change_base(self, event=None):
        if self.locked:
            return
        self._cancel_timer()
        # Switching display bases keeps the last accepted integer exactly unchanged.
        self._write_number()
        self.generate()

    def generate(self):
        if self.locked:
            return
        self._cancel_timer()
        try:
            payload = self._params()
            if self.compact:
                payload["number"] = self.number
            else:
                payload.update(text=self.number_var.get(), base=self._base())
            self._enqueue("render", payload, reanchor=True)
        except ValueError as exc:
            self._invalid(str(exc))

    def preset(self, key):
        if self.locked:
            return
        self._cancel_timer()
        try:
            self._enqueue("preset", {**self._params(), "preset": key}, reanchor=True)
        except ValueError as exc:
            self._invalid(str(exc))

    def apply_step(self):
        if self.locked or self.dirty or self.image is None:
            return False
        try:
            step = (self.step if self.step_var.get() == "已载入大步长" else
                    codec.parse_step(self.step_var.get(), self.frame["width"] * self.frame["height"] * 16))
        except ValueError as exc:
            self.status_var.set(str(exc))
            return False
        self.step = step
        self._anchor()
        self.status_var.set("步长已应用。拖动滑条或点击上一张 / 下一张。")
        self._buttons()
        return True

    def _anchor(self):
        self.anchor = self.number
        bits = self.frame["width"] * self.frame["height"] * 16
        if self.step.bit_length() > bits:
            self.step = 1
            self.step_var.set("1")
        low, high = codec.slider_bounds(self.anchor, self.step, bits)
        self.updating = True
        self.slider.configure(from_=low, to=high)
        self.offset_var.set(0)
        self.updating = False
        self._range_label()

    def _range_label(self):
        self.range_var.set(f"局部滑条  ·  偏移 {self.offset_var.get():+d} 步  ·  编号 = 本次基点 + 偏移 × 已应用步长；输入数字可跳转并重设基点")

    def _slide(self, value):
        if self.updating or self.locked or self.image is None:
            return
        offset = int(float(value))
        candidate = self.anchor + offset * self.step
        if candidate == self.number:
            return
        self._cancel_timer()
        self.serial += 1
        self.latest = self.serial
        self.pending = None
        self.dirty = True
        self._buttons()
        self._range_label()
        self.timer = self.root.after(45, lambda: self._render_value(candidate, False))

    def _render_value(self, number, reanchor):
        self.timer = None
        self._enqueue("render", {**self.frame, "number": number}, reanchor=reanchor)

    def advance(self, direction):
        if self.locked or self.dirty or not self.apply_step():
            return
        self._render_value(self.number + direction * self.step, True)

    def _enqueue(self, kind, payload, reanchor=False):
        self.serial += 1
        self.latest = self.serial
        preview = kind in ("render", "preset", "load_image", "load_session", "load_text")
        if preview:
            self.dirty = True
        else:
            self.locked = True
        task = (self.serial, kind, payload, reanchor)
        if self.busy:
            self.pending = task  # Coalesce slider motion into one latest request.
        else:
            self._dispatch(task)
        self._buttons()
        self.status_var.set("正在生成预览…" if preview else "正在保存…")

    def _dispatch(self, task):
        self.busy = task
        self.worker.submit(*task[:3])
        if task[1] == "batch":
            self.cancel_button.configure(state="normal")

    def _poll(self):
        reply = self.worker.receive()
        if reply is not None:
            serial, status, data = reply
            if self.busy and serial == self.busy[0]:
                if status == "progress":
                    self.status_var.set(f"批量导出：{data[0]} / {data[1]} 张；停止后会保留已完成的图片。")
                else:
                    task = self.busy
                    self.busy = None
                    if serial == self.latest:
                        self.locked = False
                        self.cancel_button.configure(state="disabled")
                        if status == "error":
                            self._invalid(data, dirty=task[1] in ("render", "preset", "load_image", "load_session", "load_text"))
                        elif "rgb" in data:
                            self._accept(data, task[3])
                        elif task[1] == "batch":
                            label = "已停止" if data["status"] == "cancelled" else "已完成"
                            self.status_var.set(f"{label} · 已保存 {data['completed']} 张 · {data['path']}")
                        else:
                            self.status_var.set(f"已保存 · {data['path']}")
                        self._buttons()
                    if self.closing:
                        self._destroy()
                        return
                    if self.pending:
                        pending, self.pending = self.pending, None
                        self._dispatch(pending)
        if not self.worker.process.is_alive():
            self.busy = self.pending = None
            self.locked = False
            self.worker.close()
            self.worker = Worker()
            self._invalid("后台进程已重启，请重新生成预览。")
        self.root.after(30, self._poll)

    def _accept(self, data, reanchor):
        self.number = data["number"]
        self.frame = {key: data[key] for key in ("number", "width", "height", "order")}
        self.image = Image.frombytes("RGB", (data["width"], data["height"]), data["rgb"])
        self.updating = True
        self.width_var.set(str(data["width"]))
        self.height_var.set(str(data["height"]))
        self.order_var.set(next(label for label, key in ORDER_LABELS.items() if key == data["order"]))
        self.updating = False
        if data.get("step") is not None:
            self.step = data["step"]
            if self.step.bit_count() == 1:
                self.step_var.set(f"2^{self.step.bit_length() - 1}" if self.step > 65536 else str(self.step))
            elif self.step.bit_length() <= 256:
                self.step_var.set(codec.number_text(self.step))
            else:
                # Keep arbitrary huge saved steps intact without placing them in a widget.
                self.step_var.set("已载入大步长")
        self._write_number()
        if reanchor:
            self._anchor()
        self.dirty = False
        self._redraw()
        pixels = data["width"] * data["height"]
        self.info_var.set(f"{data['width']:,} × {data['height']:,}  /  {pixels:,} 像素  /  RGB565 · 65,536 色  /  编号有效位 {self.number.bit_length():,} bit")
        self.status_var.set(f"预览已更新 · 转换 {data['elapsed'] * 1000:.0f} ms。保存 PNG 后可重新导入，恢复相同编号。")

    def _invalid(self, message, dirty=True):
        self.dirty = dirty
        self.status_var.set(message)
        self._buttons()

    def _buttons(self):
        for widget, normal in self.inputs:
            widget.configure(state="disabled" if self.locked else normal)
        for button in self.save_buttons:
            button.configure(state="normal" if self.image is not None and not self.dirty and not self.locked else "disabled")
        ready = self.image is not None and not self.dirty and not self.locked
        self.prev_button.configure(state="normal" if ready and self.number >= self.step else "disabled")
        bits = self.frame["width"] * self.frame["height"] * 16
        self.next_button.configure(state="normal" if ready and (self.number + self.step).bit_length() <= bits else "disabled")

    def _resize(self, event=None):
        if self.resize_timer is not None:
            self.root.after_cancel(self.resize_timer)
        self.resize_timer = self.root.after(60, self._redraw)

    def _redraw(self):
        self.resize_timer = None
        if self.image is None:
            return
        width, height = max(1, self.canvas.winfo_width() - 24), max(1, self.canvas.winfo_height() - 24)
        factor = min(width / self.image.width, height / self.image.height)
        size = (max(1, round(self.image.width * factor)), max(1, round(self.image.height * factor)))
        scaled = self.image.resize(size, Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(scaled, master=self.root)
        x, y = (self.canvas.winfo_width() - size[0]) // 2, (self.canvas.winfo_height() - size[1]) // 2
        self.view_rect = (x, y, *size)
        self.canvas.delete("all")
        self.canvas.create_image(x, y, image=self.photo, anchor="nw")
        self._update_loupe()

    def _hover(self, event):
        if self.image is None or self.loupe_mode.get() != "跟随鼠标":
            return
        x, y, width, height = self.view_rect
        if x <= event.x < x + width and y <= event.y < y + height:
            self.pixel = (min(self.image.width - 1, int((event.x - x) * self.image.width / width)),
                          min(self.image.height - 1, int((event.y - y) * self.image.height / height)))
            self._update_loupe()

    def _update_loupe(self):
        if self.image is None:
            return
        mode = self.loupe_mode.get()
        if mode == "最后一个像素":
            self.pixel = (self.image.width - 1, self.image.height - 1)
        elif mode == "第一个像素":
            self.pixel = (0, 0)
        x, y = min(self.pixel[0], self.image.width - 1), min(self.pixel[1], self.image.height - 1)
        left, top = max(0, min(x - 5, self.image.width - 11)), max(0, min(y - 5, self.image.height - 11))
        right, bottom = min(self.image.width, left + 11), min(self.image.height, top + 11)
        patch = self.image.crop((left, top, right, bottom)).resize((176, 176), Image.Resampling.NEAREST)
        sx, sy = 176 / (right - left), 176 / (bottom - top)
        draw = ImageDraw.Draw(patch)
        draw.rectangle((int((x - left) * sx), int((y - top) * sy),
                        int((x - left + 1) * sx) - 1, int((y - top + 1) * sy) - 1), outline=ACCENT, width=1)
        self.loupe_photo = ImageTk.PhotoImage(patch, master=self.root)
        self.loupe.delete("all")
        self.loupe.create_image(0, 0, anchor="nw", image=self.loupe_photo)
        r, g, b = self.image.getpixel((x, y))
        code = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        self.pixel_var.set(f"坐标 ({x}, {y})\nRGB  {r}, {g}, {b}\n565  {code} / 0x{code:04X}")

    def open_image(self):
        if self.locked:
            return
        path = filedialog.askopenfilename(title="导入图片：颜色量化为 RGB565，透明区域合成到黑色", filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff"), ("所有文件", "*")])
        if path:
            self._cancel_timer()
            self._enqueue("load_image", {"path": path, "order": ORDER_LABELS[self.order_var.get()]}, reanchor=True)

    def open_number(self):
        if self.locked:
            return
        path = filedialog.askopenfilename(title="打开编号：JSON 恢复参数；TXT 使用当前进制与尺寸", filetypes=[("编号文件", "*.json *.txt"), ("所有文件", "*")])
        if path:
            self._cancel_timer()
            try:
                if Path(path).suffix.lower() == ".json":
                    self._enqueue("load_session", {"path": path}, reanchor=True)
                else:
                    self._enqueue("load_text", {"path": path, "base": self._base(), **self._params()}, reanchor=True)
            except ValueError as exc:
                self._invalid(str(exc))

    def _save_path(self, extension, title):
        if self.locked or self.dirty or self.image is None:
            return None
        name = f"pixel-{datetime.now():%Y%m%d-%H%M%S}{extension}"
        return filedialog.asksaveasfilename(title=title, initialfile=name, defaultextension=extension,
                                           filetypes=[(extension.upper().lstrip("."), "*" + extension)])

    def save_png(self):
        path = self._save_path(".png", "保存当前完整分辨率的图片")
        if path:
            self._enqueue("save_png", {"path": path, **self.frame, "overwrite": True})

    def save_session(self):
        path = self._save_path(".json", "保存编号、尺寸、顺序和已应用步长")
        if path:
            self._enqueue("save_session", {"path": path, **self.frame, "step": self.step, "overwrite": True})

    def save_text(self):
        path = self._save_path(".txt", "导出完整数字；重新载入时请选择相同进制与尺寸")
        if path:
            self._enqueue("save_text", {"path": path, "number": self.number, "base": self._base()})

    def batch(self):
        if self.locked or self.dirty or self.image is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("按范围导出")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="从当前画面开始，按已应用步长递增。\n导出到新建的子文件夹，不覆盖已有图片。", justify="left").pack(anchor="w")
        count = tk.StringVar(value="10")
        ttk.Label(body, text="张数", style="Muted.TLabel").pack(anchor="w", pady=(16, 4))
        field = ttk.Entry(body, textvariable=count, width=32)
        field.pack(fill="x")
        error = tk.StringVar()
        ttk.Label(body, textvariable=error, foreground="#f69b9b", wraplength=370).pack(anchor="w", pady=8)
        def start():
            try:
                amount = int(count.get())
                if not 1 <= amount <= 1_000_000:
                    raise ValueError("张数需在 1 到 1,000,000 之间。")
                codec.validate_number(self.number + self.step * (amount - 1), self.frame["width"], self.frame["height"], self.frame["order"])
            except ValueError as exc:
                error.set(str(exc))
                return
            directory = filedialog.askdirectory(parent=dialog, title="选择批量导出的父文件夹")
            if not directory:
                return
            destination = Path(directory) / f"pixel-batch-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
            dialog.destroy()
            self._enqueue("batch", {"directory": str(destination), "start": self.number, "step": self.step,
                "count": amount, "width": self.frame["width"], "height": self.frame["height"], "order": self.frame["order"]})
        ttk.Button(body, text="选择文件夹并导出", command=start, style="Accent.TButton").pack(fill="x")
        dialog.grab_set()
        field.focus_set()

    def cancel_batch(self):
        self.worker.cancelled.set()
        self.cancel_button.configure(state="disabled")
        self.status_var.set("正在完成当前文件，随后停止；已经保存的图片会保留。")

    def close(self):
        if self.busy and self.busy[1] in ("batch", "save_png", "save_session", "save_text"):
            self.closing = True
            if self.busy[1] == "batch":
                self.cancel_batch()
            else:
                self.status_var.set("正在完成保存，随后关闭…")
        else:
            self._destroy()

    def _destroy(self):
        self.worker.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
