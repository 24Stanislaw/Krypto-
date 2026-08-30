import os
import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

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
  if st.button("🗑️ Resetuj historię i zacznij od nowa", type="secondary"):
    HISTORY_FILE = "signals_history.csv"
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
      "Wymagaj Akumulacji (OBV)", value=True,
      help="Odrzuca tokeny, w których duży kapitał realizuje zyski (Dystrybucja)."
  )

# ==========================================
# LISTA TOKENÓW SPOT (COINBASE)
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
    {"symbol": "JUP", "coinbase": "JUP-USD", "gecko_id": "jupiter-exchange-solana"},
    {"symbol": "UNI", "coinbase": "UNI-USD", "gecko_id": "uniswap"},
    {"symbol": "SEI", "coinbase": "SEI-USD", "gecko_id": "sei-network"},
    {"symbol": "KTA", "coinbase": "KTA-USD", "gecko_id": "keeta"},
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

def calc_vwap(df):
  if "volume" not in df.columns or df["volume"].sum() == 0: return float(df["close"].iloc[-1])
  typical_price = (df["high"] + df["low"] + df["close"]) / 3
  vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
  return float(vwap.iloc[-1])

def calc_obv(df):
  if "volume" not in df.columns or df["volume"].sum() == 0: return "Neutralny"
  direction = np.sign(df["close"].diff()).fillna(0)
  obv = (direction * df["volume"]).cumsum()
  if len(obv) > 5 and obv.iloc[-1] > obv.iloc[-5]: return "Akumulacja (Rosnący OBV)"
  elif len(obv) > 5 and obv.iloc[-1] < obv.iloc[-5]: return "Dystrybucja (Spadający OBV)"
  return "Brak wyraźnego trendu OBV"

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

  for item in TOKENS:
    symbol = item["symbol"]
    gecko_id = item["gecko_id"]
    try:
      df_1h = get_candles_1h(item)
      if df_1h.empty or len(df_1h) < 5: raise ValueError("Brak świec")
      df_4h = resample_ohlc(df_1h, "4h")
      df_1d = get_candles_1d(item)

      price = float(df_1h["close"].iloc[-1])
      prev_price_24h = float(df_1h["close"].iloc[-24] if len(df_1h) >= 24 else df_1h["close"].iloc[0])
      change_24h = ((price - prev_price_24h) / prev_price_24h) * 100

      log_returns = np.log(df_1h["close"] / df_1h["close"].shift(1)).dropna()
      vol_1h = float(log_returns.std()) if len(log_returns) > 5 else 0.015
      drift_1h = float(log_returns.mean()) if len(log_returns) > 5 else 0.0

      rsi_1h = calc_rsi(df_1h["close"])
      rsi_4h = calc_rsi(df_4h["close"]) if len(df_4h) >= 14 else 50.0
      rsi_1d = calc_rsi(df_1d["close"]) if not df_1d.empty and len(df_1d) >= 14 else rsi_4h

      _, _, macd_hist = calc_macd(df_4h["close"]) if len(df_4h) >= 26 else (0.0, 0.0, 0.0)
      vwap_val = calc_vwap(df_4h) if len(df_4h) > 0 else price
      obv_status = calc_obv(df_4h)
      rvol_val = calc_rvol(df_4h)

      tr = pd.concat([df_4h["high"] - df_4h["low"], (df_4h["high"] - df_4h["close"].shift()).abs(), (df_4h["low"] - df_4h["close"].shift()).abs()], axis=1).max(axis=1) if len(df_4h) > 1 else pd.Series([price * 0.02])
      atr = float(tr.rolling(min(14, len(df_4h))).mean().iloc[-1]) if len(tr) > 0 else price * 0.02
      ema200_4h = float(df_4h["close"].ewm(span=min(200, len(df_4h)), adjust=False).mean().iloc[-1]) if len(df_4h) > 0 else price

      sl = price - (2 * atr)
      support = float(df_4h["low"].min()) if len(df_4h) > 0 else price * 0.95
      resistance = float(df_4h["high"].max()) if len(df_4h) > 0 else price * 1.05

      risk = price - sl
      reward = resistance - price
      rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1

      if price > ema200_4h and macd_hist > 0: regime = "Silny Trend Wzrostowy"
      elif price > ema200_4h and macd_hist <= 0: regime = "Korekta w Trendzie Wzrostowym"
      elif price <= ema200_4h and macd_hist > 0: regime = "Próba Odbicia (Kontrtrend)"
      else: regime = "Strukturalny Trend Spadkowy"

      data.append({
          "Token": symbol, "Cena ($)": fmt(price), "24h (%)": round(change_24h, 2), "Reżim Rynkowy": regime,
          "RSI 1H": round(rsi_1h, 1), "RSI 4H": round(rsi_4h, 1), "RSI 1D": round(rsi_1d, 1),
          "RVOL (4H)": f"{rvol_val}x", "VWAP (4H)": fmt(vwap_val), "OBV Status": obv_status,
          "MACD Hist (4H)": fmt(macd_hist), "EMA 200 (4H)": fmt(ema200_4h), "SL (ATR)": fmt(sl),
          "Wsparcie": fmt(support), "Opór": fmt(resistance), "R:R": f"1:{rr_val}",
          "Price_Raw": float(price), "EMA200_Raw": float(ema200_4h), "Support_Raw": float(support),
          "Resistance_Raw": float(resistance), "RSI_1H_Raw": float(rsi_1h), "RSI_4H_Raw": float(rsi_4h),
          "RSI_1D_Raw": float(rsi_1d), "RVOL_Raw": float(rvol_val), "VWAP_Raw": float(vwap_val),
          "OBV_Raw": obv_status, "Regime_Raw": regime, "Vol_Raw": vol_1h, "Drift_Raw": drift_1h,
          "Is_Bouncing": float(df_1h["close"].iloc[-1]) >= float(df_1h["open"].iloc[-1]),
          "ATR_Raw": float(atr)
      })
      loaded_count += 1
    except Exception:
      p, chg = get_simple_coingecko_price(gecko_id)
      data.append({
          "Token": symbol, "Cena ($)": fmt(p), "24h (%)": round(chg, 2), "Reżim Rynkowy": "Brak danych / Konsolidacja",
          "RSI 1H": 50.0, "RSI 4H": 50.0, "RSI 1D": 50.0, "RVOL (4H)": "1.0x", "VWAP (4H)": fmt(p),
          "OBV Status": "Neutralny", "MACD Hist (4H)": "0.0", "EMA 200 (4H)": fmt(p), "SL (ATR)": fmt(p * 0.96),
          "Wsparcie": fmt(p * 0.95), "Opór": fmt(p * 1.05), "R:R": "1:1.5", "Price_Raw": p, "EMA200_Raw": p,
          "Support_Raw": p * 0.95, "Resistance_Raw": p * 1.05, "RSI_1H_Raw": 50.0, "RSI_4H_Raw": 50.0,
          "RSI_1D_Raw": 50.0, "RVOL_Raw": 1.0, "VWAP_Raw": p, "OBV_Raw": "Neutralny", "Regime_Raw": "Konsolidacja",
          "Vol_Raw": 0.015, "Drift_Raw": 0.0, "Is_Bouncing": False, "ATR_Raw": p * 0.02
      })
      loaded_count += 1

  return pd.DataFrame(data), fng_val, fng_class, btc_dom, alt_season, loaded_count, len(TOKENS)

