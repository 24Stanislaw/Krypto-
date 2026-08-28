import numpy as np
import pandas as pd
import requests
import streamlit as st

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Crypto Dashboard Pro", layout="wide")

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
# LOGIKA DANYCH (TA + HYBRYDA RSI/ML)
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
        return ""
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

def get_binance_funding(symbol):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}USDT"
        res = requests.get(url, timeout=3).json()
        if 'lastFundingRate' in res:
            return float(res['lastFundingRate']) * 100
    except Exception:
        pass
    return 0.01

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

            funding = get_binance_funding(item['symbol'])

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
                "Funding (%)": f"{round(funding, 4)}%",
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
            
    return pd.DataFrame(data), fng_val, fng_class, btc_d1_price, btc_d1_ema200, loaded_count, total_count

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

    def analyze_row(row):
        symbol = row["Token"]
        price = float(row["Price_Raw"])
        atr = float(row["ATR"])
        rsi = float(row["RSI"])
        change = float(row["24h (%)"])
        pct_b = float(row["%B (BB)"])
        vol_surge = float(row["Vol_Surge_Raw"])
        funding = float(str(row["Funding (%)"]).replace('%', ''))

        atr_pct = (atr / price) * 100
        dynamic_rsi_thresh = 30.0 + min(max(atr_pct * 1.5, 0.0), 10.0)

        rsi_bounce = (dynamic_rsi_thresh - rsi) * 0.0025 if rsi < dynamic_rsi_thresh else (-(rsi - 70) * 0.0020 if rsi > 70 else 0)
        bb_bounce = (0.1 - pct_b) * 0.005 if pct_b < 0.1 else (-(pct_b - 0.9) * 0.005 if pct_b > 0.9 else 0)
        funding_penalty = -0.003 if funding > 0.03 else (0.003 if funding < -0.01 else 0)

        expected_change = (change / 100 * 0.05) + rsi_bounce + bb_bounce + funding_penalty
        target_price = price * (1 + expected_change)

        shocks = np.random.normal(expected_change / 24.0, (atr / price) / np.sqrt(24), (10000, 24))
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
                signal = "🔴 SPRZEDAJ" if (prob < 42.0 or funding > 0.05) else "⏳ CZEKAJ / NEUTRALNY"

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
# GŁÓWNY INTERFEJS UŻYTKOWNIKA
# ==========================================
df_ta, fng_val, fng_class, btc_d1_price, btc_d1_ema200, loaded_count, total_count = fetch_technical_analysis()

col_title, col_btc_macro, col_fng = st.columns([2.5, 1.2, 1])
with col_title:
    st.title("📊 Zintegrowany Panel Analityczny Crypto Pro")
    st.caption(f"ℹ️ Status API: Pomyślnie załadowano dane dla **{loaded_count}/{total_count}** tokenów.")

with col_btc_macro:
    if btc_d1_price and btc_d1_ema200:
        is_bullish = btc_d1_price >= (btc_d1_ema200 * 0.985)
        status_label = "🟢 Wzrostowy (Byczy)" if is_bullish else "🔴 Spadkowy (Niedźwiedzi)"
        st.metric(label="BTC Trend D1 (EMA 200)", value=status_label, delta=f"Cena: ${fmt(btc_d1_price)}")
    else:
        st.metric(label="BTC Trend D1", value="Brak danych")

with col_fng:
    st.metric(label="Fear & Greed Index", value=f"{fng_val}/100", delta=fng_class)

# Dynamiczne wskazówki behawioralne oparte o FNG
if fng_val < 25:
    st.info("💡 **Wskazówka behawioralna (Ekstremalny strach):** Historycznie to najlepsze momenty na akumulację i zakupy DCA.")
elif fng_val > 75:
    st.warning("⚠️ **Wskazówka behawioralna (Ekstremalna chciwość):** Rynek rozgrzany – zachowaj szczególną ostrożność i rozważ realizację zysków.")

# Kontrola Funding Rate (Ostrzeżenie o przelewarowaniu)
if not df_ta.empty and "Funding (%)" in df_ta.columns:
    avg_funding = df_ta['Funding (%)'].apply(lambda x: float(str(x).replace('%', ''))).mean()
    if avg_funding > 0.03:
        st.warning(f"⚠️ **Ostrzeżenie o przelewarowaniu:** Średni Funding Rate wynosi {round(avg_funding, 4)}%. Wysokie ryzyko nagłych korekt (Long Squeeze).")

