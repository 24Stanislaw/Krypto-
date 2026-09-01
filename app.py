import os
import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# KONFIGURACJA STRONY I MOCNIEJSZY KONTRAST
# ==========================================
st.set_page_config(page_title="Analiza Krypto MTF Pro", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-color: #ffffff;
        color: #0b0f19;
    }
    dataframe, th, td {
        border-color: #d1d5db !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

HASLO = st.secrets.get("PASSWORD", "Krypto2026!")

def check_password():
    def password_entered():
        if st.session_state.get("password_input") == HASLO:
            st.session_state["password_correct"] = True
            if "password_input" in st.session_state:
                del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Dostęp Zastrzeżony")
        st.text_input(
            "Podaj hasło dostępu:",
            type="password",
            on_change=password_entered,
            key="password_input",
        )
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Dostęp Zastrzeżony")
        st.text_input(
            "Podaj hasło dostępu:",
            type="password",
            on_change=password_entered,
            key="password_input",
        )
        st.error("⛔ Niepoprawne hasło! Spróbuj ponownie.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# PANEL BOCZNY (ZARZĄDZANIE I FILTRY ALGORYTMU)
# ==========================================
with st.sidebar:
    st.subheader("⚙️ Narzędzia i Zarządzanie")
    HISTORY_FILE = "signals_history.csv"
    
    if st.button("🗑️ Resetuj historię i zacznij od nowa", type="secondary"):
        if os.path.exists(HISTORY_FILE):
            try:
                os.remove(HISTORY_FILE)
            except Exception:
                pass
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Wyczyszczono historię i stan aplikacji!")
        st.rerun()
    
    st.divider()
    
    st.subheader("🎛️ Parametry Algorytmu (Smart Score)")
    st.caption("Dostosuj restrykcyjność sygnałów zakupowych")
    
    min_smart_score = st.slider(
        "Minimalny Smart Score (%)", min_value=0.0, max_value=100.0, value=65.0, step=1.0,
        help="Im wyższy wynik, tym silniejszy trend i lepsze parametry wolumenu."
    )
    max_rsi_4h = st.slider(
        "Maksymalny RSI 4H", min_value=10.0, max_value=90.0, value=60.0, step=1.0,
        help="Odfiltruj tokeny, które są już lokalnie przegrzane/wykupione."
    )
    wymagaj_akumulacji = st.checkbox(
        "Wymagaj Akumulacji (Wygładzony OBV > EMA10)", value=True,
        help="Odrzuca tokeny, w których linia OBV jest poniżej swojej 10-okresowej EMA."
    )

# ==========================================
# LISTA TOKENÓW SPOT (COINBASE / GECKO)
# ==========================================
TOKENS = [
    {"symbol": "ONDO", "coinbase": "ONDO-USD", "gecko_id": "ondo-finance"},
    {"symbol": "INJ", "coinbase": "INJ-USD", "gecko_id": "injective-protocol"},
    {"symbol": "LINK", "coinbase": "LINK-USD", "gecko_id": "chainlink"},
    {"symbol": "RENDER", "coinbase": "RENDER-USD", "gecko_id": "render-token"},
    {"symbol": "FET", "coinbase": "FET-USD", "gecko_id": "artificial-superintelligence-alliance"},
    {"symbol": "BTC", "coinbase": "BTC-USD", "gecko_id": "bitcoin"},
    {"symbol": "ETH", "coinbase": "ETH-USD", "gecko_id": "ethereum"},
    {"symbol": "ENA", "coinbase": "ENA-USD", "gecko_id": "ethena"},
    {"symbol": "PENDLE", "coinbase": "PENDLE-USD", "gecko_id": "pendle"},
    {"symbol": "NEAR", "coinbase": "NEAR-USD", "gecko_id": "near"},
    {"symbol": "PLUME", "coinbase": "PLUME-USD", "gecko_id": "plume"},
    {"symbol": "JUP", "coinbase": None, "gecko_id": "jupiter-exchange-solana"},
    {"symbol": "UNI", "coinbase": "UNI-USD", "gecko_id": "uniswap"},
    {"symbol": "SEI", "coinbase": "SEI-USD", "gecko_id": "sei-network"},
    {"symbol": "SOL", "coinbase": "SOL-USD", "gecko_id": "solana"},
]

def fmt(val):
    if pd.isna(val) or val is None: return "-"
    if isinstance(val, (int, float)):
        if abs(val) < 0.0001: return f"{val:.6f}"
        elif abs(val) < 1.0: return round(val, 4)
        else: return round(val, 2)
    return val

# ==========================================
# FUNKCJE POBIERANIA DANYCH I WSKAŹNIKÓW
# ==========================================
def get_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=4).json()
        return int(res["data"][0]["value"]), res["data"][0]["value_classification"]
    except Exception:
        return 50, "Neutral"

def get_global_market_data():
    try:
        res = requests.get(
            "https://api.coingecko.com/api/v3/global",
            headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4
        ).json()
        return round(res["data"]["market_cap_percentage"]["btc"], 1)
    except Exception:
        return 55.0

def calculate_altcoin_season_index():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 100, "page": 1, "sparkline": "false", "price_change_percentage": "200d"}
        res = requests.get(url, params=params, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=6)
        if res.status_code != 200: return 45
        coins = res.json()
        exclude_symbols = ["usdt", "usdc", "fdusd", "dai", "usde", "wbtc", "steth", "weth"]
        btc_change = 0.0
        for coin in coins:
            if coin["symbol"].lower() == "btc":
                btc_change = coin.get("price_change_percentage_200d_in_currency", 0.0)
                break
        better_than_btc, valid_count = 0, 0
        for coin in coins:
            symbol = coin["symbol"].lower()
            if symbol == "btc" or symbol in exclude_symbols: continue
            change = coin.get("price_change_percentage_200d_in_currency")
            if change is not None:
                valid_count += 1
                if change > btc_change: better_than_btc += 1
            if valid_count >= 50: break
        if valid_count > 0: return int((better_than_btc / valid_count) * 100)
        return 45
    except Exception:
        return 45

def fetch_from_coinbase(symbol_pair, granularity=3600):
    url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?granularity={granularity}"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=["timestamp", "low", "high", "open", "close", "volume"])
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
    return df.sort_values("dt").reset_index(drop=True)