# ==========================================
# SCORING I PREDYKCJE (MONTE CARLO 7 DNI)
# ==========================================
def run_predictions(df_ta, btc_dom, min_score_filter, max_rsi_filter, req_accumulation):
  if df_ta.empty: return pd.DataFrame(), {}
  rng = np.random.default_rng(seed=int(pd.Timestamp.now().strftime("%Y%m%d%H")))
  
  monte_carlo_paths = {}

  def analyze_row(row):
    symbol = row["Token"]
    price = float(row["Price_Raw"])
    vol_1h = float(row.get("Vol_Raw", 0.015))
    drift_1h = float(row.get("Drift_Raw", 0.0))
    regime = row["Regime_Raw"]
    rsi_4h = float(row["RSI_4H_Raw"])
    obv_status = str(row.get("OBV_Raw", ""))
    rvol = float(row.get("RVOL_Raw", 1.0))

    # Symulacja 7 dni (168 godzin)
    adjusted_drift = drift_1h - (0.5 * (vol_1h**2))
    shocks = rng.normal(loc=adjusted_drift, scale=vol_1h, size=(5000, 168))
    cum_returns = np.exp(np.cumsum(shocks, axis=1))
    final_prices_paths = price * cum_returns
    
    # Zapis ścieżek do użycia na wykresie
    monte_carlo_paths[symbol] = final_prices_paths
    
    # Prognozy dla poszczególnych horyzontów
    p_24h = float(np.median(final_prices_paths[:, 23]))
    p_3d = float(np.median(final_prices_paths[:, 71]))
    p_7d = float(np.median(final_prices_paths[:, 167]))

    ci_lower_7d = float(np.percentile(final_prices_paths[:, 167], 2.5))
    ci_upper_7d = float(np.percentile(final_prices_paths[:, 167], 97.5))
    prob_up_7d = float(np.mean(final_prices_paths[:, 167] > price) * 100)

    score = 50.0 
    
    if "Silny Trend Wzrostowy" in regime: score += 25.0
    elif "Korekta" in regime: score += 10.0
    elif "Spadkowy" in regime: score -= 20.0

    score += (rvol - 1.0) * 20.0  

    if "Akumulacja" in obv_status: score += 12.0
    elif "Dystrybucja" in obv_status: score -= 15.0

    if rsi_4h < 45: score += (45 - rsi_4h) * 0.4
    elif rsi_4h > 65: score -= (rsi_4h - 65) * 0.6

    score = max(0.0, min(100.0, score))

    is_altcoin = symbol not in ["BTC", "ETH"]
    macro_headwind = btc_dom > 59.0 and is_altcoin

    if macro_headwind:
      signal = "⏳ ODRZUCONY (Silna dominacja BTC)"
    elif score >= min_score_filter and rsi_4h <= max_rsi_filter:
      if req_accumulation and "Akumulacja" not in obv_status:
        signal = "🟡 NEUTRALNY (Brak akumulacji)"
      else:
        signal = "🟢 WYSOKI EDGE (Solidna Okazja Zakupowa)"
    elif score >= 55.0:
      signal = "🟡 NEUTRALNY (Wymaga obserwacji)"
    else:
      signal = "❌ ODRZUCONY (Słaba struktura/podaż)"

    return pd.Series([
        f"${fmt(p_24h)}", f"${fmt(p_3d)}", f"${fmt(p_7d)}",
        f"${fmt(ci_lower_7d)} - ${fmt(ci_upper_7d)}",
        f"{round(prob_up_7d, 1)}%", signal, score
    ])

  df_ml = df_ta.copy()
  df_ml[["Prognoza 24h", "Prognoza 3D", "Prognoza 7D", "Zasięg MC 7D (95%)", "Szansa Wzrostu (7D)", "Ocena Przewagi (Edge)", "Smart Score (%)"]] = df_ml.apply(analyze_row, axis=1)
  df_ml["Atrakcyjność (%)"] = df_ml["Smart Score (%)"]
  
  # Wybieramy kluczowe kolumny do tabeli
  res_df = df_ml[["Token", "Cena ($)", "Reżim Rynkowy", "Atrakcyjność (%)", "Smart Score (%)", "Prognoza 24h", "Prognoza 7D", "Zasięg MC 7D (95%)", "Ocena Przewagi (Edge)", "Szansa Wzrostu (7D)"]]
  return res_df, monte_carlo_paths

