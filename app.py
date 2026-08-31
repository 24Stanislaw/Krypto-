from datetime import datetime
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

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
      "Minimalny Smart Score (%)",
      min_value=0.0,
      max_value=100.0,
      value=65.0,
      step=1.0,
      help="Im wyższy wynik, tym silniejszy trend i lepsze parametry wolumenu.",
  )
  max_rsi_4h = st.slider(
      "Maksymalny RSI 4H",
      min_value=10.0,
      max_value=90.0,
      value=60.0,
      step=1.0,
      help="Odfiltruj tokeny, które są już lokalnie przegrzane/wykupione.",
  )
  wymagaj_akumulacji = st.checkbox(
      "Wymagaj Akumulacji (OBV)",
      value=True,
      help=(
          "Odrzuca tokeny, w których duży kapitał realizuje zyski"
          " (Dystrybucja)."
      ),
  )

# ==========================================
# LISTA TOKENÓW SPOT (POPRAWIONY JUP)
# ==========================================
TOKENS = [
    {"symbol": "ONDO", "coinbase": "ONDO-USD", "gecko_id": "ondo-finance"},
    {"symbol": "INJ", "coinbase": "INJ-USD", "gecko_id": "injective-protocol"},
    {"symbol": "LINK", "coinbase": "LINK-USD", "gecko_id": "chainlink"},
    {"symbol": "RENDER", "coinbase": "RENDER-USD", "gecko_id": "render-token"},
    {
        "symbol": "FET",
        "coinbase": "FET-USD",
        "gecko_id": "artificial-superintelligence-alliance",
    },
    {"symbol": "BTC", "coinbase": "BTC-USD", "gecko_id": "bitcoin"},
    {"symbol": "ETH", "coinbase": "ETH-USD", "gecko_id": "ethereum"},
    {"symbol": "ENA", "coinbase": "ENA-USD", "gecko_id": "ethena"},
    {"symbol": "PENDLE", "coinbase": "PENDLE-USD", "gecko_id": "pendle"},
    {"symbol": "NEAR", "coinbase": "NEAR-USD", "gecko_id": "near"},
    {"symbol": "PLUME", "coinbase": "PLUME-USD", "gecko_id": "plume"},
    {"symbol": "JUP", "coinbase": None, "gecko_id": "jupiter"},
    {"symbol": "UNI", "coinbase": "UNI-USD", "gecko_id": "uniswap"},
    {"symbol": "SEI", "coinbase": "SEI-USD", "gecko_id": "sei-network"},
    {"symbol": "SOL", "coinbase": "SOL-USD", "gecko_id": "solana"},
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


# ==========================================
# FUNKCJE POBIERANIA DANYCH I WSKAŹNIKÓW
# ==========================================
def get_fear_and_greed():
  try:
    res = requests.get(
        "https://api.alternative.me/fng/?limit=1", timeout=4
    ).json()
    return int(res["data"][0]["value"]), res["data"][0]["value_classification"]
  except Exception:
    return 50, "Neutral"


def get_global_market_data():
  try:
    res = requests.get(
        "https://api.coingecko.com/api/v3/global",
        headers={"User-Agent": "CryptoDashboard/1.0"},
        timeout=4,
    ).json()
    return round(res["data"]["market_cap_percentage"]["btc"], 1)
  except Exception:
    return 55.0


def calculate_altcoin_season_index():
  try:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "200d",
    }
    res = requests.get(
        url,
        params=params,
        headers={"User-Agent": "CryptoDashboard/1.0"},
        timeout=6,
    )
    if res.status_code != 200:
      return 45
    coins = res.json()
    exclude_symbols = [
        "usdt",
        "usdc",
        "fdusd",
        "dai",
        "usde",
        "wbtc",
        "steth",
        "weth",
    ]
    btc_change = 0.0
    for coin in coins:
      if coin["symbol"].lower() == "btc":
        btc_change = coin.get("price_change_percentage_200d_in_currency", 0.0)
        break
    better_than_btc, valid_count = 0, 0
    for coin in coins:
      symbol = coin["symbol"].lower()
      if symbol == "btc" or symbol in exclude_symbols:
        continue
      change = coin.get("price_change_percentage_200d_in_currency")
      if change is not None:
        valid_count += 1
        if change > btc_change:
          better_than_btc += 1
      if valid_count >= 50:
        break
    if valid_count > 0:
      return int((better_than_btc / valid_count) * 100)
    return 45
  except Exception:
    return 45


