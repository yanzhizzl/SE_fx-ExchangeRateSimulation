"""
SCORE FX - 模拟行情与账户引擎

这是一个纯虚拟的“成绩关联交易”模拟器：
价格代表两个学科成绩的相对强弱，和现实中的货币、证券没有任何关系。
所有数值只用于游戏化的学习反馈。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# 核心参数
# ---------------------------------------------------------------------------

STARTING_BALANCE = 1000.0          # 入学时的模拟分数余额
CONTRACT_MULT = 1.0                # 每个数量单位直接对应 1 分/点的盈亏
MIN_LOTS = 0.1
MAX_LOTS = 5.0
LOT_STEP = 0.1
MAX_POSITIONS = 4
MAX_LEVERAGE = 75
MARGIN_FACTOR = 1.0                # 保证金 = 学入价 × 数量 ÷ 杠杆
MAINTENANCE_RATIO = 0.30           # 保证金率低于 30% 强制平仓
WARNING_RATIO_1 = 1.80             # 180% 风险提示
WARNING_RATIO_2 = 1.20             # 120% 严重风险提示
MARKET_TICK_MS = 1000
HISTORY_LEN = 1600
SEED_HISTORY = 960
TREND_MIN_SECONDS = 9
TREND_MAX_SECONDS = 11

TIER_DEFS = [
    {
        "id": "g1",
        "name": "高一",
        "tag": "G1",
        "subtitle": "基础学科 · 探索期",
        "description": "刚入学，知识点分散，行情相对温和。",
        "volatility": 0.86,
        "reward_mult": 1.00,
        "accent": "#4AD7FF",
        "pairs": [
            {"id": "mth_chn", "left": "数学", "right": "语文", "code": "MTH.CHN", "base": 96.80},
            {"id": "phy_eng", "left": "物理", "right": "英语", "code": "PHY.ENG", "base": 91.40},
            {"id": "chm_bio", "left": "化学", "right": "生物", "code": "CHM.BIO", "base": 88.60},
            {"id": "his_geo", "left": "历史", "right": "地理", "code": "HIS.GEO", "base": 84.20},
        ],
    },
    {
        "id": "g2",
        "name": "高二",
        "tag": "G2",
        "subtitle": "文理分化 · 波动加剧",
        "description": "科目难度提升，优势学科开始分化。",
        "volatility": 1.08,
        "reward_mult": 1.15,
        "accent": "#F2C14E",
        "pairs": [
            {"id": "mth_chn", "left": "数学", "right": "语文", "code": "MTH.CHN", "base": 102.60},
            {"id": "phy_eng", "left": "物理", "right": "英语", "code": "PHY.ENG", "base": 97.90},
            {"id": "chm_bio", "left": "化学", "right": "生物", "code": "CHM.BIO", "base": 94.30},
            {"id": "his_pol", "left": "历史", "right": "政治", "code": "HIS.POL", "base": 90.10},
            {"id": "geo_mth", "left": "地理", "right": "数学", "code": "GEO.MTH", "base": 86.70},
        ],
    },
    {
        "id": "g3",
        "name": "高三",
        "tag": "G3",
        "subtitle": "高考冲刺 · 高危阶段",
        "description": "每一次诊断考都会放大波动，风险与机会并存。",
        "volatility": 1.38,
        "reward_mult": 1.30,
        "accent": "#FF6B7A",
        "pairs": [
            {"id": "mth_phy", "left": "数学", "right": "物理", "code": "MTH.PHY", "base": 108.40},
            {"id": "chn_eng", "left": "语文", "right": "英语", "code": "CHN.ENG", "base": 103.20},
            {"id": "chm_bio", "left": "化学", "right": "生物", "code": "CHM.BIO", "base": 99.10},
            {"id": "his_pol", "left": "历史", "right": "政治", "code": "HIS.POL", "base": 95.80},
            {"id": "geo_mth", "left": "地理", "right": "数学", "code": "GEO.MTH", "base": 92.30},
            {"id": "phy_chm", "left": "物理", "right": "化学", "code": "PHY.CHM", "base": 88.90},
        ],
    },
]

# 年级分数倍率：只放大该年级产生的交易金额，不改变题目奖励和练习赚分。
TIER_SCORE_MULTIPLIER = {"g1": 1.0, "g2": 5.0, "g3": 20.0}


def tier_score_multiplier(tier_id: str) -> float:
    return float(TIER_SCORE_MULTIPLIER.get(str(tier_id), 1.0))


SUBJECT_COLORS = {
    "数学": "#4AD7FF",
    "语文": "#FF8A9A",
    "物理": "#AA8BFF",
    "英语": "#F2C14E",
    "化学": "#2DD4A7",
    "生物": "#7CDD6A",
    "历史": "#E6A96B",
    "政治": "#FF9E64",
    "地理": "#62C4E8",
}


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class PairMarket:
    uid: str
    tier_id: str
    tier_name: str
    pair_id: str
    left: str
    right: str
    code: str
    base: float
    volatility: float
    price: float
    prev_close: float
    high: float
    low: float
    history: List[float] = field(default_factory=list)
    drift: float = 0.0
    last_change: float = 0.0
    trend_remaining: int = 0
    trend_strength: float = 0.0
    wick_high: float = 0.0
    wick_low: float = 0.0
    surge: bool = False

    @property
    def name(self) -> str:
        return f"{self.left} / {self.right}"

    @property
    def change(self) -> float:
        return self.price - self.prev_close

    @property
    def change_pct(self) -> float:
        if not self.prev_close:
            return 0.0
        return self.change / self.prev_close * 100.0

    @property
    def is_up(self) -> bool:
        return self.change >= 0

    def short_history(self, count: int = 28) -> List[float]:
        return self.history[-count:]


@dataclass
class SchoolEvent:
    event_id: int
    title: str
    detail: str
    tone: str                  # good / bad / mixed
    subjects: Sequence[str]    # 空表示全科
    drift: float
    vol_mult: float
    duration: int              # 以行情 tick 计
    remaining: int
    affected_uids: set = field(default_factory=set)
    started_tick: int = 0

    @property
    def seconds_left(self) -> int:
        return max(0, int(round(self.remaining * MARKET_TICK_MS / 1000.0)))

    @property
    def tone_label(self) -> str:
        return {"good": "利好", "bad": "利空", "mixed": "波动加剧"}.get(self.tone, "事件")

    @property
    def subject_label(self) -> str:
        if not self.subjects:
            return "全科"
        if len(self.subjects) == 1:
            return self.subjects[0]
        return " / ".join(self.subjects)


@dataclass
class Position:
    pos_id: str
    pair_uid: str
    pair_id: str
    tier_id: str
    tier_name: str
    pair_name: str
    pair_code: str
    left: str
    right: str
    direction: int             # +1 做多（看涨左侧学科），-1 做空
    lots: float
    leverage: int
    entry_price: float
    margin: float
    opened_tick: int
    quiz_subject: str
    quiz_level: int
    score_factor: float = 1.0

    @property
    def direction_label(self) -> str:
        return "买入" if self.direction > 0 else "卖出"

    @property
    def direction_short(self) -> str:
        return "多" if self.direction > 0 else "空"

    @property
    def size(self) -> float:
        return self.lots * CONTRACT_MULT

    @property
    def notional(self) -> float:
        return self.entry_price * self.size * self.score_factor

    @property
    def stake(self) -> float:
        """账户实际扣除：投入资金 + 保证金。"""
        return self.notional + self.margin

    def base_pnl(self, price: float) -> float:
        """杠杆前盈亏：只按价格差 × 数量 × 年级分数倍率计算。"""
        return (price - self.entry_price) * self.direction * self.size * self.score_factor

    def pnl(self, price: float) -> float:
        """实际盈亏：杠杆前盈亏 × 杠杆倍数。"""
        return self.base_pnl(price) * max(1, self.leverage)

    def pnl_pct_of_margin(self, price: float) -> float:
        if not self.margin:
            return 0.0
        return self.pnl(price) / self.margin * 100.0


@dataclass
class TickReport:
    started_events: List[SchoolEvent] = field(default_factory=list)
    expired_events: List[SchoolEvent] = field(default_factory=list)
    surges: List[PairMarket] = field(default_factory=list)


@dataclass
class CloseResult:
    position: Position
    price: float
    pnl: float
    reason: str


# ---------------------------------------------------------------------------
# 行情引擎
# ---------------------------------------------------------------------------

class MarketEngine:
    """同时维护高一 / 高二 / 高三三套虚拟行情。"""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.tiers: Dict[str, dict] = {tier["id"]: tier for tier in TIER_DEFS}
        self.markets: Dict[str, List[PairMarket]] = {}
        self.all_pairs: Dict[str, PairMarket] = {}
        self.active_events: List[SchoolEvent] = []
        self.tick_count = 0
        self.event_seq = 0
        self._event_internal = 0
        self.next_event_tick = 8
        self._build_markets()

    # ----- 初始化 ---------------------------------------------------------

    def _build_markets(self) -> None:
        for tier in TIER_DEFS:
            pairs: List[PairMarket] = []
            for spec in tier["pairs"]:
                uid = f"{tier['id']}_{spec['id']}"
                pair = PairMarket(
                    uid=uid,
                    tier_id=tier["id"],
                    tier_name=tier["name"],
                    pair_id=spec["id"],
                    left=spec["left"],
                    right=spec["right"],
                    code=spec["code"],
                    base=float(spec["base"]),
                    volatility=0.24 + 0.020 * (len(spec["code"]) % 3),
                    price=float(spec["base"]),
                    prev_close=float(spec["base"]),
                    high=float(spec["base"]),
                    low=float(spec["base"]),
                )
                self._seed_history(pair, tier["volatility"])
                pairs.append(pair)
                self.all_pairs[uid] = pair
            self.markets[tier["id"]] = pairs

    def _seed_history(self, pair: PairMarket, tier_vol: float) -> None:
        rng = self.rng
        price = pair.base * (1.0 + rng.uniform(-0.004, 0.004))
        pair.price = round(price, 2)
        pair.trend_remaining = 0
        pair.trend_strength = 0.0
        history: List[float] = []
        for _ in range(SEED_HISTORY):
            pair.price = self._step_price(pair, tier_vol, 0.0, 1.0)
            history.append(pair.price)
        pair.history = history
        pair.price = history[-1]
        pair.high = max(history)
        pair.low = min(history)
        pair.prev_close = pair.base
        pair.last_change = 0.0
        pair.wick_high = history[-1]
        pair.wick_low = history[-1]

    def _choose_trend(self, pair: PairMarket, tier_vol: float) -> None:
        """行情不稳定：常态波动与大幅拉升/跳水交替，并允许连续同向。"""
        rng = self.rng
        previous = pair.trend_strength
        if abs(previous) < 1e-9:
            new_sign = rng.choice([-1, 1])
        else:
            previous_sign = 1 if previous > 0 else -1
            continue_probability = 0.62 if pair.surge else 0.46
            new_sign = previous_sign if rng.random() < continue_probability else -previous_sign
        is_surge = rng.random() < 0.28
        if is_surge:
            magnitude = rng.uniform(0.090, 0.260) * tier_vol
            duration = rng.randint(6, 14)
        else:
            magnitude = rng.uniform(0.020, 0.070) * tier_vol
            duration = rng.randint(TREND_MIN_SECONDS, TREND_MAX_SECONDS)
        # 小概率叠加额外行情冲击，形成更极端的连续大涨/大跌。
        if rng.random() < 0.06:
            magnitude *= rng.uniform(2.0, 3.6)
            duration = max(duration, rng.randint(8, 16))
            is_surge = True
        pair.trend_strength = new_sign * magnitude
        pair.trend_remaining = duration
        pair.surge = is_surge
        pair.drift = pair.trend_strength

    def _step_price(
        self,
        pair: PairMarket,
        tier_vol: float,
        event_drift: float = 0.0,
        event_vol: float = 1.0,
    ) -> float:
        rng = self.rng
        if pair.trend_remaining <= 0:
            self._choose_trend(pair, tier_vol)
        pair.trend_remaining -= 1

        # 噪声刻意小于趋势强度，使每一段趋势在图上以连续红/蓝线段呈现。
        noise = rng.gauss(0, 0.0075 * tier_vol * max(0.55, event_vol))
        reversion = (pair.base - pair.price) * 0.0008
        step = pair.trend_strength + event_drift * 0.42 + noise + reversion
        # 偶发的瞬时大波动，增加行情的不确定性。
        if rng.random() < 0.015:
            step += rng.choice([-1, 1]) * rng.uniform(0.08, 0.34) * tier_vol
        previous = pair.price
        new_price = round(max(20.0, min(320.0, previous + step)), 2)
        pair.price = new_price
        pair.last_change = round(new_price - previous, 2)
        wick_pad = abs(rng.gauss(0, 0.010 * tier_vol))
        pair.wick_high = round(max(previous, new_price) + wick_pad, 2)
        pair.wick_low = round(min(previous, new_price) - wick_pad, 2)
        return new_price

    # ----- 行情推进 -------------------------------------------------------

    def tick(self, active_uid: Optional[str] = None) -> TickReport:
        """推进行情。

        active_uid 为空时推进全部学科（测试/演示用）；主程序只传入当前选中学科，
        因此其他学科的价格、趋势和图表都会保持在暂停状态。
        """
        report = TickReport()
        self.tick_count += 1

        if active_uid is None:
            pairs = list(self.all_pairs.values())
        else:
            pair = self.all_pairs.get(active_uid)
            pairs = [pair] if pair is not None else []

        for pair in pairs:
            tier_vol = self.tiers[pair.tier_id]["volatility"]
            event_drift = 0.0
            event_vol = 1.0
            for event in self.active_events:
                if pair.uid in event.affected_uids:
                    event_drift += event.drift
                    event_vol *= event.vol_mult

            self._step_price(pair, tier_vol, event_drift, event_vol)
            if pair.surge and not getattr(pair, "_reported_surge", False):
                report.surges.append(pair)
                pair._reported_surge = True
            elif not pair.surge:
                pair._reported_surge = False
            pair.history.append(pair.price)
            if len(pair.history) > HISTORY_LEN:
                # 以 20 个 tick（约 20 秒）为一根细蜡烛，裁剪时保持柱体边界稳定。
                overflow = len(pair.history) - HISTORY_LEN
                trim = ((overflow + 19) // 20) * 20
                del pair.history[:trim]
            pair.high = max(pair.high, pair.wick_high, pair.price)
            pair.low = min(pair.low, pair.wick_low, pair.price)

        # 事件倒计时按真实秒数推进；暂停答题时主程序不会调用 tick。
        for event in list(self.active_events):
            event.remaining -= 1
            if event.remaining <= 0:
                self.active_events.remove(event)
                report.expired_events.append(event)

        self._event_internal += 1
        if self.tick_count >= self.next_event_tick:
            if len(self.active_events) < 2:
                event = self.spawn_random_event()
                if event:
                    report.started_events.append(event)
            self.next_event_tick = self.tick_count + self.rng.randint(17, 29)

        return report

    # ----- 校园事件 -------------------------------------------------------

    def spawn_random_event(self) -> Optional[SchoolEvent]:
        template = self.rng.choice(EVENT_TEMPLATES)
        subjects = list(template.get("subjects", []))
        affected = {
            pair.uid
            for pair in self.all_pairs.values()
            if not subjects or set(subjects) & {pair.left, pair.right}
        }
        if not affected:
            return None
        self.event_seq += 1
        event = SchoolEvent(
            event_id=self.event_seq,
            title=template["title"],
            detail=template["detail"],
            tone=template["tone"],
            subjects=subjects,
            drift=template["drift"],
            vol_mult=template["vol"],
            duration=template["duration"],
            remaining=template["duration"],
            affected_uids=affected,
            started_tick=self.tick_count,
        )
        self.active_events.append(event)
        return event

    def active_event_for(self, pair_uid: str) -> Optional[SchoolEvent]:
        for event in reversed(self.active_events):
            if pair_uid in event.affected_uids:
                return event
        return None

    def prices(self) -> Dict[str, float]:
        return {uid: pair.price for uid, pair in self.all_pairs.items()}

    def pair(self, uid: str) -> PairMarket:
        return self.all_pairs[uid]

    def tier_pairs(self, tier_id: str) -> List[PairMarket]:
        return self.markets[tier_id]


# ---------------------------------------------------------------------------
# 账户与风控
# ---------------------------------------------------------------------------

class Account:
    """分数账户、保证金与强平逻辑。"""

    def __init__(self, balance: float = STARTING_BALANCE) -> None:
        self.balance = float(balance)
        self.realized_pnl = 0.0
        self.positions: List[Position] = []
        self.closed_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.liquidation_count = 0
        self._pos_seq = 0

    # ----- 账户视图 -------------------------------------------------------

    def unrealized(self, prices: Dict[str, float]) -> float:
        return sum(pos.pnl(prices.get(pos.pair_uid, pos.entry_price)) for pos in self.positions)

    def unrealized_for(self, pos: Position, prices: Dict[str, float]) -> float:
        return pos.pnl(prices.get(pos.pair_uid, pos.entry_price))

    def equity(self, prices: Dict[str, float]) -> float:
        # 开仓时已从余额扣除「投入资金 + 保证金」；持仓当前价值包含这笔本金。
        value = sum(
            pos.stake + pos.pnl(prices.get(pos.pair_uid, pos.entry_price))
            for pos in self.positions
        )
        return self.balance + value

    def used_margin(self) -> float:
        return sum(pos.margin for pos in self.positions)

    def available(self, prices: Dict[str, float]) -> float:
        # 余额已经是扣除投入本金和保证金后的自由资金。
        return self.balance

    def margin_level(self, prices: Dict[str, float]) -> Optional[float]:
        used = self.used_margin()
        if used <= 0:
            return None
        return max(0.0, self.equity(prices) / used)

    def total_pnl(self, prices: Dict[str, float]) -> float:
        return self.realized_pnl + self.unrealized(prices)

    # ----- 开平仓 ---------------------------------------------------------

    def margin_required(
        self, price: float, lots: float, leverage: int, tier_id: str = "g1"
    ) -> float:
        return (
            price
            * lots
            * CONTRACT_MULT
            / max(1, leverage)
            * MARGIN_FACTOR
            * tier_score_multiplier(tier_id)
        )

    def can_open(
        self,
        price: float,
        lots: float,
        leverage: int,
        prices: Dict[str, float],
        tier_id: str = "g1",
    ) -> tuple[bool, str]:
        if not 1 <= int(leverage) <= MAX_LEVERAGE:
            return False, f"杠杆需在 1x–{MAX_LEVERAGE}x 之间"
        if len(self.positions) >= MAX_POSITIONS:
            return False, f"最多同时持有 {MAX_POSITIONS} 笔持仓"
        if lots < MIN_LOTS - 1e-9:
            return False, f"最少 {MIN_LOTS:g} 手"
        if lots > MAX_LOTS + 1e-9:
            return False, f"最多 {MAX_LOTS:g} 手"
        factor = tier_score_multiplier(tier_id)
        margin = self.margin_required(price, lots, leverage, tier_id)
        stake = price * lots * CONTRACT_MULT * factor + margin
        free = self.available(prices)
        if not math.isfinite(stake) or stake <= 0:
            return False, "投入分数计算异常"
        if stake > free * 0.985 + 1e-9:
            return False, "可用分数不足以扣除投入资金和保证金"
        return True, ""

    def open_position(
        self,
        pair: PairMarket,
        direction: int,
        lots: float,
        leverage: int,
        entry_price: float,
        quiz_subject: str,
        quiz_level: int,
        tick: int,
    ) -> Position:
        factor = tier_score_multiplier(pair.tier_id)
        margin = self.margin_required(entry_price, lots, leverage, pair.tier_id)
        stake = entry_price * lots * CONTRACT_MULT * factor + margin
        self._pos_seq += 1
        pos = Position(
            pos_id=f"P{self._pos_seq:03d}",
            pair_uid=pair.uid,
            pair_id=pair.pair_id,
            tier_id=pair.tier_id,
            tier_name=pair.tier_name,
            pair_name=pair.name,
            pair_code=pair.code,
            left=pair.left,
            right=pair.right,
            direction=1 if direction > 0 else -1,
            lots=round(lots, 1),
            leverage=leverage,
            entry_price=round(entry_price, 2),
            margin=margin,
            opened_tick=tick,
            quiz_subject=quiz_subject,
            quiz_level=quiz_level,
            score_factor=factor,
        )
        self.balance = max(0.0, self.balance - stake)
        self.positions.append(pos)
        return pos

    def close_position(
        self,
        pos: Position,
        price: float,
        reason: str = "考出",
        pnl_factor: float = 1.0,
    ) -> CloseResult:
        gross_pnl = pos.pnl(price)
        effective_pnl = gross_pnl * max(0.0, float(pnl_factor))
        settlement = pos.stake + effective_pnl
        self.balance = max(0.0, self.balance + settlement)
        self.realized_pnl += effective_pnl
        self.closed_count += 1
        if effective_pnl >= 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        if pos in self.positions:
            self.positions.remove(pos)
        return CloseResult(pos, price, effective_pnl, reason)

    def close_all(
        self,
        prices: Dict[str, float],
        reason: str = "一键考出",
        pnl_factor: float = 1.0,
    ) -> List[CloseResult]:
        results: List[CloseResult] = []
        for pos in list(self.positions):
            results.append(
                self.close_position(
                    pos,
                    prices.get(pos.pair_uid, pos.entry_price),
                    reason,
                    pnl_factor=pnl_factor,
                )
            )
        return results

    def liquidate_if_needed(self, prices: Dict[str, float]) -> Optional[List[CloseResult]]:
        if not self.positions:
            return None
        level = self.margin_level(prices)
        eq = self.equity(prices)
        if eq <= 0 or (level is not None and level <= MAINTENANCE_RATIO):
            self.liquidation_count += 1
            return self.close_all(prices, reason="强制平仓")
        return None

    def add_reward(self, points: float) -> None:
        self.balance += float(points)

    # ----- 辅助 -----------------------------------------------------------

    @staticmethod
    def win_rate(closed_count: int, win_count: int) -> Optional[float]:
        if closed_count <= 0:
            return None
        return win_count / closed_count * 100.0

    def approximate_liq_price(self, pos: Position, prices: Dict[str, float]) -> Optional[float]:
        """仅供 UI 参考的简化估算，其他持仓也会影响真实强平价。"""
        if not pos.size:
            return None
        # 忽略其他持仓，仅根据当前余额求 equity = MAINTENANCE_RATIO × margin
        target = MAINTENANCE_RATIO * pos.margin
        delta_needed = target - self.balance
        price = pos.entry_price + (delta_needed / (pos.direction * pos.size))
        return round(price, 2)


# ---------------------------------------------------------------------------
# 随机校园事件库
# ---------------------------------------------------------------------------

EVENT_TEMPLATES = [
    {
        "title": "重感冒袭击",
        "detail": "连续低烧三天，注意力涣散，全科成绩承压。",
        "tone": "bad",
        "subjects": [],
        "drift": -0.052,
        "vol": 1.55,
        "duration": 28,
    },
    {
        "title": "状态火热",
        "detail": "最近复习效率奇高，小测排名一路上涨。",
        "tone": "good",
        "subjects": [],
        "drift": 0.060,
        "vol": 1.18,
        "duration": 25,
    },
    {
        "title": "数学突然开窍",
        "detail": "压轴题连续做对，数学成绩被普遍看好。",
        "tone": "good",
        "subjects": ["数学"],
        "drift": 0.085,
        "vol": 1.10,
        "duration": 23,
    },
    {
        "title": "物理竞赛集训",
        "detail": "入选校队，物理思维和做题速度同步提升。",
        "tone": "good",
        "subjects": ["物理"],
        "drift": 0.078,
        "vol": 1.18,
        "duration": 24,
    },
    {
        "title": "作文被当作范文",
        "detail": "语文老师当众朗读，阅读与写作信心大增。",
        "tone": "good",
        "subjects": ["语文"],
        "drift": 0.072,
        "vol": 1.08,
        "duration": 21,
    },
    {
        "title": "英语听力崩盘",
        "detail": "听力小测连错五题，英语相关组合短线承压。",
        "tone": "bad",
        "subjects": ["英语"],
        "drift": -0.082,
        "vol": 1.35,
        "duration": 22,
    },
    {
        "title": "化学实验失误",
        "detail": "滴定操作失误，实验报告重做，化学情绪走低。",
        "tone": "bad",
        "subjects": ["化学"],
        "drift": -0.086,
        "vol": 1.38,
        "duration": 20,
    },
    {
        "title": "生物奥赛入围",
        "detail": "拿到省级初赛资格，生物学科热度上升。",
        "tone": "good",
        "subjects": ["生物"],
        "drift": 0.080,
        "vol": 1.14,
        "duration": 22,
    },
    {
        "title": "历史年代记混",
        "detail": "把两个朝代的时间记反了，历史小测失分。",
        "tone": "bad",
        "subjects": ["历史"],
        "drift": -0.076,
        "vol": 1.28,
        "duration": 20,
    },
    {
        "title": "政治小测翻车",
        "detail": "大题答偏方向，政治主观题得分低于预期。",
        "tone": "bad",
        "subjects": ["政治"],
        "drift": -0.070,
        "vol": 1.26,
        "duration": 20,
    },
    {
        "title": "地理图册丢失",
        "detail": "区域地理复习中断，地理相关组合波动放大。",
        "tone": "bad",
        "subjects": ["地理"],
        "drift": -0.066,
        "vol": 1.32,
        "duration": 19,
    },
    {
        "title": "连续熬夜刷题",
        "detail": "精神透支，虽然努力但错误率上升，波动加剧。",
        "tone": "mixed",
        "subjects": [],
        "drift": -0.025,
        "vol": 1.85,
        "duration": 26,
    },
    {
        "title": "换座位遇到学霸",
        "detail": "新同桌分享了全套笔记，整体学习氛围变好。",
        "tone": "good",
        "subjects": [],
        "drift": 0.042,
        "vol": 1.05,
        "duration": 25,
    },
    {
        "title": "手机被班主任没收",
        "detail": "晚自习突然安静下来，专注度明显提升。",
        "tone": "good",
        "subjects": [],
        "drift": 0.052,
        "vol": 0.88,
        "duration": 24,
    },
    {
        "title": "家长会临近",
        "detail": "全班人心浮动，成绩预期波动放大。",
        "tone": "mixed",
        "subjects": [],
        "drift": -0.032,
        "vol": 1.60,
        "duration": 23,
    },
    {
        "title": "错题本丢了",
        "detail": "积累半学期的错题本失踪，复习节奏被打乱。",
        "tone": "bad",
        "subjects": [],
        "drift": -0.048,
        "vol": 1.32,
        "duration": 22,
    },
    {
        "title": "周末补课取消",
        "detail": "突然多出半天自主复习时间，心态转好。",
        "tone": "good",
        "subjects": [],
        "drift": 0.036,
        "vol": 1.12,
        "duration": 20,
    },
    {
        "title": "体育课扭伤",
        "detail": "行动不便，状态受到干扰，全科短线走弱。",
        "tone": "bad",
        "subjects": [],
        "drift": -0.043,
        "vol": 1.34,
        "duration": 20,
    },
    {
        "title": "学习小组互助",
        "detail": "每晚互相讲题，薄弱学科开始补短。",
        "tone": "good",
        "subjects": [],
        "drift": 0.055,
        "vol": 0.98,
        "duration": 27,
    },
    {
        "title": "月考排名公布",
        "detail": "排名变化引发连锁反应，市场进入高波动状态。",
        "tone": "mixed",
        "subjects": [],
        "drift": 0.0,
        "vol": 2.05,
        "duration": 19,
    },
    {
        "title": "保送传闻四起",
        "detail": "数学、物理竞赛保送消息传播，相关组合被追捧。",
        "tone": "good",
        "subjects": ["数学", "物理"],
        "drift": 0.076,
        "vol": 1.62,
        "duration": 22,
    },
    {
        "title": "突然换了英语老师",
        "detail": "教学风格变化，英语相关组合进入适应期。",
        "tone": "mixed",
        "subjects": ["英语"],
        "drift": -0.020,
        "vol": 1.75,
        "duration": 23,
    },
]
