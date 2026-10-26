"""
Teknik analiz göstergeleri.
Harici bir TA kütüphanesine bağımlı kalmamak için (sürüm/uyumluluk sorunu
yaşanmasın diye) RSI, MACD, EMA ve ATR burada pandas ile sıfırdan hesaplanır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def daily_indicators(daily_df: pd.DataFrame) -> dict:
    """daily_df: Date index, OHLCV sütunlu günlük veri (en az ~60 gün)."""
    close = daily_df["Close"]
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    rsi14 = rsi(close, 14)
    macd_line, signal_line, hist = macd(close)
    atr14 = atr(daily_df, 14)
    avg_vol20 = daily_df["Volume"].rolling(20).mean()

    return {
        "close": close.iloc[-1],
        "ema20": ema20.iloc[-1],
        "ema50": ema50.iloc[-1],
        "rsi14": rsi14.iloc[-1],
        "macd": macd_line.iloc[-1],
        "macd_signal": signal_line.iloc[-1],
        "macd_hist": hist.iloc[-1],
        "macd_hist_prev": hist.iloc[-2] if len(hist) > 1 else np.nan,
        "atr14": atr14.iloc[-1],
        "avg_vol20": avg_vol20.iloc[-1],
    }