def fetch_from_coingecko(gecko_id):
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/ohlc?vs_currency=usd&days=14"
    res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=5)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=["timestamp", "open", "high", "low", "close"])
    df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["volume"] = 0.0
    return df.sort_values("dt").reset_index(drop=True)

def get_simple_coingecko_price(gecko_id):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={gecko_id}&vs_currencies=usd,usd_24h_change"
        res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4).json()
        if gecko_id in res:
            price = float(res[gecko_id].get("usd", 0))
            change = float(res[gecko_id].get("usd_24h_change", 0))
            if price > 0: return price, change
    except Exception:
        pass
    return 1.0, 0.0

def get_candles_1h(token_info):
    if token_info.get("coinbase"):
        try:
            df = fetch_from_coinbase(token_info["coinbase"], granularity=3600)
            if not df.empty and len(df) >= 20: return df
        except Exception: pass
    try: return fetch_from_coingecko(token_info["gecko_id"])
    except Exception: return pd.DataFrame()

def get_candles_1d(token_info):
    if token_info.get("coinbase"):
        try:
            df = fetch_from_coinbase(token_info["coinbase"], granularity=86400)
            if not df.empty and len(df) >= 14: return df
        except Exception: pass
    return pd.DataFrame()

def resample_ohlc(df_1h, rule):
    df = df_1h.copy()
    df.set_index("dt", inplace=True)
    return df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()

def calc_rsi(series, period=14):
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    val = 100 - (100 / (1 + (gain.iloc[-1] / (loss.iloc[-1] + 1e-9))))
    return float(val) if not pd.isna(val) else 50.0

