import numpy as np
import pandas as pd
import requests
import streamlit as st
import os

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Analiza Krypto", layout="wide")

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
        st.text_input("Podaj hasło dostępu:", type="password", on_change=password_entered, key="password_input")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Dostęp Zastrzeżony")
        st.text_input("Podaj hasło dostępu:", type="password", on_change=password_entered, key="password_input")
        st.error("⛔ Niepoprawne hasło! Spróbuj ponownie.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# LISTA TOKENÓW SPOT
# ==========================================
TOKENS = [
    {'symbol': 'BTC', 'coinbase': 'BTC-USD', 'gecko_id': 'bitcoin'},
    {'symbol': 'ETH', 'coinbase': 'ETH-USD', 'gecko_id': 'ethereum'},
    {'symbol': 'ONDO', 'coinbase': 'ONDO-USD', 'gecko_id': 'ondo-finance'},
    {'symbol': 'RENDER', 'coinbase': 'RENDER-USD', 'gecko_id': 'render-token'},
    {'symbol': 'INJ', 'coinbase': 'INJ-USD', 'gecko_id': 'injective-protocol'},
    {'symbol': 'LINK', 'coinbase': 'LINK-USD', 'gecko_id': 'chainlink'},
    {'symbol': 'FET', 'coinbase': 'FET-USD', 'gecko_id': 'artificial-superintelligence-alliance'},
    {'symbol': 'ENA', 'coinbase': 'ENA-USD', 'gecko_id': 'ethena'},
    {'symbol': 'NEAR', 'coinbase': 'NEAR-USD', 'gecko_id': 'near'},
    {'symbol': 'UNI', 'coinbase': 'UNI-USD', 'gecko_id': 'uniswap'},
    {'symbol': 'SEI', 'coinbase': 'SEI-USD', 'gecko_id': 'sei-network'},
    {'symbol': 'JUP', 'coinbase': None, 'gecko_id': 'jupiter-exchange-solana'},
    {'symbol': 'KTA', 'coinbase': None, 'gecko_id': 'keeta'}
]

def fmt(val):
    if pd.isna(val) or val is None:
        return "-"
    if isinstance(val, (int, float)):
        if abs(val) < 0.0001:
            return f"{val:.6f}"
        elif abs(val) < 1.0:
            return round(val, 4)
        elif abs(val) < 100.0:
            return round(val, 2)
        else:
            return round(val, 2)
    return val

def get_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=4).json()
        return int(res['data'][0]['value']), res['data'][0]['value_classification']
    except Exception:
        return 50, "Neutral"

def get_global_market_data():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/global", headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4).json()
        return round(res['data']['market_cap_percentage']['btc'], 1)
    except Exception:
        return 55.0

def fetch_from_coinbase(symbol_pair, granularity=3600):
    url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?granularity={granularity}"
    res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4)
    res.raise_for_status()
    return pd.DataFrame(res.json(), columns=['timestamp', 'low', 'high', 'open', 'close', 'volume']).sort_values('timestamp').reset_index(drop=True)

def fetch_from_coingecko(gecko_id):
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/ohlc?vs_currency=usd&days=1"
    res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=5)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close'])
    df['volume'] = 0.0
    return df.sort_values('timestamp').reset_index(drop=True)

def get_candles(token_info):
    if token_info['coinbase']:
        try:
            return fetch_from_coinbase(token_info['coinbase'], granularity=3600)
        except Exception:
            pass
    return fetch_from_coingecko(token_info['gecko_id'])

def get_btc_daily_macro_ema200():
    try:
        df_d1 = fetch_from_coinbase("BTC-USD", granularity=86400)
        if len(df_d1) >= 20:
            span_period = min(200, len(df_d1))
            return df_d1['close'].iloc[-1], df_d1['close'].ewm(span=span_period, adjust=False).mean().iloc[-1]
    except Exception:
        pass
    return None, None

def get_deribit_dvol(currency="BTC"):
    try:
        url = f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={currency}&resolution=1D"
        res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4).json()
        if 'result' in res and 'data' in res['result'] and len(res['result']['data']) > 0:
            return float(res['result']['data'][-1][4])
    except Exception:
        pass
    return 60.0