# ==========================================
# WYKRES PLOTLY
# ==========================================
def plot_price_forecast(symbol, current_price, price_paths):
    median_path = np.median(price_paths, axis=0)
    upper_95 = np.percentile(price_paths, 97.5, axis=0)
    lower_95 = np.percentile(price_paths, 2.5, axis=0)
    
    hours = np.arange(1, 169)
    
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=np.concatenate([hours, hours[::-1]]),
        y=np.concatenate([upper_95, lower_95[::-1]]),
        fill='toself',
        fillcolor='rgba(59, 130, 246, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Przedział Ufności 95%',
        hoverinfo='skip'
    ))

    fig.add_trace(go.Scatter(
        x=hours, y=median_path,
        mode='lines',
        line=dict(color='#2563eb', width=3),
        name='Prognoza (Mediana MC)'
    ))

    fig.add_hline(y=current_price, line_dash="dash", line_color="gray", annotation_text="Obecna cena")

    fig.update_layout(
        title=f"📈 Prognoza Trajektorii Ceny 7D (Monte Carlo): {symbol}",
        xaxis_title="Godziny od teraz",
        yaxis_title="Cena ($)",
        template="plotly_white",
        height=400,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

# ==========================================
# HISTORIA I BACKTESTING
# ==========================================
HISTORY_FILE = "signals_history.csv"

def update_history_status(df_ta):
  if not os.path.exists(HISTORY_FILE): return
  try: df_hist = pd.read_csv(HISTORY_FILE)
  except: return
  if df_hist.empty: return
  now_dt, now_date = pd.Timestamp.now(), pd.Timestamp.now().strftime("%Y-%m-%d")
  price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))
  for idx, row in df_hist.iterrows():
    entry = float(row["Cena Wejścia"]) if pd.notna(row["Cena Wejścia"]) else 0.0
    if entry <= 0: continue
    curr_price = float(price_map.get(row["Token"], entry))
    prev_extr = float(row["Ekstremum Ceny"]) if pd.notna(row["Ekstremum Ceny"]) and float(row["Ekstremum Ceny"]) > 0 else entry
    new_extr = max(prev_extr, curr_price)
    max_gain_pct = ((new_extr - entry) / entry) * 100
    curr_gain_pct = ((curr_price - entry) / entry) * 100
    df_hist.at[idx, "Ekstremum Ceny"] = float(new_extr)
    if max_gain_pct >= 5.0 and str(row["TP 5%"]) == "-": df_hist.at[idx, "TP 5%"] = f"✅ {now_date}"
    if max_gain_pct >= 7.5 and str(row["TP 7.5%"]) == "-": df_hist.at[idx, "TP 7.5%"] = f"✅ {now_date}"
    if max_gain_pct >= 10.0 and str(row["TP 10%"]) == "-": df_hist.at[idx, "TP 10%"] = f"✅ {now_date}"
    try: days_passed = (now_dt - pd.to_datetime(row["Data"])).days
    except: days_passed = 0
    if max_gain_pct >= 10.0: df_hist.at[idx, "Status"] = "🎯 Zaliczone TP 10%"
    elif curr_gain_pct <= -5.0: df_hist.at[idx, "Status"] = "❌ SL (-5%)"
    elif days_passed >= 30: df_hist.at[idx, "Status"] = "⏱️ Wygasło (30d)"
    else: df_hist.at[idx, "Status"] = f"🔄 W toku ({days_passed}/30d)"
  df_hist.to_csv(HISTORY_FILE, index=False)

