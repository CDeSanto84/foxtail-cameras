#!/usr/bin/env python3
import os
import shutil
import socket
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from configuration import load_config

APP_VERSION = "v0.5 HOME"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = load_config()

ICON_PATHS = [
    os.path.join(APP_DIR, "assets", "foxtail-cameras-launcher.png"),
    os.path.join(APP_DIR, "assets", "cctv-master.png"),
    os.path.join(APP_DIR, "assets", "Camera1-clean.png"),
    os.path.join(APP_DIR, "assets", "Camera1-app.png"),
    os.path.join(APP_DIR, "assets", "Camera.png"),
]

REOLINK_IP = CONFIG.camera_host
BLINK_SYNC_IP = CONFIG.blink_host
ALEXA_URL = "https://alexa.amazon.com"

PALMCORE_IP = CONFIG.home_assistant_host
HOME_ASSISTANT_PORT = CONFIG.home_assistant_port
HOME_ASSISTANT_URL = f"http://{PALMCORE_IP}:{HOME_ASSISTANT_PORT}" if PALMCORE_IP else ""

BG = "#030405"
SURFACE = "#0a0c0d"
CARD = "#101315"
CARD_SOFT = "#161a1d"
CARD_INNER = "#080a0b"
BORDER_SOFT = "#4f432a"
BORDER_FAINT = "#272219"
BORDER_GOLD = "#8f7340"
LINE = "#252018"

GOLD = "#d1ad67"
GOLD_BRIGHT = "#f4e4b8"
GOLD_DARK = "#6f5528"
TEXT = "#f5ecd7"
MUTED = "#aaa08d"
MUTED_DARK = "#746b5c"
GREEN = "#66e895"
RED = "#ff6b61"
BLUE = "#7fb7ff"
BUTTON_DARK = "#15181a"