def calc_macd(series, span1=12, span2=26, signal=9):
    exp1 = series.ewm(span=span1, adjust=False).mean()
    exp2 = series.ewm(span=span2, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float((macd_line - signal_line).iloc[-1])

# [POPRAWKA 1] ROLLING 7-DAY VWAP (168 GODZIN) Z WSTĘGĄ +2 STD
def calc_vwap_rolling_7d(df_1h):
    if df_1h.empty or "volume" not in df_1h.columns or df_1h["volume"].sum() == 0:
        p = float(df_1h["close"].iloc[-1]) if not df_1h.empty else 1.0
        return p, p * 1.05, False
    
    df_7d = df_1h.tail(168).copy()
    typical_price = (df_7d["high"] + df_7d["low"] + df_7d["close"]) / 3
    cum_vol = df_7d["volume"].cumsum()
    vwap = (typical_price * df_7d["volume"]).cumsum() / (cum_vol + 1e-9)
    
    variance = ((typical_price - vwap) ** 2 * df_7d["volume"]).cumsum() / (cum_vol + 1e-9)
    std_dev = np.sqrt(variance)
    
    vwap_val = float(vwap.iloc[-1])
    upper_band_2std = vwap_val + (2.0 * float(std_dev.iloc[-1]))
    curr_price = float(df_7d["close"].iloc[-1])
    
    is_overextended = curr_price >= upper_band_2std
    return vwap_val, upper_band_2std, is_overextended

# [POPRAWKA 2] WYGŁADZONY OBV Z PROCENTOWYM ODCHYLANIEM OD EMA10
def calc_smoothed_obv(df_4h):
    if "volume" not in df_4h.columns or df_4h["volume"].sum() == 0:
        return "Neutralny (0.0%)", 0.0, False
    direction = np.sign(df_4h["close"].diff()).fillna(0)
    obv = (direction * df_4h["volume"]).cumsum()
    obv_ema10 = obv.ewm(span=10, adjust=False).mean()
    
    curr_obv = float(obv.iloc[-1])
    curr_ema = float(obv_ema10.iloc[-1])
    
    diff_pct = ((curr_obv - curr_ema) / (abs(curr_ema) + 1e-9)) * 100
    is_accumulating = diff_pct > 0
    
    if is_accumulating:
        status = f"🟢 Akumulacja (+{diff_pct:.2f}%)"
    else:
        status = f"🔴 Dystrybucja ({diff_pct:.2f}%)"
    return status, round(diff_pct, 2), is_accumulating

def calc_rvol(df, period=20):
    if "volume" not in df.columns or df["volume"].sum() == 0 or len(df) < period: return 1.0
    vol_sma = df["volume"].rolling(window=period).mean()
    avg_vol = float(vol_sma.iloc[-1])
    if avg_vol <= 0: return 1.0
    return round(float(df["volume"].iloc[-1]) / avg_vol, 2)

@st.cache_data(ttl=300)
def fetch_technical_analysis():
    data = []
    loaded_count = 0
    fng_val, fng_class = get_fear_and_greed()
    btc_dom = get_global_market_data()
    alt_season = calculate_altcoin_season_index()

    btc_info = next((item for item in TOKENS if item["symbol"] == "BTC"), TOKENS[5])
    btc_df_1h = get_candles_1h(btc_info)
    btc_closes_1h = btc_df_1h["close"] if not btc_df_1h.empty else pd.Series([60000.0]*72)

    for item in TOKENS:
        symbol = item["symbol"]
        gecko_id = item["gecko_id"]
        try:
            df_1h = get_candles_1h(item)
            if df_1h.empty or len(df_1h) < 5: raise ValueError("Brak świec")
            
            df_4h = resample_ohlc(df_1h, "4h")
            df_1d = resample_ohlc(df_1h, "1d") if len(df_1h) >= 24 else get_candles_1d(item)
            df_3d = resample_ohlc(df_1h, "3d") if len(df_1h) >= 72 else df_1d

            price = float(df_1h["close"].iloc[-1])
            prev_price_24h = float(df_1h["close"].iloc[-24] if len(df_1h) >= 24 else df_1h["close"].iloc[0])
            change_24h = ((price - prev_price_24h) / prev_price_24h) * 100

            # [POPRAWKA 3] SIŁA WZGLĘDNA VS BTC W OKNIE 72H (3 DNI)
            if symbol == "BTC":
                rs_vs_btc_pct = 0.0
                rs_vs_btc_status = "➡️ BAZA (Bitcoin)"
            else:
                min_len = min(len(df_1h["close"]), len(btc_closes_1h))
                token_closes = df_1h["close"].iloc[-min_len:].reset_index(drop=True)
                btc_closes = btc_closes_1h.iloc[-min_len:].reset_index(drop=True)
                ratio = token_closes / (btc_closes + 1e-9)
                ratio_now = ratio.iloc[-1]
                lookback = 72 if len(ratio) >= 72 else len(ratio) - 1
                ratio_72h = ratio.iloc[-lookback] if lookback > 0 else ratio.iloc[0]
                rs_vs_btc_pct = float(((ratio_now - ratio_72h) / (ratio_72h + 1e-9)) * 100)
                rs_vs_btc_status = f"🟢 OUTPERFORM (+{rs_vs_btc_pct:.2f}%)" if rs_vs_btc_pct > 0 else f"🔴 UNDERPERFORM ({rs_vs_btc_pct:.2f}%)"

            log_returns = np.log(df_1h["close"] / df_1h["close"].shift(1)).dropna()
            
            raw_vol_1h = float(log_returns.std()) if len(log_returns) > 5 else 0.008
            vol_1h = float(np.clip(raw_vol_1h, 0.003, 0.008))
            
            raw_drift = float(log_returns.mean()) if len(log_returns) > 5 else 0.0
            drift_1h = float(np.clip(raw_drift, -0.0003, 0.0003))

            # [POPRAWKA 4] TRIADA RSI: 4H / 1D / 3D
            rsi_4h = calc_rsi(df_4h["close"]) if len(df_4h) >= 14 else 50.0
            rsi_1d = calc_rsi(df_1d["close"]) if len(df_1d) >= 14 else 50.0
            rsi_3d = calc_rsi(df_3d["close"]) if len(df_3d) >= 14 else rsi_1d

            _, _, macd_hist = calc_macd(df_4h["close"]) if len(df_4h) >= 26 else (0.0, 0.0, 0.0)
            
            # ROLLING 7D VWAP
            vwap_val, vwap_upper_2std, is_vwap_overextended = calc_vwap_rolling_7d(df_1h)
            
            # OBV ODCHYLENIE PROCENTOWE
            obv_status, obv_diff_pct, is_obv_accumulating = calc_smoothed_obv(df_4h)
            rvol_val = calc_rvol(df_4h)

            tr = pd.concat([df_4h["high"] - df_4h["low"], (df_4h["high"] - df_4h["close"].shift()).abs(), (df_4h["low"] - df_4h["close"].shift()).abs()], axis=1).max(axis=1) if len(df_4h) > 1 else pd.Series([price * 0.02])
            atr = float(tr.rolling(min(14, len(df_4h))).mean().iloc[-1]) if len(tr) > 0 else price * 0.02
            
            ema200_4h = float(df_4h["close"].ewm(span=min(200, len(df_4h)), adjust=False).mean().iloc[-1]) if len(df_4h) > 0 else price
            ema50_1d = float(df_1d["close"].ewm(span=min(50, len(df_1d)), adjust=False).mean().iloc[-1]) if len(df_1d) >= 50 else (price * 0.98)

            sl = price - (2.5 * atr)
            support = float(df_4h["low"].min()) if len(df_4h) > 0 else price * 0.95
            resistance = float(df_4h["high"].max()) if len(df_4h) > 0 else price * 1.05

            risk = price - sl
            reward = resistance - price
            rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1

            if price > ema200_4h and price > ema50_1d:
                regime = "🟢 Silny Trend MTF (4H+1D)"
                mtf_confluence = True
            elif price > ema200_4h and price <= ema50_1d:
                regime = "🟡 Wzrost 4H (Opór EMA50 1D)"
                mtf_confluence = False
            elif price <= ema200_4h and price > ema50_1d:
                regime = "🟡 Odbicie 1D (Pod EMA200 4H)"
                mtf_confluence = False
            else:
                regime = "🔴 Strukturalny Trend Spadkowy"
                mtf_confluence = False

            data.append({
                "Lp.": loaded_count + 1,
                "Token": symbol, "Cena ($)": fmt(price), "24h (%)": round(change_24h, 2), 
                "Reżim Rynkowy": regime,
                "EMA 200 (4H)": fmt(ema200_4h), "EMA 50 (1D)": fmt(ema50_1d),
                "Siła vs BTC (72h)": rs_vs_btc_status,
                "Wsparcie": fmt(support), "Opór": fmt(resistance), "SL (ATR)": fmt(sl), "R:R": f"1:{rr_val}",
                
                # Zmienne do Zakładki 2
                "RSI 4H": round(rsi_4h, 1), "RSI 1D": round(rsi_1d, 1), "RSI 3D": round(rsi_3d, 1),
                "RVOL (4H)": f"{rvol_val}x", "VWAP 7D": fmt(vwap_val), "VWAP +2Std": fmt(vwap_upper_2std),
                "OBV Status": obv_status, "OBV Odchylenie (%)": obv_diff_pct,
                "MACD Hist (4H)": fmt(macd_hist),
                
                # Dane Surowe (Pola Pomocnicze)
                "Price_Raw": float(price), "EMA200_Raw": float(ema200_4h), "EMA50_1D_Raw": float(ema50_1d),
                "Support_Raw": float(support), "Resistance_Raw": float(resistance), 
                "RSI_4H_Raw": float(rsi_4h), "RSI_1D_Raw": float(rsi_1d), "RSI_3D_Raw": float(rsi_3d), 
                "RVOL_Raw": float(rvol_val), "VWAP_Raw": float(vwap_val), "VWAP_Upper_Raw": float(vwap_upper_2std),
                "Is_VWAP_Overextended": is_vwap_overextended,
                "OBV_Raw": obv_status, "OBV_Diff_Pct": obv_diff_pct, "Is_OBV_Accumulating": is_obv_accumulating,
                "Regime_Raw": regime, "MTF_Confluence": mtf_confluence,
                "Vol_Raw": vol_1h, "Drift_Raw": drift_1h, "RS_BTC_Pct": rs_vs_btc_pct,
                "ATR_Raw": float(atr)
            })
            loaded_count += 1
        except Exception:
            p, chg = get_simple_coingecko_price(gecko_id)
            data.append({
                "Lp.": loaded_count + 1,
                "Token": symbol, "Cena ($)": fmt(p), "24h (%)": round(chg, 2),
                "Reżim Rynkowy": "Konsolidacja", "EMA 200 (4H)": fmt(p), "EMA 50 (1D)": fmt(p),
                "Siła vs BTC (72h)": "➡️ NEUTRALNY", "Wsparcie": fmt(p * 0.95), "Opór": fmt(p * 1.05),
                "SL (ATR)": fmt(p * 0.95), "R:R": "1:1.5",
                "RSI 4H": 50.0, "RSI 1D": 50.0, "RSI 3D": 50.0, "RVOL (4H)": "1.0x",
                "VWAP 7D": fmt(p), "VWAP +2Std": fmt(p * 1.05), "OBV Status": "Neutralny (0.0%)",
                "OBV Odchylenie (%)": 0.0, "MACD Hist (4H)": "0.0",
                "Price_Raw": p, "EMA200_Raw": p, "EMA50_1D_Raw": p, "Support_Raw": p * 0.95,
                "Resistance_Raw": p * 1.05, "RSI_4H_Raw": 50.0, "RSI_1D_Raw": 50.0, "RSI_3D_Raw": 50.0,
                "RVOL_Raw": 1.0, "VWAP_Raw": p, "VWAP_Upper_Raw": p * 1.05, "Is_VWAP_Overextended": False,
                "OBV_Raw": "Neutralny (0.0%)", "OBV_Diff_Pct": 0.0, "Is_OBV_Accumulating": False,
                "Regime_Raw": "Konsolidacja", "MTF_Confluence": False, "Vol_Raw": 0.006, "Drift_Raw": 0.0,
                "RS_BTC_Pct": 0.0, "ATR_Raw": p * 0.02
            })
            loaded_count += 1

    return pd.DataFrame(data), fng_val, fng_class, btc_dom, alt_season, loaded_count, len(TOKENS)

# ==========================================
# SCORING I PREDYKCJE (STABILNE MONTE CARLO 10 DNI)
# ==========================================
def run_predictions(df_ta, btc_dom, min_score_filter, max_rsi_filter, req_accumulation):
    if df_ta.empty: return pd.DataFrame(), {}
    rng = np.random.default_rng(seed=int(pd.Timestamp.now().strftime("%Y%m%d%H")))
    
    monte_carlo_paths = {}

    def analyze_row(row):
        symbol = row["Token"]
        price = float(row["Price_Raw"])
        vol_1h = float(row.get("Vol_Raw", 0.006))
        drift_1h = float(row.get("Drift_Raw", 0.0))
        regime = row["Regime_Raw"]
        mtf_confluence = bool(row.get("MTF_Confluence", False))
        rsi_4h = float(row["RSI_4H_Raw"])
        rsi_1d = float(row["RSI_1D_Raw"])
        rsi_3d = float(row["RSI_3D_Raw"])
        is_obv_acc = bool(row.get("Is_OBV_Accumulating", False))
        obv_diff_pct = float(row.get("OBV_Diff_Pct", 0.0))
        rvol = float(row.get("RVOL_Raw", 1.0))
        resistance = float(row.get("Resistance_Raw", price * 1.05))
        is_vwap_overextended = bool(row.get("Is_VWAP_Overextended", False))
        rs_btc_pct = float(row.get("RS_BTC_Pct", 0.0))

        score = 50.0 
        
        # 1. Konfluencja MTF (4H + 1D)
        if mtf_confluence: score += 25.0
        elif "Wzrost 4H" in regime: score += 10.0
        elif "Spadkowy" in regime: score -= 20.0

        # 2. Siła Względna vs BTC (Okienko 72h)
        if rs_btc_pct > 2.0: score += 12.0
        elif rs_btc_pct < -2.0: score -= 10.0

        # 3. RVOL i Odchylenie OBV (%)
        score += (rvol - 1.0) * 12.0  
        if obv_diff_pct > 0:
            score += min(15.0, obv_diff_pct * 1.5)
        else:
            score += max(-15.0, obv_diff_pct * 1.5)

        # 4. Triada RSI (4H / 1D / 3D)
        if rsi_4h < 45: score += (45 - rsi_4h) * 0.3
        elif rsi_4h > 65: score -= (rsi_4h - 65) * 0.5

        if rsi_1d < 45: score += (45 - rsi_1d) * 0.2
        elif rsi_1d > 70: score -= (rsi_1d - 70) * 0.4

        if rsi_3d > 75: score -= 10.0

        score = max(0.0, min(100.0, score))

        macro_daily_drift = (score - 50.0) / 100.0 * 0.008
        macro_hourly_drift = macro_daily_drift / 24.0
        target_hourly_drift = (0.8 * macro_hourly_drift) + (0.2 * drift_1h)

        hours = np.arange(1, 241)
        dampening = np.power(hours, -0.12)
        step_vols = vol_1h * dampening

        shocks = rng.normal(loc=0, scale=1.0, size=(5000, 240))
        step_drifts = target_hourly_drift - (0.5 * (step_vols ** 2))

        hourly_returns = step_drifts + (shocks * step_vols)
        cum_returns = np.exp(np.cumsum(hourly_returns, axis=1))
        final_prices_paths = price * cum_returns
        
        monte_carlo_paths[symbol] = final_prices_paths
        
        p_24h = float(np.median(final_prices_paths[:, 23]))
        p_3d = float(np.median(final_prices_paths[:, 71]))
        p_10d = float(np.median(final_prices_paths[:, 239]))

        ci_lower_10d = float(np.percentile(final_prices_paths[:, 239], 2.5))
        ci_upper_10d = float(np.percentile(final_prices_paths[:, 239], 97.5))
        prob_up_10d = float(np.mean(final_prices_paths[:, 239] > price) * 100)

        is_altcoin = symbol not in ["BTC", "ETH"]
        macro_headwind = btc_dom > 59.0 and is_altcoin

        is_overextended = (rsi_4h > 65.0) or (price >= resistance * 0.99) or is_vwap_overextended

        if macro_headwind: 
            signal = "⏳ ODRZUCONY (Silna dominacja BTC)"
        elif is_vwap_overextended:
            signal = "❌ ODRZUCONY (Przegrzany przy Wstędze VWAP 7D +2 Std)"
        elif is_overextended: 
            signal = "❌ ODRZUCONY (Przegrzany – Unikamy szczytu)"
        elif score >= min_score_filter and rsi_4h <= max_rsi_filter and mtf_confluence:
            if req_accumulation and not is_obv_acc: 
                signal = "🟡 NEUTRALNY (Brak akumulacji OBV > EMA10)"
            else: 
                signal = "🟢 WYSOKI EDGE (Solidna Okazja Zakupowa)"
        elif score >= 55.0: 
            signal = "🟡 NEUTRALNY (Wymaga obserwacji)"
        else: 
            signal = "❌ ODRZUCONY (Słaba struktura MTF/OBV)"

        return pd.Series([
            f"${fmt(p_24h)}", f"${fmt(p_3d)}", f"${fmt(p_10d)}",
            f"${fmt(ci_lower_10d)} - ${fmt(ci_upper_10d)}",
            f"{round(prob_up_10d, 1)}%", signal, score,
            p_10d
        ])

    df_ml = df_ta.copy()
    df_ml[["Prognoza 24h", "Prognoza 3D", "Prognoza 10D", "Zasięg MC 10D (95%)", "Szansa Wzrostu (10D)", "Ocena Przewagi (Edge)", "Smart Score (%)", "Prognoza_10D_Raw"]] = df_ml.apply(analyze_row, axis=1)
    df_ml["Smart Score (%)"] = df_ml["Smart Score (%)"].round(2)
    return df_ml, monte_carlo_paths

# ==========================================
# WYKRES PLOTLY
# ==========================================
def plot_price_forecast(symbol, current_price, price_paths):
    median_path = np.median(price_paths, axis=0)
    upper_95 = np.percentile(price_paths, 97.5, axis=0)
    lower_95 = np.percentile(price_paths, 2.5, axis=0)
    hours = np.arange(1, 241)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=np.concatenate([hours, hours[::-1]]),
        y=np.concatenate([upper_95, lower_95[::-1]]),
        fill='toself', fillcolor='rgba(59, 130, 246, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Przedział Ufności 95%', hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=hours, y=median_path, mode='lines',
        line=dict(color='#2563eb', width=3), name='Prognoza (Mediana MC)'
    ))
    fig.add_hline(y=current_price, line_dash="dash", line_color="gray", annotation_text="Obecna cena")
    fig.add_hline(y=current_price * 1.06, line_dash="dot", line_color="green", annotation_text="Cel TP (+6%)")
    fig.update_layout(
        title=f"📈 Prognoza Trajektorii Ceny 10D (Monte Carlo): {symbol}",
        xaxis_title="Godziny od teraz", yaxis_title="Cena ($)",
        template="plotly_white", height=420, margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

# ==========================================
# SYSTEM AUTO-ŚLEDZENIA ZAGRAŃ (ZAPIS I ROZLICZANIE)
# ==========================================
def auto_zapisz_sygnaly(df_ml, df_ta):
    if df_ml.empty: return
    kolumny = ["Data Wejścia", "Token", "Typ Sygnału", "Cena Wejścia ($)", "Cel TP (6%) ($)", "SL ($)", "Ekstremum ($)", "Data Wyjścia", "Status", "Zysk (%)"]
    
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
        except Exception:
            df_hist = pd.DataFrame(columns=kolumny)
    else:
        df_hist = pd.DataFrame(columns=kolumny)

    aktywne_tokeny = df_hist[df_hist["Status"].str.contains("W toku", na=False)]["Token"].tolist() if not df_hist.empty else []

    nowe_wiersze = []
    okazje = df_ml[df_ml["Ocena Przewagi (Edge)"].str.contains("WYSOKI EDGE", na=False)]
    
    for _, row in okazje.iterrows():
        token = row["Token"]
        if token not in aktywne_tokeny:
            cena_we = float(df_ta[df_ta["Token"] == token].iloc[0]["Price_Raw"])
            atr = float(df_ta[df_ta["Token"] == token].iloc[0]["ATR_Raw"])
            
            cel_tp = cena_we * 1.06
            sl = cena_we - (2.5 * atr)

            nowe_wiersze.append({
                "Data Wejścia": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "Token": token,
                "Typ Sygnału": "Auto (Wysoki Edge)",
                "Cena Wejścia ($)": round(cena_we, 5),
                "Cel TP (6%) ($)": round(cel_tp, 5),
                "SL ($)": round(sl, 5),
                "Ekstremum ($)": round(cena_we, 5),
                "Data Wyjścia": "-",
                "Status": "🔄 W toku",
                "Zysk (%)": 0.0
            })

    if nowe_wiersze:
        df_hist = pd.concat([df_hist, pd.DataFrame(nowe_wiersze)], ignore_index=True)
        df_hist.to_csv(HISTORY_FILE, index=False)

def aktualizuj_i_rozlicz_pozycje(df_ta):
    if not os.path.exists(HISTORY_FILE): return
    try: 
        df_hist = pd.read_csv(HISTORY_FILE)
    except Exception: 
        return
    if df_hist.empty: return

    now_dt = pd.Timestamp.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")
    price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))

    for idx, row in df_hist.iterrows():
        if "W toku" not in str(row["Status"]): continue

        token = row["Token"]
        if token not in price_map: continue

        curr_price = float(price_map[token])
        entry = float(row["Cena Wejścia ($)"])
        
        cel_tp = float(row.get("Cel TP (6%) ($)", entry * 1.06))
        sl = float(row["SL ($)"])

        prev_extr = float(row["Ekstremum ($)"]) if pd.notna(row["Ekstremum ($)"]) else entry
        new_extr = max(prev_extr, curr_price)
        df_hist.at[idx, "Ekstremum ($)"] = round(new_extr, 5)

        curr_gain_pct = ((curr_price - entry) / entry) * 100
        df_hist.at[idx, "Zysk (%)"] = round(curr_gain_pct, 2)

        data_we = pd.to_datetime(row["Data Wejścia"])
        dni_minely = (now_dt - data_we).days

        status = row["Status"]
        data_wy = row["Data Wyjścia"]

        if curr_price >= cel_tp:
            status = "✅ SUKCES (TP +6%)"
            data_wy = now_str
        elif curr_price <= sl:
            status = "❌ PORAŻKA (SL)"
            data_wy = now_str
        elif dni_minely >= 10:
            if curr_price > entry:
                status = "⚠️ ZAMKNIĘTO (Upływ 10d / Zysk)"
            else:
                status = "⚠️ ZAMKNIĘTO (Upływ 10d / Strata)"
            data_wy = now_str
        else:
            status = f"🔄 W toku ({dni_minely}/10d)"

        df_hist.at[idx, "Status"] = status
        df_hist.at[idx, "Data Wyjścia"] = data_wy

    df_hist.to_csv(HISTORY_FILE, index=False)

