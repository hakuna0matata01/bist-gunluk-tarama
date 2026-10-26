import datetime as dt

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from scanner import ScanSettings, load_all_tickers, fetch_daily_history, fetch_intraday_today
from scanner.scoring import run_scan

ISTANBUL = ZoneInfo("Europe/Istanbul")

st.set_page_config(page_title="BIST Sabah Taraması", page_icon="📈", layout="wide")

st.title("📈 BIST Sabah Taraması (10:30 Day-Trade Ön Eleme)")

st.warning(
    "⚠️ **Bu araç yatırım tavsiyesi değildir.** Sadece kural tabanlı, teknik bir "
    "ön-eleme / tarama aracıdır. Veriler Yahoo Finance'ten (ücretsiz, gecikmeli/"
    "aralıklı olabilir) alınır. Alım-satım kararı ve tüm riski kullanıcıya aittir. "
    "Uygulama MİDAS'a veya başka bir aracı kuruma bağlı değildir ve emir "
    "göndermez — sadece fiyat seviyesi **önerir**, emri siz MİDAS üzerinden "
    "manuel olarak girersiniz."
)

now = dt.datetime.now(ISTANBUL)
st.caption(f"Şu anki İstanbul saati: **{now.strftime('%H:%M:%S, %d.%m.%Y')}**")

if now.hour < 10 or (now.hour == 10 and now.minute < 30):
    st.info(
        "Piyasa 10:00'da açılır. Açılış oynaklığının oturması için taramayı "
        "**10:30'dan sonra** çalıştırmanız önerilir. Yine de denemek isterseniz "
        "aşağıdan çalıştırabilirsiniz."
    )
if now.weekday() >= 5:
    st.info("Bugün hafta sonu — BIST kapalı. Sonuçlar son işlem gününe ait olabilir.")

# ---------------- Sidebar: ayarlar ----------------
st.sidebar.header("Tarama Ayarları")

all_tickers_df = load_all_tickers()
max_available = len(all_tickers_df)

scan_universe = st.sidebar.radio(
    "Taranacak evren",
    ["Tüm BIST (yavaş ama kapsamlı)", "En likit N hisse (hızlı)"],
    index=1,
)
n_liquid = st.sidebar.slider("Hızlı modda kaç hisse taransın?", 50, max_available, 150, step=50)

min_liquidity = st.sidebar.number_input(
    "Minimum ortalama günlük işlem hacmi (TL)",
    min_value=0, value=10_000_000, step=1_000_000,
    help="Çok düşük hacimli hisseler, küçük sermaye ile bile giriş-çıkışta "
         "kayma (slipaj) riski taşıdığı için elenir.",
)
rsi_min, rsi_max = st.sidebar.slider("RSI(14) aralığı", 0, 100, (45, 72))
min_change, max_change = st.sidebar.slider(
    "Açılıştan bu ana kadarki değişim aralığı (%)", -5.0, 15.0, (0.3, 8.0), step=0.1
)
min_rel_vol = st.sidebar.slider("Minimum göreli hacim (ortalamaya oran)", 0.5, 3.0, 1.1, step=0.1)
atr_mult = st.sidebar.slider("Stop-loss mesafesi (ATR çarpanı)", 0.5, 3.0, 1.0, step=0.1)
rr_ratio = st.sidebar.slider("Risk/Ödül oranı (Take-Profit)", 1.0, 4.0, 2.0, step=0.5)
top_n = st.sidebar.slider("Kaç aday gösterilsin?", 5, 30, 15)

settings = ScanSettings(
    min_avg_liquidity_tl=min_liquidity,
    rsi_min=rsi_min,
    rsi_max=rsi_max,
    min_change_from_open_pct=min_change,
    max_change_from_open_pct=max_change,
    min_relative_volume=min_rel_vol,
    atr_stop_multiplier=atr_mult,
    risk_reward_ratio=rr_ratio,
    top_n=top_n,
)

if scan_universe.startswith("En likit"):
    universe_df = all_tickers_df.sort_values("last_volume_tl_ref", ascending=False).head(n_liquid)