def _rounded_rect(canvas, x1, y1, x2, y2, radius=24, **kwargs):
    radius = min(radius, max(0, (x2 - x1) // 2), max(0, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=28, **kwargs)


class RoundedPanel(tk.Canvas):
    def __init__(self, parent, bg_color=CARD, border_color=BORDER_SOFT, radius=28, border_width=1, pad=12):
        super().__init__(
            parent,
            bg=parent.cget("bg") if hasattr(parent, "cget") else BG,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.bg_color = bg_color
        self.border_color = border_color
        self.radius = radius
        self.border_width = border_width
        self.pad = pad

        self.inner = tk.Frame(self, bg=bg_color, bd=0, highlightthickness=0)
        self.window_id = self.create_window(
            self.pad,
            self.pad,
            anchor="nw",
            window=self.inner,
        )

        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("shape")
        w = max(2, self.winfo_width())
        h = max(2, self.winfo_height())

        # Soft outer glow/border
        _rounded_rect(
            self,
            2,
            2,
            w - 2,
            h - 2,
            radius=self.radius,
            fill=self.bg_color,
            outline=self.border_color,
            width=self.border_width,
            tags="shape",
        )

        # Subtle inner highlight line
        _rounded_rect(
            self,
            6,
            6,
            w - 6,
            h - 6,
            radius=max(8, self.radius - 6),
            fill="",
            outline=BORDER_FAINT,
            width=1,
            tags="shape",
        )

        self.coords(self.window_id, self.pad, self.pad)
        self.itemconfigure(
            self.window_id,
            width=max(1, w - self.pad * 2),
            height=max(1, h - self.pad * 2),
        )
        self.tag_lower("shape")

    def cget(self, key):
        if key == "bg":
            return self.bg_color
        return super().cget(key)


class PillButton(tk.Canvas):
    def __init__(self, parent, text, command, primary=False):
        self.primary = primary
        self.command = command
        self.text_value = text

        self.bg_parent = parent.cget("bg") if hasattr(parent, "cget") else BG
        self.fill = GOLD_BRIGHT if primary else BUTTON_DARK
        self.hover = "#fff0bd" if primary else "#23201a"
        self.fg = "#050505" if primary else TEXT
        self.border = GOLD if primary else BORDER_GOLD

        # Width tuned for current labels; height gives pill shape.
        width = max(126, len(text) * 10 + 34)
        height = 34

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=self.bg_parent,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )

        self.shape = None
        self.label = None
        self.draw(self.fill)

        self.bind("<Enter>", lambda _e: self.draw(self.hover))
        self.bind("<Leave>", lambda _e: self.draw(self.fill))
        self.bind("<Button-1>", lambda _e: self.command())

    def draw(self, fill):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        _rounded_rect(
            self,
            2,
            2,
            w - 2,
            h - 2,
            radius=h // 2,
            fill=fill,
            outline=self.border,
            width=1,
        )
        self.create_text(
            w // 2,
            h // 2,
            text=self.text_value,
            fill=self.fg,
            font=("Inter", 11, "bold"),
        )

class FoxtailCameras(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"Foxtail Cameras {APP_VERSION}")
        self.geometry("1580x800")
        self.minsize(1320, 720)
        self.configure(bg=BG)

        self.logo = self.load_icon(40)
        if self.logo:
            self.iconphoto(True, self.logo)

        self.status_vars = {
            "rtsp": tk.StringVar(value="Checking RTSP…"),
            "basic": tk.StringVar(value="Checking service…"),
            "onvif": tk.StringVar(value="Checking ONVIF…"),
            "blink": tk.StringVar(value="Checking Blink…"),
            "browser": tk.StringVar(value="Checking browser…"),
            "palmcore": tk.StringVar(value="Checking Home Core…"),
            "ha": tk.StringVar(value="Checking Home Assistant…"),
        }

        self.build()
        self.center()
        self.refresh_status()

    def center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{max(0, (sw-w)//2)}+{max(0, (sh-h)//2)}")

    def icon_path(self):
        for p in ICON_PATHS:
            if os.path.exists(p):
                return p
        return None

    def load_icon(self, size):
        p = self.icon_path()
        if not p:
            return None
        try:
            img = Image.open(p).convert("RGBA")
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(img, ((size - img.width)//2, (size - img.height)//2))
            return ImageTk.PhotoImage(canvas)
        except Exception:
            return None

    def panel(self, parent, bg=CARD, border=BORDER_SOFT, thickness=1):
        return RoundedPanel(
            parent,
            bg_color=bg,
            border_color=border,
            radius=30,
            border_width=thickness,
            pad=12,
        )

    def text(self, parent, value, size=13, fg=TEXT, bg=None, bold=False, anchor="w", **pack):
        # If parent is a rounded panel, place text inside its inner frame.
        target = parent.inner if isinstance(parent, RoundedPanel) else parent
        lbl = tk.Label(
            target,
            text=value,
            fg=fg,
            bg=bg or target.cget("bg"),
            font=("Inter", size, "bold" if bold else "normal"),
            anchor=anchor,
        )
        lbl.pack(**pack)
        return lbl

    def button(self, parent, value, command, primary=False):
        return PillButton(parent, value, command, primary)

    def separator(self, parent, bg=LINE):
        line = tk.Frame(parent, bg=bg, height=1)
        line.pack(fill="x", pady=10)
        return line

    def status_dot(self, parent, text="Online"):
        pill = tk.Frame(parent, bg="#102016", highlightbackground="#2c7d4c", highlightthickness=1, bd=0)
        pill.pack(anchor="center", pady=(6, 0))
        tk.Label(
            pill,
            text=f"● {text}",
            bg="#102016",
            fg=GREEN,
            font=("Inter", 9, "bold"),
            padx=9,
            pady=2,
        ).pack()
        return pill

    def build(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=24, pady=14)
        self.outer = outer

        self.build_header(outer)
        self.build_nav(outer)

        self.view_host = tk.Frame(outer, bg=BG)
        self.view_host.pack(fill="both", expand=True, pady=(10, 0))

        bottom = self.panel(outer, SURFACE, BORDER_SOFT)
        bottom.configure(height=82)
        bottom.pack(fill="x", pady=(6, 0))
        bottom.pack_propagate(False)

        self.build_status_strip(bottom)
        self.show_home()

    def build_header(self, parent):
        header = self.panel(parent, SURFACE, BORDER_GOLD)
        header.configure(height=86)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = tk.Frame(header.inner, bg=SURFACE)
        inner.pack(fill="x", padx=16, pady=9)

        if self.logo:
            logo_wrap = RoundedPanel(
                inner,
                bg_color="#121417",
                border_color=BORDER_GOLD,
                radius=18,
                border_width=1,
                pad=6,
            )
            logo_wrap.configure(width=58, height=58)
            logo_wrap.pack(side="left", padx=(0, 16))
            tk.Label(
                logo_wrap.inner,
                image=self.logo,
                bg="#121417",
            ).pack()

        title_box = tk.Frame(inner, bg=SURFACE)
        title_box.pack(side="left", fill="x", expand=True)

        tk.Label(
            title_box,
            text="Foxtail Cameras",
            bg=SURFACE,
            fg=GOLD_BRIGHT,
            font=("Inter", 22, "bold"),
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="Local cameras · Home Assistant · Device reachability",
            bg=SURFACE,
            fg=MUTED,
            font=("Inter", 9),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        self.ha_header_status = tk.Label(
            inner,
            textvariable=self.status_vars["ha"],
            bg=SURFACE,
            fg=GREEN,
            font=("Inter", 9, "bold"),
        )
        self.ha_header_status.pack(side="right", padx=(16, 4))

    def build_nav(self, parent):
        nav = tk.Frame(parent, bg=BG)
        nav.pack(fill="x", pady=(10, 0))

        self.button(nav, "⌂ Home", self.show_home, True).pack(
            side="left", padx=(0, 8)
        )
        self.button(nav, "◉ Cameras", self.show_cameras, False).pack(
            side="left", padx=(0, 8)
        )
        self.button(
            nav,
            "◇ Devices",
            lambda: self.show_placeholder(
                "Devices",
                "Home Assistant devices will live here.",
            ),
            False,
        ).pack(side="left", padx=(0, 8))

        self.button(
            nav,
            "⚡ Automations",
            lambda: self.show_placeholder(
                "Automations",
                "Home Core automations and scenes will live here.",
            ),
            False,
        ).pack(side="left", padx=(0, 8))

        self.button(
            nav,
            "↗ Home Assistant",
            self.open_home_assistant,
            False,
        ).pack(side="right")

    def clear_view(self):
        for child in self.view_host.winfo_children():
            child.destroy()

    def show_home(self):
        self.clear_view()

        main = tk.Frame(self.view_host, bg=BG)
        main.pack(fill="both", expand=True)

        main.grid_columnconfigure(0, weight=1, uniform="home")
        main.grid_columnconfigure(1, weight=1, uniform="home")
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        core = self.panel(main, CARD, BORDER_GOLD)
        core.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 9),
            pady=(0, 9),
        )

        security = self.panel(main, CARD, BORDER_GOLD)
        security.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(9, 0),
            pady=(0, 9),
        )

        cameras = self.panel(main, CARD, BORDER_SOFT)
        cameras.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(0, 9),
            pady=(9, 0),
        )

        actions = self.panel(main, CARD, BORDER_SOFT)
        actions.grid(
            row=1,
            column=1,
            sticky="nsew",
            padx=(9, 0),
            pady=(9, 0),
        )

        # Home Core / HA
        self.text(
            core,
            "Home Core",
            20,
            GOLD_BRIGHT,
            bold=True,
            padx=18,
            pady=(16, 2),
        )
        self.text(
            core,
            "Home Assistant backend",
            10,
            MUTED,
            padx=18,
        )

        tk.Label(
            core.inner,
            textvariable=self.status_vars["palmcore"],
            bg=CARD,
            fg=GREEN,
            font=("Inter", 12, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 3))

        tk.Label(
            core.inner,
            textvariable=self.status_vars["ha"],
            bg=CARD,
            fg=GREEN,
            font=("Inter", 11),
        ).pack(anchor="w", padx=18)

        self.text(
            core,
            f"{PALMCORE_IP}:{HOME_ASSISTANT_PORT}" if PALMCORE_IP else "Not configured",
            9,
            MUTED_DARK,
            padx=18,
            pady=(3, 14),
        )

        self.button(
            core.inner,
            "Open Home Assistant",
            self.open_home_assistant,
            True,
        ).pack(anchor="w", padx=18, pady=(0, 14))

        # Security
        self.text(
            security,
            "Security",
            20,
            GOLD_BRIGHT,
            bold=True,
            padx=18,
            pady=(16, 2),
        )
        self.text(
            security,
            "Camera and perimeter health",
            10,
            MUTED,
            padx=18,
        )

        for name, var in (
            ("Reolink RTSP", self.status_vars["rtsp"]),
            ("Reolink ONVIF", self.status_vars["onvif"]),
            ("Blink Sync Module", self.status_vars["blink"]),
        ):
            row = tk.Frame(security.inner, bg=CARD)
            row.pack(fill="x", padx=18, pady=5)

            tk.Label(
                row,
                text=name,
                bg=CARD,
                fg=TEXT,
                font=("Inter", 10, "bold"),
            ).pack(side="left")

            tk.Label(
                row,
                textvariable=var,
                bg=CARD,
                fg=GREEN,
                font=("Inter", 9),
            ).pack(side="right")

        # Cameras
        self.text(
            cameras,
            "Cameras",
            20,
            GOLD_BRIGHT,
            bold=True,
            padx=18,
            pady=(16, 2),
        )
        self.text(
            cameras,
            "Existing Foxtail camera engine preserved",
            10,
            MUTED,
            padx=18,
        )

        self.button(
            cameras.inner,
            "Open Camera Dashboard",
            self.show_cameras,
            True,
        ).pack(anchor="w", padx=18, pady=(22, 8))

        self.button(
            cameras.inner,
            "▶ Local Camera",
            lambda: self.launch_reolink("sub"),
            False,
        ).pack(anchor="w", padx=18, pady=(0, 14))

        # Actions
        self.text(
            actions,
            "Quick Actions",
            20,
            GOLD_BRIGHT,
            bold=True,
            padx=18,
            pady=(16, 2),
        )
        self.text(
            actions,
            "Direct access without digging through apps",
            10,
            MUTED,
            padx=18,
        )

        self.button(
            actions.inner,
            "↗ Blink Live",
            self.open_alexa,
            True,
        ).pack(anchor="w", padx=18, pady=(22, 8))

        self.button(
            actions.inner,
            "⟳ Refresh Systems",
            self.refresh_status,
            False,
        ).pack(anchor="w", padx=18, pady=(0, 14))

    def show_cameras(self):
        self.clear_view()

        main = tk.Frame(self.view_host, bg=BG)
        main.pack(fill="both", expand=True)

        main.grid_columnconfigure(0, weight=1, uniform="cards")
        main.grid_columnconfigure(1, weight=1, uniform="cards")
        main.grid_rowconfigure(0, weight=1)

        left = self.panel(main, CARD, BORDER_GOLD)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))

        right = self.panel(main, CARD, BORDER_GOLD)
        right.grid(row=0, column=1, sticky="nsew", padx=(18, 0))

        self.build_reolink(left)
        self.build_blink(right)

    def show_placeholder(self, title, subtitle):
        self.clear_view()

        card = self.panel(self.view_host, CARD, BORDER_GOLD)
        card.pack(fill="both", expand=True)

        self.text(
            card,
            title,
            24,
            GOLD_BRIGHT,
            bold=True,
            anchor="center",
            pady=(90, 8),
        )
        self.text(
            card,
            subtitle,
            12,
            MUTED,
            anchor="center",
        )
        self.text(
            card,
            "Connected through Home Core / Home Assistant",
            9,
            MUTED_DARK,
            anchor="center",
            pady=(8, 0),
        )

    def build_reolink(self, card):
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        top = tk.Frame(card.inner, bg=CARD)
        top.pack(fill="x", padx=22, pady=(10, 4))

        self.text(top, "Local Camera", 19, GOLD_BRIGHT, bold=True, anchor="center")
        self.text(top, "Reolink · Local RTSP", 11, MUTED, anchor="center")
        self.status_dot(top, "Status below")

        preview = self.panel(card.inner, CARD_INNER, BORDER_SOFT)
        preview.configure(height=72)
        preview.pack(fill="x", padx=22, pady=(7, 10))
        preview.pack_propagate(False)

        preview_inner = tk.Frame(preview.inner, bg=CARD_INNER)
        preview_inner.pack(fill="both", expand=True, padx=16, pady=10)

        tk.Label(
            preview_inner,
            text="Local RTSP",
            bg=CARD_INNER,
            fg=GOLD_BRIGHT,
            font=("Inter", 16, "bold"),
        ).pack(expand=True)

        tk.Label(
            preview_inner,
            text="Quick View uses sub stream · Full View uses main stream",
            bg=CARD_INNER,
            fg=MUTED,
            font=("Inter", 9),
        ).pack(pady=(0, 2))

        details = tk.Frame(card.inner, bg=CARD)
        details.pack(fill="x", padx=22, pady=(0, 7))

        self.row(details, "Host", REOLINK_IP or "Not configured")
        self.row(details, "RTSP probe", "TCP 554 · status below", MUTED)
        self.row(details, "Basic service probe", "TCP 9000 · status below", MUTED)
        self.row(details, "ONVIF probe", "TCP 8000 · status below", MUTED)

        buttons = tk.Frame(card.inner, bg=CARD)
        buttons.pack(fill="x", padx=22, pady=(0, 18))

        self.button(buttons, "▶ Quick View", lambda: self.launch_reolink("sub"), True).pack(side="left", padx=(0, 10))
        self.button(buttons, "⛶ Full View", lambda: self.launch_reolink("main"), False).pack(side="left")

    def build_blink(self, card):
        top = tk.Frame(card.inner, bg=CARD)
        top.pack(fill="x", padx=22, pady=(10, 4))

        self.text(top, "Blink Cameras", 19, GOLD_BRIGHT, bold=True, anchor="center")
        self.text(top, "via Alexa Browser", 11, MUTED, anchor="center")
        self.status_dot(top, "Status below")

        preview = self.panel(card.inner, CARD_INNER, BORDER_SOFT)
        preview.configure(height=72)
        preview.pack(fill="x", padx=22, pady=(7, 10))
        preview.pack_propagate(False)

        preview_inner = tk.Frame(preview.inner, bg=CARD_INNER)
        preview_inner.pack(fill="both", expand=True, padx=16, pady=10)

        tk.Label(
            preview_inner,
            text="Blink Live",
            bg=CARD_INNER,
            fg=GOLD_BRIGHT,
            font=("Inter", 16, "bold"),
        ).pack(expand=True)

        tk.Label(
            preview_inner,
            text="Browser-based live view/control through Alexa",
            bg=CARD_INNER,
            fg=MUTED,
            font=("Inter", 9),
        ).pack(pady=(0, 2))

        details = tk.Frame(card.inner, bg=CARD)
        details.pack(fill="x", padx=22, pady=(0, 7))

        self.row(details, "Sync Module", BLINK_SYNC_IP or "Not configured")
        self.row(details, "Launch Path", "alexa.amazon.com", MUTED)
        self.row(details, "Mode", "Browser-based view", MUTED)

        buttons = tk.Frame(card.inner, bg=CARD)
        buttons.pack(fill="x", padx=22, pady=(0, 18))

        self.button(buttons, "↗ Open Blink", self.open_alexa, True).pack(side="left", padx=(0, 10))
        self.button(buttons, "↗ Open Alexa", self.open_alexa, False).pack(side="left")

    def row(self, parent, key, value, color=TEXT):
        row = tk.Frame(parent, bg=parent.cget("bg"))
        row.pack(fill="x", pady=2)

        tk.Label(
            row,
            text=key,
            bg=parent.cget("bg"),
            fg=MUTED_DARK,
            font=("Inter", 9),
        ).pack(side="left")

        tk.Label(
            row,
            text=value,
            bg=parent.cget("bg"),
            fg=color,
            font=("Inter", 10, "bold"),
        ).pack(side="right")

        line = tk.Frame(parent, bg=LINE, height=1)
        line.pack(fill="x")

    def build_status_strip(self, strip):
        inner = tk.Frame(strip.inner, bg=SURFACE)
        inner.pack(fill="x", padx=16, pady=11)

        tk.Label(
            inner,
            text="Home Core",
            bg=SURFACE,
            fg=GOLD_BRIGHT,
            font=("Inter", 13, "bold"),
        ).pack(side="left", padx=(0, 14))

        self.status_chip(inner, "HA", self.status_vars["ha"])
        self.status_chip(inner, "RTSP", self.status_vars["rtsp"])
        self.status_chip(inner, "ONVIF", self.status_vars["onvif"])
        self.status_chip(inner, "Blink", self.status_vars["blink"])

        self.button(
            inner,
            "⟳ Refresh",
            self.refresh_status,
            False,
        ).pack(side="right")

    def status_chip(self, parent, title, var):
        chip_bg = "#111416"
        chip = RoundedPanel(parent, bg_color=chip_bg, border_color=BORDER_SOFT, radius=16, border_width=1, pad=0)
        chip.configure(width=96, height=48)
        chip.pack(side="left", padx=(0, 8))
        chip.pack_propagate(False)

        tk.Label(
            chip.inner,
            text=title,
            bg=chip_bg,
            fg=GOLD_BRIGHT,
            font=("Inter", 9, "bold"),
        ).pack(anchor="w", padx=10, pady=(7, 0))

        tk.Label(
            chip.inner,
            textvariable=var,
            bg=chip_bg,
            fg=MUTED,
            font=("Inter", 8),
        ).pack(anchor="w", padx=10, pady=(0, 7))

    def port_open(self, ip, port, timeout=0.7):
        if not ip:
            return False
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except OSError:
            return False

    def ping(self, ip):
        if not ip:
            return False
        try:
            return subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
        except Exception:
            return False

    def refresh_status(self):
        def work():
            rtsp = self.port_open(REOLINK_IP, 554)
            basic = self.port_open(REOLINK_IP, 9000)
            onvif = self.port_open(REOLINK_IP, 8000)
            blink = self.ping(BLINK_SYNC_IP)

            palmcore = self.ping(PALMCORE_IP)
            ha = self.port_open(PALMCORE_IP, HOME_ASSISTANT_PORT)

            browser = bool(self.find_browser())

            def apply():
                self.status_vars["rtsp"].set(
                    "554 reachable" if rtsp else "not reachable" if REOLINK_IP else "not configured"
                )
                self.status_vars["basic"].set(
                    "9000 reachable" if basic else "not reachable" if REOLINK_IP else "not configured"
                )
                self.status_vars["onvif"].set(
                    "8000 reachable" if onvif else "not reachable" if REOLINK_IP else "not configured"
                )
                self.status_vars["blink"].set(
                    "reachable" if blink else "not reachable" if BLINK_SYNC_IP else "not configured"
                )
                self.status_vars["palmcore"].set(
                    "● Host reachable" if palmcore else "● Host not reachable" if PALMCORE_IP else "● Host not configured"
                )
                self.status_vars["ha"].set(
                    "HA port reachable" if ha else "HA port not reachable" if PALMCORE_IP else "HA not configured"
                )
                self.status_vars["browser"].set(
                    "available" if browser else "missing"
                )

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def open_home_assistant(self):
        if not HOME_ASSISTANT_URL:
            messagebox.showinfo("Foxtail Cameras", "Set home_assistant_host in your private configuration first.")
            return
        browser = self.find_browser()
        if not browser:
            messagebox.showerror(
                "Foxtail Cameras",
                "No Chrome/Chromium browser found.",
            )
            return

        try:
            subprocess.Popen(
                [browser, f"--app={HOME_ASSISTANT_URL}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            messagebox.showerror(
                "Foxtail Cameras",
                f"Could not open Home Assistant: {exc}",
            )

    def find_browser(self):
        return (
            shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
        )

    def launch_reolink(self, stream):
        helper = str(CONFIG.viewer_helper)
        if not os.path.exists(helper):
            messagebox.showerror("Foxtail Cameras", "Missing helper: foxtail-reolink-view")
            return
        subprocess.Popen([helper, stream])

    def open_alexa(self):
        browser = self.find_browser()
        if not browser:
            messagebox.showerror("Foxtail Cameras", "No Chrome/Chromium browser found.")
            return
        subprocess.Popen([browser, f"--app={ALEXA_URL}"])


if __name__ == "__main__":
    FoxtailCameras().mainloop()