# ==========================================
# OBSZERNY RAPORT AI Z PROGNOZĄ W PODSUMOWANIU
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None, btc_dom=55.0):
    symbol = row_ta.get("Token", "UNKNOWN")
    price_raw = float(row_ta.get("Price_Raw", 0))
    ema200_raw = float(row_ta.get("EMA200_Raw", 0))
    ema50_1d_raw = float(row_ta.get("EMA50_1D_Raw", 0))
    regime = row_ta.get("Reżim Rynkowy", "Neutralny")
    
    rsi_4h = float(row_ta.get("RSI_4H_Raw", 50))
    rsi_1d = float(row_ta.get("RSI_1D_Raw", 50))
    rsi_3d = float(row_ta.get("RSI_3D_Raw", 50))
    
    rvol_str = str(row_ta.get("RVOL (4H)", "1.0x"))
    vwap_val = float(row_ta.get("VWAP_Raw", price_raw))
    vwap_upper = float(row_ta.get("VWAP_Upper_Raw", price_raw * 1.05))
    is_vwap_overextended = bool(row_ta.get("Is_VWAP_Overextended", False))
    
    obv_status = row_ta.get("OBV Status", "Neutralny")
    obv_diff_pct = float(row_ta.get("OBV_Diff_Pct", 0.0))
    rs_btc_status = str(row_ta.get("Siła vs BTC (72h)", "Neutralny"))
    macd_hist = float(row_ta.get("MACD Hist (4H)", 0.0))
    
    support_str = row_ta.get("Wsparcie", "0.00")
    resistance_str = row_ta.get("Opór", "0.00")
    sl_str = row_ta.get("SL (ATR)", "0.00")
    
    edge_status = row_ml.get("Ocena Przewagi (Edge)", "-") if row_ml is not None else "-"
    smart_score = f"{float(row_ml.get('Smart Score (%)', 50.0)):.2f}" if row_ml is not None else "50.00"
    prognoza_24h = row_ml.get("Prognoza 24h", "-") if row_ml is not None else "-"
    prognoza_3d = row_ml.get("Prognoza 3D", "-") if row_ml is not None else "-"
    prognoza_10d = row_ml.get("Prognoza 10D", "-") if row_ml is not None else "-"
    zasieg_mc_10d = row_ml.get("Zasięg MC 10D (95%)", "-") if row_ml is not None else "-"
    prob_up_10d = row_ml.get("Szansa Wzrostu (10D)", "-") if row_ml is not None else "-"
    
    target_tp1 = price_raw * 1.06

    # Opisy sekcji
    pa_desc = f"Aktywo znajduje się w reżimie **{regime}**. Aktualny kurs wynosi `{fmt(price_raw)} $`. Średnia EMA200 4H przebiega na poziomie `{fmt(ema200_raw)} $`, natomiast wyższa średnia EMA50 1D znajduje się przy `{fmt(ema50_1d_raw)} $`. "
    if "Silny Trend" in regime:
        pa_desc += "Mamy do czynienia z pełną konfluencją trendu na dwóch interwałach, co świadczy o strukturalnej dominacji strony popytowej."
    elif "Wzrost 4H" in regime:
        pa_desc += "Lokalny trend wzrostowy na 4H natrafia na opór wyższego rzędu przy średniej EMA50 1D. Wymagana ostrożność."
    else:
        pa_desc += "Cena pozostaje poniżej kluczowych średnich, co zwiększa ryzyko kontynuacji spadków lub trwałej konsolidacji."

    btc_dom_desc = f"Dominacja Bitcoina na poziomie `{btc_dom}%` wpływa na całe otoczenie rynkowe. "
    btc_dom_desc += f"Wskaźnik Siły Względnej dla {symbol} w relacji do BTC (okienko 72h) wynosi: `{rs_btc_status}`. "
    if obv_diff_pct > 0:
        btc_dom_desc += f"Dodatnie odchylenie OBV od EMA10 wynoszące `{obv_diff_pct:.2f}%` potwerdza realny dopływ kapitału."
    else:
        btc_dom_desc += f"Ujemne odchylenie OBV (`{obv_diff_pct:.2f}%`) ostrzega przed brakiem akumulacji."

    rvol_float = float(rvol_str.replace("x", "")) if "x" in rvol_str else 1.0
    rvol_desc = f"**RVOL (Względny Wolumen 4H):** `{rvol_str}`. " + ("Obserwujemy anomalię wolumenową – aktywność Smart Money." if rvol_float >= 1.5 else "Obroty pozostają na standardowym poziomie.")

    vwap_desc = f"**VWAP 7-Dniowy (Rolling):** Zlokalizowany przy `{fmt(vwap_val)} $`, z górną wstęgą +2 Std przy `{fmt(vwap_upper)} $`. "
    if is_vwap_overextended:
        vwap_desc += "⚠️ **Ryzyko Przegrzania:** Cena osiągnęła górną wstęgę +2 Std, co statystycznie zwiększa prawdopodobieństwo korekty do średniej (Mean Reversion)."
    else:
        vwap_desc += "Cena utrzymuje się w bezpiecznym przedziale względem tygodniowego VWAP."

    rsi_desc = f"**Triada RSI:** 4H (`{round(rsi_4h, 1)}`), 1D (`{round(rsi_1d, 1)}`), 3D (`{round(rsi_3d, 1)}`). "
    if rsi_4h < 40:
        rsi_desc += "Interwał 4H wykazuje lokalne wyprzedanie (potencjalne miejsce odbicia)."
    elif rsi_4h > 65:
        rsi_desc += "Interwał 4H sygnalizuje silne wykupienie."

    if "WYSOKI EDGE" in edge_status: 
        final_reco = "🟢 **REKOMENDACJA:** Sygnał zakupu wysokiej jakości. Struktura MTF, odchylenie OBV oraz symulacja MC wskazują na wyraźną przewagę statystyczną."
    elif "NEUTRALNY" in edge_status: 
        final_reco = "🟡 **REKOMENDACJA:** Pozycja neutralna / Obserwacja. Brak pełnej konfluencji średnich lub niedostateczna akumulacja na OBV."
    else: 
        final_reco = "❌ **REKOMENDACJA:** Sygnał odrzucony. Ryzyko wynikające z braku trendu, przegrzania na VWAP lub słabości względnej do BTC."

    return f"""
### 🎯 EKSPERCKI RAPORT ANALITYCZNY MTF PRO: {symbol}
**Werdykt Algorytmu:** `{edge_status}` | **Smart Score:** **{smart_score}%** | **Aktualna cena:** `{fmt(price_raw)} $`

---
#### 1. 🧠 Analiza Strukturalna i Makroekonomiczna
* **Struktura MTF (4H EMA200 & 1D EMA50):** {pa_desc}
* **Dominacja BTC & Siła Względna (72h):** {btc_dom_desc}

#### 2. 📊 Wolumen, 7D VWAP i Smart Money
* {rvol_desc}
* {vwap_desc}
* **Wygładzony OBV Status:** `{obv_status}`.

#### 3. 📈 Momentum i Oscylatory
* {rsi_desc}
* **MACD Histogram 4H:** `{fmt(macd_hist)}`.

#### 4. 🎲 Symulacja Probabilistyczna Monte Carlo (10 Dni)
* **Wizja 24-godzinna (Mediana):** `{prognoza_24h}`
* **Wizja 3-dniowa (Mediana):** `{prognoza_3d}`
* **Wizja 10-dniowa (Mediana):** `{prognoza_10d}`
* **Przedział Ufności 95% (10D):** `{zasieg_mc_10d}`
* **Prawdopodobieństwo wzrostu:** `{prob_up_10d}`

#### 5. 🛡️ Inżynieria Ryzyka i Taktyka
* **Wsparcie 4H:** `{support_str}` | **Opór 4H:** `{resistance_str}`
* **Stop Loss (2.5x ATR):** `{sl_str}`
* **Cel Taktyczny TP (+6%):** `{fmt(target_tp1)} $`

---
### 📝 PODSUMOWANIE ANALIZY I PROGNOZA KOŃCOWA
Model ocenia prawdopodobieństwo sukcesu pozycji na podstawie **Smart Score {smart_score}%** w warunkach **{regime}**.

* **Prognoza Krótkoterminowa (1-3 Dni):** Mediana skanera wskazuje poziom `{prognoza_3d}`. Ruch będzie determinowany przez utrzymanie wsparcia na poziomie `{support_str}`.
* **Prognoza Średnioterminowa (10 Dni):** Mediana symulacji wynosi `{prognoza_10d}` z dolną granicą skrajną `{zasieg_mc_10d.split('-')[0].strip()}` przy szansie powodzenia `{prob_up_10d}`.

{final_reco}
"""

