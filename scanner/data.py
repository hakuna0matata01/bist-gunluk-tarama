"""
Yahoo Finance (yfinance) üzerinden BIST verisi çekme.

Not: Bu modül ücretsiz, herkese açık Yahoo Finance verisini kullanır.
Gecikmeli / zaman zaman eksik olabilir; profesyonel bir veri sağlayıcısının
yerini tutmaz ama ücretsiz bir ön-tarama aracı için yeterlidir.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TICKERS_CSV = DATA_DIR / "bist_tickers.csv"

ISTANBUL_TZ = "Europe/Istanbul"
MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 10, 0
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 18, 0


def load_all_tickers() -> pd.DataFrame:
    """CSV'den tüm BIST sembollerini (ve referans hacim bilgisini) okur."""
    df = pd.read_csv(TICKERS_CSV)
    df["yf_symbol"] = df["symbol"].astype(str).str.strip() + ".IS"
    return df


def _chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def fetch_daily_history(yf_symbols: list[str], period: str = "6mo", batch_size: int = 40,
                         pause_sec: float = 0.4, progress_cb=None) -> dict[str, pd.DataFrame]:
    """Her sembol için günlük OHLCV verisini toplu halde indirir.

    Yahoo'yu tek tek yüzlerce istekle yormamak için sembolleri gruplar
    halinde indirir. Dönen sözlük: {sembol: DataFrame}.
    """
    results: dict[str, pd.DataFrame] = {}
    chunks = list(_chunked(yf_symbols, batch_size))
    for i, chunk in enumerate(chunks):
        try:
            data = yf.download(
                tickers=chunk,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception:
            data = None

        if data is not None:
            for sym in chunk:
                try:
                    if len(chunk) == 1:
                        df = data
                    else:
                        df = data[sym]
                    df = df.dropna(how="all")
                    if not df.empty and len(df) >= 25:
                        results[sym] = df
                except (KeyError, Exception):
                    continue

        if progress_cb:
            progress_cb((i + 1) / len(chunks))
        time.sleep(pause_sec)

    return results


def fetch_intraday_today(yf_symbols: list[str], batch_size: int = 40,
                          pause_sec: float = 0.4, progress_cb=None) -> dict[str, pd.DataFrame]:
    """Bugüne ait 15 dakikalık mum verisini indirir (açılıştan şu ana kadar)."""
    results: dict[str, pd.DataFrame] = {}
    chunks = list(_chunked(yf_symbols, batch_size))
    for i, chunk in enumerate(chunks):
        try:
            data = yf.download(
                tickers=chunk,
                period="1d",
                interval="15m",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception:
            data = None

        if data is not None:
            for sym in chunk:
                try:
                    if len(chunk) == 1:
                        df = data
                    else:
                        df = data[sym]
                    df = df.dropna(how="all")
                    if not df.empty:
                        results[sym] = df
                except (KeyError, Exception):
                    continue

        if progress_cb:
            progress_cb((i + 1) / len(chunks))
        time.sleep(pause_sec)

    return results