def fetch_from_coinbase(symbol_pair, granularity=3600):
  url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?granularity={granularity}"
  res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
  res.raise_for_status()
  df = pd.DataFrame(
      res.json(), columns=["timestamp", "low", "high", "open", "close", "volume"]
  )
  df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
  return df.sort_values("dt").reset_index(drop=True)


def fetch_from_coingecko(gecko_id):
  url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/market_chart?vs_currency=usd&days=14"
  res = requests.get(
      url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=6
  )
  res.raise_for_status()
  data = res.json()

  prices = data.get("prices", [])
  volumes = data.get("total_volumes", [])

  if not prices:
    return pd.DataFrame()

  df_p = pd.DataFrame(prices, columns=["timestamp", "close"])
  df_v = pd.DataFrame(volumes, columns=["timestamp", "volume"])

  df = pd.merge(df_p, df_v, on="timestamp")
  df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")

  df["open"] = df["close"].shift(1).fillna(df["close"])
  df["high"] = df[["open", "close"]].max(axis=1)
  df["low"] = df[["open", "close"]].min(axis=1)

  return df.sort_values("dt").reset_index(drop=True)


def get_candles_1h(token_info):
  if token_info.get("coinbase"):
    try:
      df = fetch_from_coinbase(token_info["coinbase"], granularity=3600)
      if not df.empty and len(df) >= 3:
        return df
    except Exception:
      pass
  try:
    return fetch_from_coingecko(token_info["gecko_id"])
  except Exception:
    return pd.DataFrame()


def get_candles_1d(token_info):
  if token_info.get("coinbase"):
    try:
      df = fetch_from_coinbase(token_info["coinbase"], granularity=86400)
      if not df.empty and len(df) >= 3:
        return df
    except Exception:
      pass
  return pd.DataFrame()


def resample_ohlc(df_1h, rule):
  df = df_1h.copy()
  df.set_index("dt", inplace=True)
  return (
      df.resample(rule)
      .agg({
          "open": "first",
          "high": "max",
          "low": "min",
          "close": "last",
          "volume": "sum",
      })
      .dropna()
      .reset_index()
  )


def calc_rsi(series, period=14):
  if len(series) < 2:
    return 50.0
  period = min(period, len(series) - 1)
  delta = series.diff()
  gain = delta.clip(lower=0).rolling(period).mean()
  loss = (-delta.clip(upper=0)).rolling(period).mean()
  val = 100 - (100 / (1 + (gain.iloc[-1] / (loss.iloc[-1] + 1e-9))))
  return float(val) if not pd.isna(val) else 50.0


def calc_macd(series, span1=12, span2=26, signal=9):
  if len(series) < 3:
    return 0.0, 0.0, 0.0
  exp1 = series.ewm(span=min(span1, len(series)), adjust=False).mean()
  exp2 = series.ewm(span=min(span2, len(series)), adjust=False).mean()
  macd_line = exp1 - exp2
  signal_line = macd_line.ewm(
      span=min(signal, len(series)), adjust=False
  ).mean()
  return (
      float(macd_line.iloc[-1]),
      float(signal_line.iloc[-1]),
      float((macd_line - signal_line).iloc[-1]),
  )


def calc_vwap(df):
  if "volume" not in df.columns or df["volume"].sum() == 0:
    return float(df["close"].iloc[-1])
  typical_price = (df["high"] + df["low"] + df["close"]) / 3
  vwap = (typical_price * df["volume"]).cumsum() / (
      df["volume"].cumsum() + 1e-9
  )
  return float(vwap.iloc[-1])


def calc_obv(df):
  if "volume" not in df.columns or df["volume"].sum() == 0:
    return "Neutralny"
  direction = np.sign(df["close"].diff()).fillna(0)
  obv = (direction * df["volume"]).cumsum()
  if len(obv) > 2 and obv.iloc[-1] > obv.iloc[-2]:
    return "Akumulacja (Rosnący OBV)"
  elif len(obv) > 2 and obv.iloc[-1] < obv.iloc[-2]:
    return "Dystrybucja (Spadający OBV)"
  return "Brak wyraźnego trendu OBV"