# ==========================================
# INTERFEJS GŁÓWNY STREAMLIT (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane na żywo z API i przeliczam wskaźniki..."):
    df_ta, fng_val, fng_class, btc_dom, alt_season, loaded_c, total_c = fetch_technical_analysis()
    df_ml, mc_paths = run_predictions(df_ta, btc_dom, min_smart_score, max_rsi_4h, wymagaj_akumulacji)
    
    auto_zapisz_sygnaly(df_ml, df_ta)
    aktualizuj_i_rozlicz_pozycje(df_ta)

col_t, col_d1, col_d2, col_f = st.columns([2.0, 1, 1, 1])
col_t.title("📊 Analiza Krypto MTF Pro")
col_t.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Załadowano: {loaded_c}/{total_c}")
col_d1.metric("Dominacja BTC", f"{btc_dom}%")
col_d2.metric("Sezon Altcoinów", f"{alt_season}/100", "Sezon BTC" if alt_season < 50 else "Sezon Alt")
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

st.markdown("---")

st.markdown("### 🔥 Najlepsze Okazje Zakupowe")
if not df_ml.empty:
    okazje_df = df_ml[df_ml["Ocena Przewagi (Edge)"].str.contains("WYSOKI EDGE", na=False)]
    if not okazje_df.empty:
        cols_okazje = st.columns(min(len(okazje_df), 4))
        for i, (_, row) in enumerate(okazje_df.iterrows()):
            with cols_okazje[i % len(cols_okazje)]:
                score_val = float(row['Smart Score (%)'])
                st.success(f"**{row['Token']}**\n\nCena: `{row['Cena ($)']}`\nSmart Score: **{score_val:.2f}%**\nPrognoza 10D: **{row['Prognoza 10D']}**")
    else:
        st.info("Obecnie żaden token nie spełnia restrykcyjnych warunków algorytmu (odfiltrowano przegrzane aktywa oraz brak konfluencji MTF/OBV).")