@st.cache_data(ttl=60)
def fetch_technical_analysis():
    data = []
    loaded_count = 0
    fng_val, fng_class = get_fear_and_greed()
    btc_dom = get_global_market_data()
    btc_d1_price, btc_d1_ema200 = get_btc_daily_macro_ema200()

    for item in TOKENS:
        try:
            df = get_candles(item)
            if len(df) < 12:
                continue
                
            price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[0] if len(df) < 24 else df['close'].iloc[-24]
            change_24h = ((price - prev_price) / prev_price) * 100
            
            delta = df['close'].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / (loss.iloc[-1] + 1e-9))))
            
            tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(min(14, len(df))).mean().iloc[-1]
            ema200 = df['close'].ewm(span=min(200, len(df)), adjust=False).mean().iloc[-1]

            sma20 = df['close'].rolling(min(20, len(df))).mean().iloc[-1]
            std20 = df['close'].rolling(min(20, len(df))).std().iloc[-1]
            pct_b = (price - (sma20 - (std20 * 2))) / (((sma20 + (std20 * 2)) - (sma20 - (std20 * 2))) + 1e-9)

            vol_surge = (df['volume'].iloc[-2] / df['volume'].iloc[:-1].rolling(min(20, len(df)-1)).mean().iloc[-1]) if len(df) > 2 and df['volume'].sum() > 0 else 1.0

            sl = price - (2 * atr)
            support = df['low'].min()
            resistance = df['high'].max()
            
            risk = price - sl
            reward = resistance - price
            rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1
            
            atr_pct = (atr / price) * 100
            dynamic_rsi_thresh = 30.0 + min(max(atr_pct * 1.5, 0.0), 10.0)
            
            rsi_score = (dynamic_rsi_thresh - rsi) * 0.9 + 5.0 if rsi < dynamic_rsi_thresh else (-(rsi - 70) * 0.8 if rsi > 70 else (rsi - 50) * 0.2)
            support_score = max(0.0, (3.0 - (((price - support) / price) * 100)) * 2.5)
            chance = round(min(max(50.0 + rsi_score + support_score + (50 - fng_val) * 0.2 + (5.0 if price > ema200 else -5.0) + (change_24h * 0.1), 20.0), 90.0), 1)
            
            okazja_score = round(min(max(chance * min(max(rr_val / 2.0, 0.5), 1.3), 10.0), 99.0), 1)
            okazja_str = f"🔥 {okazja_score}%" if okazja_score >= 70.0 else (f"👀 {okazja_score}%" if okazja_score >= 50.0 else f"⚪ {okazja_score}%")

            data.append({
                "Token": item['symbol'], "Cena ($)": fmt(price), "24h (%)": round(change_24h, 2),
                "RSI": round(rsi, 1), "%B (BB)": round(pct_b, 2), "EMA 200": fmt(ema200),
                "Wolumen (x)": f"{round(vol_surge, 1)}x", "Vol_Surge_Raw": vol_surge, "ATR": fmt(atr),
                "SL (ATR)": fmt(sl), "Wsparcie": fmt(support), "Opór": fmt(resistance), "R:R": f"1:{rr_val}",
                "Szansa (%)": f"{chance}%", "Atrakcyjność (%)": okazja_str, "RawScore": okazja_score,
                "Price_Raw": price, "EMA200_Raw": ema200, "BTC_D1_Price": btc_d1_price, "BTC_D1_EMA200": btc_d1_ema200
            })
            loaded_count += 1
        except Exception:
            continue
            
    return pd.DataFrame(data), fng_val, fng_class, btc_dom, btc_d1_price, btc_d1_ema200, loaded_count, len(TOKENS)