def get_backtest_stats(target_pct_str):
  if not os.path.exists(HISTORY_FILE): return pd.DataFrame(), 0, 0, 0.0
  try: df_hist = pd.read_csv(HISTORY_FILE)
  except: return pd.DataFrame(), 0, 0, 0.0
  if df_hist.empty: return df_hist, 0, 0, 0.0
  col_tp = f"TP {target_pct_str}"
  wins, total, results = 0, 0, []
  for _, row in df_hist.iterrows():
    try: entry, extr_p = float(row.get("Cena Wejścia", 0)), float(row.get("Ekstremum Ceny", float(row.get("Cena Wejścia", 0))))
    except: continue
    tp_hit, status = str(row.get(col_tp, "-")), str(row.get("Status", "-"))
    max_gain = ((extr_p - entry) / entry) * 100 if entry > 0 else 0.0
    if "✅" in tp_hit: wins += 1; total += 1; res_status = f"✅ Osiągnięto {target_pct_str}"
    elif "SL" in status: total += 1; res_status = "❌ SL (-5%)"
    elif "Wygasło" in status: total += 1; res_status = "⏱️ Wygasło (30d)"
    else: res_status = f"🔄 W toku (Max: +{round(max_gain, 1)}%)"
    results.append({"Data Wejścia": row.get("Data"), "Token": row.get("Token"), "Sygnał": str(row.get("Typ Sygnału", "")), "Cena Wejścia ($)": fmt(entry), "Ekstremum ($)": fmt(extr_p), "Max Zysk (%)": f"+{round(max_gain, 2)}%", f"Cel {target_pct_str}": tp_hit, "Status": res_status})
  return pd.DataFrame(results), total, wins, round((wins / total) * 100, 1) if total > 0 else 0.0

