"""SCORE FX - 视觉主题与通用工具。"""

from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import font as tkfont


class C:
    """深色行情终端配色。"""

    BG = "#060B10"
    HEADER = "#081018"
    FOOTER = "#070D13"
    PANEL = "#0B141C"
    PANEL_2 = "#0F1B25"
    PANEL_3 = "#142531"
    FIELD = "#0D1822"
    BORDER = "#1A2B37"
    BORDER_LIGHT = "#294351"
    GRID = "#14232E"
    TEXT = "#F5FAFD"
    SOFT = "#C2D5E1"
    MUTED = "#8DA4B5"
    DIM = "#5C7384"
    WHITE = "#FFFFFF"

    ACCENT = "#4AD7FF"
    ACCENT_SOFT = "#1B4653"
    ACCENT_DIM = "#10313D"

    UP = "#FF6B7A"        # 上涨 / 盈利红
    UP_DARK = "#C93E50"   # 红色按钮按下态
    DOWN = "#4DA3FF"      # 下跌 / 亏损蓝
    LINE_DOWN = "#4DA3FF"
    UP_GLOW = "#3A1E26"
    DOWN_GLOW = "#122D47"
    BUY = "#E95062"
    BUY_HOVER = "#FF6477"
    SELL = "#2D8CFF"
    SELL_HOVER = "#57A9FF"

    GOLD = "#F2C14E"
    GOLD_DIM = "#3A3016"
    PURPLE = "#AA8BFF"
    BLUE = "#58A6FF"
    EVENT_GOOD = "#63DB86"
    EVENT_BAD = "#FF7C88"
    EVENT_MIXED = "#F2C14E"


def setup_dpi_awareness() -> None:
    """Windows 高分屏下尽量保持字体清晰。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class FontBook:
    def __init__(self) -> None:
        self.ui_family = "Microsoft YaHei UI"
        self.num_family = "Bahnschrift"
        self.mono_family = "Consolas"
        self._ready = False

    def detect(self, root: tk.Misc) -> None:
        available = set(tkfont.families(root))
        self.ui_family = self._first(
            available,
            ["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "SimHei", "Segoe UI"],
            "TkDefaultFont",
        )
        self.num_family = self._first(
            available,
            ["Bahnschrift", "DIN Alternate", "Segoe UI Semibold", "Arial", "Segoe UI"],
            "TkDefaultFont",
        )
        self.mono_family = self._first(
            available,
            ["Cascadia Mono", "JetBrains Mono", "Consolas", "Courier New"],
            "TkFixedFont",
        )
        self._ready = True

    @staticmethod
    def _first(available, choices, fallback):
        for name in choices:
            if name in available:
                return name
        try:
            return tkfont.nametofont(fallback).actual("family")
        except Exception:
            return "TkDefaultFont"

    def ui(self, size: int, weight: str = "normal"):
        return (self.ui_family, max(8, size), weight)

    def num(self, size: int, weight: str = "normal"):
        return (self.num_family, size, weight)

    def mono(self, size: int, weight: str = "normal"):
        return (self.mono_family, max(8, size), weight)


FONTS = FontBook()


def fmt_num(value: float, decimals: int = 1, signed: bool = False) -> str:
    if value is None:
        return "--"
    format_spec = f"{'+' if signed else ''},.{decimals}f"
    return format(value, format_spec)


def fmt_money(value: float, signed: bool = False) -> str:
    return fmt_num(value, 1, signed)


def fmt_pct(value: float, signed: bool = True) -> str:
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def pnl_color(value: float) -> str:
    if value > 0.005:
        return C.UP
    if value < -0.005:
        return C.DOWN
    return C.TEXT


def event_color(tone: str) -> str:
    return {"good": C.EVENT_GOOD, "bad": C.EVENT_BAD}.get(tone, C.EVENT_MIXED)


def round_points(x1: float, y1: float, x2: float, y2: float, r: float):
    """返回用于 Canvas smooth 多边形的圆角矩形顶点。"""
    r = max(1.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


def draw_round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kwargs):
    return canvas.create_polygon(
        round_points(x1, y1, x2, y2, r),
        smooth=True,
        splinesteps=20,
        **kwargs,
    )


def make_card(parent: tk.Misc) -> tk.Frame:
    return tk.Frame(
        parent,
        bg=C.PANEL,
        highlightbackground=C.BORDER,
        highlightthickness=1,
        bd=0,
    )


def make_flat_button(
    parent: tk.Misc,
    text: str,
    command,
    *,
    bg: str = C.PANEL_2,
    fg: str = C.TEXT,
    active_bg: str = C.PANEL_3,
    font=None,
    padx: int = 10,
    pady: int = 5,
    width: int = 0,
    anchor: str = "center",
) -> tk.Button:
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=active_bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=font or FONTS.ui(9),
        padx=padx,
        pady=pady,
        cursor="hand2",
        takefocus=0,
        anchor=anchor,
    )
    if width:
        btn.configure(width=width)
    return btn
