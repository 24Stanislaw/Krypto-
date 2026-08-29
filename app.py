import numpy as np
import pandas as pd
import requests
import streamlit as st
import os

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Analiza", layout="wide")

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
        st.text_input("Podaj hasło dostępu, aby otworzyć panel:", type="password", on_change=password_entered, key="password_input")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Dostęp Zastrzeżony")
        st.text_input("Podaj hasło dostępu, aby otworzyć panel:", type="password", on_change=password_entered, key="password_input")
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
        if abs(val) < 1.0:
            return round(val, 6)
        elif abs(val) < 100.0:
            return round(val, 4)
        else:
            return round(val, 2)
    return val

def get_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=4).json()
        val = int(res['data'][0]['value'])
        classification = res['data'][0]['value_classification']
        return val, classification
    except Exception:
        return 50, "Neutral"

def get_global_market_data():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/global", headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4).json()
        btc_dom = res['data']['market_cap_percentage']['btc']
        return round(btc_dom, 1)
    except Exception:
        return 55.0

def fetch_from_coinbase(symbol_pair, granularity=3600):
    url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?granularity={granularity}"
    headers = {"User-Agent": "CryptoDashboard/1.0"}
    res = requests.get(url, headers=headers, timeout=4)
    res.raise_for_status()
    df = pd.DataFrame(res.json(), columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
    return df.sort_values('timestamp').reset_index(drop=True)

def fetch_from_coingecko(gecko_id):
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/ohlc?vs_currency=usd&days=1"
    headers = {"User-Agent": "CryptoDashboard/1.0"}
    res = requests.get(url, headers=headers, timeout=5)
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
            ema200_d1 = df_d1['close'].ewm(span=span_period, adjust=False).mean().iloc[-1]
            last_price = df_d1['close'].iloc[-1]
            return last_price, ema200_d1
    except Exception:
        pass
    return None, None

def get_deribit_dvol(currency="BTC"):
    try:
        url = f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={currency}&resolution=1D"
        headers = {"User-Agent": "CryptoDashboard/1.0"}
        res = requests.get(url, headers=headers, timeout=4).json()
        if 'result' in res and 'data' in res['result'] and len(res['result']['data']) > 0:
            return float(res['result']['data'][-1][4])
    except Exception:
        pass
    return 60.0

@st.cache_data(ttl=60)
def fetch_technical_analysis():
    data = []
    loaded_count = 0
    total_count = len(TOKENS)
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
            
            tr = pd.concat([
                df['high'] - df['low'],
                (df['high'] - df['close'].shift()).abs(),
                (df['low'] - df['close'].shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(min(14, len(df))).mean().iloc[-1]
            
            span_period = min(200, len(df))
            ema200 = df['close'].ewm(span=span_period, adjust=False).mean().iloc[-1]

            sma20 = df['close'].rolling(min(20, len(df))).mean().iloc[-1]
            std20 = df['close'].rolling(min(20, len(df))).std().iloc[-1]
            upper_bb = sma20 + (std20 * 2)
            lower_bb = sma20 - (std20 * 2)
            pct_b = (price - lower_bb) / (upper_bb - lower_bb + 1e-9)

            if len(df) > 2 and df['volume'].sum() > 0:
                vol_ma = df['volume'].iloc[:-1].rolling(min(20, len(df)-1)).mean().iloc[-1]
                last_vol = df['volume'].iloc[-2]
                vol_surge = (last_vol / vol_ma) if vol_ma > 0 else 1.0
            else:
                vol_surge = 1.0

            sl = price - (2 * atr)
            support = df['low'].min()
            resistance = df['high'].max()
            
            risk = price - sl
            reward = resistance - price
            rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1
            rr_str = f"1:{rr_val}"
            
            atr_pct = (atr / price) * 100
            dynamic_rsi_thresh = 30.0 + min(max(atr_pct * 1.5, 0.0), 10.0)
            
            rsi_score = (dynamic_rsi_thresh - rsi) * 0.9 + 5.0 if rsi < dynamic_rsi_thresh else (-(rsi - 70) * 0.8 if rsi > 70 else (rsi - 50) * 0.2)
            support_score = max(0.0, (3.0 - (((price - support) / price) * 100)) * 2.5)
            fng_score = (50 - fng_val) * 0.2
            ema_score = 5.0 if price > ema200 else -5.0
            
            calculated_chance = 50.0 + rsi_score + support_score + fng_score + ema_score + (change_24h * 0.1)
            chance = round(min(max(calculated_chance, 20.0), 90.0), 1)
            
            rr_weight = min(max(rr_val / 2.0, 0.5), 1.3)
            okazja_score = round(min(max(chance * rr_weight, 10.0), 99.0), 1)

            okazja_str = f"🔥 {okazja_score}%" if okazja_score >= 70.0 else (f"👀 {okazja_score}%" if okazja_score >= 50.0 else f"⚪ {okazja_score}%")

            data.append({
                "Token": item['symbol'],
                "Cena ($)": fmt(price),
                "24h (%)": round(change_24h, 2),
                "RSI": round(rsi, 2),
                "%B (BB)": round(pct_b, 2),
                "EMA 200": fmt(ema200),
                "Wolumen (x)": f"{round(vol_surge, 1)}x",
                "Vol_Surge_Raw": vol_surge,
                "ATR": fmt(atr),
                "SL (ATR)": fmt(sl),
                "Wsparcie": fmt(support),
                "Opór": fmt(resistance),
                "R:R": rr_str,
                "Szansa (%)": f"{chance}%",
                "Atrakcyjność (%)": okazja_str,
                "RawScore": okazja_score,
                "Price_Raw": price,
                "EMA200_Raw": ema200,
                "BTC_D1_Price": btc_d1_price,
                "BTC_D1_EMA200": btc_d1_ema200
            })
            loaded_count += 1
        except Exception:
            continue
            
    return pd.DataFrame(data), fng_val, fng_class, btc_dom, btc_d1_price, btc_d1_ema200, loaded_count, total_count

def run_predictions(df_ta, fng_val):
    if df_ta.empty or "RawScore" not in df_ta.columns:
        return pd.DataFrame({"Komunikat": ["Brak danych do prognozy."]})

    dvol_btc = get_deribit_dvol("BTC")
    btc_row = df_ta[df_ta["Token"] == "BTC"]
    
    btc_bullish_macro = True
    btc_vol_ratio = 0.01
    
    if not df_ta.empty and "BTC_D1_Price" in df_ta.columns and df_ta["BTC_D1_Price"].iloc[0] is not None:
        b_price = float(df_ta["BTC_D1_Price"].iloc[0])
        b_ema_d1 = float(df_ta["BTC_D1_EMA200"].iloc[0])
        btc_bullish_macro = b_price >= (b_ema_d1 * 0.985)

    if not btc_row.empty:
        btc_vol_ratio = (float(btc_row["ATR"].values[0]) / float(btc_row["Price_Raw"].values[0]))

    seed_val = int(pd.Timestamp.now().strftime("%Y%m%d%H"))
    rng = np.random.default_rng(seed=seed_val)

    def analyze_row(row):
        symbol = row["Token"]
        price = float(row["Price_Raw"])
        atr = float(row["ATR"])
        rsi = float(row["RSI"])
        change = float(row["24h (%)"])
        pct_b = float(row["%B (BB)"])
        vol_surge = float(row["Vol_Surge_Raw"])

        atr_pct = (atr / price) * 100
        dynamic_rsi_thresh = 30.0 + min(max(atr_pct * 1.5, 0.0), 10.0)

        rsi_bounce = (dynamic_rsi_thresh - rsi) * 0.0025 if rsi < dynamic_rsi_thresh else (-(rsi - 70) * 0.0020 if rsi > 70 else 0)
        bb_bounce = (0.1 - pct_b) * 0.005 if pct_b < 0.1 else (-(pct_b - 0.9) * 0.005 if pct_b > 0.9 else 0)

        expected_change = (change / 100 * 0.05) + rsi_bounce + bb_bounce
        target_price = price * (1 + expected_change)

        shocks = rng.normal(expected_change / 24.0, (atr / price) / np.sqrt(24), (10000, 24))
        final_prices = price * np.exp(np.cumsum(shocks, axis=1))[:, -1]

        prob = np.mean(final_prices > price) * 100
        token_iv = dvol_btc * ((atr / price) / btc_vol_ratio)
        sigma_24h = (token_iv / 100.0) / np.sqrt(365)

        if expected_change > 0:
            if prob >= 55.0 or rsi < 30 or fng_val < 25:
                if symbol != "BTC" and not btc_bullish_macro:
                    signal = "📈 KUP (Słaby)"
                elif vol_surge < 1.0 and symbol != "BTC":
                    signal = "📈 KUP (Słaby)"
                else:
                    signal = "🟢 KUP (Mocny)"
            elif prob >= 50.0:
                signal = "📈 KUP (Słaby)"
            else:
                signal = "⏳ CZEKAJ / NEUTRALNY"
        else:
            if rsi <= 45:
                signal = "⏳ CZEKAJ / NEUTRALNY"
            else:
                signal = "🔴 SPRZEDAJ" if prob < 42.0 else "⏳ CZEKAJ / NEUTRALNY"

        return pd.Series([
            f"${fmt(target_price)}",
            f"${fmt(np.percentile(final_prices, 2.5))} - ${fmt(np.percentile(final_prices, 97.5))}",
            f"${fmt(price * (1.0 - 1.96 * sigma_24h))} - ${fmt(price * (1.0 + 1.96 * sigma_24h))}",
            f"{round(token_iv, 1)}%",
            f"{round(prob, 1)}%",
            signal
        ])

    df_ml = df_ta.copy()
    df_ml[["Prognoza ML (24h)", "Zasięg Monte Carlo (95%)", "Zasięg Opcji DVOL (95%)", "Implikowana Zmienność (IV)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]] = df_ml.apply(analyze_row, axis=1)
    
    return df_ml[["Token", "Cena ($)", "Prognoza ML (24h)", "Zasięg Monte Carlo (95%)", "Zasięg Opcji DVOL (95%)", "Implikowana Zmienność (IV)", "Prawdopodobieństwo", "Sygnał Hybrydowy"]]

# ==========================================
# MODUŁ ŚLEDZENIA SKUTECZNOŚCI (BACKTEST)
# ==========================================
HISTORY_FILE = "signals_history.csv"

def log_signals_to_history(df_ml):
    if df_ml.empty or "Sygnał Hybrydowy" not in df_ml.columns:
        return
    
    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    new_rows = []
    
    for _, row in df_ml.iterrows():
        sig = row["Sygnał Hybrydowy"]
        if "KUP" in sig or "SPRZEDAJ" in sig:
            try:
                price_clean = float(str(row["Cena ($)"]).replace("$", "").replace(",", ""))
            except Exception:
                continue
                
            new_rows.append({
                "Data": now_str,
                "Token": row["Token"],
                "Typ Sygnału": sig,
                "Cena Wejścia": price_clean,
                "Cena Aktualna": price_clean
            })
            
    if not new_rows:
        return
        
    df_new = pd.DataFrame(new_rows)
    
    if os.path.exists(HISTORY_FILE):
        try:
            df_old = pd.read_csv(HISTORY_FILE)
            # Zapisujemy tylko unikalne wpisy z danego dnia/godziny dla tokena, żeby nie spamować
            combined = pd.concat([df_old, df_new]).drop_duplicates(subset=["Data", "Token", "Typ Sygnału"], keep="last")
            combined.to_csv(HISTORY_FILE, index=False)
        except Exception:
            df_new.to_csv(HISTORY_FILE, index=False)
    else:
        df_new.to_csv(HISTORY_FILE, index=False)

def get_backtest_stats(df_current_prices):
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame(), 0, 0, 0.0
        
    try:
        df_hist = pd.read_csv(HISTORY_FILE)
    except Exception:
        return pd.DataFrame(), 0, 0, 0.0
        
    if df_hist.empty:
        return df_hist, 0, 0, 0.0

    price_map = dict(zip(df_current_prices["Token"], df_current_prices["Price_Raw"]))
    
    results = []
    wins = 0
    total = 0
    
    for _, row in df_hist.iterrows():
        token = row["Token"]
        entry_price = float(row["Cena Wejścia"])
        sig_type = row["Typ Sygnału"]
        
        current_price = price_map.get(token, entry_price)
        change_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Ocena sukcesu: dla KUP chcemy wzrostu, dla SPRZEDAJ spadku
        if "KUP" in sig_type:
            is_win = change_pct > 0
        else:
            is_win = change_pct < 0
            
        if is_win:
            wins += 1
        total += 1
        
        results.append({
            "Data": row["Data"],
            "Token": token,
            "Sygnał": sig_type,
            "Cena Wejścia ($)": fmt(entry_price),
            "Cena Obecna ($)": fmt(current_price),
            "Wynik (%)": round(change_pct, 2),
            "Status": "✅ Trafiony" if is_win else "❌ Stratny"
        })
        
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
    return pd.DataFrame(results), total, wins, win_rate

# ==========================================
# RAZBUDOWANY RAPORT ANALITYCZNY AI
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None):
    symbol = row_ta.get("Token", "Token")
    price_val = row_ta.get("Price_Raw", 0.0)
    price_str = str(row_ta.get("Cena ($)", "-"))
    rsi = float(row_ta.get("RSI", 50.0))
    sl_str = str(row_ta.get("SL (ATR)", "-"))
    support_str = str(row_ta.get("Wsparcie", "-"))
    resistance_str = str(row_ta.get("Opór", "-"))
    rr = str(row_ta.get("R:R", "-"))
    vol_str = str(row_ta.get("Wolumen (x)", "1.0x"))
    change_24h = row_ta.get("24h (%)", 0.0)
    ema200_val = row_ta.get("EMA200_Raw", 0.0)
    pct_b = float(row_ta.get("%B (BB)", 0.5))

    if isinstance(price_val, (float, int)) and isinstance(ema200_val, (float, int)) and ema200_val > 0:
        trend_desc = "wzrostowym (cena znajduje się powyżej kluczowej średniej EMA 200, co historycznie faworyzuje długie pozycje)" if price_val > ema200_val else "spadkowym (cena poniżej EMA 200 generuje techniczną presję podażową)"
    else:
        trend_desc = "bocznym lub brakuje wyraźnego potwierdzenia kierunku"

    if rsi < 30:
        rsi_desc = f"na ekstremalnie niskim poziomie **{rsi}**. Świadczy to o głębokim wyprzedaniu i potencjalnej rynkowej panice."
    elif rsi > 70:
        rsi_desc = f"na podwyższonym poziomie **{rsi}**. Rynek jest aktualnie mocno wykupiony, rośnie ryzyko korekty."
    else:
        rsi_desc = f"na zrównoważonym poziomie **{rsi}**."

    prog, mc, iv, prob, signal = "-", "-", "-", "-", "-"
    prob_num = 50.0
    
    if row_ml is not None:
        prog = str(row_ml.get("Prognoza ML (24h)", "-"))
        mc = str(row_ml.get("Zasięg Monte Carlo (95%)", "-"))
        iv = str(row_ml.get("Implikowana Zmienność (IV)", "-"))
        prob = str(row_ml.get("Prawdopodobieństwo", "-"))
        signal = str(row_ml.get("Sygnał Hybrydowy", "-"))
        try:
            prob_num = float(prob.replace("%", ""))
        except Exception:
            pass

    if prob_num > 55:
        scenariusz = f"Najbardziej prawdopodobnym wydarzeniem jest **zdecydowany atak kapitału w kierunku oporu ${resistance_str}**."
    elif prob_num < 45:
        scenariusz = f"Najbardziej realistycznym wariantem jest **dalsze osuwanie się kursu i test wsparcia ${support_str}**."
    else:
        scenariusz = f"Kurs najpewniej utknie w **bocznym przedziale ({mc})**."

    pewnosc = max(prob_num, 100 - prob_num)
    if "KUP (Mocny)" in signal:
        decyzja = "🟢 **ZDECYDOWANIE KUPUJ**"
    elif "KUP (Słaby)" in signal:
        decyzja = "📈 **KUPUJ OSTROŻNIE (DCA)**"
    elif "SPRZEDAJ" in signal:
        decyzja = "🔴 **NIE KUPUJ / SPRZEDAWAJ**"
    else:
        decyzja = "⏳ **WSTRZYMAJ SIĘ / CZEKAJ**"

    return f"""
📑 **RAPORT AI: {symbol}** (${price_str}, Zmiana 24h: {change_24h}%)
Trend strukturalny: **{trend_desc}**

* **Momentum (RSI):** {rsi_desc}
* **Prawdopodobieństwo Sukcesu:** **{prob}**
* **Zasięg Symulacji (Monte Carlo):** {mc}

---
🔮 **NAJBARDZIEJ PRAWDOPODOBNA PRZYSZŁOŚĆ**
{scenariusz}

---
💡 **WERDYKT I REKOMENDACJA**
* **Decyzja:** {decyzja}
* **Pewność Sygnału:** **{pewnosc:.1f}%**
* **Stosunek Zysku do Ryzyka (R:R):** {rr}
* **Wymagany Stop Loss:** Ustaw bezwzględnie na poziomie **${sl_str}**.
"""

# ==========================================
# INTERFEJS UŻYTKOWNIKA (UI)
# ==========================================
df_ta, fng_val, fng_class, btc_dom, btc_d1_price, btc_d1_ema200, loaded_count, total_count = fetch_technical_analysis()

col_title, col_btc_macro, col_dom, col_fng = st.columns([2.0, 1.1, 0.9, 1.0])
with col_title:
    st.title("📊 Analiza")
    st.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Tokeny: {loaded_count}/{total_count}")

with col_btc_macro:
    if btc_d1_price and btc_d1_ema200:
        is_bullish = btc_d1_price >= (btc_d1_ema200 * 0.985)
        status_label = "🟢 Byczy" if is_bullish else "🔴 Niedźwiedzi"
        st.metric(label="BTC Trend D1", value=status_label, delta=f"${fmt(btc_d1_price)}")
    else:
        st.metric(label="BTC Trend D1", value="Brak danych")

with col_dom:
    st.metric(label="Dominacja BTC", value=f"{btc_dom}%", delta="Kapitał Spot")

with col_fng:
    st.metric(label="Fear & Greed", value=f"{fng_val}/100", delta=fng_class)

if not df_ta.empty:
    st.markdown("---")
    selected_token = st.selectbox("📱 Szybki podgląd wybranego tokena:", df_ta["Token"].tolist())
    token_row = df_ta[df_ta["Token"] == selected_token].iloc[0]
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Cena Spot", token_row["Cena ($)"])
    m2.metric("Zmiana 24h", f"{token_row['24h (%)']}%")
    m3.metric("RSI (14)", token_row["RSI"])
    m4.metric("Atrakcyjność", token_row["Atrakcyjność (%)"])
    m5.metric("Sugerowany SL", token_row["SL (ATR)"])

st.markdown("---")
if st.button("🔄 Odśwież dane rynkowe", type="primary"):
    st.cache_data.clear()
    st.rerun()

df_ml = run_predictions(df_ta, fng_val)
log_signals_to_history(df_ml) # Automatyczny zapis sygnałów do bintestu

df_ta_clean = df_ta.drop(columns=["RawScore", "Vol_Surge_Raw", "Price_Raw", "EMA200_Raw", "BTC_D1_Price", "BTC_D1_EMA200"], errors="ignore")

# ZAKŁADKI APLIKACJI
tab1, tab2, tab3 = st.tabs(["1. Tabela Techniczna Spot", "2. Sygnały Hybrydowe & Monte Carlo", "3. Skuteczność Sygnałów (Backtest)"])

with tab1:
    st.dataframe(df_ta_clean.style.map(lambda v: 'color: #2e7d32; font-weight: bold;' if isinstance(v, (int, float)) and v > 0 else ('color: #c62828; font-weight: bold;' if isinstance(v, (int, float)) and v < 0 else ''), subset=['24h (%)']), use_container_width=True)

with tab2:
    st.dataframe(df_ml, use_container_width=True)

with tab3:
    st.subheader("📈 Analiza Historyczna Skuteczności Sygnałów")
    st.caption("Modulator weryfikuje, jak wygenerowane wcześniej sygnały radzą sobie w zetknięciu z aktualnymi cenami rynkowymi.")
    
    bt_df, total_sigs, win_sigs, win_rate = get_backtest_stats(df_ta)
    
    if total_sigs > 0:
        k1, k2, k3 = st.columns(3)
        k1.metric("Łącznie Sygnałów", total_sigs)
        k2.metric("Trafione Sygnały", win_sigs)
        k3.metric("Skuteczność (Win Rate)", f"{win_rate}%")
        
        st.markdown("---")
        st.dataframe(bt_df, use_container_width=True)
    else:
        st.info("Brak zapisanej historii. Sygnały zaczną się zbierać automatycznie po kolejnych odświeżeniach danych.")

# ==========================================
# RAPORT ANALITYCZNY AI
# ==========================================
if not df_ta.empty:
    st.divider()
    st.subheader("🤖 Raport Analityczny AI")
    selected_ai_token = st.selectbox("Wybierz token, aby wygenerować pełny raport opisowy:", df_ta["Token"].tolist(), key="ai_select_box")
    
    row_ta_sel = df_ta[df_ta["Token"] == selected_ai_token].iloc[0]
    row_ml_sel = df_ml[df_ml["Token"] == selected_ai_token].iloc[0] if not df_ml.empty and "Token" in df_ml.columns else None
    
    st.info(generuj_raport_ai(row_ta_sel, row_ml_sel))

# ==========================================
# PODSUMOWANIE DLA HANDLU SPOT
# ==========================================
st.divider()
st.subheader("💡 Strategiczne Podsumowanie Spot")

if not df_ml.empty and "Sygnał Hybrydowy" in df_ml.columns:
    strong_buys = df_ml[df_ml["Sygnał Hybrydowy"] == "🟢 KUP (Mocny)"]["Token"].tolist()
    weak_buys = df_ml[df_ml["Sygnał Hybrydowy"] == "📈 KUP (Słaby)"]["Token"].tolist()
    sells = df_ml[df_ml["Sygnał Hybrydowy"] == "🔴 SPRZEDAJ"]["Token"].tolist()

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### 🟢 Mocna Akumulacja Spot")
        if strong_buys:
            st.success(f"**Tokeny:** {', '.join(strong_buys)}\n\nPotrójne potwierdzenie: wysoka szansa wzrostu, poprawny wolumen i sprzyjający trend BTC.")
        else:
            st.info("Brak tokenów w silnej strefie zakupowej.")

    with c2:
        st.markdown("### 📈 Ostrożne Wejście (DCA)")
        if weak_buys:
            st.warning(f"**Tokeny:** {', '.join(weak_buys)}\n\nRozważ zakup hybrydowy lub mniejsze transakcje metodą DCA ze względu na mieszane warunki wolumenowe.")
        else:
            st.info("Brak tokenów w strefie ostrożnej akumulacji.")

    with c3:
        st.markdown("### 🔴 Realizacja Zysków")
        if sells:
            st.error(f"**Tokeny:** {', '.join(sells)}\n\nPrzegrzane wskaźniki – dobra chwila na rozważenie sprzedaży częściowej lub całościowej pozycji spot.")
        else:
            st.success("Brak sygnałów pilnej wyprzedaży.")