st.markdown("---")

if st.button("🔄 Odśwież dane", type="primary"):
    st.cache_data.clear()
    st.rerun()

# RADYKALNE ROZDZIELENIE DANYCH W ZAKŁADKACH
df_tab1_view = df_ta[["Lp.", "Token", "Cena ($)", "24h (%)", "Reżim Rynkowy", "EMA 200 (4H)", "EMA 50 (1D)", "Siła vs BTC (72h)", "Wsparcie", "Opór", "SL (ATR)", "R:R"]].copy()

if not df_ml.empty:
    df_tab2_view = df_ml[["Lp.", "Token", "Cena ($)", "Smart Score (%)", "Ocena Przewagi (Edge)", "RSI 4H", "RSI 1D", "RSI 3D", "RVOL (4H)", "VWAP 7D", "VWAP +2Std", "OBV Odchylenie (%)", "Prognoza 10D", "Zasięg MC 10D (95%)", "Szansa Wzrostu (10D)"]].copy()
else:
    df_tab2_view = pd.DataFrame()

config_tabel_tab1 = {
    "Lp.": st.column_config.NumberColumn("Lp.", format="%d"),
    "24h (%)": st.column_config.NumberColumn("24h (%)", format="%.2f"),
}

config_tabel_tab2 = {
    "Lp.": st.column_config.NumberColumn("Lp.", format="%d"),
    "Smart Score (%)": st.column_config.NumberColumn("Smart Score (%)", format="%.2f"),
    "RSI 4H": st.column_config.NumberColumn("RSI 4H", format="%.1f"),
    "RSI 1D": st.column_config.NumberColumn("RSI 1D", format="%.1f"),
    "RSI 3D": st.column_config.NumberColumn("RSI 3D", format="%.1f"),
    "OBV Odchylenie (%)": st.column_config.NumberColumn("OBV Odchylenie (%)", format="%.2f"),
}

