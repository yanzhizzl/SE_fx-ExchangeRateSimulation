"""SCORE FX - 自定义界面组件。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from typing import Callable, Optional

import engine as E
import questions as Q
from theme import (
    C,
    FONTS,
    draw_round_rect,
    event_color,
    fmt_pct,
    make_flat_button,
    pnl_color,
)


ASSET_DIR = Path(__file__).resolve().parent / "assets"


class BrightSlider(tk.Canvas):
    """高对比度自绘滑杆，数量与杠杆使用同一套明亮配色。"""

    def __init__(
        self,
        parent,
        from_: float,
        to: float,
        value: float,
        *,
        step: float = 1.0,
        command: Optional[Callable] = None,
        parent_bg: str = C.PANEL,
        color: str = C.ACCENT,
        integer: bool = False,
    ) -> None:
        super().__init__(
            parent,
            height=30,
            width=1,
            bg=parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._from = float(from_)
        self._to = float(to)
        self._step = float(step)
        self._integer = integer
        self._value = self._clamp(value)
        self._command = command
        self._color = color
        self._dragging = False
        self._hover = False
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.after_idle(self._draw)

    def _clamp(self, value: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = self._from
        value = max(self._from, min(self._to, value))
        steps = round((value - self._from) / self._step)
        value = self._from + steps * self._step
        if self._integer:
            return int(round(value))
        return round(value, 4)

    def get(self):
        return self._value

    def set(self, value, notify: bool = False):
        new_value = self._clamp(value)
        if new_value == self._value:
            self._draw()
            return
        self._value = new_value
        self._draw()
        if notify and self._command:
            self._command(self._value)

    def _fraction(self):
        span = self._to - self._from
        return (self._value - self._from) / span if span else 0.0

    def _draw(self):
        self.delete("all")
        w = max(20, self.winfo_width())
        h = max(16, self.winfo_height())
        pad = 12
        x1, x2 = pad, w - pad
        mid = h / 2
        track_h = 6
        # 暗色轨道
        draw_round_rect(
            self, x1, mid - track_h / 2, x2, mid + track_h / 2, track_h / 2,
            fill=C.BORDER_LIGHT, outline=C.BORDER_LIGHT
        )
        fraction = max(0.0, min(1.0, self._fraction()))
        thumb_x = x1 + (x2 - x1) * fraction
        if thumb_x > x1:
            draw_round_rect(
                self, x1, mid - track_h / 2, max(x1 + 3, thumb_x), mid + track_h / 2,
                track_h / 2, fill=self._color, outline=self._color
            )
        # 刻度点
        for i in range(5):
            x = x1 + (x2 - x1) * i / 4
            dot_color = self._color if x <= thumb_x else C.DIM
            self.create_oval(x - 1, mid - 13, x + 1, mid - 11, fill=dot_color, outline=dot_color)
        # 发光圆钮
        radius = 8 if not self._hover else 9
        self.create_oval(
            thumb_x - radius - 4, mid - radius - 4,
            thumb_x + radius + 4, mid + radius + 4,
            fill=C.ACCENT_DIM, outline=C.ACCENT_DIM
        )
        self.create_oval(
            thumb_x - radius, mid - radius,
            thumb_x + radius, mid + radius,
            fill=C.TEXT, outline=self._color, width=2
        )
        self.create_oval(
            thumb_x - 3, mid - 3, thumb_x + 3, mid + 3,
            fill=self._color, outline=self._color
        )

    def _on_enter(self, _event=None):
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._draw()

    def _on_press(self, event):
        self._dragging = True
        self._set_from_x(event.x)

    def _on_drag(self, event):
        if self._dragging:
            self._set_from_x(event.x)

    def _on_release(self, _event=None):
        self._dragging = False

    def _set_from_x(self, x):
        width = max(1, self.winfo_width())
        pad = 12
        usable = max(1, width - 2 * pad)
        fraction = max(0.0, min(1.0, (x - pad) / usable))
        value = self._from + fraction * (self._to - self._from)
        new_value = self._clamp(value)
        if new_value != self._value:
            self._value = new_value
            self._draw()
            if self._command:
                self._command(self._value)
        else:
            self._draw()


# ---------------------------------------------------------------------------
# 可滚动弹窗容器
# ---------------------------------------------------------------------------

class SlimScrollbar(tk.Canvas):
    """不依赖系统主题的细滚动条，避免 Windows 原生滚动条破坏深色界面。"""

    def __init__(self, parent, command, bg: str = C.PANEL):
        super().__init__(
            parent,
            width=9,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._command = command
        self._first = 0.0
        self._last = 1.0
        self._dragging = False
        self._drag_offset = 0.0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_dragging", False))

    def set(self, first, last):
        try:
            self._first = max(0.0, min(1.0, float(first)))
            self._last = max(0.0, min(1.0, float(last)))
        except (TypeError, ValueError):
            self._first, self._last = 0.0, 1.0
        self._draw()

    def _thumb_bounds(self):
        height = max(1, self.winfo_height())
        if self._last - self._first >= 0.999:
            return None
        thumb_h = max(20.0, height * (self._last - self._first))
        top = self._first * height
        top = min(height - thumb_h, max(0.0, top))
        return top, top + thumb_h

    def _draw(self):
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.create_rectangle(
            width - 3, 2, width - 1, height - 2,
            fill=C.GRID, outline=C.GRID,
        )
        thumb = self._thumb_bounds()
        if thumb is None:
            return
        top, bottom = thumb
        draw_round_rect(
            self,
            1, top, width - 1, bottom,
            max(2, (width - 2) / 2),
            fill=C.MUTED,
            outline=C.MUTED,
        )

    def _on_press(self, event):
        thumb = self._thumb_bounds()
        if thumb is None:
            return
        height = max(1, self.winfo_height())
        top, bottom = thumb
        if top <= event.y <= bottom:
            self._dragging = True
            self._drag_offset = event.y - top
        else:
            self._dragging = True
            self._drag_offset = (bottom - top) / 2
            self._move_to(event.y)
        self._draw()

    def _on_drag(self, event):
        if self._dragging:
            self._move_to(event.y)
            self._draw()

    def _move_to(self, mouse_y):
        height = max(1, self.winfo_height())
        thumb = self._thumb_bounds()
        if thumb is None:
            return
        thumb_h = thumb[1] - thumb[0]
        top = max(0.0, min(height - thumb_h, mouse_y - self._drag_offset))
        first = top / height
        try:
            self._command("moveto", str(first))
        except Exception:
            pass


class ScrollableFrame(tk.Frame):
    """固定大小弹窗内使用的纵向滚动区域，滚轮与滚动条均可使用。"""

    def __init__(self, parent, bg: str = C.PANEL):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(
            self,
            bg=bg,
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.scrollbar = SlimScrollbar(self, command=self.canvas.yview, bg=bg)
        self.scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollbar.set(*self.canvas.yview())

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=max(1, event.width))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollbar.set(*self.canvas.yview())

    def bind_wheel_to_children(self):
        self._bind_mousewheel(self.inner)
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.scrollbar)

    def _bind_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel(child)

    def _on_mousewheel(self, event):
        content_height = max(1, self.inner.winfo_reqheight())
        view_height = max(1, self.canvas.winfo_height())
        if content_height <= view_height + 2:
            return None
        if getattr(event, "num", None) == 4:
            amount = -1
        elif getattr(event, "num", None) == 5:
            amount = 1
        else:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return None
            amount = -1 if delta > 0 else 1
        self.canvas.yview_scroll(amount * 3, "units")
        return "break"

    def scroll_to_end(self):
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(1.0)


# ---------------------------------------------------------------------------
# 按钮与弹出提示
# ---------------------------------------------------------------------------

class RoundedButton(tk.Canvas):
    """纯 Canvas 绘制的圆角按钮，避免系统按钮的灰色边框。"""

    def __init__(
        self,
        parent,
        text: str,
        command: Optional[Callable] = None,
        *,
        width: int = 130,
        height: int = 38,
        fill: str = C.PANEL_2,
        hover_fill: Optional[str] = None,
        fg: str = C.TEXT,
        font=None,
        subtext: str = "",
        subfont=None,
        outline: Optional[str] = None,
        parent_bg: str = C.PANEL,
        radius: int = 8,
        enabled: bool = True,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2" if enabled else "arrow",
        )
        self._text = text
        self._subtext = subtext
        self._command = command
        self._fill = fill
        self._hover_fill = hover_fill or fill
        self._fg = fg
        self._font = font or FONTS.ui(10, "bold")
        self._subfont = subfont or FONTS.ui(8)
        self._outline = outline
        self._radius = radius
        self._enabled = enabled
        self._hover = False
        self._req_width = width
        self._req_height = height
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.after_idle(self._draw)

    def _draw(self) -> None:
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        self.delete("all")
        if self._enabled:
            fill = self._hover_fill if self._hover else self._fill
            fg = self._fg
            outline = self._outline or fill
        else:
            fill = C.PANEL_3
            fg = C.DIM
            outline = C.BORDER
        draw_round_rect(self, 1, 1, w - 1, h - 1, self._radius, fill=fill, outline=outline, width=1)
        if self._subtext:
            self.create_text(
                w / 2, h / 2 - 7, text=self._text, fill=fg, font=self._font, anchor="center"
            )
            self.create_text(
                w / 2, h / 2 + 11, text=self._subtext, fill=fg, font=self._subfont, anchor="center"
            )
        else:
            self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font, anchor="center")

    def _on_enter(self, _event=None):
        if self._enabled:
            self._hover = True
            self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._draw()

    def _on_click(self, _event=None):
        if self._enabled and self._command:
            self._command()

    def set_text(self, text: str, subtext: Optional[str] = None):
        self._text = text
        if subtext is not None:
            self._subtext = subtext
        self._draw()

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_colors(self, fill: str, hover_fill: Optional[str] = None, fg: Optional[str] = None):
        self._fill = fill
        self._hover_fill = hover_fill or fill
        if fg is not None:
            self._fg = fg
        self._draw()


class ToastManager:
    """主窗口顶部浮出的临时提示。"""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.frame: Optional[tk.Frame] = None
        self._after_id = None

    def show(self, title: str, detail: str = "", tone: str = "info", duration: int = 4600) -> None:
        self._hide()
        color = event_color(tone) if tone in ("good", "bad", "mixed") else C.ACCENT
        frame = tk.Frame(
            self.root,
            bg=C.PANEL_2,
            highlightbackground=color,
            highlightthickness=1,
            bd=0,
        )
        frame.place(relx=0.5, y=104, anchor="n")
        frame.lift()

        strip = tk.Frame(frame, bg=color, width=3)
        strip.pack(side="left", fill="y")
        content = tk.Frame(frame, bg=C.PANEL_2)
        content.pack(side="left", fill="both", expand=True, padx=14, pady=10)
        title_row = tk.Frame(content, bg=C.PANEL_2)
        title_row.pack(fill="x")
        tk.Label(
            title_row,
            text=title,
            bg=C.PANEL_2,
            fg=color,
            font=FONTS.ui(10, "bold"),
            anchor="w",
        ).pack(side="left")
        close_btn = tk.Label(
            title_row,
            text="×",
            bg=C.PANEL_2,
            fg=C.MUTED,
            font=FONTS.ui(12),
            cursor="hand2",
            padx=8,
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _e: self._hide())
        if detail:
            tk.Label(
                content,
                text=detail,
                bg=C.PANEL_2,
                fg=C.SOFT,
                font=FONTS.ui(9),
                wraplength=460,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(4, 0))
        self.frame = frame
        self._after_id = self.root.after(duration, self._hide)

    def _hide(self):
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.frame is not None:
            try:
                self.frame.destroy()
            except Exception:
                pass
            self.frame = None


# ---------------------------------------------------------------------------
# 行情列表
# ---------------------------------------------------------------------------

class MarketRow(tk.Frame):
    def __init__(self, parent, pair: E.PairMarket, on_select: Callable[[str], None], selected=False):
        super().__init__(parent, bg=C.PANEL_2, height=50, bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.pair = pair
        self.on_select = on_select
        self.selected = bool(selected)
        self._hovered = False

        self.stripe = tk.Frame(self, width=3, bg=C.PANEL_2)
        self.stripe.pack(side="left", fill="y")

        self.inner = tk.Frame(self, bg=C.PANEL_2)
        self.inner.pack(side="left", fill="both", expand=True, padx=(10, 9), pady=4)
        self.inner.columnconfigure(1, weight=1)
        self.inner.rowconfigure(0, weight=1)
        self.inner.rowconfigure(1, weight=1)

        color = E.SUBJECT_COLORS.get(pair.left, C.ACCENT)
        self.badge = tk.Canvas(self.inner, width=30, height=30, bg=C.PANEL_2, highlightthickness=0)
        self.badge.grid(row=0, column=0, rowspan=2, padx=(0, 9), sticky="w")
        draw_round_rect(self.badge, 1, 1, 29, 29, 7, fill=color, outline=color)
        self.badge.create_text(
            15, 15, text=pair.left[0], fill="#071117", font=FONTS.ui(11, "bold")
        )

        self.name_label = tk.Label(
            self.inner,
            text=pair.name,
            bg=C.PANEL_2,
            fg=C.TEXT,
            font=FONTS.ui(10, "bold"),
            anchor="w",
        )
        self.name_label.grid(row=0, column=1, sticky="ew")
        self.code_label = tk.Label(
            self.inner,
            text=pair.code,
            bg=C.PANEL_2,
            fg=C.MUTED,
            font=FONTS.mono(7),
            anchor="w",
        )
        self.code_label.grid(row=1, column=1, sticky="ew")

        self.spark = tk.Canvas(
            self.inner, width=46, height=24, bg=C.PANEL_2, highlightthickness=0
        )
        self.spark.grid(row=0, column=2, rowspan=2, padx=(4, 6))

        self.price_label = tk.Label(
            self.inner,
            text=f"{pair.price:.2f}",
            bg=C.PANEL_2,
            fg=C.TEXT,
            font=FONTS.num(11, "bold"),
            anchor="e",
        )
        self.price_label.grid(row=0, column=3, sticky="e")
        self.change_label = tk.Label(
            self.inner,
            text="",
            bg=C.PANEL_2,
            fg=C.MUTED,
            font=FONTS.num(8),
            anchor="e",
        )
        self.change_label.grid(row=1, column=3, sticky="e")

        self._surface_widgets = [
            self.inner,
            self.badge,
            self.name_label,
            self.code_label,
            self.spark,
            self.price_label,
            self.change_label,
        ]
        self._bind_clicks(self)
        self._apply_surface(C.PANEL_2)
        self.set_selected(selected)
        self.update_market()

    def _bind_clicks(self, widget):
        widget.bind("<Button-1>", lambda _e: self.on_select(self.pair.uid))
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            self._bind_clicks(child)

    def _on_enter(self, _event=None):
        self._hovered = True
        if not self.selected:
            self._apply_surface(C.PANEL_3)

    def _on_leave(self, _event=None):
        self._hovered = False
        if not self.selected:
            self._apply_surface(C.PANEL_2)

    def _apply_surface(self, color: str):
        self.configure(bg=color)
        for widget in self._surface_widgets:
            try:
                widget.configure(bg=color)
            except Exception:
                pass
        self.stripe.configure(bg=C.ACCENT if self.selected else color)

    def set_selected(self, selected: bool):
        self.selected = bool(selected)
        color = C.PANEL_3 if self.selected or self._hovered else C.PANEL_2
        self._apply_surface(color)
        if self.selected:
            self.name_label.configure(fg=C.WHITE)
            self.price_label.configure(fg=C.WHITE)
            self.code_label.configure(text=f"{self.pair.code} · LIVE", fg=C.ACCENT)
        else:
            self.name_label.configure(fg=C.TEXT)
            self.price_label.configure(fg=C.TEXT)
            self.code_label.configure(text=f"{self.pair.code} · PAUSED", fg=C.DIM)

    def update_market(self):
        pair = self.pair
        up = pair.change >= 0
        color = C.UP if up else C.DOWN
        self.price_label.configure(text=f"{pair.price:.2f}")
        self.change_label.configure(
            text=f"{'▲' if up else '▼'} {fmt_pct(pair.change_pct)}",
            fg=color,
        )
        self._draw_spark(color)

    def _draw_spark(self, color: str):
        self.spark.delete("all")
        values = self.pair.short_history(24)
        if len(values) < 2:
            return
        lo, hi = min(values), max(values)
        span = max(0.01, hi - lo)
        w, h = 46.0, 24.0
        pad = 2.0
        points = []
        for i, value in enumerate(values):
            x = pad + i * (w - 2 * pad) / (len(values) - 1)
            y = pad + (hi - value) / span * (h - 2 * pad)
            points.extend([x, y])
        self.spark.create_line(*points, fill=color, width=1.3, smooth=True)
        ex, ey = points[-2], points[-1]
        self.spark.create_oval(ex - 2, ey - 2, ex + 2, ey + 2, fill=color, outline=color)


def configure_position_columns(frame: tk.Misc) -> None:
    frame.columnconfigure(0, weight=2, minsize=124)
    frame.columnconfigure(1, minsize=46)
    frame.columnconfigure(2, minsize=42)
    frame.columnconfigure(3, minsize=38)
    frame.columnconfigure(4, minsize=60)
    frame.columnconfigure(5, minsize=60)
    frame.columnconfigure(6, minsize=104)
    frame.columnconfigure(7, minsize=56)


class PositionRow(tk.Frame):
    def __init__(self, parent, position: E.Position, on_close: Callable[[str], None], index=0):
        super().__init__(parent, bg=C.PANEL_2 if index % 2 == 0 else C.FIELD, height=46)
        self.pack_propagate(False)
        self.position = position
        self.on_close = on_close
        bg = C.PANEL_2 if index % 2 == 0 else C.FIELD
        configure_position_columns(self)

        pair_box = tk.Frame(self, bg=bg)
        pair_box.grid(row=0, column=0, sticky="w", padx=(12, 4))
        self.name_label = tk.Label(
            pair_box, text=position.pair_name, bg=bg, fg=C.TEXT, font=FONTS.ui(9, "bold"), anchor="w"
        )
        self.name_label.pack(anchor="w")
        tk.Label(
            pair_box,
            text=f"{position.tier_name} · {position.pair_code}",
            bg=bg,
            fg=C.MUTED,
            font=FONTS.mono(7),
            anchor="w",
        ).pack(anchor="w")

        direction_color = C.UP if position.direction > 0 else C.DOWN
        self.dir_label = tk.Label(
            self,
            text=position.direction_label,
            bg=C.ACCENT_DIM if position.direction > 0 else "#0D233B",
            fg=direction_color,
            font=FONTS.ui(8, "bold"),
            padx=5,
            pady=2,
        )
        self.dir_label.grid(row=0, column=1, sticky="w")

        self.lots_label = tk.Label(
            self, text=f"{position.lots:.1f}", bg=bg, fg=C.SOFT, font=FONTS.num(9), anchor="w"
        )
        self.lots_label.grid(row=0, column=2, sticky="w")
        self.lev_label = tk.Label(
            self, text=f"{position.leverage}x", bg=bg, fg=C.GOLD, font=FONTS.num(9), anchor="w"
        )
        self.lev_label.grid(row=0, column=3, sticky="w")
        self.entry_label = tk.Label(
            self, text=f"{position.entry_price:.2f}", bg=bg, fg=C.SOFT, font=FONTS.mono(8), anchor="w"
        )
        self.entry_label.grid(row=0, column=4, sticky="w")
        self.price_label = tk.Label(
            self, text="--", bg=bg, fg=C.TEXT, font=FONTS.mono(8), anchor="w"
        )
        self.price_label.grid(row=0, column=5, sticky="w")
        self.pnl_label = tk.Label(
            self, text="+0.0", bg=bg, fg=C.TEXT, font=FONTS.num(9, "bold"), anchor="e"
        )
        self.pnl_label.grid(row=0, column=6, sticky="e", padx=(2, 8))

        self.close_btn = tk.Button(
            self,
            text="考出",
            command=lambda: self.on_close(self.position.pos_id),
            bg=C.UP,
            fg=C.WHITE,
            activebackground=C.UP_DARK,
            activeforeground=C.WHITE,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=FONTS.ui(8),
            padx=7,
            pady=3,
            cursor="hand2",
            takefocus=0,
        )
        self.close_btn.grid(row=0, column=7, sticky="e", padx=(0, 10))

    def update_price(self, price: float):
        pnl = self.position.pnl(price)
        ret = self.position.pnl_pct_of_margin(price)
        self.price_label.configure(text=f"{price:.2f}")
        self.price_label.configure(fg=C.UP if pnl >= 0 else C.DOWN)
        self.pnl_label.configure(
            text=f"{pnl:+,.2f} / {ret:+.1f}%",
            fg=pnl_color(pnl),
        )


# ---------------------------------------------------------------------------
# 答题弹窗
# ---------------------------------------------------------------------------

class QuizDialog:
    def __init__(
        self,
        app,
        *,
        mode: str,
        subject: str,
        level: int,
        question: dict,
        context_title: str,
        context_subtitle: str,
        order_session: Optional[dict] = None,
        on_success: Optional[Callable] = None,
        on_closed: Optional[Callable] = None,
    ) -> None:
        self.app = app
        self.mode = mode
        self.subject = subject
        self.level = level
        self.question = question
        self.context_title = context_title
        self.context_subtitle = context_subtitle
        self.order_session = order_session
        self.on_success = on_success
        self.on_closed = on_closed
        self.meta = Q.DIFFICULTY_META[level]
        self.type_meta = Q.QUESTION_TYPE_META.get(
            question.get("type", "choice"), Q.QUESTION_TYPE_META["choice"]
        )
        self.selected: Optional[int] = None
        self.answer_var = tk.StringVar(master=app.root, value="")
        self.finished = False
        self.closed = False
        self.correct = False
        self.reward = 0
        self.resolution: dict = {}
        self.remaining = int(self.meta["time_limit"])
        self._timer_id = None

        self.top = tk.Toplevel(app.root)
        self.top.title("SCORE FX · 作答")
        self.top.configure(bg=C.PANEL)
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self._build()
        self.top.update_idletasks()
        content_height = self.scroll.inner.winfo_reqheight()
        action_height = self.action_bar.winfo_reqheight()
        desired_height = max(600, min(760, content_height + action_height + 46))
        desired_height = min(desired_height, max(560, self.top.winfo_screenheight() - 110))
        self._center(700, desired_height)
        self.top.grab_set()
        self.top.focus_force()
        self._bind_keys()
        if self.question.get("type") in ("fill", "numeric"):
            self.top.after(120, self._focus_answer_entry)
        self._tick_timer()

    # ----- 构建 -----------------------------------------------------------

    def _build(self):
        color = self.meta["color"]
        tk.Frame(self.top, bg=color, height=5).pack(fill="x")

        # 操作栏固定在底部，中间内容放入滚动区域，避免文字被截断。
        self.action_bar = tk.Frame(self.top, bg=C.PANEL)
        self.action_bar.pack(side="bottom", fill="x", padx=26, pady=(0, 16))

        self.scroll = ScrollableFrame(self.top, bg=C.PANEL)
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(6, 0))
        body = tk.Frame(self.scroll.inner, bg=C.PANEL)
        body.pack(fill="both", expand=True, padx=8, pady=12)

        head = tk.Frame(body, bg=C.PANEL)
        head.pack(fill="x")
        if self.mode == "open":
            eyebrow = "学入资格测验  /  ENTRY EXAM"
        elif self.mode == "exit":
            eyebrow = "考出资格测验  /  EXIT EXAM"
        else:
            eyebrow = "自习室  /  PRACTICE ROOM"
        tk.Label(
            head, text=eyebrow, bg=C.PANEL, fg=color, font=FONTS.mono(8, "bold"), anchor="w"
        ).pack(side="left")
        self.timer_label = tk.Label(
            head, text=f"剩余 {self.remaining}s", bg=C.PANEL, fg=C.GOLD, font=FONTS.num(10, "bold")
        )
        self.timer_label.pack(side="right")
        if self.question.get("type") in ("choice", "judge"):
            tk.Label(
                head,
                text="可提前提交",
                bg=C.ACCENT_DIM,
                fg=C.ACCENT,
                font=FONTS.ui(8),
                padx=7,
                pady=1,
            ).pack(side="right", padx=(0, 10))

        tk.Label(
            body,
            text=self.context_title,
            bg=C.PANEL,
            fg=C.TEXT,
            font=FONTS.ui(17, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(12, 2))
        tk.Label(
            body,
            text=self.context_subtitle,
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(9),
            anchor="w",
        ).pack(fill="x")

        chips = tk.Frame(body, bg=C.PANEL)
        chips.pack(fill="x", pady=(10, 8))
        grade_id = self.question.get("grade") or getattr(self.app, "tier_id", "g1")
        grade_name = Q.GRADE_META.get(grade_id, {}).get("name", "高一")
        self._chip(chips, f"{grade_name}题库 · {self.subject}", C.ACCENT)
        self._chip(chips, f"{self.meta['short']} · {self.meta['label']}", color)
        self._chip(
            chips,
            f"题型 · {self.type_meta['label']}",
            self.type_meta["color"],
        )
        if self.mode == "exit":
            self._chip(chips, "考出答题 · 正常结算", C.GOLD)
        else:
            self._chip(chips, f"答对 +{self.app.preview_reward(self.level, self.mode)} 分起", C.GOLD)

        if self.mode == "open" and self.order_session:
            planned = self.order_session.get("planned_margin", 0.0)
            risk_text = (
                f"学入答题惩罚：答错将扣除 2 倍保证金（共 {planned * 2:,.2f} 分），"
                "本次不建立头寸。"
            )
            risk_color = C.UP
        elif self.mode == "exit" and self.order_session:
            risk_text = (
                "考出答题：答对正常结算；答错时，若当前盈利则收益减半，"
                "若当前亏损则亏损额翻倍。行情保持暂停。"
            )
            risk_color = C.GOLD
        else:
            risk_text = "行情已暂停；答对可赚分，答错不扣分。提交后会显示正确答案与解析。"
            risk_color = C.SOFT
        risk_box = tk.Frame(
            body,
            bg=C.PANEL_2,
            highlightbackground=C.BORDER,
            highlightthickness=1,
        )
        risk_box.pack(fill="x", pady=(0, 10))
        tk.Label(
            risk_box,
            text="风险规则",
            bg=C.PANEL_2,
            fg=C.GOLD,
            font=FONTS.ui(8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=11, pady=(6, 1))
        tk.Label(
            risk_box,
            text=risk_text,
            bg=C.PANEL_2,
            fg=risk_color,
            font=FONTS.ui(8),
            wraplength=620,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=11, pady=(0, 6))

        tk.Frame(body, bg=C.BORDER, height=1).pack(fill="x")

        question_box = tk.Frame(body, bg=C.FIELD, highlightbackground=C.BORDER, highlightthickness=1)
        question_box.pack(fill="x", pady=(12, 10))
        tk.Label(
            question_box,
            text=self.question["prompt"],
            bg=C.FIELD,
            fg=C.TEXT,
            font=FONTS.ui(12, "bold"),
            wraplength=590,
            justify="left",
            anchor="w",
            padx=16,
            pady=12,
        ).pack(fill="x")

        self.option_buttons = []
        self.answer_entry = None
        if self.question.get("type") in ("choice", "judge"):
            options_frame = tk.Frame(body, bg=C.PANEL)
            options_frame.pack(fill="x")
            is_judge = self.question.get("type") == "judge"
            for idx, option in enumerate(self.question["options"]):
                prefix = "AB"[idx] if idx < 2 else "ABCD"[idx]
                btn = tk.Button(
                    options_frame,
                    text=f"{prefix}.  {option}",
                    command=lambda i=idx: self._select(i),
                    bg=C.PANEL_2,
                    fg=C.TEXT,
                    activebackground=C.ACCENT_DIM,
                    activeforeground=C.TEXT,
                    relief="flat",
                    bd=0,
                    highlightthickness=1,
                    highlightbackground=C.BORDER,
                    highlightcolor=C.ACCENT,
                    font=FONTS.ui(10),
                    wraplength=570,
                    justify="left",
                    anchor="w",
                    padx=14,
                    pady=11 if is_judge else 8,
                    cursor="hand2",
                    takefocus=0,
                )
                btn.pack(fill="x", pady=3)
                self.option_buttons.append(btn)
        else:
            answer_area = tk.Frame(
                body,
                bg=C.PANEL_2,
                highlightbackground=C.BORDER,
                highlightthickness=1,
            )
            answer_area.pack(fill="x", pady=(0, 4))
            tk.Label(
                answer_area,
                text="你的答案",
                bg=C.PANEL_2,
                fg=C.MUTED,
                font=FONTS.ui(8),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(9, 4))
            entry_row = tk.Frame(answer_area, bg=C.PANEL_2)
            entry_row.pack(fill="x", padx=14, pady=(0, 5))
            self.answer_entry = tk.Entry(
                entry_row,
                textvariable=self.answer_var,
                bg=C.FIELD,
                fg=C.TEXT,
                insertbackground=C.ACCENT,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=C.BORDER,
                highlightcolor=C.ACCENT,
                font=FONTS.ui(14, "bold"),
            )
            self.answer_entry.pack(side="left", fill="x", expand=True, ipady=7)
            if self.question.get("type") == "numeric":
                tk.Label(
                    entry_row,
                    text="  数值  ",
                    bg=C.PANEL_3,
                    fg=C.GOLD,
                    font=FONTS.ui(8),
                ).pack(side="left", padx=(8, 0), fill="y")
            self.answer_entry.bind("<KeyRelease>", self._on_text_changed)
            self.answer_entry.bind("<Return>", lambda _e: self._submit())
            hint = self.question.get("input_hint") or "输入答案后按 Enter 提交"
            tk.Label(
                answer_area,
                text=f"{hint} · 支持 Enter 提交",
                bg=C.PANEL_2,
                fg=C.MUTED,
                font=FONTS.ui(8),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(0, 9))

        self.feedback = tk.Frame(
            body, bg=C.FIELD, highlightbackground=C.BORDER, highlightthickness=1
        )
        self.feedback.pack(fill="x", pady=(10, 9))
        self.feedback_title = tk.Label(
            self.feedback,
            text="作答提示",
            bg=C.FIELD,
            fg=C.SOFT,
            font=FONTS.ui(9, "bold"),
            anchor="w",
        )
        self.feedback_title.pack(fill="x", padx=13, pady=(9, 2))
        if self.mode == "open" and self.order_session:
            initial_note = (
                "准备好后即可提前提交。答错将扣除 2 倍保证金，且不建立头寸。"
            )
        elif self.mode == "exit" and self.order_session:
            initial_note = (
                "考出答题已开始。答对正常结算；答错时盈利减半、亏损翻倍。行情保持暂停。"
            )
        else:
            initial_note = "答对立即获得分数；答错不扣分。提交后会显示正确答案与解析。"
        self.feedback_body = tk.Label(
            self.feedback,
            text=initial_note,
            bg=C.FIELD,
            fg=C.MUTED,
            font=FONTS.ui(9),
            wraplength=600,
            justify="left",
            anchor="w",
        )
        self.feedback_body.pack(fill="x", padx=13, pady=(0, 9))

        self.scroll.bind_wheel_to_children()

        tk.Label(
            self.action_bar,
            text="内容较多时可使用鼠标滚轮或右侧滚动条查看完整信息",
            bg=C.PANEL,
            fg=C.DIM,
            font=FONTS.ui(8),
            anchor="e",
        ).pack(fill="x", pady=(0, 6))
        actions = tk.Frame(self.action_bar, bg=C.PANEL)
        actions.pack(fill="x")
        is_option_question = self.question.get("type") in ("choice", "judge")
        self.primary = RoundedButton(
            actions,
            "提前提交答案" if is_option_question else "提交答案",
            self._submit,
            width=540,
            height=44,
            fill=color,
            hover_fill=color,
            fg="#071117",
            font=FONTS.ui(10, "bold"),
            parent_bg=C.PANEL,
            radius=8,
            enabled=is_option_question,
        )
        self.primary.pack(side="left", fill="x", expand=True)
        self.cancel_btn = make_flat_button(
            actions,
            "放弃",
            self._on_window_close,
            bg=C.PANEL,
            fg=C.MUTED,
            active_bg=C.PANEL,
            font=FONTS.ui(9),
            padx=14,
            pady=8,
        )
        self.cancel_btn.pack(side="left", padx=(10, 0))

    def _chip(self, parent, text, color):
        tk.Label(
            parent,
            text=text,
            bg=C.PANEL_2,
            fg=color,
            font=FONTS.ui(8),
            padx=9,
            pady=3,
        ).pack(side="left", padx=(0, 6))

    def _center(self, width, height):
        self.top.update_idletasks()
        parent = self.app.root
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        x = max(0, min(sw - width, px + (pw - width) // 2))
        y = max(0, min(sh - height, py + (ph - height) // 2))
        self.top.geometry(f"{width}x{height}+{x}+{y}")

    def _bind_keys(self):
        self.top.bind("<Escape>", lambda _e: self._on_window_close())
        self.top.bind("<Return>", self._on_return)
        if self.question.get("type") in ("choice", "judge"):
            for i, key in enumerate(("1", "2", "3", "4")):
                if i < len(self.option_buttons):
                    self.top.bind(key, lambda _e, idx=i: self._select(idx))

    def _focus_answer_entry(self):
        if self.answer_entry is not None and not self.finished and not self.closed:
            self.answer_entry.focus_set()

    def _on_text_changed(self, _event=None):
        if self.finished:
            return
        self.primary.set_enabled(bool(self.answer_var.get().strip()))

    def _on_return(self, _event=None):
        if self.finished:
            self._dismiss()
        elif self.question.get("type") in ("fill", "numeric"):
            if self.answer_var.get().strip():
                self._submit()
        elif self.selected is not None:
            self._submit()

    # ----- 作答 -----------------------------------------------------------

    def _tick_timer(self):
        if self.finished or self.closed:
            return
        self.remaining -= 1
        if self.remaining <= 0:
            self.remaining = 0
            self.timer_label.configure(text="剩余 0s", fg=C.UP)
            self._submit(timeout=True)
            return
        color = C.UP if self.remaining <= 10 else C.GOLD
        self.timer_label.configure(text=f"剩余 {self.remaining}s", fg=color)
        self._timer_id = self.top.after(1000, self._tick_timer)

    def _select(self, index: int):
        if self.finished:
            return
        self.selected = index
        for i, btn in enumerate(self.option_buttons):
            if i == index:
                btn.configure(bg=C.ACCENT_DIM, highlightbackground=C.ACCENT)
            else:
                btn.configure(bg=C.PANEL_2, highlightbackground=C.BORDER)
        self.primary.set_enabled(True)

    def _submit(self, timeout: bool = False):
        if self.finished:
            return
        is_text = self.question.get("type") in ("fill", "numeric")
        if not timeout:
            if is_text and not self.answer_var.get().strip():
                return
            if not is_text and self.selected is None:
                self.feedback_title.configure(text="请选择一个答案", fg=C.GOLD)
                self.feedback_body.configure(
                    text="点击选项，或使用数字键 1–4 选择。选择后可点击底部「提前提交答案」，无需等待计时结束。",
                    fg=C.SOFT,
                )
                self._scroll_result_into_view()
                return
        if timeout:
            correct = False
        elif is_text:
            correct = Q.check_answer(self.question, None, self.answer_var.get())
        else:
            correct = Q.check_answer(self.question, self.selected, "")
        self.finished = True
        if self._timer_id:
            try:
                self.top.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        self.correct = correct

        if self.mode == "open" and self.order_session:
            self.resolution = self.app.resolve_open_quiz(self.order_session, correct)
        elif self.mode == "exit" and self.order_session:
            self.resolution = self.app.resolve_exit_quiz(self.order_session, correct)
            self.reward = 0
        else:
            self.reward = self.app.record_answer(
                correct=correct,
                subject=self.subject,
                level=self.level,
                mode=self.mode,
            )
            self.resolution = {"kind": "practice", "correct": correct, "reward": self.reward}
        self.reward = int(self.resolution.get("reward", 0) or 0)

        for btn in self.option_buttons:
            btn.configure(state="disabled", disabledforeground=C.MUTED)
        if self.answer_entry is not None:
            self.answer_entry.configure(
                state="disabled",
                disabledbackground=C.PANEL_3,
                disabledforeground=C.SOFT,
            )
        # 标出选择题 / 判断题的正确答案
        answer = self.question.get("answer")
        if isinstance(answer, int) and 0 <= answer < len(self.option_buttons):
            self.option_buttons[answer].configure(
                bg="#0E352D",
                disabledforeground=C.EVENT_GOOD,
                highlightbackground=C.EVENT_GOOD,
            )
            if self.selected is not None and not correct:
                self.option_buttons[self.selected].configure(
                    bg="#351A20",
                    disabledforeground=C.EVENT_BAD,
                    highlightbackground=C.EVENT_BAD,
                )

        answer_text = self.question.get("correct_display", "见解析")
        kind = self.resolution.get("kind", "")
        prefix = "时间到 · " if timeout else ""

        if self.mode == "exit" and kind == "exit":
            self.feedback_title.configure(
                text=f"{prefix}考出完成 · 答题{'正确' if correct else '错误'}",
                fg=C.EVENT_GOOD if correct else C.EVENT_BAD,
            )
            self.feedback_body.configure(
                text=(
                    f"{self.resolution.get('summary', '')}\n\n"
                    f"正确答案：{answer_text}\n{self.question['explain']}"
                ),
                fg=C.SOFT,
            )
            self.primary.set_text("返回行情")
            self.primary.set_colors(C.PANEL_3, C.PANEL_3, C.SOFT)
        elif correct:
            self.feedback_title.configure(
                text=f"回答正确 · +{self.reward} 分已计入分数账户", fg=C.EVENT_GOOD
            )
            self.feedback_body.configure(
                text=f"{self.question['explain']}\n连对 {self.app.stats['streak']} 题 · 继续加油！",
                fg=C.SOFT,
            )
            if self.mode == "open":
                self.primary.set_text("确认学入 →")
                self.primary.set_colors(C.ACCENT, "#72E4FF", "#071117")
            else:
                self.primary.set_text("收下奖励并返回")
                self.primary.set_colors(C.GOLD, "#FFD978", "#1A1403")
        elif kind == "entry_penalty":
            penalty = self.resolution.get("penalty", 0.0)
            balance = self.resolution.get("balance", self.app.account.balance)
            self.feedback_title.configure(
                text=f"{prefix}学入失败 · 已扣除 2 倍保证金 {penalty:,.2f} 分",
                fg=C.EVENT_BAD,
            )
            self.feedback_body.configure(
                text=(
                    f"正确答案：{answer_text}\n"
                    f"本次没有建立头寸。当前余额 {balance:,.1f} 分。\n"
                    f"{self.question['explain']}"
                ),
                fg=C.SOFT,
            )
            self.primary.set_text("返回行情")
            self.primary.set_colors(C.PANEL_3, C.PANEL_3, C.SOFT)
        elif kind in ("profit_zero", "loss_double", "flat"):
            before = self.resolution.get("pnl_before", 0.0)
            after = self.resolution.get("pnl_after", 0.0)
            penalty = self.resolution.get("penalty", 0.0)
            opened = self.resolution.get("opened", False)
            settle_label = {
                "profit_zero": "盈利归零规则",
                "loss_double": "亏损两倍规则",
                "flat": "盈亏为零",
            }.get(kind, "右侧学入结算")
            trade_note = (
                f"右侧学入已成交：{self.resolution.get('pair_name', self.context_title)} "
                f"{self.resolution.get('lots', 0):.1f} 手。"
                if opened
                else "右侧学入结算已执行，但未能建立新头寸。"
            )
            self.feedback_title.configure(
                text=f"{prefix}右侧学入已成交 · {settle_label}",
                fg=C.EVENT_BAD,
            )
            self.feedback_body.configure(
                text=(
                    f"{trade_note}\n"
                    f"账户盈亏 {before:+,.1f} → {after:+,.1f} 分 · 额外扣除 {penalty:,.1f} 分。\n"
                    f"正确答案：{answer_text} · {self.question['explain']}"
                ),
                fg=C.SOFT,
            )
            self.primary.set_text("返回行情")
            self.primary.set_colors(C.PANEL_3, C.PANEL_3, C.SOFT)
        else:
            self.feedback_title.configure(
                text=f"{prefix}回答错误 · 本次未通过", fg=C.EVENT_BAD
            )
            self.feedback_body.configure(
                text=f"正确答案：{answer_text}\n{self.question['explain']}",
                fg=C.SOFT,
            )
            self.primary.set_text("返回行情")
            self.primary.set_colors(C.PANEL_3, C.PANEL_3, C.SOFT)

        self.primary.set_enabled(True)
        self.primary._command = self._dismiss  # type: ignore[attr-defined]
        self.cancel_btn.configure(text="关闭")
        if getattr(self, "scroll", None) is not None:
            self.top.after(60, self._scroll_result_into_view)

    def _scroll_result_into_view(self):
        if self.closed:
            return
        try:
            if not self.top.winfo_exists():
                return
            self.scroll.scroll_to_end()
        except Exception:
            pass

    def _dismiss(self, execute: bool = True):
        if self.closed:
            return
        self.closed = True
        if self._timer_id:
            try:
                self.top.after_cancel(self._timer_id)
            except Exception:
                pass
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            self.top.destroy()
        except Exception:
            pass

        if execute and self.finished and self.correct and self.mode == "open" and self.on_success:
            self.on_success()
        elif execute and self.finished and self.correct and self.mode == "practice":
            self.app.toast.show(
                "练习完成",
                f"{self.subject} {self.meta['short']} 答对，+{self.reward} 分已到账。",
                "good",
            )
        elif execute and self.finished and not self.correct and self.mode != "exit":
            kind = self.resolution.get("kind", "")
            if kind == "entry_penalty":
                penalty = self.resolution.get("penalty", 0.0)
                self.app.toast.show(
                    "学入惩罚已执行",
                    f"已扣除 2 倍保证金 {penalty:,.2f} 分，本次学入取消。",
                    "bad",
                )
            elif kind in ("profit_zero", "loss_double", "flat"):
                before = self.resolution.get("pnl_before", 0.0)
                after = self.resolution.get("pnl_after", 0.0)
                self.app.toast.show(
                    "右侧学入已成交",
                    f"盈亏按规则结算：{before:+,.1f} → {after:+,.1f} 分。",
                    "bad",
                )
            else:
                self.app.toast.show(
                    "本次未通过",
                    "已给出解析，不扣除分数。可以再来一题。",
                    "info",
                )
        if self.on_closed:
            self.on_closed()

    def _on_window_close(self):
        # 用户主动关闭：答对奖励保留，但不会替用户执行学入。
        if self.closed:
            return
        if self.finished and self.correct and self.mode == "open":
            self.app.toast.show("学入已取消", "答对奖励已保留，可随时重新学入。", "info")
        self._dismiss(execute=False)


# ---------------------------------------------------------------------------
# 新手引导
# ---------------------------------------------------------------------------

class TutorialDialog:
    """首次进入与重新开始时显示的新手引导。"""

    PAGES = 3

    def __init__(self, parent, on_finish: Callable) -> None:
        self.parent = parent
        self.on_finish = on_finish
        self.page = 1
        self.closed = False
        self.top = tk.Toplevel(parent)
        self.top.title("SCORE FX · 新手引导")
        self.top.configure(bg=C.PANEL)
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._finish)

        tk.Frame(self.top, bg=C.ACCENT, height=5).pack(fill="x")
        header = tk.Frame(self.top, bg=C.PANEL)
        header.pack(fill="x", padx=24, pady=(16, 4))
        tk.Label(
            header,
            text="新手引导  /  GETTING STARTED",
            bg=C.PANEL,
            fg=C.ACCENT,
            font=FONTS.mono(9, "bold"),
            anchor="w",
        ).pack(side="left")
        self.page_label = tk.Label(
            header, text="", bg=C.PANEL, fg=C.SOFT, font=FONTS.num(9, "bold")
        )
        self.page_label.pack(side="right")
        make_flat_button(
            header,
            "跳过",
            self._finish,
            bg=C.PANEL,
            fg=C.MUTED,
            active_bg=C.PANEL_2,
            font=FONTS.ui(8),
            padx=8,
            pady=2,
        ).pack(side="right", padx=(0, 14))

        self.action_bar = tk.Frame(self.top, bg=C.PANEL)
        self.action_bar.pack(side="bottom", fill="x", padx=24, pady=(0, 17))
        self.prev_btn = RoundedButton(
            self.action_bar,
            "上一步",
            self._prev,
            width=160,
            height=40,
            fill=C.PANEL_2,
            hover_fill=C.PANEL_3,
            fg=C.SOFT,
            outline=C.BORDER,
            parent_bg=C.PANEL,
        )
        self.prev_btn.pack(side="left")
        self.next_btn = RoundedButton(
            self.action_bar,
            "下一步",
            self._next,
            width=260,
            height=40,
            fill=C.ACCENT,
            hover_fill="#79E5FF",
            fg="#071117",
            parent_bg=C.PANEL,
            font=FONTS.ui(10, "bold"),
        )
        self.next_btn.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.scroll = ScrollableFrame(self.top, bg=C.PANEL)
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(4, 8))
        self.content = tk.Frame(self.scroll.inner, bg=C.PANEL)
        self.content.pack(fill="x", padx=12, pady=10)
        self._render()

        self.top.update_idletasks()
        width = 700
        height = min(720, max(600, self.parent.winfo_screenheight() - 120))
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = max(0, px + (pw - width) // 2)
        y = max(0, py + (ph - height) // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        self.top.grab_set()
        self.top.focus_force()
        self.top.bind("<Escape>", lambda _e: self._finish())

    def _render(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.page_label.configure(text=f"{self.page} / {self.PAGES}")
        self.prev_btn.set_enabled(self.page > 1)
        self.next_btn.set_text("开始体验" if self.page == self.PAGES else "下一步")
        if self.page == 1:
            self._page_welcome()
        elif self.page == 2:
            self._page_howto()
        else:
            self._page_rules()
        self.scroll.bind_wheel_to_children()
        self.scroll.canvas.yview_moveto(0)

    def _title(self, text: str, sub: str):
        tk.Label(
            self.content,
            text=text,
            bg=C.PANEL,
            fg=C.TEXT,
            font=FONTS.ui(20, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(2, 4))
        tk.Label(
            self.content,
            text=sub,
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(9),
            wraplength=590,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 14))

    def _bullets(self, items):
        for number, title, text in items:
            row = tk.Frame(self.content, bg=C.PANEL_2, highlightbackground=C.BORDER, highlightthickness=1)
            row.pack(fill="x", pady=5)
            tk.Label(
                row,
                text=number,
                bg=C.ACCENT_DIM,
                fg=C.ACCENT,
                font=FONTS.num(12, "bold"),
                width=3,
                pady=6,
            ).pack(side="left", fill="y")
            body = tk.Frame(row, bg=C.PANEL_2)
            body.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            tk.Label(
                body, text=title, bg=C.PANEL_2, fg=C.TEXT, font=FONTS.ui(10, "bold"), anchor="w"
            ).pack(fill="x")
            tk.Label(
                body,
                text=text,
                bg=C.PANEL_2,
                fg=C.SOFT,
                font=FONTS.ui(8),
                wraplength=520,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(2, 0))

    def _image_block(self, filename: str):
        path = ASSET_DIR / filename
        try:
            photo = tk.PhotoImage(file=str(path))
        except Exception:
            return
        self._tutorial_photo = photo
        tk.Label(
            self.content,
            image=photo,
            bg=C.PANEL,
            bd=0,
            highlightthickness=1,
            highlightbackground=C.BORDER,
        ).pack(pady=(0, 10))

    def _warning_box(self, title: str, text: str):
        box = tk.Frame(self.content, bg=C.UP_GLOW, highlightbackground=C.UP, highlightthickness=1)
        box.pack(fill="x", pady=(12, 6))
        tk.Label(
            box,
            text=title,
            bg=C.UP_GLOW,
            fg=C.UP,
            font=FONTS.ui(9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(
            box,
            text=text,
            bg=C.UP_GLOW,
            fg=C.SOFT,
            font=FONTS.ui(8),
            wraplength=560,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 9))

    def _page_welcome(self):
        self._title(
            "欢迎来到 SCORE FX",
            "这是一个把高中学科成绩变化做成行情走势的单机学习模拟游戏。你不需要投入任何真实货币。",
        )
        self._image_block("girl_420.png")
        self._warning_box(
            "仅供娱乐 · 严禁赌博",
            "本程序为虚拟学习娱乐产品，不涉及真实货币、充值、提现或任何真实交易。"
            "请勿将游戏结果与现实投资、赌博行为混为一谈；请理性游戏、注意休息，切勿沉迷。",
        )
        self._bullets([
            ("01", "这是虚拟分数盘", "账户里的“分数”只用于游戏内答题、学入与考出，不能兑换现金或实物。"),
            ("02", "答题就是你的操作资格", "答对题目获得分数；学入前需要先通过对应学科测验。"),
            ("03", "随时可以停下", "关闭窗口会自动存档；如果感到疲劳或情绪受影响，请立即休息。"),
        ])

    def _page_howto(self):
        self._title(
            "三步开始",
            "先熟悉流程，再调整手数和杠杆。答题时行情会暂停，给你充分的思考时间。",
        )
        self._bullets([
            ("01", "选年级与学科对", "高一、高二、高三各有不同学科组合。只有当前选中的学科对会实时波动。"),
            ("02", "调整数量与杠杆", "拖动明亮的滑杆选择手数（0.1–5.0）和杠杆（1–75x）。杠杆越高，题目难度越高。"),
            ("03", "学入与考出", "点击“学入(学科)”参加测验；持仓可点“考出”或“一键考出”，考出同样要答题。"),
        ])
        tk.Label(
            self.content,
            text="提示：选择题与判断题可以提前提交；弹窗内容较多时可用滚轮查看完整文字。",
            bg=C.PANEL,
            fg=C.MUTED,
            font=FONTS.ui(8),
            wraplength=590,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

    def _page_rules(self):
        self._title(
            "风险规则与提醒",
            "行情会出现连续大涨、大跌与交叉波动。杠杆、保证金和答题惩罚都会放大结果。",
        )
        self._bullets([
            ("01", "保证金与强平", "开仓会扣除投入本金和保证金；保证金率跌到 30% 会触发强制平仓。高杠杆请控制手数。"),
            ("02", "答题结果会影响账户", "学入答错扣除 2 倍保证金；考出答错时亏损翻倍、盈利减半。"),
            ("03", "行情只在你关注的学科对运行", "答题或查看弹窗时，行情暂停；关闭后继续。"),
        ])
        self._warning_box(
            "再次提醒：这只是娱乐",
            "本程序不提供真实金融服务，也不构成任何投资建议。严禁任何形式的赌博；"
            "请合理安排时间，量力而行。如果你喜欢这个模拟游戏，把它当作学习之余的放松即可。",
        )

    def _prev(self):
        if self.page > 1:
            self.page -= 1
            self._render()

    def _next(self):
        if self.page < self.PAGES:
            self.page += 1
            self._render()
        else:
            self._finish()

    def _finish(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            self.top.destroy()
        except Exception:
            pass
        if self.on_finish:
            self.on_finish()


# ---------------------------------------------------------------------------
# 两千万成就弹窗
# ---------------------------------------------------------------------------

class MilestoneDialog:
    def __init__(self, parent, on_close: Callable) -> None:
        self.on_close = on_close
        self.closed = False
        self.top = tk.Toplevel(parent)
        self.top.title("SCORE FX · 两千万成就")
        self.top.configure(bg=C.PANEL)
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._close)

        tk.Frame(self.top, bg=C.GOLD, height=5).pack(fill="x")
        body = tk.Frame(self.top, bg=C.PANEL)
        body.pack(fill="both", expand=True, padx=26, pady=(18, 16))
        tk.Label(
            body,
            text="成就解锁  /  MILESTONE",
            bg=C.PANEL,
            fg=C.GOLD,
            font=FONTS.mono(9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text="没想到你真的能赚到两千万，我承认你是神了。",
            bg=C.PANEL,
            fg=C.TEXT,
            font=FONTS.ui(17, "bold"),
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(12, 5))
        tk.Label(
            body,
            text="账户余额已达到 20,000,000 分 · 这是纯粹的游戏成就，不代表任何真实收益。",
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(8),
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 12))

        path = ASSET_DIR / "girl_420.png"
        try:
            photo = tk.PhotoImage(file=str(path))
            self.image = photo
            tk.Label(
                body,
                image=photo,
                bg=C.PANEL,
                bd=0,
                highlightthickness=1,
                highlightbackground=C.BORDER,
            ).pack(pady=(0, 14))
        except Exception:
            self.image = None

        button = RoundedButton(
            body,
            "继续游戏",
            self._close,
            width=240,
            height=40,
            fill=C.GOLD,
            hover_fill="#FFD978",
            fg="#1A1403",
            parent_bg=C.PANEL,
            font=FONTS.ui(10, "bold"),
        )
        button.pack(fill="x")

        self.top.update_idletasks()
        width = 560
        height = self.top.winfo_reqheight() + 10
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = max(0, px + (pw - width) // 2)
        y = max(0, py + (ph - height) // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        self.top.bind("<Escape>", lambda _e: self._close())
        self.top.grab_set()
        self.top.focus_force()

    def _close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            self.top.destroy()
        except Exception:
            pass
        if self.on_close:
            self.on_close()


# ---------------------------------------------------------------------------
# 通用确认弹窗
# ---------------------------------------------------------------------------

class ConfirmDialog:
    def __init__(
        self,
        parent,
        title: str,
        message: str,
        on_confirm: Callable,
        *,
        confirm_text: str = "确认",
        cancel_text: str = "取消",
        danger: bool = False,
    ) -> None:
        self.on_confirm = on_confirm
        self.top = tk.Toplevel(parent)
        self.top.title(f"SCORE FX · {title}")
        self.top.configure(bg=C.PANEL)
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._close)

        accent = C.UP if danger else C.ACCENT
        tk.Frame(self.top, bg=accent, height=5).pack(fill="x")
        body = tk.Frame(self.top, bg=C.PANEL)
        body.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(
            body,
            text=title,
            bg=C.PANEL,
            fg=C.TEXT,
            font=FONTS.ui(16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text=message,
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(9),
            wraplength=400,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(10, 16))

        actions = tk.Frame(body, bg=C.PANEL)
        actions.pack(fill="x")
        confirm = RoundedButton(
            actions,
            confirm_text,
            self._confirm,
            width=190,
            height=40,
            fill=accent,
            hover_fill=C.BUY_HOVER if danger else "#72E4FF",
            fg="#071117" if not danger else C.WHITE,
            parent_bg=C.PANEL,
        )
        confirm.pack(side="left", fill="x", expand=True)
        cancel = RoundedButton(
            actions,
            cancel_text,
            self._close,
            width=140,
            height=40,
            fill=C.PANEL_2,
            hover_fill=C.PANEL_3,
            fg=C.SOFT,
            outline=C.BORDER,
            parent_bg=C.PANEL,
        )
        cancel.pack(side="left", padx=(8, 0))

        self.top.update_idletasks()
        width, height = 500, 255
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = max(0, px + (pw - width) // 2)
        y = max(0, py + (ph - height) // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        self.top.bind("<Escape>", lambda _e: self._close())
        self.top.grab_set()
        self.top.focus_force()

    def _confirm(self):
        self._close()
        self.on_confirm()

    def _close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            self.top.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 强制平仓通知
# ---------------------------------------------------------------------------

class LiquidationDialog:
    def __init__(self, app, results, balance_after: float) -> None:
        self.app = app
        self.results = results
        self.balance_after = balance_after
        self.top = tk.Toplevel(app.root)
        self.top.title("SCORE FX · 风险控制通知")
        self.top.configure(bg=C.PANEL)
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.protocol("WM_DELETE_WINDOW", self._close)

        tk.Frame(self.top, bg=C.UP, height=5).pack(fill="x")
        outer = tk.Frame(self.top, bg=C.PANEL)
        outer.pack(fill="both", expand=True, padx=18, pady=(0, 0))

        self.action_bar = tk.Frame(outer, bg=C.PANEL)
        self.action_bar.pack(side="bottom", fill="x", pady=(0, 16))
        self.scroll = ScrollableFrame(outer, bg=C.PANEL)
        self.scroll.pack(fill="both", expand=True, padx=(4, 0), pady=(8, 0))
        body = tk.Frame(self.scroll.inner, bg=C.PANEL)
        body.pack(fill="x", padx=10, pady=(12, 4))
        tk.Label(
            body,
            text="保证金不足  /  MARGIN CALL",
            bg=C.PANEL,
            fg=C.UP,
            font=FONTS.mono(9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text="强制平仓通知",
            bg=C.PANEL,
            fg=C.TEXT,
            font=FONTS.ui(18, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(8, 4))
        tk.Label(
            body,
            text="保证金率跌破 30%，系统已按最新市价自动平掉全部持仓。",
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(9),
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 12))

        box = tk.Frame(body, bg=C.FIELD, highlightbackground=C.BORDER, highlightthickness=1)
        box.pack(fill="x")
        total = sum(result.pnl for result in self.results)
        rows = [
            ("被强平持仓", f"{len(self.results)} 笔"),
            ("本次实现盈亏", f"{total:+,.1f} 分"),
            ("当前分数余额", f"{self.balance_after:,.1f} 分"),
            ("风险阈值", "保证金率 ≤ 30%"),
        ]
        for idx, (label, value) in enumerate(rows):
            row = tk.Frame(box, bg=C.FIELD)
            row.pack(fill="x", padx=12, pady=5)
            tk.Label(
                row, text=label, bg=C.FIELD, fg=C.MUTED, font=FONTS.ui(9), anchor="w"
            ).pack(side="left")
            tk.Label(
                row,
                text=value,
                bg=C.FIELD,
                fg=C.UP if "盈亏" in label and total < 0 else C.TEXT,
                font=FONTS.num(10, "bold"),
                anchor="e",
            ).pack(side="right")

        note = (
            "这是模拟盘的风险教育提示。分数账户已经归零保护，不会出现负数；"
            "可以前往自习室答题赚取分数，再重新制定仓位计划。"
        )
        tk.Label(
            body,
            text=note,
            bg=C.PANEL,
            fg=C.MUTED,
            font=FONTS.ui(8),
            wraplength=440,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(12, 14))

        actions = tk.Frame(self.action_bar, bg=C.PANEL)
        actions.pack(fill="x")
        practice = RoundedButton(
            actions,
            "去自习室补分",
            self._practice,
            width=210,
            height=40,
            fill=C.GOLD,
            hover_fill="#FFD978",
            fg="#1A1403",
            parent_bg=C.PANEL,
        )
        practice.pack(side="left", fill="x", expand=True)
        close = RoundedButton(
            actions,
            "返回行情",
            self._close,
            width=150,
            height=40,
            fill=C.PANEL_2,
            hover_fill=C.PANEL_3,
            fg=C.SOFT,
            outline=C.BORDER,
            parent_bg=C.PANEL,
        )
        close.pack(side="left", padx=(8, 0))
        self.scroll.bind_wheel_to_children()

        self.top.update_idletasks()
        content_height = self.scroll.inner.winfo_reqheight()
        action_height = self.action_bar.winfo_reqheight()
        h = min(540, max(420, content_height + action_height + 40))
        w = 520
        px, py = app.root.winfo_rootx(), app.root.winfo_rooty()
        pw, ph = app.root.winfo_width(), app.root.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.top.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.top.grab_set()
        self.top.focus_force()

    def _practice(self):
        self._close()
        self.app.open_practice()

    def _close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            self.top.destroy()
        except Exception:
            pass
        if self.app.liquidation_dialog is self:
            self.app.liquidation_dialog = None


# ---------------------------------------------------------------------------
# 可选的置顶实时浮窗
# ---------------------------------------------------------------------------

class RealtimeWindow:
    def __init__(self, app) -> None:
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title("SCORE FX · 实时提醒")
        self.top.configure(bg=C.BG)
        self.top.geometry("370x390")
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.attributes("-topmost", True)
        self.top.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(self.top, bg=C.HEADER, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        inner = tk.Frame(header, bg=C.HEADER)
        inner.pack(fill="both", expand=True, padx=14, pady=9)
        self.dot = tk.Label(inner, text="●", bg=C.HEADER, fg=C.UP, font=FONTS.ui(8))
        self.dot.pack(side="left")
        tk.Label(
            inner, text=" 实时提醒 / LIVE", bg=C.HEADER, fg=C.TEXT, font=FONTS.ui(10, "bold")
        ).pack(side="left")
        self.clock = tk.Label(
            inner, text="", bg=C.HEADER, fg=C.MUTED, font=FONTS.mono(8)
        )
        self.clock.pack(side="right")

        body = tk.Frame(self.top, bg=C.BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        metrics = tk.Frame(body, bg=C.PANEL_2, highlightbackground=C.BORDER, highlightthickness=1)
        metrics.pack(fill="x")
        self.equity_label = tk.Label(
            metrics, text="净值 --", bg=C.PANEL_2, fg=C.TEXT, font=FONTS.num(14, "bold"), anchor="w"
        )
        self.equity_label.pack(side="left", padx=12, pady=9)
        self.pnl_label = tk.Label(
            metrics, text="总盈亏 --", bg=C.PANEL_2, fg=C.SOFT, font=FONTS.num(9), anchor="e"
        )
        self.pnl_label.pack(side="right", padx=12)

        event_box = tk.Frame(body, bg=C.PANEL, highlightbackground=C.BORDER, highlightthickness=1)
        event_box.pack(fill="x", pady=(9, 8))
        self.event_title = tk.Label(
            event_box,
            text="当前校园事件",
            bg=C.PANEL,
            fg=C.GOLD,
            font=FONTS.ui(9, "bold"),
            anchor="w",
        )
        self.event_title.pack(fill="x", padx=10, pady=(8, 2))
        self.event_detail = tk.Label(
            event_box,
            text="正在监听校园动态…",
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(8),
            wraplength=330,
            justify="left",
            anchor="w",
        )
        self.event_detail.pack(fill="x", padx=10, pady=(0, 8))

        feed_box = tk.Frame(body, bg=C.PANEL)
        feed_box.pack(fill="both", expand=True)
        self.feed = tk.Text(
            feed_box,
            width=1,
            height=6,
            bg=C.PANEL,
            fg=C.SOFT,
            font=FONTS.ui(8),
            bd=0,
            highlightthickness=1,
            highlightbackground=C.BORDER,
            padx=9,
            pady=7,
            wrap="word",
            state="disabled",
            cursor="arrow",
        )
        self.feed.pack(side="left", fill="both", expand=True)
        self.feed_scroll = SlimScrollbar(feed_box, command=self.feed.yview, bg=C.PANEL)
        self.feed_scroll.pack(side="right", fill="y", padx=(5, 0))
        self.feed.configure(yscrollcommand=self.feed_scroll.set)
        self.feed.bind("<MouseWheel>", self._on_feed_wheel, add="+")
        self.feed_scroll.bind("<MouseWheel>", self._on_feed_wheel, add="+")
        self.feed.tag_configure("time", foreground=C.DIM)
        self.feed.tag_configure("good", foreground=C.EVENT_GOOD)
        self.feed.tag_configure("bad", foreground=C.EVENT_BAD)
        self.feed.tag_configure("mixed", foreground=C.EVENT_MIXED)
        self.feed.tag_configure("info", foreground=C.ACCENT)

        bottom = tk.Frame(body, bg=C.BG)
        bottom.pack(fill="x", pady=(8, 0))
        tk.Label(
            bottom,
            text="置顶窗口 · 数据随主盘同步",
            bg=C.BG,
            fg=C.MUTED,
            font=FONTS.ui(7),
        ).pack(side="left")
        close_btn = make_flat_button(
            bottom,
            "关闭浮窗",
            self.close,
            bg=C.PANEL,
            fg=C.SOFT,
            active_bg=C.PANEL_3,
            font=FONTS.ui(8),
            padx=8,
            pady=3,
        )
        close_btn.pack(side="right")

        self.top.update_idletasks()
        px, py = app.root.winfo_rootx(), app.root.winfo_rooty()
        pw = app.root.winfo_width()
        self.top.geometry(f"370x390+{px + pw - 390}+{py + 120}")
        self.update()

    def _on_feed_wheel(self, event):
        delta = int(getattr(event, "delta", 0))
        if delta == 0:
            return None
        self.feed.yview_scroll(-1 if delta > 0 else 1, "units")
        return "break"

    def update(self):
        if not self.top.winfo_exists():
            return
        prices = self.app.engine.prices()
        equity = self.app.account.equity(prices)
        pnl = self.app.account.total_pnl(prices)
        self.equity_label.configure(text=f"净值 {equity:,.1f}")
        self.pnl_label.configure(text=f"总盈亏 {pnl:+,.2f}", fg=pnl_color(pnl))
        self.clock.configure(text=datetime.now().strftime("%H:%M:%S"))
        events = self.app.engine.active_events
        if events:
            ev = events[-1]
            extra = f"（另有 {len(events)-1} 个）" if len(events) > 1 else ""
            self.event_title.configure(
                text=f"◆ {ev.title} · {ev.seconds_left}s{extra}", fg=event_color(ev.tone)
            )
            self.event_detail.configure(text=f"{ev.detail}  影响：{ev.subject_label}")
        else:
            self.event_title.configure(text="当前校园事件", fg=C.MUTED)
            self.event_detail.configure(text="风平浪静，随机事件正在路上。")
        signature = tuple(
            (msg["time"], msg["kind"], msg["text"], msg["tone"])
            for msg in self.app.live_messages[:5]
        )
        if signature == getattr(self, "_feed_signature", None):
            return
        self._feed_signature = signature
        self.feed.configure(state="normal")
        self.feed.delete("1.0", "end")
        for msg in self.app.live_messages[:5]:
            self.feed.insert("end", f"{msg['time']} ", "time")
            self.feed.insert("end", "● ", msg["tone"])
            self.feed.insert("end", msg["text"] + "\n", msg["tone"])
        self.feed.configure(state="disabled")
        self.feed.yview_moveto(0)
        self.feed_scroll.set(*self.feed.yview())

    def close(self):
        try:
            self.top.destroy()
        except Exception:
            pass
        if self.app.float_window is self:
            self.app.float_window = None
        try:
            self.app.float_btn.set_text("实时浮窗")
        except Exception:
            pass