def calc_rvol(df, period=20):
  if "volume" not in df.columns or df["volume"].sum() == 0 or len(df) < 2:
    return 1.0
  p = min(period, len(df))
  vol_sma = df["volume"].rolling(window=p).mean()
  avg_vol = float(vol_sma.iloc[-1])
  if avg_vol <= 0:
    return 1.0
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
    try:
      df_1h = get_candles_1h(item)
      if df_1h.empty or len(df_1h) < 2:
        continue

      df_4h = resample_ohlc(df_1h, "4h") if len(df_1h) >= 4 else df_1h.copy()
      df_1d = get_candles_1d(item)

      price = float(df_1h["close"].iloc[-1])
      prev_price_24h = float(
          df_1h["close"].iloc[-24]
          if len(df_1h) >= 24
          else df_1h["close"].iloc[0]
      )
      change_24h = (
          ((price - prev_price_24h) / prev_price_24h) * 100
          if prev_price_24h > 0
          else 0.0
      )

      log_returns = np.log(df_1h["close"] / df_1h["close"].shift(1)).dropna()
      vol_1h = float(log_returns.std()) if len(log_returns) > 2 else 0.015
      drift_1h = float(log_returns.mean()) if len(log_returns) > 2 else 0.0

      rsi_1h = calc_rsi(df_1h["close"])
      rsi_4h = calc_rsi(df_4h["close"]) if not df_4h.empty else 50.0
      rsi_1d = (
          calc_rsi(df_1d["close"])
          if not df_1d.empty and len(df_1d) >= 2
          else rsi_4h
      )

      _, _, macd_hist = (
          calc_macd(df_4h["close"]) if not df_4h.empty else (0.0, 0.0, 0.0)
      )
      vwap_val = calc_vwap(df_4h) if len(df_4h) > 0 else price
      obv_status = calc_obv(df_4h)
      rvol_val = calc_rvol(df_4h)

      if len(df_4h) > 1:
        tr = pd.concat([
            df_4h["high"] - df_4h["low"],
            (df_4h["high"] - df_4h["close"].shift()).abs(),
            (df_4h["low"] - df_4h["close"].shift()).abs(),
        ], axis=1).max(axis=1)
      else:
        tr = pd.Series([price * 0.02])

      atr = (
          float(tr.rolling(min(14, len(df_4h))).mean().iloc[-1])
          if len(tr) > 0
          else price * 0.02
      )
      ema200_4h = (
          float(
              df_4h["close"]
              .ewm(span=min(200, len(df_4h)), adjust=False)
              .mean()
              .iloc[-1]
          )
          if len(df_4h) > 0
          else price
      )

      sl = price - (2.5 * atr)
      support = float(df_4h["low"].min()) if len(df_4h) > 0 else price * 0.95
      resistance = (
          float(df_4h["high"].max()) if len(df_4h) > 0 else price * 1.05
      )

      risk = price - sl
      reward = resistance - price
      rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1

      if price > ema200_4h and macd_hist > 0:
        regime = "Silny Trend Wzrostowy"
      elif price > ema200_4h and macd_hist <= 0:
        regime = "Korekta w Trendzie Wzrostowym"
      elif price <= ema200_4h and macd_hist > 0:
        regime = "Próba Odbicia (Kontrtrend)"
      else:
        regime = "Strukturalny Trend Spadkowy"

      loaded_count += 1
      data.append({
          "Lp.": loaded_count,
          "Token": symbol,
          "Cena ($)": fmt(price),
          "24h (%)": round(change_24h, 2),
          "Reżim Rynkowy": regime,
          "RSI 1H": round(rsi_1h, 1),
          "RSI 4H": round(rsi_4h, 1),
          "RSI 1D": round(rsi_1d, 1),
          "RVOL (4H)": f"{rvol_val}x",
          "VWAP (4H)": fmt(vwap_val),
          "OBV Status": obv_status,
          "MACD Hist (4H)": fmt(macd_hist),
          "EMA 200 (4H)": fmt(ema200_4h),
          "SL (ATR)": fmt(sl),
          "Wsparcie": fmt(support),
          "Opór": fmt(resistance),
          "R:R": f"1:{rr_val}",
          "Price_Raw": price,
          "EMA200_Raw": ema200_4h,
          "Support_Raw": support,
          "Resistance_Raw": resistance,
          "RSI_1H_Raw": rsi_1h,
          "RSI_4H_Raw": rsi_4h,
          "RSI_1D_Raw": rsi_1d,
          "RVOL_Raw": rvol_val,
          "VWAP_Raw": vwap_val,
          "OBV_Raw": obv_status,
          "Regime_Raw": regime,
          "Vol_Raw": vol_1h,
          "Drift_Raw": drift_1h,
          "Is_Bouncing": False,
          "ATR_Raw": atr,
      })
    except Exception:
      continue

  return (
      pd.DataFrame(data),
      fng_val,
      fng_class,
      btc_dom,
      alt_season,
      loaded_count,
      len(TOKENS),
  )