# ==========================================
# OBSZERNY RAPORT AI (UWZGLĘDNIA SMART SCORE I MC)
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None, btc_dom=55.0):
  symbol = row_ta.get("Token", "UNKNOWN")
  price_raw = float(row_ta.get("Price_Raw", 0))
  ema_raw = float(row_ta.get("EMA200_Raw", 0))
  atr_raw = float(row_ta.get("ATR_Raw", price_raw * 0.02))
  regime = row_ta.get("Reżim Rynkowy", "Neutralny")
  rsi_1h, rsi_4h, rsi_1d = float(row_ta.get("RSI_1H_Raw", 50)), float(row_ta.get("RSI_4H_Raw", 50)), float(row_ta.get("RSI_1D_Raw", 50))
  rvol_str = row_ta.get("RVOL (4H)", "1.0x")
  vwap_val = float(row_ta.get("VWAP_Raw", price_raw))
  obv_status = row_ta.get("OBV Status", "Neutralny")
  macd_hist = float(row_ta.get("MACD Hist (4H)", 0.0))
  support_str, resistance_str, sl_str = row_ta.get("Wsparcie", "0.00"), row_ta.get("Opór", "0.00"), row_ta.get("SL (ATR)", "0.00")
  edge_status = row_ml.get("Ocena Przewagi (Edge)", "-") if row_ml is not None else "-"
  
  raw_smart_score = row_ml.get("Smart Score (%)", 50.0) if row_ml is not None else 50.0
  smart_score = f"{float(raw_smart_score):.2f}"
  
  prognoza_7d = row_ml.get("Prognoza 7D", "-") if row_ml is not None else "-"
  zasieg_mc_7d = row_ml.get("Zasięg MC 7D (95%)", "-") if row_ml is not None else "-"
  prob_up_7d = row_ml.get("Szansa Wzrostu (7D)", "-") if row_ml is not None else "-"

  target_tp1 = price_raw + (1.5 * atr_raw)

  if "Silny Trend" in regime: 
      pa_wniosek = "Pełna dominacja popytu. Ruch charakteryzuje się wysoką dynamiką, a pozycje pro-trendowe mają najwyższą przewagę statystyczną."
      pa_stan = f"Cena na poziomie `${fmt(price_raw)}` notowana jest wysoce powyżej długoterminowej średniej EMA200 (`${fmt(ema_raw)}`)."
  elif "Korekta" in regime: 
      pa_wniosek = "Klasyczny układ 'kupna po obniżce' (buy the dip). Popyt broni fundamentalnej średniej, co daje dobre R:R."
      pa_stan = f"Cena (`${fmt(price_raw)}`) cofa się lokalnie, ale utrzymuje obronny pułap ponad EMA200 (`${fmt(ema_raw)}`)."
  elif "Spadkowy" in regime: 
      pa_wniosek = "Rynek jest w rękach niedźwiedzi. Każde lokalne podbicie ceny stanowi szansę na realizację dystrybucji przez duży kapitał."
      pa_stan = f"Cena (`${fmt(price_raw)}`) znajduje się pod presją podażową poniżej kluczowej średniej EMA200 (`${fmt(ema_raw)}`)."
  else: 
      pa_wniosek = "Brak jednoznacznego trendu wyższego rzędu. Należy ograniczyć aktywność do czasu wybicia z konsolidacji."
      pa_stan = f"Cena (`${fmt(price_raw)}`) porusza się w horyzontalnym paśmie w pobliżu EMA200 (`${fmt(ema_raw)}`)."

  is_altcoin = symbol not in ["BTC", "ETH"]
  if is_altcoin and btc_dom > 59.0:
      macro_stan = f"Dominacja Bitcoina wysoka (`{btc_dom}%`)."
      macro_wniosek = f"Środowisko makro jest toksyczne dla altcoinów jak {symbol}. Brak płynności grozi zanegowaniem sygnałów technicznych."
  else:
      macro_stan = f"Dominacja Bitcoina na umiarkowanym poziomie (`{btc_dom}%`)."
      macro_wniosek = "Kapitał swobodnie rotuje do walorów o niższej kapitalizacji. Otoczenie wspiera kontynuację ruchów popytowych."

  rvol_float = float(rvol_str.replace("x", "")) if "x" in rvol_str else 1.0
  if rvol_float >= 1.5:
      rvol_stan = f"Współczynnik wynosi `{rvol_str}` średniej z 20 okresów."
      rvol_wniosek = "Pojawił się instytucjonalny wolumen. Wybicia cenowe mają realne pokrycie w aktywach."
  elif rvol_float >= 1.0:
      rvol_stan = f"Współczynnik w normie (`{rvol_str}`)."
      rvol_wniosek = "Standardowa aktywność rynkowa bez nadzwyczajnego zaangażowania dużych graczy."
  else:
      rvol_stan = f"Niski wolumen (`{rvol_str}`)."
      rvol_wniosek = "Rynek 'pusty' płynnościowo. Występuje wysokie ryzyko generowania fałszywych wybić (fakeoutów)."

  if "WYSOKI EDGE" in edge_status:
      final_reco = "**Rekomendacja:** Zdecydowane **Zezwolenie na handel (🟢)**. Pełne zebranie sprzyjających czynników trendowych, wolumenowych i interwałowych."
  elif "NEUTRALNY" in edge_status:
      final_reco = "**Rekomendacja:** Status **Obserwacja (🟡)**. Wykryto braki w zaangażowaniu kapitału lub lokalne przegrzanie. Wstrzymaj się z wejściem."
  else:
      final_reco = "**Rekomendacja:** Sygnał **Odrzucony (❌)**. Układ sił faworyzuje niedźwiedzie lub otoczenie makro uderza w płynność."

  return f"""
### 🎯 EKSPERCKA SYNTEZA MTF PRO: {symbol}
**Werdykt Algorytmu:** `{edge_status}` | **Smart Score:** **{smart_score}%** | **Cena Aktualna:** `${fmt(price_raw)}` | **Reżim Rynkowy:** **{regime}**

---
#### 1. 🧠 Analiza Strukturalna i Makroekonomiczna
* **Zachowanie Ceny (Price Action & EMA200):** {pa_stan} {pa_wniosek}
* **Otoczenie Makroekonomiczne (Dominacja BTC):** {macro_stan} {macro_wniosek}

#### 2. 📊 Płynność i Ślady Smart Money
* **Względny Wolumen (RVOL 4H):** {rvol_stan} {rvol_wniosek}
* **Poziom VWAP (4H):** Wyznaczony poziom VWAP wynosi `${fmt(vwap_val)}`. Cena powracająca do VWAP od góry daje szansę na reakcję popytową.

#### 3. 📈 Wskaźniki Pędu (Multi-Timeframe)
* **Korelacja RSI:** **1H:** `{round(rsi_1h, 1)}` | **4H:** `{round(rsi_4h, 1)}` | **1D:** `{round(rsi_1d, 1)}`. 
* **MACD Histogram (4H):** `{fmt(macd_hist)}`.

#### 4. 🎲 Symulacja Monte Carlo i Cele Cenowe (W perspektywie 7D)
* **Mediana prognozy na 7 dni:** `{prognoza_7d}` (Szansa na zamknięcie wyżej: `{prob_up_7d}`)
* **Przedział ufności (95%):** `{zasieg_mc_7d}`
* **Cele Cenowe ATR (Dynamiczne):** 
  * TP1 (1.5x ATR): `${fmt(target_tp1)}`
  * Cel Opór (Techniczny): `{resistance_str}`

#### 5. 🛡️ Inżynieria Ryzyka
* **Poziom Inwalidacji (Stop Loss z buforem ATR):** `${sl_str}`
* **Wsparcie:** `${support_str}`

---
#### 🏁 6. Podsumowanie i Werdykt Końcowy
{final_reco}
"""

