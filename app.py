import numpy as np
import pandas as pd
import requests
import streamlit as st
import os
import time
import datetime

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Analiza Krypto MTF PRO", layout="wide")

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
    return True

if not check_password():
    st.stop()

# ==========================================
# PANEL BOCZNY (ZARZĄDZANIE / RESET)
# ==========================================
with st.sidebar:
    st.subheader("⚙️ Narzędzia i Zarządzanie")
    if st.button("🗑️ Resetuj historię i zacznij od nowa", type="secondary"):
        HISTORY_FILE = "signals_history.csv"
        if os.path.exists(HISTORY_FILE):
            try: os.remove(HISTORY_FILE)
            except Exception: pass
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Wyczyszczono historię!")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🧠 O systemie MTF PRO")
    st.info("System łączy analizę wielu intermajęciowych ram czasowych (1H, 4H, 12H), wskaźnik siły względnej RSI, dynamiczne wsparcia oparte o EMA 200 oraz symulacje stochastyczne Monte Carlo w celu generowania wysokiej jakości sygnałów.")

# ==========================================
# LISTA TOKENÓW SPOT
# ==========================================
TOKENS = [
    {'symbol': 'ONDO', 'coinbase': 'ONDO-USD', 'gecko_id': 'ondo-finance'},
    {'symbol': 'INJ', 'coinbase': 'INJ-USD', 'gecko_id': 'injective-protocol'},
    {'symbol': 'LINK', 'coinbase': 'LINK-USD', 'gecko_id': 'chainlink'},
    {'symbol': 'RENDER', 'coinbase': 'RENDER-USD', 'gecko_id': 'render-token'},
    {'symbol': 'FET', 'coinbase': 'FET-USD', 'gecko_id': 'artificial-superintelligence-alliance'},
    {'symbol': 'BTC', 'coinbase': 'BTC-USD', 'gecko_id': 'bitcoin'},
    {'symbol': 'ETH', 'coinbase': 'ETH-USD', 'gecko_id': 'ethereum'},
    {'symbol': 'ENA', 'coinbase': 'ENA-USD', 'gecko_id': 'ethena'},
    {'symbol': 'PENDLE', 'coinbase': None, 'gecko_id': 'pendle'},
    {'symbol': 'NEAR', 'coinbase': 'NEAR-USD', 'gecko_id': 'near'},
    {'symbol': 'PLUME', 'coinbase': None, 'gecko_id': 'plume'},
    {'symbol': 'JUP', 'coinbase': None, 'gecko_id': 'jupiter-exchange-solana'},
    {'symbol': 'UNI', 'coinbase': 'UNI-USD', 'gecko_id': 'uniswap'},
    {'symbol': 'SEI', 'coinbase': 'SEI-USD', 'gecko_id': 'sei-network'},
    {'symbol': 'KTA', 'coinbase': None, 'gecko_id': 'keeta'},
    {'symbol': 'SOL', 'coinbase': 'SOL-USD', 'gecko_id': 'solana'}
]

def fmt(val):
    if pd.isna(val) or val is None: return "-"
    if isinstance(val, (int, float)):
        if abs(val) < 0.0001: return f"{val:.6f}"
        elif abs(val) < 1.0: return round(val, 4)
        else: return round(val, 2)
    return val

def get_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=4).json()
        return int(res['data'][0]['value']), res['data'][0]['value_classification']
    except Exception: return 50, "Neutral"

def get_global_market_data():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/global", headers={"User-Agent": "CryptoDashboard/2.0"}, timeout=4).json()
        return round(res['data']['market_cap_percentage']['btc'], 1)
    except Exception: return 55.0

