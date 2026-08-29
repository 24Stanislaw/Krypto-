import numpy as np
import pandas as pd
import requests
import streamlit as st

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Crypto Spot Pro", layout="wide")

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

            vol_ma = df['volume'].rolling(min(20, len(df))).mean().iloc[-1]
            vol_surge = (df['volume'].iloc[-1] / vol_ma) if vol_ma > 0 else 1.0

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

    # Stałe ziarno zależne od godziny (stabilność wyników Monte Carlo)
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
# INTERFEJS UŻYTKOWNIKA (UI)
# ==========================================
df_ta, fng_val, fng_class, btc_dom, btc_d1_price, btc_d1_ema200, loaded_count, total_count = fetch_technical_analysis()

col_title, col_btc_macro, col_dom, col_fng = st.columns([2.0, 1.1, 0.9, 1.0])
with col_title:
    st.title("🎯 Crypto Spot Pro")
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

# Szybki filtr / podgląd mobilny (wybór tokena na samej górze)
if not df_ta.empty:
    st.markdown("---")
    selected_token = st.selectbox("📱 Szybki podgląd wybranego tokena (dla wygody na telefonie):", df_ta["Token"].tolist())
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
df_ta_clean = df_ta.drop(columns=["RawScore", "Vol_Surge_Raw", "Price_Raw", "EMA200_Raw", "BTC_D1_Price", "BTC_D1_EMA200"], errors="ignore")

tab1, tab2 = st.tabs(["1. Tabela Techniczna Spot", "2. Sygnały Hybrydowe & Monte Carlo"])

with tab1:
    st.dataframe(df_ta_clean.style.map(lambda v: 'color: #2e7d32; font-weight: bold;' if isinstance(v, (int, float)) and v > 0 else ('color: #c62828; font-weight: bold;' if isinstance(v, (int, float)) and v < 0 else ''), subset=['24h (%)']), use_container_width=True)

with tab2:
    st.dataframe(df_ml, use_container_width=True)

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
