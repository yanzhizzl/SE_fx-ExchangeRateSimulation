"""SCORE FX - 会话存档。

只保存模拟游戏状态：账户、持仓、答题统计、行情历史、进行中的校园事件和
部分界面偏好。不会保存任何真实个人信息。
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Optional

import engine as E


SAVE_VERSION = 2
SAVE_APP = "SCORE_FX"
MAX_SAVE_BYTES = 5 * 1024 * 1024


class SaveGameError(Exception):
    pass


def app_dir() -> Path:
    """源码运行时用源码目录；打包成 exe 后用 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_save_path() -> Path:
    return app_dir() / "savegame.json"


# ---------------------------------------------------------------------------
# 读取校验
# ---------------------------------------------------------------------------

def _clamp(value, low, high, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(low, min(high, number))


def _as_int(value, default=0, low=0, high=10**9):
    number = _clamp(value, low, high, None)
    if number is None:
        return default
    return int(number)


def _text(value, max_len=400, default=""):
    if not isinstance(value, str):
        return default
    return value[:max_len]


def _pair_payload(pair: E.PairMarket) -> dict:
    return {
        "price": pair.price,
        "prev_close": pair.prev_close,
        "high": pair.high,
        "low": pair.low,
        "drift": pair.drift,
        "last_change": pair.last_change,
        "trend_remaining": pair.trend_remaining,
        "trend_strength": pair.trend_strength,
        "wick_high": pair.wick_high,
        "wick_low": pair.wick_low,
        "surge": pair.surge,
        "history": pair.history[-E.HISTORY_LEN:],
    }


def _position_payload(position: E.Position) -> dict:
    return {
        "pos_id": position.pos_id,
        "pair_uid": position.pair_uid,
        "direction": position.direction,
        "lots": position.lots,
        "leverage": position.leverage,
        "entry_price": position.entry_price,
        "margin": position.margin,
        "score_factor": position.score_factor,
        "opened_tick": position.opened_tick,
        "quiz_subject": position.quiz_subject,
        "quiz_level": position.quiz_level,
    }


def _event_payload(event: E.SchoolEvent) -> dict:
    return {
        "event_id": event.event_id,
        "title": event.title,
        "detail": event.detail,
        "tone": event.tone,
        "subjects": list(event.subjects),
        "drift": event.drift,
        "vol_mult": event.vol_mult,
        "duration": event.duration,
        "remaining": event.remaining,
        "affected_uids": sorted(event.affected_uids),
        "started_tick": event.started_tick,
    }


def build_snapshot(engine: E.MarketEngine, account: E.Account, stats: dict, ui: dict, messages: list) -> dict:
    return {
        "app": SAVE_APP,
        "version": SAVE_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "engine": {
            "tick_count": engine.tick_count,
            "event_seq": engine.event_seq,
            "next_event_tick": engine.next_event_tick,
            "pairs": {uid: _pair_payload(pair) for uid, pair in engine.all_pairs.items()},
            "active_events": [_event_payload(event) for event in engine.active_events],
        },
        "account": {
            "balance": account.balance,
            "realized_pnl": account.realized_pnl,
            "closed_count": account.closed_count,
            "win_count": account.win_count,
            "loss_count": account.loss_count,
            "liquidation_count": account.liquidation_count,
            "positions": [_position_payload(position) for position in account.positions],
        },
        "stats": {
            "attempts": int(stats.get("attempts", 0)),
            "correct": int(stats.get("correct", 0)),
            "streak": int(stats.get("streak", 0)),
            "best_streak": int(stats.get("best_streak", 0)),
            "earned": float(stats.get("earned", 0.0)),
        },
        "ui": {
            "tier_id": ui.get("tier_id", "g1"),
            "selected_uid": ui.get("selected_uid"),
            "lots": ui.get("lots", 0.5),
            "leverage": ui.get("leverage", 2),
            "timeframe": ui.get("timeframe", "1m"),
            "risk_stage": ui.get("risk_stage", 0),
            "tutorial_seen": bool(ui.get("tutorial_seen", False)),
            "milestone_20m_seen": bool(ui.get("milestone_20m_seen", False)),
        },
        "messages": [
            {
                "time": _text(item.get("time"), 20),
                "kind": _text(item.get("kind"), 20),
                "text": _text(item.get("text"), 1000),
                "tone": _text(item.get("tone"), 12, "info"),
            }
            for item in messages[:30]
            if isinstance(item, dict)
        ],
    }


# ---------------------------------------------------------------------------
# 保存
# ---------------------------------------------------------------------------

def save_state(
    path: Path,
    engine: E.MarketEngine,
    account: E.Account,
    stats: dict,
    ui: dict,
    messages: list,
) -> None:
    path = Path(path)
    payload = build_snapshot(engine, account, stats, ui, messages)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def delete_save(path: Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 恢复
# ---------------------------------------------------------------------------

def _restore_pairs(engine: E.MarketEngine, data: dict) -> None:
    pair_data = data.get("pairs")
    if not isinstance(pair_data, dict):
        raise SaveGameError("存档缺少行情数据")
    restored_any = False
    for uid, payload in pair_data.items():
        pair = engine.all_pairs.get(uid)
        if pair is None or not isinstance(payload, dict):
            continue
        restored_any = True
        history_raw = payload.get("history")
        history = []
        if isinstance(history_raw, list):
            for item in history_raw[-E.HISTORY_LEN:]:
                value = _clamp(item, 20.0, 320.0, None)
                if value is not None:
                    history.append(round(value, 2))
        if len(history) >= 2:
            pair.history = history
        price = _clamp(payload.get("price"), 20.0, 320.0, pair.history[-1])
        price = round(price, 2)
        if len(pair.history) >= 2:
            pair.history[-1] = price
        pair.price = price
        pair.prev_close = round(
            _clamp(payload.get("prev_close"), 20.0, 320.0, pair.base), 2
        )
        pair.high = round(
            _clamp(payload.get("high"), max(20.0, max(pair.history)), 320.0, price), 2
        )
        pair.low = round(
            _clamp(payload.get("low"), 20.0, min(320.0, min(pair.history)), price), 2
        )
        pair.high = max(pair.high, price, max(pair.history))
        pair.low = min(pair.low, price, min(pair.history))
        pair.drift = _clamp(payload.get("drift"), -0.2, 0.2, 0.0)
        pair.last_change = _clamp(payload.get("last_change"), -10.0, 10.0, 0.0)
        pair.trend_remaining = _as_int(payload.get("trend_remaining"), 0, 0, 12)
        pair.trend_strength = _clamp(payload.get("trend_strength"), -0.2, 0.2, 0.0)
        pair.wick_high = _clamp(
            payload.get("wick_high"), pair.price, 320.0, pair.price
        )
        pair.wick_low = _clamp(
            payload.get("wick_low"), 20.0, pair.price, pair.price
        )
        pair.surge = bool(payload.get("surge", False))
    if not restored_any:
        raise SaveGameError("存档中的学科行情都无法识别")


def _restore_engine(data: dict) -> E.MarketEngine:
    engine = E.MarketEngine()
    if not isinstance(data, dict):
        raise SaveGameError("行情模块格式错误")
    _restore_pairs(engine, data)
    engine.tick_count = _as_int(data.get("tick_count"), 0, 0)
    engine.event_seq = _as_int(data.get("event_seq"), 0, 0)
    engine.next_event_tick = _as_int(
        data.get("next_event_tick"), engine.tick_count + 10, engine.tick_count, engine.tick_count + 1000
    )
    events_raw = data.get("active_events")
    if isinstance(events_raw, list):
        for payload in events_raw[:4]:
            if not isinstance(payload, dict):
                continue
            title = _text(payload.get("title"), 80)
            if not title:
                continue
            affected = {
                uid
                for uid in payload.get("affected_uids", [])
                if isinstance(uid, str) and uid in engine.all_pairs
            }
            if not affected:
                continue
            duration = _as_int(payload.get("duration"), 20, 1, 200)
            remaining = _as_int(payload.get("remaining"), duration, 1, duration)
            tone = _text(payload.get("tone"), 12, "mixed")
            if tone not in ("good", "bad", "mixed"):
                tone = "mixed"
            subjects = [
                subject
                for subject in payload.get("subjects", [])
                if isinstance(subject, str)
            ]
            event = E.SchoolEvent(
                event_id=_as_int(payload.get("event_id"), 1, 1),
                title=title,
                detail=_text(payload.get("detail"), 500),
                tone=tone,
                subjects=subjects,
                drift=_clamp(payload.get("drift"), -0.3, 0.3, 0.0),
                vol_mult=_clamp(payload.get("vol_mult"), 0.5, 3.0, 1.0),
                duration=duration,
                remaining=remaining,
                affected_uids=affected,
                started_tick=_as_int(payload.get("started_tick"), 0, 0),
            )
            engine.active_events.append(event)
            engine.event_seq = max(engine.event_seq, event.event_id)
    return engine


def _restore_account(data: dict, engine: E.MarketEngine) -> E.Account:
    account = E.Account()
    if not isinstance(data, dict):
        raise SaveGameError("账户模块格式错误")
    account.balance = _clamp(data.get("balance"), 0.0, 10**9, E.STARTING_BALANCE)
    account.realized_pnl = _clamp(data.get("realized_pnl"), -10**9, 10**9, 0.0)
    account.closed_count = _as_int(data.get("closed_count"), 0)
    account.win_count = min(account.closed_count, _as_int(data.get("win_count"), 0))
    account.loss_count = min(account.closed_count, _as_int(data.get("loss_count"), 0))
    account.liquidation_count = _as_int(data.get("liquidation_count"), 0)

    positions_raw = data.get("positions")
    if isinstance(positions_raw, list):
        used_ids = set()
        for payload in positions_raw[: E.MAX_POSITIONS]:
            if not isinstance(payload, dict):
                continue
            pair = engine.all_pairs.get(payload.get("pair_uid"))
            if pair is None:
                continue
            direction = 1 if _as_int(payload.get("direction"), 1) >= 0 else -1
            lots = _clamp(payload.get("lots"), E.MIN_LOTS, E.MAX_LOTS, None)
            leverage = _as_int(payload.get("leverage"), 2)
            if lots is None or not 1 <= leverage <= E.MAX_LEVERAGE:
                continue
            entry_price = _clamp(payload.get("entry_price"), 1.0, 1000.0, None)
            if entry_price is None:
                continue
            margin = _clamp(payload.get("margin"), 0.01, 10**9, None)
            score_factor = _clamp(payload.get("score_factor"), 1.0, 20.0, 1.0)
            if margin is None:
                base_margin = (
                    entry_price * lots * E.CONTRACT_MULT
                    / max(1, leverage)
                    * E.MARGIN_FACTOR
                )
                margin = base_margin * score_factor
            pos_id = _text(payload.get("pos_id"), 20)
            if not pos_id or pos_id in used_ids:
                account._pos_seq += 1
                pos_id = f"P{account._pos_seq:03d}"
            used_ids.add(pos_id)
            try:
                seq = int(pos_id.lstrip("P"))
                account._pos_seq = max(account._pos_seq, seq)
            except ValueError:
                pass
            quiz_subject = _text(payload.get("quiz_subject"), 20, pair.left)
            if quiz_subject not in (
                "数学", "语文", "物理", "英语", "化学", "生物", "历史", "政治", "地理"
            ):
                quiz_subject = pair.left
            position = E.Position(
                pos_id=pos_id,
                pair_uid=pair.uid,
                pair_id=pair.pair_id,
                tier_id=pair.tier_id,
                tier_name=pair.tier_name,
                pair_name=pair.name,
                pair_code=pair.code,
                left=pair.left,
                right=pair.right,
                direction=direction,
                lots=round(lots, 1),
                leverage=leverage,
                entry_price=round(entry_price, 2),
                margin=round(margin, 4),
                opened_tick=_as_int(payload.get("opened_tick"), 0, 0),
                quiz_subject=quiz_subject,
                quiz_level=_as_int(payload.get("quiz_level"), 1, 1, 4),
                score_factor=score_factor,
            )
            account.positions.append(position)
    return account


def _restore_stats(data: dict) -> dict:
    stats = {"attempts": 0, "correct": 0, "streak": 0, "best_streak": 0, "earned": 0.0}
    if not isinstance(data, dict):
        return stats
    stats["attempts"] = _as_int(data.get("attempts"), 0)
    stats["correct"] = min(stats["attempts"], _as_int(data.get("correct"), 0))
    stats["streak"] = min(stats["correct"], _as_int(data.get("streak"), 0))
    stats["best_streak"] = min(
        stats["correct"], _as_int(data.get("best_streak"), stats["streak"])
    )
    stats["earned"] = _clamp(data.get("earned"), 0.0, 10**9, 0.0)
    return stats


def _restore_ui(data: dict, engine: E.MarketEngine) -> dict:
    data = data if isinstance(data, dict) else {}
    tier_id = data.get("tier_id")
    if tier_id not in engine.markets:
        tier_id = "g1"
    selected_uid = data.get("selected_uid")
    valid_uids = {pair.uid for pair in engine.markets[tier_id]}
    if selected_uid not in valid_uids:
        selected_uid = engine.markets[tier_id][0].uid
    lots = _clamp(data.get("lots"), E.MIN_LOTS, E.MAX_LOTS, 0.5)
    lots = round(lots, 1)
    leverage = _as_int(data.get("leverage"), 2)
    if not 1 <= leverage <= E.MAX_LEVERAGE:
        leverage = 2
    timeframe = data.get("timeframe")
    if timeframe not in ("1m", "5m", "15m"):
        timeframe = "1m"
    risk_stage = _as_int(data.get("risk_stage"), 0, 0, 2)
    return {
        "tier_id": tier_id,
        "selected_uid": selected_uid,
        "lots": lots,
        "leverage": leverage,
        "timeframe": timeframe,
        "risk_stage": risk_stage,
        "tutorial_seen": bool(data.get("tutorial_seen", False)),
        "milestone_20m_seen": bool(data.get("milestone_20m_seen", False)),
    }


def _restore_messages(data) -> list:
    messages = []
    if not isinstance(data, list):
        return messages
    for item in data[:30]:
        if not isinstance(item, dict):
            continue
        tone = _text(item.get("tone"), 12, "info")
        if tone not in ("good", "bad", "mixed", "info"):
            tone = "info"
        messages.append(
            {
                "time": _text(item.get("time"), 20),
                "kind": _text(item.get("kind"), 20),
                "text": _text(item.get("text"), 1000),
                "tone": tone,
            }
        )
    return messages


def load_state(path: Path) -> Optional[dict]:
    """读取存档；不存在返回 None，损坏则抛出 SaveGameError。"""
    path = Path(path)
    if not path.exists():
        return None
    try:
        if path.stat().st_size > MAX_SAVE_BYTES:
            raise SaveGameError("存档文件过大")
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except SaveGameError:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise SaveGameError(f"存档无法解析：{exc}") from exc

    if not isinstance(payload, dict) or payload.get("app") != SAVE_APP:
        raise SaveGameError("不是 SCORE FX 存档")
    version = payload.get("version")
    if version not in (1, SAVE_VERSION):
        raise SaveGameError("存档版本不兼容")

    engine = _restore_engine(payload.get("engine", {}))
    account = _restore_account(payload.get("account", {}), engine)
    if version == 1:
        # v1 的余额没有扣除开仓本金；升级到 v2 时补做扣除。
        for position in account.positions:
            position.margin = account.margin_required(
                position.entry_price, position.lots, position.leverage
            )
            stake = (
                position.entry_price * position.lots * E.CONTRACT_MULT
                + position.margin
            )
            account.balance = max(0.0, account.balance - stake)
    stats = _restore_stats(payload.get("stats", {}))
    ui = _restore_ui(payload.get("ui", {}), engine)
    messages = _restore_messages(payload.get("messages", []))
    saved_at = _text(payload.get("saved_at"), 40)
    return {
        "engine": engine,
        "account": account,
        "stats": stats,
        "ui": ui,
        "messages": messages,
        "saved_at": saved_at,
    }
