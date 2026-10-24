"""SCORE FX - 20 秒细蜡烛分时图。

每 2 秒刷新一次，累计 10 次刷新（约 20 秒）形成一根新柱：
- 上涨：红色细柱 + 上下影线
- 下跌：蓝色细柱 + 上下影线
只展示当前选中学科；父窗口负责暂停与行情刷新。
"""

from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from typing import Optional

import engine as E
from theme import C, FONTS, draw_round_rect


BAR_SECONDS = 20


class PulseCandleChart(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, bg=C.PANEL, highlightthickness=0, bd=0)
        self.pair: Optional[E.PairMarket] = None
        self.window_seconds = 300
        self._geom = None
        self._hover = None
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)

    def set_data(self, pair: E.PairMarket, window_seconds: int = 300):
        changed = self.pair is not pair
        self.pair = pair
        self.window_seconds = max(BAR_SECONDS * 2, int(window_seconds))
        if changed:
            self._hover = None
        self.redraw()

    def _bars(self):
        if not self.pair:
            return []
        history = self.pair.history
        if not history:
            return []
        all_bars = []
        now = datetime.now()
        for start in range(0, len(history), BAR_SECONDS):
            chunk = history[start : start + BAR_SECONDS]
            if not chunk:
                continue
            all_bars.append(
                {
                    "o": chunk[0],
                    "h": max(chunk),
                    "l": min(chunk),
                    "c": chunk[-1],
                    "n": len(chunk),
                }
            )
        count = max(2, self.window_seconds // BAR_SECONDS)
        all_bars = all_bars[-count:]
        total = len(all_bars)
        for index, bar in enumerate(all_bars):
            start_time = now - timedelta(
                seconds=(total - 1 - index) * BAR_SECONDS + BAR_SECONDS
            )
            bar["start"] = start_time.strftime("%H:%M:%S")
            bar["end"] = (start_time + timedelta(seconds=BAR_SECONDS)).strftime("%H:%M:%S")
            bar["complete"] = bar["n"] >= BAR_SECONDS
        return all_bars

    def redraw(self):
        self.delete("all")
        self._geom = None
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 80 or h < 80 or not self.pair:
            return

        bars = self._bars()
        if not bars:
            self.create_text(
                w / 2, h / 2, text="等待行情数据…", fill=C.MUTED, font=FONTS.ui(10)
            )
            return

        # 行情图铺满卡片左右两侧；全屏时会自然扩展。
        right_axis = 64.0
        x0 = 18.0
        x1 = max(x0 + 60.0, w - right_axis)
        y0, y1 = 28, h - 30
        if x1 - x0 < 60 or y1 - y0 < 50:
            return

        hi = max(bar["h"] for bar in bars)
        lo = min(bar["l"] for bar in bars)
        if hi - lo < 0.20:
            hi += 0.10
            lo -= 0.10
        pad = (hi - lo) * 0.13
        hi += pad
        lo -= pad

        def y_of(price):
            return y0 + (hi - price) / (hi - lo) * (y1 - y0)

        for i in range(5):
            y = y0 + (y1 - y0) * i / 4
            self.create_line(x0, y, x1, y, fill=C.GRID)
            value = hi - (hi - lo) * i / 4
            self.create_text(
                x1 + 8,
                y,
                text=f"{value:.2f}",
                fill=C.MUTED,
                font=FONTS.mono(8),
                anchor="w",
            )
        self.create_line(x1, y0, x1, y1, fill=C.BORDER)

        step = (x1 - x0) / max(1, len(bars))
        # 全屏/宽屏时进一步加宽蜡烛实体，让画面更舒服。
        plot_width = x1 - x0
        if plot_width >= 1100:
            body_w = min(30.0, max(18.0, step * 0.55))
        else:
            body_w = min(16.5, max(3.3, step * 0.51))
        centers = [x0 + step * (index + 0.5) for index in range(len(bars))]

        # 时间轴标签数量随宽度增加，既铺满横轴，也避免文字过度稀疏。
        target_labels = max(5, min(14, int((x1 - x0) / 110) + 1))
        if len(bars) <= 1:
            label_indices = [0]
        else:
            label_indices = sorted(
                {
                    0,
                    len(bars) - 1,
                    *[
                        round(index * (len(bars) - 1) / max(1, target_labels - 1))
                        for index in range(target_labels)
                    ],
                }
            )
        for index in label_indices:
            if not 0 <= index < len(bars):
                continue
            x = centers[index]
            self.create_line(x, y0, x, y1, fill=C.GRID)
            anchor = "nw" if index == 0 else ("ne" if index == len(bars) - 1 else "n")
            label_x = x0 + 2 if index == 0 else (x1 - 2 if index == len(bars) - 1 else x)
            self.create_text(
                label_x,
                y1 + 11,
                text=bars[index]["start"],
                fill=C.MUTED,
                font=FONTS.mono(8),
                anchor=anchor,
            )

        # 基准线
        prev_y = y_of(self.pair.prev_close)
        if y0 < prev_y < y1:
            self.create_line(x0, prev_y, x1, prev_y, fill=C.DIM, dash=(2, 5))
            self.create_text(
                x0 + 4,
                prev_y - 8,
                text=f"基准 {self.pair.prev_close:.2f}",
                fill=C.DIM,
                font=FONTS.mono(8),
                anchor="w",
            )

        # 每 20 秒（10 次图表刷新）一根细蜡烛。
        for index, bar in enumerate(bars):
            x = centers[index]
            color = C.UP if bar["c"] >= bar["o"] else C.LINE_DOWN
            yh, yl = y_of(bar["h"]), y_of(bar["l"])
            yo, yc = y_of(bar["o"]), y_of(bar["c"])
            wick_width = 2 if (not bar["complete"] or body_w >= 14) else 1
            self.create_line(
                x, yh, x, yl, fill=color, width=wick_width, capstyle="round"
            )
            top, bottom = min(yo, yc), max(yo, yc)
            if bottom - top < 1.4:
                bottom = top + 1.4
            self.create_rectangle(
                x - body_w / 2,
                top,
                x + body_w / 2,
                bottom,
                fill=color,
                outline=color,
            )
            if not bar["complete"]:
                # 当前柱的小端点，强调这一秒正在变化。
                self.create_oval(
                    x - 2.4, yc - 2.4, x + 2.4, yc + 2.4,
                    fill=C.TEXT, outline=color
                )

        # 最新价、价格标签和虚线
        last_price = self.pair.price
        last_y = y_of(last_price)
        last_color = (
            C.UP if bars[-1]["c"] >= bars[-1]["o"] else C.LINE_DOWN
        )
        self.create_line(x0, last_y, x1, last_y, fill=last_color, dash=(3, 4))
        tag_right = x1 + 56
        draw_round_rect(
            self, x1 + 2, last_y - 9, tag_right, last_y + 9, 3,
            fill=last_color, outline=last_color
        )
        self.create_text(
            (x1 + 2 + tag_right) / 2,
            last_y,
            text=f"{last_price:.2f}",
            fill="#071117",
            font=FONTS.mono(8, "bold"),
            anchor="center",
        )

        # 图例
        self.create_rectangle(x0 + 4, y0 + 4, x0 + 13, y0 + 12, fill=C.UP, outline=C.UP)
        self.create_text(
            x0 + 18, y0 + 8, text="上涨", fill=C.UP, font=FONTS.ui(8), anchor="w"
        )
        self.create_rectangle(
            x0 + 57, y0 + 4, x0 + 66, y0 + 12, fill=C.LINE_DOWN, outline=C.LINE_DOWN
        )
        self.create_text(
            x0 + 71, y0 + 8, text="下跌", fill=C.LINE_DOWN, font=FONTS.ui(8), anchor="w"
        )
        if getattr(self.pair, "surge", False):
            surge_up = getattr(self.pair, "trend_strength", 0.0) >= 0
            surge_color = C.UP if surge_up else C.LINE_DOWN
            self.create_text(
                x0 + 118,
                y0 + 8,
                text="⚡ 大幅" + ("上涨" if surge_up else "下跌"),
                fill=surge_color,
                font=FONTS.ui(8, "bold"),
                anchor="w",
            )
        self.create_text(
            x1 - 5,
            y0 + 9,
            text=f"每 20 秒 1 根 · 10 次刷新 · {len(bars)} 根",
            fill=C.MUTED,
            font=FONTS.mono(8),
            anchor="e",
        )

        self.create_text(
            x0 + 6,
            y1 - 8,
            text="SCORE FX · 10S",
            fill="#0E1E27",
            font=FONTS.num(18, "bold"),
            anchor="sw",
        )

        self._geom = {
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "step": step,
            "bars": bars,
            "centers": centers,
            "hi": hi,
            "lo": lo,
        }
        if self._hover:
            self._draw_crosshair(*self._hover)

    def _on_motion(self, event):
        if not self._geom:
            return
        self._hover = (event.x, event.y)
        self._draw_crosshair(event.x, event.y)

    def _on_leave(self, _event=None):
        self._hover = None
        self.delete("hover")

    def _draw_crosshair(self, mx, my):
        self.delete("hover")
        if not self._geom:
            return
        g = self._geom
        x0, y0, x1, y1 = g["x0"], g["y0"], g["x1"], g["y1"]
        if not (x0 <= mx <= x1 and y0 <= my <= y1):
            return
        bars = g["bars"]
        centers = g["centers"]
        index = int((mx - x0) / max(0.001, g["step"]))
        index = max(0, min(len(bars) - 1, index))
        bar = bars[index]
        cx = centers[index]
        self.create_line(cx, y0, cx, y1, fill=C.SOFT, dash=(3, 4), tags="hover")
        self.create_line(x0, my, x1, my, fill=C.SOFT, dash=(3, 4), tags="hover")

        value = g["hi"] - (my - y0) / max(1, (y1 - y0)) * (g["hi"] - g["lo"])
        draw_round_rect(
            self, x1 + 2, my - 8, x1 + 56, my + 8, 3,
            fill=C.PANEL_3, outline=C.BORDER_LIGHT, tags="hover"
        )
        self.create_text(
            (x1 + 2 + x1 + 56) / 2,
            my,
            text=f"{value:.2f}",
            fill=C.TEXT,
            font=FONTS.mono(8),
            tags="hover",
        )

        color = C.UP if bar["c"] >= bar["o"] else C.LINE_DOWN
        box_w, box_h = 184, 72
        bx = cx + 12
        if bx + box_w > x1 - 4:
            bx = cx - box_w - 12
        by = my + 12
        if by + box_h > y1 - 4:
            by = my - box_h - 12
        bx = max(x0 + 4, bx)
        by = max(y0 + 4, by)
        draw_round_rect(
            self, bx, by, bx + box_w, by + box_h, 5,
            fill=C.PANEL_3, outline=C.BORDER_LIGHT, tags="hover"
        )
        state = "进行中" if not bar.get("complete") else "已完成"
        text = (
            f"{bar['start']} – {bar['end']}  {state}\n"
            f"开 {bar['o']:.2f}  高 {bar['h']:.2f}\n"
            f"低 {bar['l']:.2f}  收 {bar['c']:.2f}"
        )
        self.create_text(
            bx + 9,
            by + 8,
            text=text,
            fill=color,
            font=FONTS.mono(8),
            anchor="nw",
            justify="left",
            tags="hover",
        )
