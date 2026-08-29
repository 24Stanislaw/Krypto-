import numpy as np
import pandas as pd
import requests
import streamlit as st
import os
if os.path.exists("signals_history.csv"):
    os.remove("signals_history.csv")

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Analiza Krypto MTF (1H-12H)", layout="wide")

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

# Świece 1H
def fetch_from_coinbase(symbol_pair):
    url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?granularity=3600"
    res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
    df['dt'] = pd.to_datetime(df['timestamp'], unit='s')
    return df.sort_values('dt').reset_index(drop=True)

def fetch_from_coingecko(gecko_id):
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/ohlc?vs_currency=usd&days=14"
    res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=5)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close'])
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['volume'] = 0.0
    return df.sort_values('dt').reset_index(drop=True)

def get_candles_1h(token_info):
    if token_info['coinbase']:
        try:
            return fetch_from_coinbase(token_info['coinbase'])
        except Exception:
            pass
    return fetch_from_coingecko(token_info['gecko_id'])

# Resampling danych 1h do wyższych interwałów (2h, 4h, 12h)
def resample_ohlc(df_1h, rule):
    df = df_1h.copy()
    df.set_index('dt', inplace=True)
    res = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna().reset_index()
    return res

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + (gain.iloc[-1] / (loss.iloc[-1] + 1e-9))))

def get_deribit_dvol(currency="BTC"):
    try:
        url = f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={currency}&resolution=1D"
        res = requests.get(url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4).json()
        if 'result' in res and 'data' in res['result'] and len(res['result']['data']) > 0:
            return float(res['result']['data'][-1][4])
    except Exception:
        pass
    return 60.0