# ==========================================
# SCORING I PREDYKCJE (MONTE CARLO 10 DNI)
# ==========================================
def run_predictions(
    df_ta, btc_dom, min_score_filter, max_rsi_filter, req_accumulation
):
  if df_ta.empty:
    return pd.DataFrame(), {}

  # POPRAWKA: Bezpieczne przekazanie ziarna (seed) jako int do default_rng
  seed_val = int(pd.Timestamp.now().strftime("%Y%m%d"))
  rng = np.random.default_rng(seed=seed_val)
  monte_carlo_paths = {}

  def analyze_row(row):
    symbol = row["Token"]
    price = float(row["Price_Raw"])
    vol_1h = float(row.get("Vol_Raw", 0.015))
    drift_1h = float(row.get("Drift_Raw", 0.0))
    regime = row["Regime_Raw"]
    rsi_1h = float(row["RSI_1H_Raw"])
    rsi_4h = float(row["RSI_4H_Raw"])
    obv_status = str(row.get("OBV_Raw", ""))
    rvol = float(row.get("RVOL_Raw", 1.0))
    resistance = float(row.get("Resistance_Raw", price * 1.05))

    adjusted_drift = drift_1h - (0.5 * (vol_1h**2))
    shocks = rng.normal(loc=adjusted_drift, scale=vol_1h, size=(5000, 240))
    cum_returns = np.exp(np.cumsum(shocks, axis=1))
    final_prices_paths = price * cum_returns

    monte_carlo_paths[symbol] = final_prices_paths

    p_24h = float(np.median(final_prices_paths[:, 23]))
    p_3d = float(np.median(final_prices_paths[:, 71]))
    p_10d = float(np.median(final_prices_paths[:, 239]))

    ci_lower_10d = float(np.percentile(final_prices_paths[:, 239], 2.5))
    ci_upper_10d = float(np.percentile(final_prices_paths[:, 239], 97.5))
    prob_up_10d = float(np.mean(final_prices_paths[:, 239] > price) * 100)

    score = 50.0
    if "Silny Trend Wzrostowy" in regime:
      score += 25.0
    elif "Korekta" in regime:
      score += 10.0
    elif "Spadkowy" in regime:
      score -= 20.0

    score += (rvol - 1.0) * 20.0
    if "Akumulacja" in obv_status:
      score += 12.0
    elif "Dystrybucja" in obv_status:
      score -= 15.0

    if rsi_4h < 45:
      score += (45 - rsi_4h) * 0.4
    elif rsi_4h > 65:
      score -= (rsi_4h - 65) * 0.6

    score = max(0.0, min(100.0, score))

    is_altcoin = symbol not in ["BTC", "ETH"]
    macro_headwind = btc_dom > 59.0 and is_altcoin

    is_overextended = (rsi_1h > 65.0) or (price >= resistance * 0.99)

    if macro_headwind:
      signal = "⏳ ODRZUCONY (Silna dominacja BTC)"
    elif is_overextended:
      signal = "❌ ODRZUCONY (Przegrzany – Unikamy szczytu)"
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
        f"${fmt(p_24h)}",
        f"${fmt(p_3d)}",
        f"${fmt(p_10d)}",
        f"${fmt(ci_lower_10d)} - ${fmt(ci_upper_10d)}",
        f"{round(prob_up_10d, 1)}%",
        signal,
        round(score, 2),
        p_10d,
    ])

  df_ml = df_ta.copy()
  df_ml[[
      "Prognoza 24h",
      "Prognoza 3D",
      "Prognoza 10D",
      "Zasięg MC 10D (95%)",
      "Szansa Wzrostu (10D)",
      "Ocena Przewagi (Edge)",
      "Smart Score (%)",
      "Prognoza_10D_Raw",
  ]] = df_ml.apply(analyze_row, axis=1)
  df_ml["Atrakcyjność (%)"] = df_ml["Smart Score (%)"]
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
  fig.add_trace(
      go.Scatter(
          x=np.concatenate([hours, hours[::-1]]),
          y=np.concatenate([upper_95, lower_95[::-1]]),
          fill="toself",
          fillcolor="rgba(59, 130, 246, 0.15)",
          line=dict(color="rgba(255,255,255,0)"),
          name="Przedział Ufności 95%",
          hoverinfo="skip",
      )
  )
  fig.add_trace(
      go.Scatter(
          x=hours,
          y=median_path,
          mode="lines",
          line=dict(color="#2563eb", width=3),
          name="Prognoza (Mediana MC)",
      )
  )
  fig.add_hline(
      y=current_price,
      line_dash="dash",
      line_color="gray",
      annotation_text="Obecna cena",
  )
  fig.add_hline(
      y=current_price * 1.06,
      line_dash="dot",
      line_color="green",
      annotation_text="Cel TP (+6%)",
  )
  fig.update_layout(
      title=f"📈 Prognoza Trajektorii Ceny 10D (Monte Carlo): {symbol}",
      xaxis_title="Godziny od teraz",
      yaxis_title="Cena ($)",
      template="plotly_white",
      height=400,
      margin=dict(l=20, r=20, t=50, b=20),
  )
  return fig


