"""
Günlük + gün içi (intraday) verileri birleştirip her hisseye bir "sabah
10:30 puanı" verir ve stop-loss / take-profit seviyeleri önerir.

Bu bir yatırım tavsiyesi değildir; sadece kural tabanlı, teknik bir
ön-eleme aracıdır. Nihai kararı ve riski kullanıcı üstlenir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .indicators import daily_indicators

SESSION_MINUTES = (18 - 10) * 60  # 10:00-18:00


@dataclass
class ScanSettings:
    min_avg_liquidity_tl: float = 10_000_000.0   # ortalama günlük işlem hacmi (TL) alt sınırı
    rsi_min: float = 45.0
    rsi_max: float = 72.0
    min_change_from_open_pct: float = 0.3        # açılıştan bu yüzdeden az artanları eleme
    max_change_from_open_pct: float = 8.0        # çok uzamış (kovalanacak) hisseleri eleme
    min_relative_volume: float = 1.1
    atr_stop_multiplier: float = 1.0
    risk_reward_ratio: float = 2.0
    top_n: int = 15


@dataclass
class ScanResult:
    symbol: str
    score: float
    price: float
    change_from_open_pct: float
    rsi14: float
    trend_ok: bool
    macd_bullish: bool
    opening_range_breakout: bool
    relative_volume: float
    atr14: float
    suggested_stop_loss: float
    suggested_take_profit: float
    stop_loss_pct: float
    take_profit_pct: float
    notes: list = field(default_factory=list)


def _minutes_since_open(now_istanbul) -> float:
    open_dt = now_istanbul.replace(hour=10, minute=0, second=0, microsecond=0)
    delta = (now_istanbul - open_dt).total_seconds() / 60.0
    return max(delta, 1.0)


def evaluate_symbol(symbol: str, daily_df: pd.DataFrame, intraday_df: pd.DataFrame,
                     now_istanbul, settings: ScanSettings) -> ScanResult | None:
    if daily_df is None or daily_df.empty or len(daily_df) < 25:
        return None
    if intraday_df is None or intraday_df.empty:
        return None

    ind = daily_indicators(daily_df)
    if any(pd.isna(v) for v in [ind["close"], ind["ema20"], ind["rsi14"], ind["atr14"]]):
        return None

    today_open = intraday_df["Open"].iloc[0]
    last_price = intraday_df["Close"].iloc[-1]
    today_volume_so_far = intraday_df["Volume"].sum()

    if today_open <= 0 or last_price <= 0:
        return None

    change_from_open_pct = (last_price - today_open) / today_open * 100

    # Açılış aralığı: ilk 30 dakika (10:00-10:30, yani ilk iki 15dk mumu)
    opening_bars = intraday_df.iloc[: min(2, len(intraday_df))]
    opening_high = opening_bars["High"].max()
    breakout = last_price > opening_high if len(intraday_df) > 2 else False

    minutes_elapsed = _minutes_since_open(now_istanbul)
    fraction_of_day = min(minutes_elapsed / SESSION_MINUTES, 1.0)
    expected_vol_so_far = (ind["avg_vol20"] or np.nan) * fraction_of_day
    relative_volume = (
        today_volume_so_far / expected_vol_so_far
        if expected_vol_so_far and expected_vol_so_far > 0
        else np.nan
    )

    trend_ok = ind["close"] > ind["ema20"] > ind["ema50"]
    macd_bullish = ind["macd"] > ind["macd_signal"] and ind["macd_hist"] > ind["macd_hist_prev"]
    rsi_ok = settings.rsi_min <= ind["rsi14"] <= settings.rsi_max

    # --- Puanlama (0-100) ---
    score = 0.0
    notes = []
    if trend_ok:
        score += 25
        notes.append("Günlük trend yukarı (Fiyat>EMA20>EMA50)")
    if macd_bullish:
        score += 20
        notes.append("MACD pozitif / güçleniyor")
    if rsi_ok:
        score += 15
        notes.append(f"RSI dengeli ({ind['rsi14']:.0f})")
    if breakout:
        score += 20
        notes.append("Açılış aralığını (10:00-10:30) yukarı kırdı")
    if not np.isnan(relative_volume) and relative_volume >= settings.min_relative_volume:
        bonus = min((relative_volume - 1) * 10, 20)
        score += max(bonus, 0)
        notes.append(f"Hacim ortalamanın {relative_volume:.1f} katı")

    # --- Elemeler (hard filter) ---
    if change_from_open_pct < settings.min_change_from_open_pct:
        return None
    if change_from_open_pct > settings.max_change_from_open_pct:
        return None

    atr14 = ind["atr14"]
    stop_loss = last_price - settings.atr_stop_multiplier * atr14
    risk = last_price - stop_loss
    take_profit = last_price + settings.risk_reward_ratio * risk
    if stop_loss <= 0:
        stop_loss = last_price * 0.97
        risk = last_price - stop_loss
        take_profit = last_price + settings.risk_reward_ratio * risk

    return ScanResult(
        symbol=symbol,
        score=round(score, 1),
        price=round(float(last_price), 4),
        change_from_open_pct=round(float(change_from_open_pct), 2),
        rsi14=round(float(ind["rsi14"]), 1),
        trend_ok=bool(trend_ok),
        macd_bullish=bool(macd_bullish),
        opening_range_breakout=bool(breakout),
        relative_volume=round(float(relative_volume), 2) if not np.isnan(relative_volume) else float("nan"),
        atr14=round(float(atr14), 4),
        suggested_stop_loss=round(float(stop_loss), 4),
        suggested_take_profit=round(float(take_profit), 4),
        stop_loss_pct=round(float((stop_loss - last_price) / last_price * 100), 2),
        take_profit_pct=round(float((take_profit - last_price) / last_price * 100), 2),
        notes=notes,
    )


def run_scan(tickers_df, daily_data: dict, intraday_data: dict, now_istanbul,
             settings: ScanSettings) -> pd.DataFrame:
    liquidity_map = dict(zip(tickers_df["yf_symbol"], tickers_df["last_volume_tl_ref"]))
    rows = []
    for sym, daily_df in daily_data.items():
        if liquidity_map.get(sym, 0) < settings.min_avg_liquidity_tl:
            continue
        intraday_df = intraday_data.get(sym)
        res = evaluate_symbol(sym, daily_df, intraday_df, now_istanbul, settings)
        if res is not None:
            rows.append(res)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([r.__dict__ for r in rows])
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df.head(settings.top_n)