# ==========================================
# INTERFEJS GŁÓWNY STREMLIT (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane na żywo z API i przeliczam wskaźniki..."):
  df_ta, fng_val, fng_class, btc_dom, alt_season, loaded_c, total_c = fetch_technical_analysis()
  df_ml, mc_paths = run_predictions(df_ta, btc_dom, min_smart_score, max_rsi_4h, wymagaj_akumulacji)
  update_history_status(df_ta)

col_t, col_d1, col_d2, col_f = st.columns([2.0, 1, 1, 1])
col_t.title("📊 Analiza Krypto MTF Pro")
col_t.caption(f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Załadowano: {loaded_c}/{total_c}")
col_d1.metric("Dominacja BTC", f"{btc_dom}%")
col_d2.metric("Sezon Altcoinów", f"{alt_season}/100", "Sezon BTC" if alt_season < 50 else "Sezon Alt")
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

st.markdown("---")

# SEKCJA OKAZJI
st.markdown("### 🔥 Najlepsze Okazje Zakupowe")
if not df_ml.empty:
  okazje_df = df_ml[df_ml["Ocena Przewagi (Edge)"].str.contains("WYSOKI EDGE", na=False)]
  if not okazje_df.empty:
    cols_okazje = st.columns(min(len(okazje_df), 4))
    for i, (_, row) in enumerate(okazje_df.iterrows()):
      with cols_okazje[i % len(cols_okazje)]:
        score_val = float(row['Smart Score (%)'])
        st.success(f"**{row['Token']}**\n\nCena: `{row['Cena ($)']}`\nSmart Score: **{score_val:.2f}%**\nPrognoza 7D: **{row['Prognoza 7D']}**")
  else:
    st.info("Obecnie żaden token nie spełnia restrykcyjnych warunków algorytmu.")

st.markdown("---")

if st.button("🔄 Odśwież dane", type="primary"):
  st.cache_data.clear()
  st.rerun()

df_ta_clean = df_ta.drop(columns=["Price_Raw", "EMA200_Raw", "Support_Raw", "Resistance_Raw", "RSI_1H_Raw", "RSI_4H_Raw", "RSI_1D_Raw", "RVOL_Raw", "VWAP_Raw", "OBV_Raw", "Regime_Raw", "Vol_Raw", "Drift_Raw", "Is_Bouncing", "ATR_Raw"], errors="ignore")
if "Atrakcyjność (%)" not in df_ta_clean.columns and not df_ml.empty: df_ta_clean["Atrakcyjność (%)"] = df_ml["Smart Score (%)"]

config_tabel = {
    "Atrakcyjność (%)": st.column_config.NumberColumn("Atrakcyjność (%)", format="%.2f"),
    "Smart Score (%)": st.column_config.NumberColumn("Smart Score (%)", format="%.2f"),
    "24h (%)": st.column_config.NumberColumn("24h (%)", format="%.2f"),
    "RSI 1H": st.column_config.NumberColumn("RSI 1H", format="%.1f"),
    "RSI 4H": st.column_config.NumberColumn("RSI 4H", format="%.1f"),
    "RSI 1D": st.column_config.NumberColumn("RSI 1D", format="%.1f"),
}

def apply_high_contrast_striping(df):
  return df.style.apply(
      lambda row: ['background-color: #f1f5f9; color: #0b0f19; font-weight: 500;' if row.name % 2 == 1 else 'background-color: #ffffff; color: #0b0f19; font-weight: 500;' for _ in row],
      axis=1
  )

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Reżimy", "2. Ocena Przewagi (Smart Score)", "3. ⚡ Aktywne Pozycje", "4. 🗂️ Archiwum", "5. 📈 Backtest"])

with tab1: 
  st.dataframe(apply_high_contrast_striping(df_ta_clean), column_config=config_tabel, use_container_width=True)
with tab2:
  st.dataframe(apply_high_contrast_striping(df_ml), column_config=config_tabel, use_container_width=True)
  st.markdown("---")
  st.subheader("➕ Otwórz i śledź wybraną pozycję ręcznie")
  col_sel_tok, col_sel_btn = st.columns([2, 1])
  chosen_token = col_sel_tok.selectbox("Wybierz token:", df_ml["Token"].tolist(), key="manual_token_pick")
  if col_sel_btn.button("🚀 Dodaj do aktywnych", type="primary"):
    price_clean = float(df_ta[df_ta["Token"] == chosen_token].iloc[0]["Price_Raw"])
    new_entry = pd.DataFrame([{"Data": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "Token": chosen_token, "Typ Sygnału": df_ml[df_ml["Token"] == chosen_token].iloc[0]["Ocena Przewagi (Edge)"], "Cena Wejścia": price_clean, "Ekstremum Ceny": price_clean, "TP 5%": "-", "TP 7.5%": "-", "TP 10%": "-", "Status": "🔄 W toku (0/30d)"}])
    df_h = pd.concat([pd.read_csv(HISTORY_FILE), new_entry], ignore_index=True) if os.path.exists(HISTORY_FILE) else new_entry
    df_h.to_csv(HISTORY_FILE, index=False)
    st.success(f"Dodano {chosen_token} po ${fmt(price_clean)}!")
    st.rerun()

with tab3:
  if os.path.exists(HISTORY_FILE):
    df_active = pd.read_csv(HISTORY_FILE)[pd.read_csv(HISTORY_FILE)["Status"].str.contains("W toku", na=False)]
    if not df_active.empty: st.dataframe(apply_high_contrast_striping(df_active.sort_values("Data", ascending=False)), use_container_width=True)
    else: st.info("Brak aktywnych pozycji.")
  else: st.info("Brak danych.")

with tab4:
  if os.path.exists(HISTORY_FILE):
    df_closed = pd.read_csv(HISTORY_FILE)[~pd.read_csv(HISTORY_FILE)["Status"].str.contains("W toku", na=False)]
    if not df_closed.empty: st.dataframe(apply_high_contrast_striping(df_closed.sort_values("Data", ascending=False)), use_container_width=True)
    else: st.info("Brak zamkniętych.")

with tab5:
  t_choice = st.radio("Próg TP / SL:", ["5%", "7.5%", "10%"], horizontal=True)
  bt_df, tot, wins, wr = get_backtest_stats(t_choice)
  if tot > 0:
    k1, k2, k3 = st.columns(3)
    k1.metric("Sygnały", tot); k2.metric("Wygrane", wins); k3.metric("Win Rate", f"{wr}%")
    st.dataframe(apply_high_contrast_striping(bt_df), use_container_width=True)
  else: st.info("Brak rozliczonych.")

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