# ==========================================
# SYSTEM AUTO-ŚLEDZENIA ZAGRAŃ
# ==========================================
def auto_zapisz_sygnaly(df_ml, df_ta):
  if df_ml.empty:
    return
  kolumny = [
      "Data Wejścia",
      "Token",
      "Typ Sygnału",
      "Cena Wejścia ($)",
      "Cel TP (6%) ($)",
      "SL ($)",
      "Ekstremum ($)",
      "Data Wyjścia",
      "Status",
      "Zysk (%)",
  ]

  if os.path.exists(HISTORY_FILE):
    try:
      df_hist = pd.read_csv(HISTORY_FILE)
    except Exception:
      df_hist = pd.DataFrame(columns=kolumny)
  else:
    df_hist = pd.DataFrame(columns=kolumny)

  aktywne_tokeny = (
      df_hist[df_hist["Status"].str.contains("W toku", na=False)][
          "Token"
      ].tolist()
      if not df_hist.empty
      else []
  )

  nowe_wiersze = []
  okazje = df_ml[
      df_ml["Ocena Przewagi (Edge)"].str.contains("WYSOKI EDGE", na=False)
  ]

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
          "Zysk (%)": 0.0,
      })

  if nowe_wiersze:
    df_hist = pd.concat([df_hist, pd.DataFrame(nowe_wiersze)], ignore_index=True)
    df_hist.to_csv(HISTORY_FILE, index=False)