# ==========================================
# POBIERANIE DANYCH
# ==========================================
def fetch_from_coinbase(symbol_pair):
    df_list = []
    end_time = datetime.datetime.utcnow()
    for _ in range(2):
        start_time = end_time - datetime.timedelta(hours=450)
        url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?start={start_time.isoformat()}&end={end_time.isoformat()}&granularity=3600"
        res = requests.get(url, headers={"User-Agent": "CryptoDashboard/2.0"}, timeout=5)
        if res.status_code == 200 and res.json():
            df_temp = pd.DataFrame(res.json(), columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
            df_list.append(df_temp)
            end_time = start_time
        else:
            break
        time.sleep(0.3)
        
    if df_list:
        df = pd.concat(df_list).drop_duplicates('timestamp')
        df['dt'] = pd.to_datetime(df['timestamp'], unit='s')
        return df.sort_values('dt').reset_index(drop=True)
    raise ValueError("Brak danych z Coinbase")

def fetch_from_coingecko(gecko_id):
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/ohlc?vs_currency=usd&days=40"
    res = requests.get(url, headers={"User-Agent": "CryptoDashboard/2.0"}, timeout=5)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close'])
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['volume'] = 0.0
    return df.sort_values('dt').reset_index(drop=True)

def get_simple_coingecko_price(gecko_id):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={gecko_id}&vs_currencies=usd,usd_24h_change"
        res = requests.get(url, headers={"User-Agent": "CryptoDashboard/2.0"}, timeout=4).json()
        if gecko_id in res:
            return float(res[gecko_id].get('usd', 0)), float(res[gecko_id].get('usd_24h_change', 0))
    except Exception: pass
    if gecko_id == 'keeta': return 0.08, 0.0
    return 1.0, 0.0

def get_candles_1h(token_info):
    if token_info['coinbase']:
        try: return fetch_from_coinbase(token_info['coinbase'])
        except Exception: pass
    try: return fetch_from_coingecko(token_info['gecko_id'])
    except Exception: return pd.DataFrame()

def resample_ohlc(df_1h, rule):
    df = df_1h.copy()
    df.set_index('dt', inplace=True)
    res = df.resample(rule).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
    return res

def calc_rsi(series, period=14):
    if len(series) < period: return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    val = 100 - (100 / (1 + (gain.iloc[-1] / (loss.iloc[-1] + 1e-9))))
    return float(val) if not pd.isna(val) else 50.0

@st.cache_data(ttl=300)
def fetch_technical_analysis():
    data = []
    hist_dfs = {}
    loaded_count = 0
    fng_val, fng_class = get_fear_and_greed()
    btc_dom = get_global_market_data()

    for item in TOKENS:
        symbol = item['symbol']
        gecko_id = item['gecko_id']
        try:
            df_1h = get_candles_1h(item)
            if df_1h.empty or len(df_1h) < 100:
                raise ValueError("Brak wystarczających danych")
                
            hist_dfs[symbol] = df_1h[['dt', 'high', 'low', 'close']]

            df_2h = resample_ohlc(df_1h, '2h')
            df_4h = resample_ohlc(df_1h, '4h')
            df_12h = resample_ohlc(df_1h, '12h')

            price = float(df_1h['close'].iloc[-1])
            change_24h = ((price - df_1h['close'].iloc[-24]) / df_1h['close'].iloc[-24]) * 100 if len(df_1h) >= 24 else 0.0

            rsi_1h = calc_rsi(df_1h['close'])
            rsi_4h = calc_rsi(df_4h['close'])
            rsi_12h = calc_rsi(df_12h['close'])
            
            rsi_4h_closed = calc_rsi(df_4h['close'].iloc[:-1])
            rsi_12h_closed = calc_rsi(df_12h['close'].iloc[:-1])

            ema200_4h = float(df_4h['close'].ewm(span=200, adjust=False).mean().iloc[-1])
            
            # Bollinger Bands %B
            bb_ma = df_4h['close'].rolling(20).mean().iloc[-1]
            bb_std = df_4h['close'].rolling(20).std().iloc[-1]
            bb_upper = bb_ma + (2 * bb_std)
            bb_lower = bb_ma - (2 * bb_std)
            bb_pct = (price - bb_lower) / (bb_upper - bb_lower + 1e-9)

            tr = pd.concat([df_4h['high'] - df_4h['low'], (df_4h['high'] - df_4h['close'].shift()).abs(), (df_4h['low'] - df_4h['close'].shift()).abs()], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])
            sl = price - (2 * atr)

            support = float(df_4h['low'].quantile(0.15))
            resistance = float(df_4h['high'].quantile(0.85))
            if price > ema200_4h: support = max(support, float(ema200_4h))
            elif price < ema200_4h: resistance = min(resistance, float(ema200_4h))
            
            vol_sma = df_4h['volume'].rolling(20).mean().iloc[-2] if 'volume' in df_4h.columns and df_4h['volume'].sum() > 0 else 0
            curr_vol = df_4h['volume'].iloc[-1]
            vol_spike = (curr_vol > (vol_sma * 1.5)) if vol_sma > 0 else True
            
            mtf_score = 0
            if rsi_1h <= 45: mtf_score += 1
            if rsi_4h_closed <= 52: mtf_score += 1
            if rsi_12h_closed <= 55: mtf_score += 1
            if vol_spike: mtf_score += 1
            
            data.append({
                "Token": symbol, "Cena ($)": fmt(price), "24h (%)": round(change_24h, 2),
                "RSI 1H": round(rsi_1h, 1), "RSI 4H": round(rsi_4h, 1), "RSI 12H": round(rsi_12h, 1),
                "MTF Zgoda": f"{mtf_score}/4", "EMA 200 (4H)": fmt(ema200_4h), "ATR": fmt(atr),
                "SL (ATR)": fmt(sl), "Wsparcie": fmt(support), "Opór": fmt(resistance),
                "Price_Raw": float(price), "EMA200_Raw": float(ema200_4h),
                "RSI_1H_Raw": float(rsi_1h), "RSI_4H_Closed": float(rsi_4h_closed), 
                "MTF_Score": mtf_score, "ATR_Raw": float(atr), "Vol_Spike": vol_spike,
                "BB_Pct": float(bb_pct)
            })
            loaded_count += 1
        except Exception:
            p, chg = get_simple_coingecko_price(gecko_id)
            data.append({
                "Token": symbol, "Cena ($)": fmt(p), "24h (%)": round(chg, 2),
                "RSI 1H": 50.0, "RSI 4H": 50.0, "RSI 12H": 50.0,
                "MTF Zgoda": "0/4", "EMA 200 (4H)": fmt(p), "ATR": fmt(p * 0.02),
                "SL (ATR)": fmt(p * 0.96), "Wsparcie": fmt(p * 0.95), "Opór": fmt(p * 1.05),
                "Price_Raw": p, "EMA200_Raw": p, "RSI_1H_Raw": 50.0, "RSI_4H_Closed": 50.0,
                "MTF_Score": 0, "ATR_Raw": p * 0.02, "Vol_Spike": False, "BB_Pct": 0.5
            })
            
    return pd.DataFrame(data), hist_dfs, fng_val, fng_class, btc_dom, loaded_count, len(TOKENS)