@st.cache_data(ttl=300)
def fetch_technical_analysis():
    data = []
    loaded_count = 0
    fng_val, fng_class = get_fear_and_greed()
    btc_dom = get_global_market_data()

    for item in TOKENS:
        try:
            df_1h = get_candles_1h(item)
            if len(df_1h) < 24:
                continue

            df_2h = resample_ohlc(df_1h, '2h')
            df_4h = resample_ohlc(df_1h, '4h')
            df_12h = resample_ohlc(df_1h, '12h')

            price = float(df_1h['close'].iloc[-1])
            prev_price_24h = float(df_1h['close'].iloc[-24] if len(df_1h) >= 24 else df_1h['close'].iloc[0])
            change_24h = ((price - prev_price_24h) / prev_price_24h) * 100

            rsi_1h = calc_rsi(df_1h['close'])
            rsi_2h = calc_rsi(df_2h['close'])
            rsi_4h = calc_rsi(df_4h['close'])
            rsi_12h = calc_rsi(df_12h['close']) if len(df_12h) >= 14 else 50.0

            tr = pd.concat([df_4h['high'] - df_4h['low'], (df_4h['high'] - df_4h['close'].shift()).abs(), (df_4h['low'] - df_4h['close'].shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(min(14, len(df_4h))).mean().iloc[-1]
            ema200_4h = df_4h['close'].ewm(span=min(200, len(df_4h)), adjust=False).mean().iloc[-1]

            sl = price - (2 * atr)
            support = df_4h['low'].min()
            resistance = df_4h['high'].max()
            
            risk = price - sl
            reward = resistance - price
            rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1

            # Konsensus MTF
            mtf_score = 0
            if rsi_1h <= 45: mtf_score += 1
            if rsi_2h <= 48: mtf_score += 1
            if rsi_4h <= 52: mtf_score += 1
            if rsi_12h <= 55: mtf_score += 1

            okazja_score = round(min(max((mtf_score * 20.0) + (50 - rsi_4h) * 0.5 + (10.0 if price > ema200_4h else 0), 10.0), 99.0), 1)
            okazja_str = f"🔥 {okazja_score}%" if okazja_score >= 70.0 else (f"👀 {okazja_score}%" if okazja_score >= 50.0 else f"⚪ {okazja_score}%")

            data.append({
                "Token": item['symbol'], "Cena ($)": fmt(price), "24h (%)": round(change_24h, 2),
                "RSI 1H": round(rsi_1h, 1), "RSI 2H": round(rsi_2h, 1), "RSI 4H": round(rsi_4h, 1), "RSI 12H": round(rsi_12h, 1),
                "MTF Zgoda": f"{mtf_score}/4", "EMA 200 (4H)": fmt(ema200_4h), "ATR": fmt(atr),
                "SL (ATR)": fmt(sl), "Wsparcie": fmt(support), "Opór": fmt(resistance), "R:R": f"1:{rr_val}",
                "Atrakcyjność (%)": okazja_str, "RawScore": okazja_score, "Price_Raw": float(price), "EMA200_Raw": float(ema200_4h),
                "RSI_1H_Raw": float(rsi_1h), "RSI_4H_Raw": float(rsi_4h), "RSI_12H_Raw": float(rsi_12h), "MTF_Score": mtf_score
            })
            loaded_count += 1
        except Exception:
            continue
            
    return pd.DataFrame(data), fng_val, fng_class, btc_dom, loaded_count, len(TOKENS)

def run_predictions(df_ta, fng_val):
    if df_ta.empty:
        return pd.DataFrame()

    dvol_btc = get_deribit_dvol("BTC")
    rng = np.random.default_rng(seed=int(pd.Timestamp.now().strftime("%Y%m%d%H")))

    def analyze_row(row):
        symbol, price, atr = row["Token"], float(row["Price_Raw"]), float(row["ATR"])
        rsi_1h, rsi_4h, rsi_12h, mtf_score = float(row["RSI_1H_Raw"]), float(row["RSI_4H_Raw"]), float(row["RSI_12H_Raw"]), int(row["MTF_Score"])
        
        expected_change = ((48.0 - rsi_4h) * 0.002) + ((50.0 - rsi_1h) * 0.001)
        target_price = price * (1 + expected_change)

        shocks = rng.normal(expected_change / 24.0, (atr / price) / np.sqrt(24), (3000, 24))
        final_prices = price * np.exp(np.cumsum(shocks, axis=1))[:, -1]
        prob = np.mean(final_prices > price) * 100

        # Kryteria Sygnału oparte na MTF
        if mtf_score >= 3 and rsi_12h <= 60 and rsi_1h <= 45:
            signal = "🟢 KUP (Mocny MTF)"
        elif mtf_score >= 2 and rsi_1h <= 40:
            signal = "📈 KUP (Słaby / Scalp)"
        elif rsi_1h >= 68 or rsi_4h >= 72:
            signal = "🔴 SPRZEDAJ (Wykupienie)"
        else:
            signal = "⏳ CZEKAJ / NEUTRALNY"

        return pd.Series([
            f"${fmt(target_price)}",
            f"${fmt(np.percentile(final_prices, 2.5))} - ${fmt(np.percentile(final_prices, 97.5))}",
            f"{round(prob, 1)}%", signal
        ])

    df_ml = df_ta.copy()
    df_ml[["Prognoza MC (24h)", "Zasięg Monte Carlo (95%)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]] = df_ml.apply(analyze_row, axis=1)
    return df_ml[["Token", "Cena ($)", "RSI 1H", "RSI 4H", "RSI 12H", "MTF Zgoda", "Prognoza MC (24h)", "Zasięg Monte Carlo (95%)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]]

# ==========================================
# HISTORIA ZLECEŃ I REJESTRACJA
# ==========================================
HISTORY_FILE = "signals_history.csv"

def update_and_log_history(df_ml, df_ta):
    now_dt = pd.Timestamp.now()
    now_date = now_dt.strftime("%Y-%m-%d")
    now_full = now_dt.strftime("%Y-%m-%d %H:%M")
    
    if os.path.exists(HISTORY_FILE):
        try: df_hist = pd.read_csv(HISTORY_FILE)
        except Exception: df_hist = pd.DataFrame()
    else: df_hist = pd.DataFrame()

    req_cols = ["Data", "Token", "Typ Sygnału", "Cena Wejścia", "Max Cena", "TP 5%", "TP 7.5%", "TP 10%", "Status"]
    for col in req_cols:
        if col not in df_hist.columns:
            df_hist[col] = "-" if "TP" in col else ("🔄 W toku (0/30d)" if col == "Status" else "")

    price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))
    rsi_1h_map = dict(zip(df_ta["Token"], df_ta["RSI_1H_Raw"]))

    if not df_hist.empty:
        for idx, row in df_hist.iterrows():
            token = row["Token"]
            try: entry = float(row["Cena Wejścia"])
            except Exception: continue
            if entry <= 0: continue
            
            curr_price = float(price_map.get(token, entry))
            prev_max = float(row["Max Cena"]) if pd.notna(row["Max Cena"]) and str(row["Max Cena"]) != "-" and float(row["Max Cena"]) > 0 else entry
            new_max = max(prev_max, curr_price)
            df_hist.at[idx, "Max Cena"] = new_max
            
            max_gain_pct = ((new_max - entry) / entry) * 100
            curr_gain_pct = ((curr_price - entry) / entry) * 100
            
            if max_gain_pct >= 5.0 and str(row["TP 5%"]) == "-": df_hist.at[idx, "TP 5%"] = f"✅ {now_date}"
            if max_gain_pct >= 7.5 and str(row["TP 7.5%"]) == "-": df_hist.at[idx, "TP 7.5%"] = f"✅ {now_date}"
            if max_gain_pct >= 10.0 and str(row["TP 10%"]) == "-": df_hist.at[idx, "TP 10%"] = f"✅ {now_date}"
            
            start_date = pd.to_datetime(row["Data"])
            days_passed = (now_dt - start_date).days
            
            if max_gain_pct >= 10.0: df_hist.at[idx, "Status"] = "🎯 Zaliczone TP 10%"
            elif curr_gain_pct <= -5.0: df_hist.at[idx, "Status"] = "❌ SL (-5%)"
            elif days_passed >= 30: df_hist.at[idx, "Status"] = "⏱️ Wygasło (30d)"
            else: df_hist.at[idx, "Status"] = f"🔄 W toku ({days_passed}/30d)"

    active_tokens = set()
    last_signal_time = {}
    if not df_hist.empty:
        for _, row in df_hist.iterrows():
            tok, dt_val = row["Token"], pd.to_datetime(row["Data"])
            if tok not in last_signal_time or dt_val > last_signal_time[tok]: last_signal_time[tok] = dt_val
            if "W toku" in str(row["Status"]): active_tokens.add(tok)

    new_rows = []
    if not df_ml.empty and "Sygnał Hybrydowy" in df_ml.columns:
        for _, row in df_ml.iterrows():
            sig, token = str(row["Sygnał Hybrydowy"]), row["Token"]
            curr_rsi_1h = rsi_1h_map.get(token, 100.0)
            
            is_mocny_kup = "🟢 KUP (Mocny MTF)" in sig
            is_rsi_ready = curr_rsi_1h <= 45.0
            
            hours_since = (now_dt - last_signal_time[token]).total_seconds() / 3600.0 if token in last_signal_time else 999.0

            if is_mocny_kup and (token not in active_tokens) and is_rsi_ready and hours_since >= 24.0:
                try: price_clean = float(str(row["Cena ($)"]).replace("$", "").replace(",", ""))
                except Exception: continue
                new_rows.append({
                    "Data": now_full, "Token": token, "Typ Sygnału": sig, "Cena Wejścia": price_clean,
                    "Max Cena": price_clean, "TP 5%": "-", "TP 7.5%": "-", "TP 10%": "-", "Status": "🔄 W toku (0/30d)"
                })
                active_tokens.add(token)

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_hist = pd.concat([df_hist, df_new], ignore_index=True) if not df_hist.empty else df_new
    if not df_hist.empty:
        df_hist.to_csv(HISTORY_FILE, index=False)

def get_backtest_stats(target_pct_str):
    if not os.path.exists(HISTORY_FILE): return pd.DataFrame(), 0, 0, 0.0
    try: df_hist = pd.read_csv(HISTORY_FILE)
    except Exception: return pd.DataFrame(), 0, 0, 0.0
    if df_hist.empty: return df_hist, 0, 0, 0.0

    col_tp = f"TP {target_pct_str}"
    wins, total, results = 0, 0, []

    for _, row in df_hist.iterrows():
        entry = float(row.get("Cena Wejścia", 0))
        tp_hit = str(row.get(col_tp, "-"))
        status = str(row.get("Status", "-"))
        max_p = float(row.get("Max Cena", entry))
        max_gain = ((max_p - entry) / entry) * 100 if entry > 0 else 0.0

        if "✅" in tp_hit:
            wins += 1; total += 1
            res_status = f"✅ Osiągnięto {target_pct_str}"
        elif "SL" in status:
            total += 1
            res_status = "❌ SL (-5%)"
        elif "Wygasło" in status:
            total += 1
            res_status = "⏱️ Wygasło (30d)"
        else:
            res_status = f"🔄 W toku (Max: +{round(max_gain, 1)}%)"

        results.append({
            "Data Wejścia": row.get("Data"), "Token": row.get("Token"), "Sygnał": row.get("Typ Sygnału"),
            "Cena Wejścia ($)": fmt(entry), "Max Cena ($)": fmt(max_p), "Max Wzrost (%)": f"+{round(max_gain, 2)}%",
            f"Cel {target_pct_str}": tp_hit, "Status": res_status
        })

    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    return pd.DataFrame(results), total, wins, win_rate

def generuj_raport_ai(row_ta, row_ml=None):
    symbol = row_ta.get("Token")
    price_str = row_ta.get("Cena ($)")
    price_raw = float(row_ta.get("Price_Raw", 0))
    ema_raw = float(row_ta.get("EMA200_Raw", 0))
    rsi_1h = float(row_ta.get("RSI_1H_Raw", 50))
    rsi_4h = float(row_ta.get("RSI_4H_Raw", 50))
    rsi_12h = float(row_ta.get("RSI_12H_Raw", 50))
    mtf_score = row_ta.get("MTF Zgoda")
    change_24h = row_ta.get("24h (%)")
    support_str = row_ta.get("Wsparcie")
    resistance_str = row_ta.get("Opór")
    sl_str = row_ta.get("SL (ATR)")
    rr = row_ta.get("R:R")

    prognoza_mc, mc_range, prob_str, signal = "-", "-", "50.0%", "⏳ CZEKAJ / NEUTRALNY"
    if row_ml is not None:
        prognoza_mc = row_ml.get("Prognoza MC (24h)", "-")
        mc_range = row_ml.get("Zasięg Monte Carlo (95%)", "-")
        prob_str = row_ml.get("Prawdopodobieństwo", "50.0%")
        signal = row_ml.get("Sygnał Hybrydowy", "⏳ CZEKAJ / NEUTRALNY")

    trend_status = "🟢 Byczy (Cena powyżej EMA 200 H4)" if price_raw > ema_raw else "🔴 Niedźwiedzi / Boczny (Cena poniżej EMA 200 H4)"

    tp_5 = price_raw * 1.05
    tp_75 = price_raw * 1.075
    tp_10 = price_raw * 1.10

    return f"""
### 📑 RAPORT ANALITYCZNY MTF AI: {symbol}
**Aktualna cena:** `${price_str}` | **Zmiana 24h:** `{change_24h}%` | **Rekomendacja:** **{signal}**

---

#### 1. 📌 Podsumowanie i MTF Konsensus
* **Status Sygnału:** **{signal}**
* **Zgoda Multi-Timeframe:** `{mtf_score}` (Punkty schłodzenia na interwałach 1H-12H)
* **Struktura Rynku:** Token znajduje się w trendzie **{trend_status}**.

#### 2. 📊 Układ Wskaźników RSI
* **RSI 1H:** `{rsi_1h}` (Reakcja na żywo)
* **RSI 4H:** `{rsi_4h}` (Momentum średnioterminowe)
* **RSI 12H:** `{rsi_12h}` (Główny filtr kierunkowy)
* **Średnia EMA 200 (4H):** `${fmt(ema_raw)}`

#### 3. 🎲 Symulacja Monte Carlo (24h)
* **Średnia prognoza Monte Carlo:** `{prognoza_mc}`
* **Przewidywany zasięg (95% pewności):** `{mc_range}`
* **Statystyczna szansa wzrostu:** **{prob_str}**

#### 4. 🎯 Poziomy Docelowe Take Profit & Risk Management
* **Kluczowe Wsparcie:** `${support_str}` | **Kluczowy Opór:** `${resistance_str}`
* **Stop Loss (2x ATR):** `${sl_str}` | **R:R:** `{rr}`
* **Targety TP:** **TP1 (+5%):** `${fmt(tp_5)}` | **TP2 (+7.5%):** `${fmt(tp_75)}` | **TP3 (+10%):** `${fmt(tp_10)}`
"""

# ==========================================
# INTERFEJS GŁÓWNY (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane i obliczam Multi-Timeframe (1H, 2H, 4H, 12H)..."):
    df_ta, fng_val, fng_class, btc_dom, loaded_c, total_c = fetch_technical_analysis()
    df_ml = run_predictions(df_ta, fng_val)
    update_and_log_history(df_ml, df_ta)

col_t, col_d, col_f = st.columns([2.5, 1, 1])
col_t.title("📊 Analiza Krypto (Multi-Timeframe)")
col_t.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Załadowano: {loaded_c}/{total_c}")
col_d.metric("Dominacja BTC", f"{btc_dom}%")
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

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
            st.success("Wyczyszczono baze historii!")
            st.rerun()

df_ta_clean = df_ta.drop(columns=["RawScore", "Price_Raw", "EMA200_Raw", "RSI_1H_Raw", "RSI_4H_Raw", "RSI_12H_Raw", "MTF_Score"], errors="ignore")

# Rozdzielone Zakładki
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. Tabela Techniczna MTF", 
    "2. Sygnały Hybrydowe", 
    "3. ⚡ Aktywne Pozycje", 
    "4. 🗂️ Archiwum (Zamknięte)", 
    "5. 📈 Backtest"
])

with tab1:
    st.dataframe(df_ta_clean, use_container_width=True)

with tab2:
    st.dataframe(df_ml, use_container_width=True)

with tab3:
    st.subheader("⚡ Pozycje Otwarte (Śledzone w czasie rzeczywistym)")
    if os.path.exists(HISTORY_FILE):
        try:
            df_h = pd.read_csv(HISTORY_FILE)
            df_active = df_h[df_h["Status"].str.contains("W toku", na=False)]
            if not df_active.empty:
                st.dataframe(df_active.sort_values(by="Data", ascending=False), use_container_width=True)
            else:
                st.info("Brak aktywnych pozycji w tej chwili.")
        except Exception:
            st.info("Brak danych.")
    else:
        st.info("Brak otwartych pozycji.")

with tab4:
    st.subheader("🗂️ Historia Zamkniętych Pozycji (TP / SL / Wygasłe)")
    if os.path.exists(HISTORY_FILE):
        try:
            df_h = pd.read_csv(HISTORY_FILE)
            df_closed = df_h[~df_h["Status"].str.contains("W toku", na=False)]
            if not df_closed.empty:
                st.dataframe(df_closed.sort_values(by="Data", ascending=False), use_container_width=True)
            else:
                st.info("Archiwum zamkniętych pozycji jest puste — brak zakończonych transakcji.")
        except Exception:
            st.info("Błąd odczytu archiwum.")
    else:
        st.info("Brak pliku historii.")

with tab5:
    st.subheader("📈 Skuteczność Sygnałów (Backtest MTF)")
    t_choice = st.radio("Próg TP / SL:", ["5%", "7.5%", "10%"], horizontal=True, key="bt_rad")
    bt_df, tot, wins, wr = get_backtest_stats(t_choice)
    if tot > 0:
        k1, k2, k3 = st.columns(3)
        k1.metric("Zamknięte Sygnały", tot)
        k2.metric(f"Wygrane ({t_choice})", wins)
        k3.metric("Win Rate", f"{wr}%")
        st.dataframe(bt_df, use_container_width=True)
    else:
        st.info("Brak rozliczonych sygnałów w archiwum.")

if not df_ta.empty:
    st.divider()
    st.subheader("🤖 Raport Analityczny MTF AI")
    sel_ai = st.selectbox("Wybierz token do pełnego raportu:", df_ta["Token"].tolist(), key="ai_box")
    st.markdown(generuj_raport_ai(df_ta[df_ta["Token"] == sel_ai].iloc[0], df_ml[df_ml["Token"] == sel_ai].iloc[0] if not df_ml.empty else None))