if not df_ta.empty and "RawScore" in df_ta.columns:
    top_deals = df_ta[df_ta["RawScore"] >= 70.0]
    if not top_deals.empty:
        st.success(f"🔥 **WYKRYTO MOCNE OKAZJE:** Tokeny {', '.join(top_deals['Token'].tolist())} osiągnęły wysoki poziom atrakcyjności!")
    else:
        st.info("ℹ️ Brak w tej chwili wygenerowanych sygnałów o wysokim priorytecie (≥70%).")

if st.button("🔄 Odśwież dane", type="primary"):
    st.cache_data.clear()

df_ml = run_predictions(df_ta, fng_val)
df_ta_clean = df_ta.drop(columns=["RawScore", "Vol_Surge_Raw", "Price_Raw", "EMA200_Raw", "BTC_D1_Price", "BTC_D1_EMA200"], errors="ignore")

tab1, tab2 = st.tabs(["1. Pełna Analiza Techniczna", "2. Prognoza Hybrydowa ML & Monte Carlo"])

with tab1:
    st.dataframe(df_ta_clean, use_container_width=True)

with tab2:
    st.dataframe(df_ml, use_container_width=True)

# ==========================================
# AUTOMATYCZNE PODSUMOWANIE I INTERPRETACJA
# ==========================================
st.divider()
st.subheader("💡 Podsumowanie i Interpretacja Wyników")

if not df_ml.empty and "Sygnał Hybrydowy" in df_ml.columns:
    strong_buys = df_ml[df_ml["Sygnał Hybrydowy"] == "🟢 KUP (Mocny)"]["Token"].tolist()
    weak_buys = df_ml[df_ml["Sygnał Hybrydowy"] == "📈 KUP (Słaby)"]["Token"].tolist()
    sells = df_ml[df_ml["Sygnał Hybrydowy"] == "🔴 SPRZEDAJ"]["Token"].tolist()

    col_sum1, col_sum2, col_sum3 = st.columns(3)

    with col_sum1:
        st.markdown("### 🟢 Najsilniejsze Okazje")
        if strong_buys:
            st.success(f"**Tokeny:** {', '.join(strong_buys)}\n\n"
                       "**Interpretacja:** Aktywa te posiadają potrójne potwierdzenie: wysokie prawdopodobieństwo wzrostu, podwyższony wolumen oraz sprzyjające otoczenie makro Bitcoina.")
        else:
            st.info("Brak tokenów kwalifikujących się do pełnego sygnału akumulacji.")

    with col_sum2:
        st.markdown("### 📈 Akumulacja Ostrożna")
        if weak_buys:
            st.warning(f"**Tokeny:** {', '.join(weak_buys)}\n\n"
                       "**Interpretacja:** Sygnał wzrostowy z zastrzeżeniem. Może to wynikać ze słabszego wolumenu lub ograniczenia narzuconego przez trend makro BTC.")
        else:
            st.info("Brak tokenów w strefie umiarkowanego zakupu.")

    with col_sum3:
        st.markdown("### 🔴 Ryzyko / Wyprzedaż")
        if sells:
            st.error(f"**Tokeny:** {', '.join(sells)}\n\n"
                     "**Interpretacja:** Wysokie ryzyko spadku cen lub przegrzane wskaźniki (np. wysoki Funding Rate). Zalecana realizacja zysków lub ucieczka do kapitału.")
        else:
            st.success("Brak tokenów z aktywnym sygnałem wyprzedaży.")

    st.markdown("---")
    st.markdown("### 🔍 Kluczowe Wnioski Rynkowe")
    
    btc_macro_text = "Byczy (sprzyja altcoinom)" if btc_d1_price and btc_d1_ema200 and btc_d1_price >= (btc_d1_ema200 * 0.985) else "Niedźwiedzi (ostrożność na altcoinach)"
    
    st.markdown(f"""
    * **Sentyment ogólny:** Fear & Greed Index wynosi **{fng_val}/100 ({fng_class})**. 
    * **Filtr Trendu BTC:** Trend dzienny Bitcoina oceniono jako **{btc_macro_text}**.
    * **Rekomendacja:** W przypadku sygnałów *KUP (Słaby)* warto rozważyć wchodzenie w pozycje metodą DCA (podział kapitału na części), natomiast dla sygnałów *KUP (Mocny)* można rozważyć wejście przy obecnych wsparciach z ustawionym zleceniem Stop-Loss.
    """)