def run_predictions(df_ta):
    if df_ta.empty: return pd.DataFrame()
    rng = np.random.default_rng(seed=int(pd.Timestamp.now().strftime("%Y%m%d%H")))

    def analyze_row(row):
        price, atr = float(row["Price_Raw"]), float(row["ATR_Raw"])
        rsi_1h, rsi_4h_closed = float(row["RSI_1H_Raw"]), float(row["RSI_4H_Closed"])
        mtf_score, vol_spike = int(row["MTF_Score"]), row["Vol_Spike"]
        
        momentum_24h = float(row["24h (%)"]) / 100.0 if pd.notna(row["24h (%)"]) else 0.0
        hourly_drift = np.clip(momentum_24h / 24.0, -0.01, 0.01)
        if rsi_1h > 75: hourly_drift -= 0.002
        if rsi_1h < 25: hourly_drift += 0.002
        
        target_price = price * (1 + (hourly_drift * 24.0))
        shocks = rng.normal(hourly_drift, (atr / price) / np.sqrt(24), (3000, 24))
        final_prices = price * np.exp(np.cumsum(shocks, axis=1))[:, -1]
        prob = np.mean(final_prices > price) * 100

        is_uptrend = price > float(row["EMA200_Raw"])

        if mtf_score >= 3 and rsi_1h <= 45:
            if is_uptrend and vol_spike:
                signal = "🟢 KUP (Trend + Wolumen)"
            elif is_uptrend:
                signal = "🟢 KUP (Zgodnie z trendem)"
            else:
                signal = "🟡 SZANSA (Pod prąd)"
        elif rsi_1h >= 68 or rsi_4h_closed >= 72:
            signal = "🔴 SPRZEDAJ (Wykupienie)"
        else:
            signal = "⏳ CZEKAJ"

        return pd.Series([
            f"${fmt(target_price)}",
            f"${fmt(np.percentile(final_prices, 2.5))} - ${fmt(np.percentile(final_prices, 97.5))}",
            f"{round(prob, 1)}%", signal
        ])

    df_ml = df_ta.copy()
    df_ml[["Prognoza MC (24h)", "Zasięg MC (95%)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]] = df_ml.apply(analyze_row, axis=1)
    return df_ml[["Token", "Cena ($)", "RSI 1H", "RSI 4H", "RSI 12H", "MTF Zgoda", "Prognoza MC (24h)", "Zasięg MC (95%)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]]

# ==========================================
# HISTORIA I WSTECZNE SKANOWANIE EKSTREMÓW
# ==========================================
HISTORY_FILE = "signals_history.csv"

def update_and_log_history(df_ml, df_ta, hist_dfs):
    now_dt = pd.Timestamp.now()
    now_full = now_dt.strftime("%Y-%m-%d %H:%M")
    
    df_hist = pd.DataFrame()
    if os.path.exists(HISTORY_FILE):
        try: df_hist = pd.read_csv(HISTORY_FILE)
        except Exception: pass

    req_cols = ["Data", "Token", "Typ Sygnału", "Cena Wejścia", "Ekstremum Ceny", "ATR Wejścia", "TP1", "TP2", "TP3", "Status"]
    for col in req_cols:
        if col not in df_hist.columns:
            df_hist[col] = "-" if "TP" in col else ("🔄 W toku" if col == "Status" else "")

    price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))
    atr_map = dict(zip(df_ta["Token"], df_ta["ATR_Raw"]))
    rsi_1h_map = dict(zip(df_ta["Token"], df_ta["RSI_1H_Raw"]))

    if not df_hist.empty:
        for idx, row in df_hist.iterrows():
            token = row["Token"]
            typ_sig = str(row.get("Typ Sygnału", ""))
            kierunek = "SHORT" if "SPRZEDAJ" in typ_sig else "LONG"
            
            try:
                entry = float(row.get("Cena Wejścia"))
            except (ValueError, TypeError):
                entry = 0.0
            if entry <= 0: continue
            
            curr_price = float(price_map.get(token, entry))
            
            try:
                prev_extr = float(row.get("Ekstremum Ceny"))
            except (ValueError, TypeError):
                prev_extr = entry
            
            historical_max_min = prev_extr
            if token in hist_dfs and "W toku" in str(row["Status"]):
                try:
                    entry_date = pd.to_datetime(row["Data"])
                    df_token_hist = hist_dfs[token]
                    post_entry_df = df_token_hist[df_token_hist['dt'] >= entry_date]
                    if not post_entry_df.empty:
                        if kierunek == "LONG":
                            historical_max_min = max(prev_extr, float(post_entry_df['high'].max()))
                        else:
                            historical_max_min = min(prev_extr, float(post_entry_df['low'].min()))
                except Exception: pass

            if kierunek == "LONG":
                new_extr = max(historical_max_min, curr_price)
                max_gain_pct = ((new_extr - entry) / entry) * 100
                curr_gain_pct = ((curr_price - entry) / entry) * 100
            else:
                new_extr = min(historical_max_min, curr_price) if historical_max_min > 0 else curr_price
                max_gain_pct = ((entry - new_extr) / entry) * 100
                curr_gain_pct = ((entry - curr_price) / entry) * 100

            df_hist.at[idx, "Ekstremum Ceny"] = float(new_extr)

            try:
                entry_atr = float(row.get("ATR Wejścia"))
                if pd.isna(entry_atr) or entry_atr <= 0:
                    entry_atr = entry * 0.02
            except (ValueError, TypeError):
                entry_atr = entry * 0.02

            tp1_pct = ((1.5 * entry_atr) / entry) * 100
            tp2_pct = ((3.0 * entry_atr) / entry) * 100
            tp3_pct = ((5.0 * entry_atr) / entry) * 100
            sl_pct = -((2.0 * entry_atr) / entry) * 100

            if max_gain_pct >= tp1_pct and str(row["TP1"]) == "-": df_hist.at[idx, "TP1"] = f"✅ {now_dt.strftime('%Y-%m-%d')}"
            if max_gain_pct >= tp2_pct and str(row["TP2"]) == "-": df_hist.at[idx, "TP2"] = f"✅ {now_dt.strftime('%Y-%m-%d')}"
            if max_gain_pct >= tp3_pct and str(row["TP3"]) == "-": df_hist.at[idx, "TP3"] = f"✅ {now_dt.strftime('%Y-%m-%d')}"
            
            try: days_passed = (now_dt - pd.to_datetime(row["Data"])).days
            except Exception: days_passed = 0
            
            if max_gain_pct >= tp3_pct: df_hist.at[idx, "Status"] = "🎯 Zaliczone TP3"
            elif curr_gain_pct <= sl_pct: df_hist.at[idx, "Status"] = f"❌ SL ({round(sl_pct, 1)}%)"
            elif days_passed >= 30: df_hist.at[idx, "Status"] = "⏱️ Wygasło"
            else: df_hist.at[idx, "Status"] = f"🔄 W toku (Max: {round(max_gain_pct, 1)}%)"

    active_tokens = set()
    last_signal_time = {}
    if not df_hist.empty:
        for _, row in df_hist.iterrows():
            tok = row["Token"]
            try:
                dt_val = pd.to_datetime(row["Data"])
                if tok not in last_signal_time or dt_val > last_signal_time[tok]: last_signal_time[tok] = dt_val
            except Exception: pass
            if "W toku" in str(row["Status"]): active_tokens.add(tok)

    new_rows = []
    if not df_ml.empty and "Sygnał Hybrydowy" in df_ml.columns:
        for _, row in df_ml.iterrows():
            sig, token = str(row["Sygnał Hybrydowy"]), row["Token"]
            curr_rsi_1h = rsi_1h_map.get(token, 50.0)
            curr_atr = atr_map.get(token, 0.02)
            
            is_kup = "🟢 KUP" in sig or "🟡 SZANSA" in sig
            is_sprzedaj = "🔴 SPRZEDAJ" in sig
            
            hours_since = (now_dt - last_signal_time[token]).total_seconds() / 3600.0 if token in last_signal_time else 999.0

            if (token not in active_tokens) and hours_since >= 24.0:
                try: price_clean = float(str(row["Cena ($)"]).replace("$", "").replace(",", ""))
                except Exception: continue

                if is_kup and curr_rsi_1h <= 45.0:
                    new_rows.append({"Data": now_full, "Token": token, "Typ Sygnału": sig, "Cena Wejścia": price_clean, "Ekstremum Ceny": price_clean, "ATR Wejścia": curr_atr, "TP1": "-", "TP2": "-", "TP3": "-", "Status": "🔄 W toku"})
                    active_tokens.add(token)
                elif is_sprzedaj and curr_rsi_1h >= 65.0:
                    new_rows.append({"Data": now_full, "Token": token, "Typ Sygnału": sig, "Cena Wejścia": price_clean, "Ekstremum Ceny": price_clean, "ATR Wejścia": curr_atr, "TP1": "-", "TP2": "-", "TP3": "-", "Status": "🔄 W toku"})
                    active_tokens.add(token)

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_hist = pd.concat([df_hist, df_new], ignore_index=True) if not df_hist.empty else df_new
    if not df_hist.empty:
        df_hist.to_csv(HISTORY_FILE, index=False)

def get_backtest_stats(target_str):
    if not os.path.exists(HISTORY_FILE): return pd.DataFrame(), 0, 0, 0.0
    try: df_hist = pd.read_csv(HISTORY_FILE)
    except Exception: return pd.DataFrame(), 0, 0, 0.0
    if df_hist.empty: return df_hist, 0, 0, 0.0

    col_tp = target_str.split(" ")[0]
    wins, total, results = 0, 0, []

    for _, row in df_hist.iterrows():
        try:
            entry = float(row.get("Cena Wejścia"))
        except (ValueError, TypeError):
            entry = 0.0
        try:
            extr_p = float(row.get("Ekstremum Ceny"))
        except (ValueError, TypeError):
            extr_p = entry
        if entry <= 0: continue
            
        tp_hit = str(row.get(col_tp, "-"))
        status = str(row.get("Status", "-"))
        kierunek = "SHORT" if "SPRZEDAJ" in str(row.get("Typ Sygnału", "")) else "LONG"
        
        max_gain = ((extr_p - entry) / entry) * 100 if kierunek == "LONG" else ((entry - extr_p) / entry) * 100
        if "✅" in tp_hit:
            wins += 1; total += 1
            res_status = f"✅ Zaliczone"
        elif "SL" in status:
            total += 1
            res_status = status
        elif "Wygasło" in status:
            total += 1
            res_status = "⏱️ Wygasło"
        else: res_status = f"🔄 W toku (+{round(max_gain, 1)}%)"

        results.append({
            "Data Wejścia": row.get("Data"), "Token": row.get("Token"), "Sygnał": row.get("Typ Sygnału"),
            "Cena Wejścia": fmt(entry), "Ekstremum": fmt(extr_p), "Max Zysk (%)": f"+{round(max_gain, 2)}%",
            f"Cel {col_tp}": tp_hit, "Status": res_status
        })

    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    return pd.DataFrame(results), total, wins, win_rate

# ==========================================
# UI APLIKACJI
# ==========================================
with st.spinner("🔄 Pobieram zoptymalizowaną historię, obliczam EMA 200 i sprawdzam wolumen..."):
    df_ta, hist_dfs, fng_val, fng_class, btc_dom, loaded_c, total_c = fetch_technical_analysis()
    df_ml = run_predictions(df_ta)
    update_and_log_history(df_ml, df_ta, hist_dfs)

col_t, col_d1, col_f = st.columns([2.0, 1, 1])
col_t.title("📊 Analiza Krypto MTF PRO")
col_t.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Załadowano: {loaded_c}/{total_c}")
col_d1.metric("Dominacja BTC", f"{btc_dom}%")
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

st.markdown("---")
if st.button("🔄 Odśwież dane", type="primary"):
    st.cache_data.clear()
    st.rerun()

df_ta_clean = df_ta.drop(columns=["Price_Raw", "EMA200_Raw", "RSI_1H_Raw", "RSI_4H_Closed", "MTF_Score", "ATR_Raw", "Vol_Spike", "BB_Pct"], errors="ignore")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["1. Tabela Techniczna", "2. Sygnały", "3. ⚡ Aktywne Pozycje", "4. 🗂️ Archiwum", "5. 📈 Backtest", "6. 📝 Analiza Pisemna i Wnioski"])

with tab1: st.dataframe(df_ta_clean, use_container_width=True)
with tab2: st.dataframe(df_ml, use_container_width=True)

with tab3:
    if os.path.exists(HISTORY_FILE):
        try:
            df_h = pd.read_csv(HISTORY_FILE)
            df_active = df_h[df_h["Status"].str.contains("W toku", na=False)]
            if not df_active.empty: st.dataframe(df_active.sort_values(by="Data", ascending=False), use_container_width=True)
            else: st.info("Brak aktywnych pozycji.")
        except Exception: st.info("Błąd.")

with tab4:
    if os.path.exists(HISTORY_FILE):
        try:
            df_h = pd.read_csv(HISTORY_FILE)
            df_closed = df_h[~df_h["Status"].str.contains("W toku", na=False)]
            if not df_closed.empty: st.dataframe(df_closed.sort_values(by="Data", ascending=False), use_container_width=True)
            else: st.info("Archiwum puste.")
        except Exception: st.info("Błąd.")

with tab5:
    t_choice = st.radio("Próg TP:", ["TP1 (1.5 ATR)", "TP2 (3 ATR)", "TP3 (5 ATR)"], horizontal=True)
    bt_df, tot, wins, wr = get_backtest_stats(t_choice)
    if tot > 0:
        k1, k2, k3 = st.columns(3)
        k1.metric("Zamknięte Sygnały", tot)
        k2.metric("Wygrane", wins)
        k3.metric("Win Rate", f"{wr}%")
        st.dataframe(bt_df, use_container_width=True)
    else: st.info("Brak rozliczonych sygnałów.")

with tab6:
    st.subheader("📝 Szczegółowy Raport i Wnioski Rynkowe w Czasie Rzeczywistym")
    
    selected_token = st.selectbox("Wybierz token do szczegółowej analizy pisemnej:", df_ta["Token"].tolist())
    row_data = df_ta[df_ta["Token"] == selected_token].iloc[0]
    
    price = row_data["Price_Raw"]
    ema = row_data["EMA200_Raw"]
    rsi1h = row_data["RSI_1H_Raw"]
    rsi4h = row_data["RSI_4H_Closed"]
    mtf = row_data["MTF_Score"]
    sup = row_data["Wsparcie"]
    res = row_data["Opór"]
    atr = row_data["ATR_Raw"]
    bb_p = row_data["BB_Pct"]
    
    trend_desc = "wzrostowym (Cena powyżej długoterminowej EMA 200 na interwały 4H)" if price > ema else "spadkowym (Cena poniżej EMA 200, presja niedźwiedzi)"
    momentum_desc = "wykupienia" if rsi1h > 65 else ("wyprzedania" if rsi1h < 35 else "neutralnym")
    
    st.markdown(f"### 📄 Raport Analityczny AI dla: **{selected_token}**")
    
    st.markdown(f"""
    * **Struktura rynku i Trend:** Aktywo znajduje się w trendzie **{trend_desc}**. Wskazuje to na dominację sił {'byczych' if price > ema else 'niedźwiedzich'} w średnim horyzoncie czasowym.
    * **Wskaźnik Momentum (RSI):** RSI dla interwału 1H wynosi **{round(rsi1h, 1)}**, co klasyfikuje bieżący stan jako **{momentum_desc}**. Na interwale 4H RSI zamknęło się na poziomie **{round(rsi4h, 1)}**.
    * **Zgoda Wieloramowa (MTF Score):** Wynik zgodności ramy wielointerwałowej wynosi **{mtf}/4**, co określa siłę konfluencji sygnału technicznego.
    * **Poziomy Krytyczne:** Najbliższe istotne wsparcie techniczne wyznaczono na poziomie **${fmt(sup)}**, natomiast kluczowy opór znajduje się na wysokości **${fmt(res)}**.
    * **Zarządzanie Ryzykiem (ATR):** Średni zasięg zmienności (ATR 4H) wynosi **${fmt(atr)}**. Zalecany poziom obrony (Stop Loss) znajduje się w okolicach **${fmt(price - 2*atr)}**.
    """)
    
    st.markdown("---")
    st.markdown("### 💡 Kluczowe Wnioski i Strategia Inwestycyjna")
    
    if mtf >= 3 and rsi1h <= 45:
        st.success(f"**Wniosek:** Token generuje silny sygnał pro-wzrostowy (Buy Setup). Konfluencja niskiego RSI oraz wsparcia strukturalnego stwarza korzystny stosunek zysku do ryzyka (Risk/Reward) przy wejściu długim (Long).")
    elif rsi1h >= 68:
        st.warning(f"**Wniosek:** Widoczne silne wyczerpanie ruchu wzrostowego i wykupienie krótkoterminowe. Wskazana ostrożność, rozważenie realizacji części zysków lub przygotowanie się pod korektę.")
    else:
        st.info(f"**Wniosek:** Rynek w stanie konsolidacji lub braku klarownego układu sił. Zalecane oczekiwanie na test kluczowych poziomów wsparcia/oporu przed zajęciem pozycji.")