def aktualizuj_i_rozlicz_pozycje(df_ta):
  if not os.path.exists(HISTORY_FILE):
    return
  try:
    df_hist = pd.read_csv(HISTORY_FILE)
  except Exception:
    return
  if df_hist.empty:
    return

  now_dt = pd.Timestamp.now()
  now_str = now_dt.strftime("%Y-%m-%d %H:%M")
  price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))

  for idx, row in df_hist.iterrows():
    if "W toku" not in str(row["Status"]):
      continue

    token = row["Token"]
    if token not in price_map:
      continue

    curr_price = float(price_map[token])
    entry = float(row.get("Cena Wejścia ($)", curr_price))

    cel_tp = float(row.get("Cel TP (6%) ($)", entry * 1.06))
    sl = float(row.get("SL ($)", entry * 0.95))

    prev_extr = (
        float(row["Ekstremum ($)"])
        if "Ekstremum ($)" in row and pd.notna(row["Ekstremum ($)"])
        else entry
    )
    new_extr = max(prev_extr, curr_price)
    df_hist.at[idx, "Ekstremum ($)"] = round(new_extr, 5)

    curr_gain_pct = (
        ((curr_price - entry) / entry) * 100 if entry > 0 else 0.0
    )
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
# OBSZERNY RAPORT AI
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None, btc_dom=55.0):
  symbol = row_ta.get("Token", "UNKNOWN")
  price_raw = float(row_ta.get("Price_Raw", 0))
  ema_raw = float(row_ta.get("EMA200_Raw", 0))
  regime = row_ta.get("Reżim Rynkowy", "Neutralny")

  rsi_1h = float(row_ta.get("RSI_1H_Raw", 50))
  rsi_4h = float(row_ta.get("RSI_4H_Raw", 50))
  rsi_1d = float(row_ta.get("RSI_1D_Raw", 50))

  rvol_str = str(row_ta.get("RVOL (4H)", "1.0x"))
  vwap_val = float(row_ta.get("VWAP_Raw", price_raw))
  obv_status = str(row_ta.get("OBV Status", "Neutralny"))
  macd_hist = float(row_ta.get("MACD Hist (4H)", 0.0))

  support_str = str(row_ta.get("Wsparcie", "0.00"))
  resistance_str = str(row_ta.get("Opór", "0.00"))
  sl_str = str(row_ta.get("SL (ATR)", "0.00"))

  edge_status = (
      row_ml.get("Ocena Przewagi (Edge)", "-") if row_ml is not None else "-"
  )
  smart_score = (
      f"{float(row_ml.get('Smart Score (%)', 50.0)):.2f}"
      if row_ml is not None
      else "50.00"
  )
  prognoza_10d = (
      str(row_ml.get("Prognoza 10D", "-")) if row_ml is not None else "-"
  )
  zasieg_mc_10d = (
      str(row_ml.get("Zasięg MC 10D (95%)", "-")) if row_ml is not None else "-"
  )
  prob_up_10d = (
      str(row_ml.get("Szansa Wzrostu (10D)", "-"))
      if row_ml is not None
      else "-"
  )

  target_tp1 = price_raw * 1.06

  if "Silny Trend" in regime:
    pa_desc = (
        "Aktywo znajduje się w wyraźnym trendzie wzrostowym, notując cenę"
        f" powyżej kluczowej, 200-okresowej średniej kroczącej (EMA200:"
        f" ${fmt(ema_raw)})."
    )
  elif "Spadkowy" in regime:
    pa_desc = (
        "Cena notowana jest poniżej EMA200"
        f" (${fmt(ema_raw)}). Struktura ta definiuje strukturalny trend"
        " spadkowy, co zwiększa ryzyko dla pozycji długich."
    )
  else:
    pa_desc = (
        "Aktywo porusza się w fazie horyzontalnej konsolidacji, oscylując w"
        f" pobliżu EMA200 (${fmt(ema_raw)}). Sugeruje to walkę popytu z podażą."
    )

  btc_dom_desc = (
      f"Wskaźnik dominacji Bitcoina (obecnie na poziomie {btc_dom}%) określa,"
      " jaka część kapitału znajduje się w BTC. "
      + (
          "Wysoki poziom wysysa płynność z altcoinów, utrudniając im niezależne"
          " wzrosty."
          if btc_dom > 59.0
          else (
              "Umiarkowany trend dominacji sprzyja rotacji kapitału do"
              " altcoinów."
          )
      )
  )

  rvol_float = (
      float(rvol_str.replace("x", ""))
      if isinstance(rvol_str, str) and "x" in rvol_str
      else 1.0
  )
  if rvol_float >= 1.5:
    rvol_desc = (
        f"RVOL: Wynosi {rvol_str}. Podwyższony wolumen sugeruje ponadprzeciętne"
        " zaangażowanie dużego kapitału (Smart Money)."
    )
  elif rvol_float <= 0.7:
    rvol_desc = (
        f"RVOL: Wynosi {rvol_str}. Niski wolumen obrotu wskazuje na apatię"
        " rynkową i ryzyko fałszywych wybić."
    )
  else:
    rvol_desc = (
        f"RVOL: Wynosi {rvol_str}. Wolumen utrzymuje się w standardowych"
        " granicach."
    )

  vwap_desc = (
      f"VWAP (4H): Wynosi ${fmt(vwap_val)}. Cena bieżąca znajdująca się"
      f" {'powyżej' if price_raw > vwap_val else 'poniżej'} VWAP wskazuje na"
      f" śróddzienną przewagę {'kupujących' if price_raw > vwap_val else 'sprzedających'}."
  )
  obv_desc = (
      f"OBV: Status to {obv_status}. Odczyt sugeruje"
      f" {'systematyczną akumulację' if 'Akumulacja' in obv_status else 'realizację zysków (dystrybucję)' if 'Dystrybucja' in obv_status else 'równowagę sił'}."
  )

  rsi_desc = (
      f"RSI: Zestawienie wieloramowe (1H: {round(rsi_1h, 1)} | 4H:"
      f" {round(rsi_4h, 1)} | 1D: {round(rsi_1d, 1)}). Rynek"
      f" krótkoterminowo jest {'przegrzany' if rsi_4h > 65 else 'wyprzedany' if rsi_4h < 40 else 'w neutralnej strefie'}."
  )
  macd_desc = (
      f"MACD Hist (4H): Wynosi {fmt(macd_hist)}. Wartość"
      f" {'dodatnia potwierdza pęd wzrostowy' if macd_hist > 0 else 'ujemna ostrzega o przewadze podaży'}."
  )

  if "WYSOKI EDGE" in edge_status:
    final_reco = (
        "🟢 REKOMENDACJA: Zdecydowane zezwolenie na handel. Aktywo spełnia"
        " kryteria algorytmu, łącząc dobry potencjał zysku z poparciem"
        " wolumenu."
    )
  elif "NEUTRALNY" in edge_status:
    final_reco = (
        "🟡 REKOMENDACJA: Obserwacja. Zalecane oczekiwanie na dogodniejszą"
        " strefę wejścia."
    )
  else:
    final_reco = (
        "❌ REKOMENDACJA: Odrzucenie sygnału. Kondycja techniczna faworyzuje"
        " sprzedających."
    )

  return f"""
🎯 EKSPERCKA SYNTEZA MTF PRO: {symbol}
Werdykt: {edge_status} | Smart Score: {smart_score}% | Cena wejścia: ${fmt(price_raw)}

───

1. 🧠 Analiza Strukturalna i Makro
• Kondycja Trendu (Price Action vs EMA200): {pa_desc}
• Otoczenie Makro (Dominacja BTC): {btc_dom_desc}

2. 📊 Płynność i Ślady Smart Money
• {rvol_desc}
• {vwap_desc}
• {obv_desc}

3. 📈 Wskaźniki Pędu (Momentum)
• {rsi_desc}
• {macd_desc}

4. 🎲 Symulacja Monte Carlo
• Mediana prognozy (10 dni): {prognoza_10d} (Prawdopodobieństwo wzrostu: {prob_up_10d}).
• Przedział ufności 95% (10 dni): {zasieg_mc_10d}

5. 🛡️ Inżynieria Ryzyka
• Architektura Ceny: Wsparcie przy ${support_str}, opór przy ${resistance_str}.
• Stop Loss (ATR): ${sl_str}.
• Cel Taktyczny (TP1 +6%): ${fmt(target_tp1)}

───

📝 PODSUMOWANIE
Syntetyczna ocena (Smart Score): {smart_score}% | Reżim: {regime}.

{final_reco}
"""