else:
    universe_df = all_tickers_df

st.sidebar.caption(f"Taranacak hisse sayısı: **{len(universe_df)}** / {max_available}")

run_clicked = st.button("🔍 Taramayı Başlat", type="primary")

if "scan_df" not in st.session_state:
    st.session_state["scan_df"] = None
    st.session_state["scan_time"] = None

if run_clicked:
    symbols = universe_df["yf_symbol"].tolist()
    progress = st.progress(0.0, text="Günlük veriler indiriliyor...")
    daily_data = fetch_daily_history(symbols, period="6mo", progress_cb=lambda f: progress.progress(f * 0.5, text="Günlük veriler indiriliyor..."))
    progress.progress(0.5, text="Bugünkü gün içi veriler indiriliyor...")
    intraday_data = fetch_intraday_today(symbols, progress_cb=lambda f: progress.progress(0.5 + f * 0.5, text="Bugünkü gün içi veriler indiriliyor..."))
    progress.progress(1.0, text="Puanlanıyor...")

    result_df = run_scan(universe_df, daily_data, intraday_data, now, settings)
    st.session_state["scan_df"] = result_df
    st.session_state["scan_time"] = now
    progress.empty()

    st.caption(
        f"{len(daily_data)} hissenin günlük verisi, {len(intraday_data)} hissenin "
        f"gün içi verisi başarıyla alındı."
    )

result_df = st.session_state["scan_df"]

if result_df is not None:
    if result_df.empty:
        st.error("Kriterlere uyan hisse bulunamadı. Filtreleri gevşetmeyi deneyin.")
    else:
        st.success(f"En iyi {len(result_df)} aday (yüksekten düşüğe puanlanmış):")

        display_df = result_df.rename(columns={
            "symbol": "Hisse",
            "score": "Puan",
            "price": "Fiyat",
            "change_from_open_pct": "Açılıştan % Değişim",
            "rsi14": "RSI(14)",
            "relative_volume": "Göreli Hacim",
            "suggested_stop_loss": "Stop-Loss",
            "suggested_take_profit": "Take-Profit",
            "stop_loss_pct": "Stop-Loss %",
            "take_profit_pct": "Take-Profit %",
        })[[
            "Hisse", "Puan", "Fiyat", "Açılıştan % Değişim", "RSI(14)",
            "Göreli Hacim", "Stop-Loss", "Stop-Loss %", "Take-Profit", "Take-Profit %",
        ]]

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("### Detay")
        pick = st.selectbox("Detayını görmek istediğiniz hisse", result_df["symbol"].tolist())
        row = result_df[result_df["symbol"] == pick].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Güncel Fiyat", f"{row['price']:.2f} TL", f"{row['change_from_open_pct']:.2f}% (açılıştan)")
        c2.metric("Önerilen Stop-Loss", f"{row['suggested_stop_loss']:.2f} TL", f"{row['stop_loss_pct']:.2f}%")
        c3.metric("Önerilen Take-Profit", f"{row['suggested_take_profit']:.2f} TL", f"{row['take_profit_pct']:.2f}%")
        st.write("**Neden öne çıktı:**")
        for n in row["notes"]:
            st.write(f"- {n}")

        st.caption(
            "Stop-loss ve take-profit seviyeleri ATR (ortalama gerçek aralık) "
            "bazlı basit bir risk yönetimi önerisidir; kesin bir garanti değildir. "
            "MİDAS uygulamasında bu seviyeleri emir olarak siz giriyorsunuz."
        )
else:
    st.info("Ayarları seçip **'Taramayı Başlat'** butonuna basın.")

st.divider()
st.caption(
    "Veri kaynağı: Yahoo Finance (yfinance). Hisse listesi İş Yatırım verisinden "
    "türetilmiştir. Bu uygulama bağımsız, eğitim amaçlı bir araçtır; herhangi bir "
    "aracı kurum veya yatırım kuruluşu ile bağlantılı değildir."
)
