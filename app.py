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
                
            price = float(df['close'].iloc[-1])
            prev_price = float(df['close'].iloc[0] if len(df) < 24 else df['close'].iloc[-24])
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
                "Price_Raw": float(price), "EMA200_Raw": float(ema200), "BTC_D1_Price": btc_d1_price, "BTC_D1_EMA200": btc_d1_ema200,
                "RSI_Raw": float(rsi)
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
    df_ml[["Symulacja Monte Carlo (24h)", "Zasięg Monte Carlo (95%)", "Zasięg Opcji DVOL (95%)", "Implikowana Zmienność (IV)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]] = df_ml.apply(analyze_row, axis=1)
    return df_ml[["Token", "Cena ($)", "Symulacja Monte Carlo (24h)", "Zasięg Monte Carlo (95%)", "Zasięg Opcji DVOL (95%)", "Implikowana Zmienność (IV)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]]

# ==========================================
# HISTORIA I BACKTEST (ZLECANIE WĄTKÓW TP/SL + FILTRY WEJŚCIA)
# ==========================================
HISTORY_FILE = "signals_history.csv"

def update_and_log_history(df_ml, df_ta):
    now_dt = pd.Timestamp.now()
    now_date = now_dt.strftime("%Y-%m-%d")
    now_full = now_dt.strftime("%Y-%m-%d %H:%M")
    
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
        except Exception:
            df_hist = pd.DataFrame()
    else:
        df_hist = pd.DataFrame()

    req_cols = ["Data", "Token", "Typ Sygnału", "Cena Wejścia", "Max Cena", "TP 5%", "TP 7.5%", "TP 10%", "Status"]
    for col in req_cols:
        if col not in df_hist.columns:
            if col == "Max Cena":
                df_hist[col] = df_hist["Cena Wejścia"] if "Cena Wejścia" in df_hist.columns else 0.0
            elif col in ["TP 5%", "TP 7.5%", "TP 10%"]:
                df_hist[col] = "-"
            elif col == "Status":
                df_hist[col] = "🔄 W toku (0/30d)"
            else:
                df_hist[col] = ""

    price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))
    rsi_map = dict(zip(df_ta["Token"], df_ta["RSI_Raw"]))

    if not df_hist.empty:
        for idx, row in df_hist.iterrows():
            token = row["Token"]
            try:
                entry = float(row["Cena Wejścia"])
            except Exception:
                continue
            if entry <= 0: continue
            
            curr_price = float(price_map.get(token, entry))
            prev_max = float(row["Max Cena"]) if pd.notna(row["Max Cena"]) and float(row["Max Cena"]) > 0 else entry
            new_max = max(prev_max, curr_price)
            df_hist.at[idx, "Max Cena"] = new_max
            
            max_gain_pct = ((new_max - entry) / entry) * 100
            curr_gain_pct = ((curr_price - entry) / entry) * 100
            
            if max_gain_pct >= 5.0 and (pd.isna(row["TP 5%"]) or str(row["TP 5%"]) == "-"):
                df_hist.at[idx, "TP 5%"] = f"✅ {now_date}"
            if max_gain_pct >= 7.5 and (pd.isna(row["TP 7.5%"]) or str(row["TP 7.5%"]) == "-"):
                df_hist.at[idx, "TP 7.5%"] = f"✅ {now_date}"
            if max_gain_pct >= 10.0 and (pd.isna(row["TP 10%"]) or str(row["TP 10%"]) == "-"):
                df_hist.at[idx, "TP 10%"] = f"✅ {now_date}"
            
            start_date = pd.to_datetime(row["Data"])
            days_passed = (now_dt - start_date).days
            
            if max_gain_pct >= 10.0:
                df_hist.at[idx, "Status"] = "🎯 Zaliczone TP 10%"
            elif curr_gain_pct <= -5.0:
                df_hist.at[idx, "Status"] = "❌ SL (-5%)"
            elif days_passed >= 30:
                df_hist.at[idx, "Status"] = "⏱️ Wygasło (30d)"
            else:
                df_hist.at[idx, "Status"] = f"🔄 W toku ({days_passed}/30d)"

    active_tokens = set()
    last_signal_time = {}
    
    if not df_hist.empty:
        for _, row in df_hist.iterrows():
            tok = row["Token"]
            dt_val = pd.to_datetime(row["Data"])
            if tok not in last_signal_time or dt_val > last_signal_time[tok]:
                last_signal_time[tok] = dt_val
                
            if "W toku" in str(row["Status"]):
                active_tokens.add(tok)

    new_rows = []
    if not df_ml.empty and "Sygnał Hybrydowy" in df_ml.columns:
        for _, row in df_ml.iterrows():
            sig = str(row["Sygnał Hybrydowy"])
            token = row["Token"]
            curr_rsi = rsi_map.get(token, 100.0)
            
            # FILTRY SELEKCJI:
            # 1. Tylko '🟢 KUP (Mocny)'
            # 2. Token nie ma aktywnej pozycji
            # 3. RSI po schłodzeniu (RSI <= 48)
            # 4. Cooldown 24h od ostatniego wpisu w historii
            is_mocny_kup = "🟢 KUP (Mocny)" in sig
            is_rsi_ready = curr_rsi <= 48.0
            
            hours_since_last = 999.0
            if token in last_signal_time:
                hours_since_last = (now_dt - last_signal_time[token]).total_seconds() / 3600.0
            is_cooldown_passed = hours_since_last >= 24.0

            if is_mocny_kup and (token not in active_tokens) and is_rsi_ready and is_cooldown_passed:
                try:
                    price_clean = float(str(row["Cena ($)"]).replace("$", "").replace(",", ""))
                except Exception:
                    continue
                new_rows.append({
                    "Data": now_full,
                    "Token": token,
                    "Typ Sygnału": sig,
                    "Cena Wejścia": price_clean,
                    "Max Cena": price_clean,
                    "TP 5%": "-",
                    "TP 7.5%": "-",
                    "TP 10%": "-",
                    "Status": "🔄 W toku (0/30d)"
                })
                active_tokens.add(token)

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_hist = pd.concat([df_hist, df_new], ignore_index=True) if not df_hist.empty else df_new

    if not df_hist.empty:
        df_hist.to_csv(HISTORY_FILE, index=False)

def get_backtest_stats(target_pct_str):
    if not os.path.exists(HISTORY_FILE): 
        return pd.DataFrame(), 0, 0, 0.0
    try: 
        df_hist = pd.read_csv(HISTORY_FILE)
    except Exception: 
        return pd.DataFrame(), 0, 0, 0.0
    if df_hist.empty: 
        return df_hist, 0, 0, 0.0

    col_tp = f"TP {target_pct_str}"
    wins = 0
    total = 0
    results = []

    for _, row in df_hist.iterrows():
        token = row.get("Token")
        entry = float(row.get("Cena Wejścia", 0))
        sig_type = row.get("Typ Sygnału")
        tp_hit = str(row.get(col_tp, "-"))
        status = str(row.get("Status", "-"))
        max_p = float(row.get("Max Cena", entry))
        max_gain = ((max_p - entry) / entry) * 100 if entry > 0 else 0.0

        is_tp = "✅" in tp_hit
        is_closed = is_tp or ("SL" in status) or ("Wygasło" in status) or ("Zaliczone" in status)

        if is_tp:
            wins += 1
            total += 1
            res_status = f"✅ Osiągnięto {target_pct_str} ({tp_hit.replace('✅ ', '')})"
        elif "SL" in status:
            total += 1
            res_status = "❌ SL (-5%)"
        elif "Wygasło" in status:
            total += 1
            res_status = "⏱️ Wygasło (30d)"
        else:
            res_status = f"🔄 W toku (Max: +{round(max_gain, 1)}%)"

        results.append({
            "Data Wejścia": row.get("Data"),
            "Token": token,
            "Sygnał": sig_type,
            "Cena Wejścia ($)": fmt(entry),
            "Max Cena ($)": fmt(max_p),
            "Max Wzrost (%)": f"+{round(max_gain, 2)}%",
            f"Cel {target_pct_str}": tp_hit,
            "Status": res_status
        })

    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    return pd.DataFrame(results), total, wins, win_rate

# ==========================================
# RAPORT AI
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None):
    symbol = row_ta.get("Token")
    price_str = row_ta.get("Cena ($)")
    price_raw = float(row_ta.get("Price_Raw", 0))
    ema_raw = float(row_ta.get("EMA200_Raw", 0))
    rsi = float(row_ta.get("RSI", 50))
    pct_b = float(row_ta.get("%B (BB)", 0.5))
    change_24h = row_ta.get("24h (%)")
    support_str = row_ta.get("Wsparcie")
    resistance_str = row_ta.get("Opór")
    sl_str = row_ta.get("SL (ATR)")
    rr = row_ta.get("R:R")
    
    trend_desc = "wzrostowym (Cena powyżej EMA 200)" if price_raw > ema_raw else "spadkowym/bocznym (Cena poniżej EMA 200)"

    prob_str, prognoza_mc, signal = "50.0%", "-", "⏳ CZEKAJ"
    if row_ml is not None:
        prognoza_mc = row_ml.get("Symulacja Monte Carlo (24h)")
        prob_str = row_ml.get("Prawdopodobieństwo")
        signal = row_ml.get("Sygnał Hybrydowy")
        
    try:
        prob_val = float(str(prob_str).replace("%", ""))
    except Exception:
        prob_val = 50.0

    return f"""
### 📑 RAPORT AI: {symbol} (${price_str}, Zmiana 24h: {change_24h}%)
* **Trend strukturalny:** {trend_desc}
* **Momentum (RSI):** {rsi} | **Wstęgi Bollingera (%B):** {pct_b:.2f}
* **Symulacja Monte Carlo (24h):** {prognoza_mc} | **Szansa na sukces:** **{prob_val}%**
* **Poziomy krytyczne:** Wsparcie: `${support_str}` | Opór: `${resistance_str}` | Stop Loss: `${sl_str}`
* **R:R:** `{rr}` | **Sygnał:** {signal}
"""

# ==========================================
# INTERFEJS GŁÓWNY (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane rynkowe..."):
    df_ta, fng_val, fng_class, btc_dom, btc_d1_p, btc_d1_e, loaded_c, total_c = fetch_technical_analysis()
    df_ml = run_predictions(df_ta, fng_val)
    update_and_log_history(df_ml, df_ta)

col_t, col_b, col_d, col_f = st.columns([2, 1.1, 0.9, 1])
col_t.title("📊 Analiza Krypto")
col_t.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Tokeny: {loaded_c}/{total_c}")

if btc_d1_p and btc_d1_e:
    col_b.metric("BTC Trend D1", "🟢 Byczy" if btc_d1_p >= btc_d1_e*0.985 else "🔴 Niedźwiedzi", f"${fmt(btc_d1_p)}")
else:
    col_b.metric("BTC Trend D1", "Brak danych")

col_d.metric("Dominacja BTC", f"{btc_dom}%")
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

# ==========================================
# STRATEGICZNE PODSUMOWANIE SPOT
# ==========================================
if not df_ml.empty and "Sygnał Hybrydowy" in df_ml.columns:
    st.markdown("---")
    st.markdown("### 💡 Strategiczne Podsumowanie Spot")
    
    mocne_kup = df_ml[df_ml["Sygnał Hybrydowy"].str.contains("Mocny", na=False)]["Token"].tolist()
    slabe_kup = df_ml[df_ml["Sygnał Hybrydowy"].str.contains("Słaby", na=False)]["Token"].tolist()
    sprzedaz = df_ml[df_ml["Sygnał Hybrydowy"].str.contains("SPRZEDAJ", na=False)]["Token"].tolist()
    
    c_kafl1, c_kafl2, c_kafl3 = st.columns(3)
    with c_kafl1:
        st.success(f"🟢 **Mocna Akumulacja Spot**\n\n**Tokeny:** {', '.join(mocne_kup) if mocne_kup else 'Brak'}\n\nWysoka szansa wzrostu i poprawny wolumen.")
    with c_kafl2:
        st.warning(f"📈 **Ostrożne Wejście (DCA)**\n\n**Tokeny:** {', '.join(slabe_kup) if slabe_kup else 'Brak'}\n\nRozważ mniejsze zakupy metodą DCA.")
    with c_kafl3:
        st.error(f"🔴 **Realizacja Zysków**\n\n**Tokeny:** {', '.join(sprzedaz) if sprzedaz else 'Brak'}\n\nPrzegrzane wskaźniki – rozważ redukcję pozycji.")

st.markdown("---")
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    if st.button("🔄 Odśwież dane", type="primary"):
        st.cache_data.clear()
        st.rerun()
with col_btn2:
    if st.button("🗑️ Wyczyść historię sygnałów"):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            st.success("Wyczyszczono plik historii!")
            st.rerun()

df_ta_clean = df_ta.drop(columns=["RawScore", "Vol_Surge_Raw", "Price_Raw", "EMA200_Raw", "BTC_D1_Price", "BTC_D1_EMA200", "RSI_Raw"], errors="ignore")

tab1, tab2, tab3, tab4 = st.tabs(["1. Tabela Techniczna", "2. Sygnały Hybrydowe", "3. Backtest", "4. Archiwum"])

with tab1:
    st.dataframe(df_ta_clean, use_container_width=True)

with tab2:
    st.dataframe(df_ml, use_container_width=True)

with tab3:
    st.subheader("📈 Skuteczność Sygnałów (Backtest)")
    t_choice = st.radio("Próg TP / SL:", ["5%", "7.5%", "10%"], horizontal=True, key="bt_rad")
    bt_df, tot, wins, wr = get_backtest_stats(t_choice)
    if tot > 0:
        k1, k2, k3 = st.columns(3)
        k1.metric("Zamknięte Sygnały", tot)
        k2.metric(f"Wygrane ({t_choice})", wins)
        k3.metric("Win Rate", f"{wr}%")
        st.dataframe(bt_df, use_container_width=True)
    else:
        st.info("Brak rozliczonych sygnałów dla tego progu (pozycje są w toku lub wyczyściłeś plik).")

with tab4:
    st.subheader("🗂️ Pełne Archiwum Sygnałów")
    if os.path.exists(HISTORY_FILE):
        try:
            df_hist = pd.read_csv(HISTORY_FILE)
            if not df_hist.empty:
                st.dataframe(df_hist.sort_values(by="Data", ascending=False), use_container_width=True)
            else:
                st.info("Archiwum jest puste.")
        except Exception:
            st.info("Błąd odczytu archiwum.")
    else:
        st.info("Brak pliku historii.")

if not df_ta.empty:
    st.divider()
    st.subheader("🤖 Rozbudowany Raport Analityczny AI")
    sel_ai = st.selectbox("Wybierz token do pełnego raportu:", df_ta["Token"].tolist(), key="ai_box")
    st.markdown(generuj_raport_ai(df_ta[df_ta["Token"] == sel_ai].iloc[0], df_ml[df_ml["Token"] == sel_ai].iloc[0] if not df_ml.empty else None))