def apply_high_contrast_striping(df):
    return df.style.apply(
        lambda row: ['background-color: #f1f5f9; color: #0b0f19; font-weight: 500;' if row.name % 2 == 1 else 'background-color: #ffffff; color: #0b0f19; font-weight: 500;' for _ in row],
        axis=1
    )

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. 🏛️ Skaner Makro i Struktura", "2. ⚡ Skaner Sygnałowy i Egzekucja", "3. 🎯 Aktywne Pozycje", "4. 🗂️ Archiwum", "5. 📈 Skuteczność Algorytmu"])

with tab1: 
    st.subheader("🏛️ Struktura Rynkowa i Konfluencja MTF")
    st.dataframe(apply_high_contrast_striping(df_tab1_view), column_config=config_tabel_tab1, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("⚡ Oceny Przewagi i Sygnały Transakcyjne")
    st.dataframe(apply_high_contrast_striping(df_tab2_view), column_config=config_tabel_tab2, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.subheader("➕ Śledź wybraną pozycję ręcznie")
    col_sel_tok, col_sel_btn = st.columns([2, 1])
    chosen_token = col_sel_tok.selectbox("Wybierz token:", df_ta["Token"].tolist(), key="manual_token_pick")
    
    if col_sel_btn.button("🚀 Dodaj do śledzenia", type="primary"):
        cena_we = float(df_ta[df_ta["Token"] == chosen_token].iloc[0]["Price_Raw"])
        atr = float(df_ta[df_ta["Token"] == chosen_token].iloc[0]["ATR_Raw"])
        cel_tp = cena_we * 1.06
        sl = cena_we - (2.5 * atr)
        
        nowa = pd.DataFrame([{
            "Data Wejścia": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "Token": chosen_token,
            "Typ Sygnału": "Dodano ręcznie",
            "Cena Wejścia ($)": round(cena_we, 5),
            "Cel TP (6%) ($)": round(cel_tp, 5),
            "SL ($)": round(sl, 5),
            "Ekstremum ($)": round(cena_we, 5),
            "Data Wyjścia": "-",
            "Status": "🔄 W toku",
            "Zysk (%)": 0.0
        }])
        
        df_h = pd.concat([pd.read_csv(HISTORY_FILE), nowa], ignore_index=True) if os.path.exists(HISTORY_FILE) else nowa
        df_h.to_csv(HISTORY_FILE, index=False)
        st.success(f"Rozpoczęto śledzenie {chosen_token} po ${fmt(cena_we)} z celem TP (+6%): ${fmt(cel_tp)}!")
        st.rerun()

with tab3:
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            df_active = df_hist[df_hist["Status"].str.contains("W toku", na=False)]
            if not df_active.empty: 
                st.dataframe(apply_high_contrast_striping(df_active.sort_values("Data Wejścia", ascending=False)), use_container_width=True, hide_index=True)
            else: 
                st.info("Brak aktywnych pozycji (żaden token nie spełnia obecnie warunków zakupu po odfiltrowaniu szczytów).")
        except Exception:
            st.info("Brak aktywnych pozycji.")
    else: 
        st.info("Brak danych w bazie.")

with tab4:
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            df_closed = df_hist[~df_hist["Status"].str.contains("W toku", na=False)]
            if not df_closed.empty: 
                st.dataframe(apply_high_contrast_striping(df_closed.sort_values("Data Wyjścia", ascending=False)), use_container_width=True, hide_index=True)
            else: 
                st.info("Algorytm nie zamknął jeszcze żadnej transakcji po nowych regułach.")
        except Exception:
            st.info("Brak zamkniętych pozycji.")
    else: 
        st.info("Brak zamkniętych.")

with tab5:
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            df_closed = df_hist[~df_hist["Status"].str.contains("W toku", na=False)]
            
            if not df_closed.empty:
                sukcesy = len(df_closed[df_closed["Status"].str.contains("✅", na=False)])
                wszystkie = len(df_closed)
                win_rate = (sukcesy / wszystkie) * 100
                sredni_zysk = df_closed["Zysk (%)"].mean()
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Zakończone Sygnały", wszystkie)
                k2.metric("Osiągnięty TP (Sukces)", sukcesy)
                k3.metric("Skuteczność (Win Rate)", f"{win_rate:.1f}%")
                k4.metric("Średni Zysk/Strata z pozycji", f"{sredni_zysk:.2f}%")
                
                st.markdown("### Dystrybucja zysków/strat po zamknięciu")
                st.bar_chart(df_closed.set_index("Token")["Zysk (%)"])
            else:
                st.info("Algorytm zbiera dane... Poczekaj na pierwsze zamknięcia pozycji w archiwum.")
        except Exception:
            st.info("Brak opublikowanych zamkniętych pozycji.")
    else:
        st.info("Brak pliku z historią.")

if not df_ta.empty:
    st.divider()
    st.subheader("🤖 Ekspercki Raport Analityczny Pro")
    sel_ai = st.selectbox("Wybierz token do dogłębnej analizy:", df_ta["Token"].tolist())
    
    col_rep_text, col_rep_chart = st.columns([1.2, 1])
    
    with col_rep_text:
        st.markdown(generuj_raport_ai(df_ta[df_ta["Token"] == sel_ai].iloc[0], df_ml[df_ml["Token"] == sel_ai].iloc[0] if not df_ml.empty else None, btc_dom))
    
    with col_rep_chart:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if sel_ai in mc_paths:
            current_price = float(df_ta[df_ta["Token"] == sel_ai].iloc[0]["Price_Raw"])
            st.plotly_chart(plot_price_forecast(sel_ai, current_price, mc_paths[sel_ai]), use_container_width=True)
        else:
            st.info("Brak danych symulacji dla tego tokena.")