# ==========================================
# INTERFEJS GŁÓWNY STREAMLIT (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane na żywo z API i przeliczam wskaźniki..."):
  df_ta, fng_val, fng_class, btc_dom, alt_season, loaded_c, total_c = (
      fetch_technical_analysis()
  )
  df_ml, mc_paths = run_predictions(
      df_ta, btc_dom, min_smart_score, max_rsi_4h, wymagaj_akumulacji
  )

  auto_zapisz_sygnaly(df_ml, df_ta)
  aktualizuj_i_rozlicz_pozycje(df_ta)

col_t, col_d1, col_d2, col_f = st.columns([2.0, 1, 1, 1])
col_t.title("📊 Analiza Krypto MTF Pro")
col_t.caption(
    f"Aktualizacja: {pd.Timestamp.now().strftime('%H:%M:%S')} | Załadowano:"
    f" {loaded_c}/{total_c}"
)
col_d1.metric("Dominacja BTC", f"{btc_dom}%")
col_d2.metric(
    "Sezon Altcoinów",
    f"{alt_season}/100",
    "Sezon BTC" if alt_season < 50 else "Sezon Alt",
)
col_f.metric("Fear & Greed", f"{fng_val}/100", fng_class)

st.markdown("---")

st.markdown("### 🔥 Najlepsze Okazje Zakupowe")
if not df_ml.empty:
  okazje_df = df_ml[
      df_ml["Ocena Przewagi (Edge)"].str.contains("WYSOKI EDGE", na=False)
  ]
  if not okazje_df.empty:
    cols_okazje = st.columns(min(len(okazje_df), 4))
    for i, (_, row) in enumerate(okazje_df.iterrows()):
      with cols_okazje[i % len(cols_okazje)]:
        score_val = float(row["Smart Score (%)"])
        st.success(
            f"**{row['Token']}**\n\nCena: {row['Cena ($)']}\nSmart Score:"
            f" {score_val:.2f}%\nPrognoza 10D: {row['Prognoza 10D']}"
        )
  else:
    st.info(
        "Obecnie żaden token nie spełnia restrykcyjnych warunków algorytmu"
        " (odfiltrowano przegrzane aktywa)."
    )

st.markdown("---")

if st.button("🔄 Odśwież dane", type="primary"):
  st.cache_data.clear()
  st.rerun()

df_ta_clean = df_ta.drop(
    columns=[
        "Price_Raw",
        "EMA200_Raw",
        "Support_Raw",
        "Resistance_Raw",
        "RSI_1H_Raw",
        "RSI_4H_Raw",
        "RSI_1D_Raw",
        "RVOL_Raw",
        "VWAP_Raw",
        "OBV_Raw",
        "Regime_Raw",
        "Vol_Raw",
        "Drift_Raw",
        "Is_Bouncing",
        "ATR_Raw",
    ],
    errors="ignore",
)
if "Atrakcyjność (%)" not in df_ta_clean.columns and not df_ml.empty:
  df_ta_clean["Atrakcyjność (%)"] = df_ml["Smart Score (%)"]

df_ml_widok = (
    df_ml.drop(columns=["Prognoza_10D_Raw"], errors="ignore")
    if not df_ml.empty
    else df_ml
)