def run_predictions(df_ta, fng_val):
    if df_ta.empty or "RawScore" not in df_ta.columns:
        return pd.DataFrame({"Komunikat": ["Brak danych do prognozy."]})

    dvol_btc = get_deribit_dvol("BTC")
    btc_row = df_ta[df_ta["Token"] == "BTC"]
    btc_bullish_macro = True
    btc_vol_ratio = 0.01
    
    if not df_ta.empty and df_ta["BTC_D1_Price"].iloc[0] is not None:
        btc_bullish_macro = float(df_ta["BTC_D1_Price"].iloc[0]) >= (float(df_ta["BTC_D1_EMA200"].iloc[0]) * 0.985)
    if not btc_row.empty:
        btc_vol_ratio = float(btc_row["ATR"].values[0]) / float(btc_row["Price_Raw"].values[0])

    rng = np.random.default_rng(seed=int(pd.Timestamp.now().strftime("%Y%m%d%H")))

    def analyze_row(row):
        symbol, price, atr, rsi, change, pct_b, vol_surge = row["Token"], float(row["Price_Raw"]), float(row["ATR"]), float(row["RSI"]), float(row["24h (%)"]), float(row["%B (BB)"]), float(row["Vol_Surge_Raw"])
        expected_change = (change / 100 * 0.05) + ((30.0 - rsi) * 0.0025 if rsi < 30 else (-(rsi - 70) * 0.002 if rsi > 70 else 0))
        target_price = price * (1 + expected_change)

        shocks = rng.normal(expected_change / 24.0, (atr / price) / np.sqrt(24), (5000, 24))
        final_prices = price * np.exp(np.cumsum(shocks, axis=1))[:, -1]
        prob = np.mean(final_prices > price) * 100
        token_iv = dvol_btc * ((atr / price) / btc_vol_ratio)

        if expected_change > 0:
            signal = "🟢 KUP (Mocny)" if (prob >= 55.0 or rsi < 30 or fng_val < 25) and (symbol == "BTC" or (btc_bullish_macro and vol_surge >= 1.0)) else "📈 KUP (Słaby)"
        else:
            signal = "⏳ CZEKAJ / NEUTRALNY" if rsi <= 45 else ("🔴 SPRZEDAJ" if prob < 42.0 else "⏳ CZEKAJ / NEUTRALNY")

        return pd.Series([
            f"${fmt(target_price)}",
            f"${fmt(np.percentile(final_prices, 2.5))} - ${fmt(np.percentile(final_prices, 97.5))}",
            f"${fmt(price * (1.0 - 1.96 * (token_iv / 100.0) / np.sqrt(365)))} - ${fmt(price * (1.0 + 1.96 * (token_iv / 100.0) / np.sqrt(365)))}",
            f"{round(token_iv, 1)}%", f"{round(prob, 1)}%", signal
        ])

    df_ml = df_ta.copy()
    df_ml[["Prognoza ML (24h)", "Zasięg Monte Carlo (95%)", "Zasięg Opcji DVOL (95%)", "Implikowana Zmienność (IV)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]] = df_ml.apply(analyze_row, axis=1)
    return df_ml[["Token", "Cena ($)", "Prognoza ML (24h)", "Zasięg Monte Carlo (95%)", "Zasięg Opcji DVOL (95%)", "Implikowana Zmienność (IV)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]]

# ==========================================
# HISTORIA I BACKTEST
# ==========================================
HISTORY_FILE = "signals_history.csv"

def log_signals_to_history(df_ml):
    if df_ml.empty or "Sygnał Hybrydowy" not in df_ml.columns: return
    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    existing = pd.read_csv(HISTORY_FILE).to_dict(orient="records") if os.path.exists(HISTORY_FILE) else []
    new_rows = []
    
    for _, row in df_ml.iterrows():
        sig = row["Sygnał Hybrydowy"]
        if "KUP" in sig or "SPRZEDAJ" in sig:
            try: price_clean = float(str(row["Cena ($)"]).replace("$", "").replace(",", ""))
            except: continue
            token = row["Token"]
            if not any(o.get("Token") == token and o.get("Typ Sygnału") == sig for o in existing):
                new_rows.append({"Data": now_str, "Token": token, "Typ Sygnału": sig, "Cena Wejścia": price_clean})
                
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        if os.path.exists(HISTORY_FILE):
            pd.concat([pd.read_csv(HISTORY_FILE), df_new]).drop_duplicates(subset=["Data", "Token", "Typ Sygnału"], keep="last").to_csv(HISTORY_FILE, index=False)
        else:
            df_new.to_csv(HISTORY_FILE, index=False)

def get_backtest_stats(df_current_prices, target_pct=5.0):
    if not os.path.exists(HISTORY_FILE): return pd.DataFrame(), 0, 0, 0.0
    try: df_hist = pd.read_csv(HISTORY_FILE)
    except: return pd.DataFrame(), 0, 0, 0.0
    if df_hist.empty: return df_hist, 0, 0, 0.0

    price_map = dict(zip(df_current_prices["Token"], df_current_prices["Price_Raw"]))
    results, wins, total = [], 0, 0
    
    for _, row in df_hist.iterrows():
        token, entry, sig_type = row["Token"], float(row["Cena Wejścia"]), row["Typ Sygnału"]
        curr = price_map.get(token, entry)
        change_pct = ((curr - entry) / entry) * 100
        
        status = f"✅ TP (+{target_pct}%)" if change_pct >= target_pct else (f"❌ SL (-{target_pct}%)" if change_pct <= -target_pct else "🔄 W toku (Spot)")
        if status.startswith("✅"): wins += 1
        total += 1
        
        results.append({"Data": row["Data"], "Token": token, "Sygnał": sig_type, "Cena Wejścia ($)": fmt(entry), "Cena Obecna ($)": fmt(curr), "Wynik (%)": round(change_pct, 2), "Status": status})
        
    return pd.DataFrame(results), total, wins, (round((wins / total) * 100, 1) if total > 0 else 0.0)

# ==========================================
# CZYTELNY RAPORT AI
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None):
    symbol, price_str, rsi, sl_str, support_str, resistance_str, rr = row_ta.get("Token"), row_ta.get("Cena ($)"), float(row_ta.get("RSI", 50)), row_ta.get("SL (ATR)"), row_ta.get("Wsparcie"), row_ta.get("Opór"), row_ta.get("R:R")
    change_24h, trend_desc = row_ta.get("24h (%)"), "wzrostowym (powyżej EMA 200)" if row_ta.get("Price_Raw", 0) > row_ta.get("EMA200_Raw", 0) else "spadkowym/bocznym"
    
    prob, prognoza_ml, zasieg_mc, signal = "50.0%", "-", "-", "⏳ CZEKAJ"
    if row_ml is not None:
        prognoza_ml, zasieg_mc, prob, signal = row_ml.get("Prognoza ML (24h)"), row_ml.get("Zasięg Monte Carlo (95%)"), row_ml.get("Prawdopodobieństwo"), row_ml.get("Sygnał Hybrydowy")
        
    pewnosc = max(float(prob.replace("%", "")), 100 - float(prob.replace("%", "")))
    decyzja = "🟢 **KUPUJ (Mocny)**" if "KUP (Mocny)" in signal else ("📈 **KUPUJ OSTROŻNIE / DCA**" if "KUP (Słaby)" in signal else "⏳ **WSTRZYMAJ SIĘ / CZEKAJ**")

    return f"""
### 📑 RAPORT TECHNICZNY: {symbol} (${price_str})
* **Zmiana 24h:** {change_24h}% | **Trend strukturalny:** {trend_desc}
* **Momentum (RSI):** Poziom **{rsi}** | **Wsparcie:** ${support_str} | **Opór:** ${resistance_str}

---
### 🎲 SYMULACJA PROGNOZY (ML & MONTE CARLO)
* **Prognoza ceny (24h):** {prognoza_ml} | **Przedział MC (95%):** {zasieg_mc}
* **Prawdopodobieństwo sukcesu:** **{prob}**

---
### 🎯 KLUCZOWI WNIOSEK I REKOMENDACJA
* **Rekomendacja:** {decyzja}
* **Pewność modelu:** **{pewnosc:.1f}%** | **Stosunek Zysku do Ryzyka (R:R):** {rr}
* **Zalecany Stop Loss:** **${sl_str}**
"""

# ==========================================
# INTERFEJS GŁÓWNY (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane rynkowe i analizuję rynek..."):
    df_ta, fng_val, fng_class, btc_dom, btc_d1_p, btc_d1_e, loaded_c, total_c = fetch_technical_analysis()
    df_ml = run_predictions(df_ta, fng_val)
    log_signals_to_history(df_ml)

col_t, col_b, col_d, col_f = st.columns([2, 1.1, 0.9, 1])
col_t.title("📊 Analiza Krypto")
col_t.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Tokeny: {loaded_c}/{total_c}")

if btc_d1_p and btc_d1_e:
    col_b.metric("BTC Trend D1", "🟢 Byczy" if btc_d1_p >= btc_d1_e*0.985 else "🔴 Niedźwiedzi", f"${fmt(btc_d1_p)}")
else:
    col_b.metric("BTC Trend D1", "Brak danych")

col_d.metric("Dominacja BTC", f"{btc_dom}%")
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

if not df_ta.empty:
    st.markdown("---")
    sel_token = st.selectbox("📱 Szybki podgląd tokena:", df_ta["Token"].tolist())
    t_row = df_ta[df_ta["Token"] == sel_token].iloc[0]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Cena Spot", t_row["Cena ($)"])
    m2.metric("Zmiana 24h", f"{t_row['24h (%)']}%")
    m3.metric("RSI (14)", t_row["RSI"])
    m4.metric("Atrakcyjność", t_row["Atrakcyjność (%)"])
    m5.metric("Sugerowany SL", t_row["SL (ATR)"])

st.markdown("---")
if st.button("🔄 Odśwież dane rynkowe", type="primary"):
    st.cache_data.clear()
    st.rerun()

df_ta_clean = df_ta.drop(columns=["RawScore", "Vol_Surge_Raw", "Price_Raw", "EMA200_Raw", "BTC_D1_Price", "BTC_D1_EMA200"], errors="ignore")

tab1, tab2, tab3, tab4 = st.tabs(["1. Tabela Techniczna", "2. Sygnały Hybrydowe", "3. Backtest", "4. Archiwum"])

with tab1:
    st.dataframe(df_ta_clean.style.map(lambda v: 'color: #2e7d32; font-weight: bold;' if isinstance(v, (int, float)) and v > 0 else ('color: #c62828; font-weight: bold;' if isinstance(v, (int, float)) and v < 0 else ''), subset=['24h (%)']), use_container_width=True)

with tab2:
    st.dataframe(df_ml, use_container_width=True)

with tab3:
    st.subheader("📈 Skuteczność Sygnałów (Backtest)")
    t_choice = st.radio("Próg TP / SL:", ["5%", "7.5%", "10%"], horizontal=True, key="bt_rad")
    t_val = 5.0 if t_choice == "5%" else (7.5 if t_choice == "7.5%" else 10.0)
    bt_df, tot, wins, wr = get_backtest_stats(df_ta, t_val)
    if tot > 0:
        k1, k2, k3 = st.columns(3)
        k1.metric("Sygnały", tot)
        k2.metric("Wygrane (TP)", wins)
        k3.metric("Win Rate", f"{wr}%")
        st.dataframe(bt_df, use_container_width=True)
    else:
        st.info("Brak zapisanej historii.")

with tab4:
    st.subheader("🗂️ Archiwum Sygnałów")
    if os.path.exists(HISTORY_FILE):
        df_hist = pd.read_csv(HISTORY_FILE)
        if not df_hist.empty:
            st.dataframe(df_hist.sort_values(by="Data", ascending=False), use_container_width=True)
            with open(HISTORY_FILE, "rb") as f:
                st.download_button("📥 Pobierz archiwum (CSV)", f, "archiwum.csv", "text/csv")
        else:
            st.info("Archiwum jest puste.")
    else:
        st.info("Brak pliku historii.")

if not df_ta.empty:
    st.divider()
    st.subheader("🤖 Raport Analityczny AI")
    sel_ai = st.selectbox("Wybierz token do raportu opisowego:", df_ta["Token"].tolist(), key="ai_box")
    st.info(generuj_raport_ai(df_ta[df_ta["Token"] == sel_ai].iloc[0], df_ml[df_ml["Token"] == sel_ai].iloc[0] if not df_ml.empty else None))