config_tabel = {
    "Lp.": st.column_config.NumberColumn("Lp.", format="%d"),
    "Atrakcyjność (%)": st.column_config.NumberColumn(
        "Atrakcyjność (%)", format="%.2f"
    ),
    "Smart Score (%)": st.column_config.NumberColumn(
        "Smart Score (%)", format="%.2f"
    ),
    "24h (%)": st.column_config.NumberColumn("24h (%)", format="%.2f"),
    "RSI 1H": st.column_config.NumberColumn("RSI 1H", format="%.1f"),
    "RSI 4H": st.column_config.NumberColumn("RSI 4H", format="%.1f"),
    "RSI 1D": st.column_config.NumberColumn("RSI 1D", format="%.1f"),
}


def apply_high_contrast_striping(df):
  return df.style.apply(
      lambda row: [
          (
              "background-color: #f1f5f9; color: #0b0f19; font-weight: 500;"
              if row.name % 2 == 1
              else "background-color: #ffffff; color: #0b0f19; font-weight:"
              " 500;"
          )
          for _ in row
      ],
      axis=1,
  )


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. Reżimy",
    "2. Ocena Przewagi",
    "3. ⚡ Aktywne Pozycje",
    "4. 🗂️ Archiwum",
    "5. 📈 Skuteczność Algorytmu",
])

with tab1:
  st.dataframe(
      apply_high_contrast_striping(df_ta_clean),
      column_config=config_tabel,
      use_container_width=True,
      hide_index=True,
  )
with tab2:
  st.dataframe(
      apply_high_contrast_striping(df_ml_widok),
      column_config=config_tabel,
      use_container_width=True,
      hide_index=True,
  )
  st.markdown("---")
  st.subheader("➕ Śledź wybraną pozycję ręcznie")
  col_sel_tok, col_sel_btn = st.columns([2, 1])
  chosen_token = col_sel_tok.selectbox(
      "Wybierz token:", df_ml["Token"].tolist(), key="manual_token_pick"
  )

  if col_sel_btn.button("🚀 Dodaj do śledzenia", type="primary"):
    cena_we = float(
        df_ta[df_ta["Token"] == chosen_token].iloc[0]["Price_Raw"]
    )
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
        "Zysk (%)": 0.0,
    }])

    df_h = (
        pd.concat([pd.read_csv(HISTORY_FILE), nowa], ignore_index=True)
        if os.path.exists(HISTORY_FILE)
        else nowa
    )
    df_h.to_csv(HISTORY_FILE, index=False)
    st.success(
        f"Rozpoczęto śledzenie {chosen_token} po ${fmt(cena_we)} z celem TP"
        f" (+6%): ${fmt(cel_tp)}!"
    )
    st.rerun()

with tab3:
  if os.path.exists(HISTORY_FILE):
    try:
      df_hist = pd.read_csv(HISTORY_FILE)
      df_active = df_hist[df_hist["Status"].str.contains("W toku", na=False)]
      if not df_active.empty:
        st.dataframe(
            apply_high_contrast_striping(
                df_active.sort_values("Data Wejścia", ascending=False)
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info("Brak aktywnych pozycji.")
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
        st.dataframe(
            apply_high_contrast_striping(
                df_closed.sort_values("Data Wyjścia", ascending=False)
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.info(
            "Algorytm nie zamknął jeszcze żadnej transakcji po nowych regułach."
        )
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
        sukcesy = len(
            df_closed[df_closed["Status"].str.contains("✅", na=False)]
        )
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
        st.info("Algorytm zbiera dane...")
    except Exception:
      st.info("Brak danych.")
  else:
    st.info("Brak pliku z historią.")

if not df_ta.empty:
  st.divider()
  st.subheader("🤖 Ekspercki Raport Analityczny Pro")
  sel_ai = st.selectbox(
      "Wybierz token do dogłębnej analizy:", df_ta["Token"].tolist()
  )

  col_rep_text, col_rep_chart = st.columns([1.2, 1])

  with col_rep_text:
    row_t = df_ta[df_ta["Token"] == sel_ai].iloc[0]
    row_m = (
        df_ml[df_ml["Token"] == sel_ai].iloc[0] if not df_ml.empty else None
    )
    st.markdown(generuj_raport_ai(row_t, row_m, btc_dom))

  with col_rep_chart:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if sel_ai in mc_paths:
      current_price = float(
          df_ta[df_ta["Token"] == sel_ai].iloc[0]["Price_Raw"]
      )
      st.plotly_chart(
          plot_price_forecast(sel_ai, current_price, mc_paths[sel_ai]),
          use_container_width=True,
      )
    else:
      st.info("Brak danych symulacji dla tego tokena.")
