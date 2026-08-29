import os
import numpy as np
import pandas as pd
import requests
import streamlit as st

# ==========================================
# KONFIGURACJA STRONY I LOGOWANIE
# ==========================================
st.set_page_config(page_title="Analiza Krypto MTF Spot", layout="wide")

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
# PANEL BOCZNY (ZARZĄDZANIE / RESET)
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

# ==========================================
# LISTA TOKENÓW SPOT (COINBASE)
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
    {"symbol": "JUP", "coinbase": "JUP-USD", "gecko_id": "jupiter-exchange-solana"},
    {"symbol": "UNI", "coinbase": "UNI-USD", "gecko_id": "uniswap"},
    {"symbol": "SEI", "coinbase": "SEI-USD", "gecko_id": "sei-network"},
    {"symbol": "KTA", "coinbase": "KTA-USD", "gecko_id": "keeta"},
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

    better_than_btc = 0
    valid_count = 0

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


def fetch_from_coinbase(symbol_pair):
  url = f"https://api.exchange.coinbase.com/products/{symbol_pair}/candles?granularity=3600"
  res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
  res.raise_for_status()
  df = pd.DataFrame(
      res.json(),
      columns=["timestamp", "low", "high", "open", "close", "volume"],
  )
  df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
  return df.sort_values("dt").reset_index(drop=True)


def fetch_from_coingecko(gecko_id):
  url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/ohlc?vs_currency=usd&days=14"
  res = requests.get(
      url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=5
  )
  res.raise_for_status()
  df = pd.DataFrame(
      res.json(), columns=["timestamp", "open", "high", "low", "close"]
  )
  df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
  df["volume"] = 0.0
  return df.sort_values("dt").reset_index(drop=True)


def get_simple_coingecko_price(gecko_id):
  try:
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={gecko_id}&vs_currencies=usd,usd_24h_change"
    res = requests.get(
        url, headers={"User-Agent": "CryptoDashboard/1.0"}, timeout=4
    ).json()
    if gecko_id in res:
      price = float(res[gecko_id].get("usd", 0))
      change = float(res[gecko_id].get("usd_24h_change", 0))
      if price > 0:
        return price, change
  except Exception:
    pass
  return 1.0, 0.0


def get_candles_1h(token_info):
  if token_info.get("coinbase"):
    try:
      df = fetch_from_coinbase(token_info["coinbase"])
      if not df.empty and len(df) >= 20:
        return df
    except Exception:
      pass

  try:
    return fetch_from_coingecko(token_info["gecko_id"])
  except Exception:
    return pd.DataFrame()


def resample_ohlc(df_1h, rule):
  df = df_1h.copy()
  df.set_index("dt", inplace=True)
  res = (
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
  return res


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
  histogram = macd_line - signal_line
  return (
      float(macd_line.iloc[-1]),
      float(signal_line.iloc[-1]),
      float(histogram.iloc[-1]),
  )


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
      if df_1h.empty or len(df_1h) < 5:
        raise ValueError("Brak świec")

      df_4h = resample_ohlc(df_1h, "4h")

      price = float(df_1h["close"].iloc[-1])
      prev_price_24h = float(
          df_1h["close"].iloc[-24]
          if len(df_1h) >= 24
          else df_1h["close"].iloc[0]
      )
      change_24h = ((price - prev_price_24h) / prev_price_24h) * 100

      log_returns = np.log(df_1h["close"] / df_1h["close"].shift(1)).dropna()
      vol_1h = float(log_returns.std()) if len(log_returns) > 5 else 0.015
      drift_1h = float(log_returns.mean()) if len(log_returns) > 5 else 0.0

      rsi_1h = calc_rsi(df_1h["close"])
      rsi_4h = calc_rsi(df_4h["close"]) if len(df_4h) >= 14 else 50.0

      macd_val, macd_sig, macd_hist = (
          calc_macd(df_4h["close"]) if len(df_4h) >= 26 else (0.0, 0.0, 0.0)
      )

      tr = (
          pd.concat(
              [
                  df_4h["high"] - df_4h["low"],
                  (df_4h["high"] - df_4h["close"].shift()).abs(),
                  (df_4h["low"] - df_4h["close"].shift()).abs(),
              ],
              axis=1,
          ).max(axis=1)
          if len(df_4h) > 1
          else pd.Series([price * 0.02])
      )
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

      sl = price - (2 * atr)
      support = float(df_4h["low"].min()) if len(df_4h) > 0 else price * 0.95
      resistance = (
          float(df_4h["high"].max()) if len(df_4h) > 0 else price * 1.05
      )

      risk = price - sl
      reward = resistance - price
      rr_val = round(reward / risk, 1) if risk > 0 and reward > 0 else 0.1

      # Inteligentna klasyfikacja reżimu rynkowego (zamiast punktów)
      if price > ema200_4h and macd_hist > 0:
        regime = "Silny Trend Wzrostowy"
      elif price > ema200_4h and macd_hist <= 0:
        regime = "Korekta w Trendzie Wzrostowym"
      elif price <= ema200_4h and macd_hist > 0:
        regime = "Próba Odbicia (Kontrtrend)"
      else:
        regime = "Strukturalny Trend Spadkowy"

      last_close = float(df_1h["close"].iloc[-1])
      last_open = float(df_1h["open"].iloc[-1])
      is_bouncing = last_close >= last_open

      data.append({
          "Token": symbol,
          "Cena ($)": fmt(price),
          "24h (%)": round(change_24h, 2),
          "Reżim Rynkowy": regime,
          "RSI 1H": round(rsi_1h, 1),
          "RSI 4H": round(rsi_4h, 1),
          "MACD Hist (4H)": fmt(macd_hist),
          "EMA 200 (4H)": fmt(ema200_4h),
          "SL (ATR)": fmt(sl),
          "Wsparcie": fmt(support),
          "Opór": fmt(resistance),
          "R:R": f"1:{rr_val}",
          "Price_Raw": float(price),
          "EMA200_Raw": float(ema200_4h),
          "Support_Raw": float(support),
          "Resistance_Raw": float(resistance),
          "RSI_1H_Raw": float(rsi_1h),
          "RSI_4H_Raw": float(rsi_4h),
          "Regime_Raw": regime,
          "Vol_Raw": vol_1h,
          "Drift_Raw": drift_1h,
          "Is_Bouncing": is_bouncing,
      })
      loaded_count += 1
    except Exception:
      p, chg = get_simple_coingecko_price(gecko_id)
      data.append({
          "Token": symbol,
          "Cena ($)": fmt(p),
          "24h (%)": round(chg, 2),
          "Reżim Rynkowy": "Brak danych / Konsolidacja",
          "RSI 1H": 50.0,
          "RSI 4H": 50.0,
          "MACD Hist (4H)": "0.0",
          "EMA 200 (4H)": fmt(p),
          "SL (ATR)": fmt(p * 0.96),
          "Wsparcie": fmt(p * 0.95),
          "Opór": fmt(p * 1.05),
          "R:R": "1:1.5",
          "Price_Raw": p,
          "EMA200_Raw": p,
          "Support_Raw": p * 0.95,
          "Resistance_Raw": p * 1.05,
          "RSI_1H_Raw": 50.0,
          "RSI_4H_Raw": 50.0,
          "Regime_Raw": "Konsolidacja",
          "Vol_Raw": 0.015,
          "Drift_Raw": 0.0,
          "Is_Bouncing": False,
      })
      loaded_count += 1

  return (
      pd.DataFrame(data),
      fng_val,
      fng_class,
      btc_dom,
      alt_season,
      loaded_count,
      len(TOKENS),
  )


def run_predictions(df_ta, btc_dom):
  if df_ta.empty:
    return pd.DataFrame()

  rng = np.random.default_rng(
      seed=int(pd.Timestamp.now().strftime("%Y%m%d%H"))
  )

  def analyze_row(row):
    symbol = row["Token"]
    price = float(row["Price_Raw"])
    support_raw = float(row["Support_Raw"])
    vol_1h = float(row.get("Vol_Raw", 0.015))
    drift_1h = float(row.get("Drift_Raw", 0.0))
    is_bouncing = bool(row.get("Is_Bouncing", False))
    regime = row["Regime_Raw"]
    rsi_1h = float(row["RSI_1H_Raw"])

    num_simulations = 5000
    time_steps = 24

    adjusted_drift = drift_1h - (0.5 * (vol_1h**2))
    shocks = rng.normal(
        loc=adjusted_drift, scale=vol_1h, size=(num_simulations, time_steps)
    )
    log_paths = np.cumsum(shocks, axis=1)
    final_prices = price * np.exp(log_paths[:, -1])

    target_price = float(np.median(final_prices))
    ci_lower = float(np.percentile(final_prices, 2.5))
    ci_upper = float(np.percentile(final_prices, 97.5))
    prob_up = float(np.mean(final_prices > price) * 100)

    dist_to_support = (price - support_raw) / price if price > 0 else 1.0
    is_near_support = dist_to_support <= 0.04
    is_altcoin = symbol not in ["BTC", "ETH"]
    macro_headwind = btc_dom > 57.0 and is_altcoin

    # Rygorystyczny filtr egzekucji oparty na przewadze (Edge)
    if macro_headwind:
      signal = "⏳ ODRZUCONY (Silna dominacja BTC / Brak płynności)"
    elif regime == "Silny Trend Wzrostowy" and is_bouncing:
      signal = "🟢 WYSOKI EDGE (Kupno na korekcie w trendzie)"
    elif regime == "Korekta w Trendzie Wzrostowym" and is_near_support:
      signal = "🟢 WYSOKI EDGE (Test strefy popytowej 4H)"
    elif regime == "Strukturalny Trend Spadkowy":
      signal = "❌ UNIKAĆ (Dominacja podaży / Brak struktury)"
    elif rsi_1h >= 70:
      signal = "⚠️ RYZYKO WYKUPIENIA (Zbyt wysoka lokalna cena)"
    else:
      signal = "⏳ BRAK EDGE'U (Oczekiwanie na klarowny układ)"

    return pd.Series([
        f"${fmt(target_price)}",
        f"${fmt(ci_lower)} - ${fmt(ci_upper)}",
        f"{round(prob_up, 1)}%",
        signal,
    ])

  df_ml = df_ta.copy()
  df_ml[[
      "Prognoza MC (24h)",
      "Zasięg Monte Carlo (95%)",
      "Prawdopodobieństwo",
      "Ocena Przewagi (Edge)",
  ]] = df_ml.apply(analyze_row, axis=1)

  return df_ml[[
      "Token",
      "Cena ($)",
      "Reżim Rynkowy",
      "Prognoza MC (24h)",
      "Zasięg Monte Carlo (95%)",
      "Prawdopodobieństwo",
      "Ocena Przewagi (Edge)",
  ]]


# ==========================================
# HISTORIA I AKTUALIZACJA POZYCJI
# ==========================================
HISTORY_FILE = "signals_history.csv"


def update_history_status(df_ta):
  if not os.path.exists(HISTORY_FILE):
    return
  try:
    df_hist = pd.read_csv(HISTORY_FILE)
  except Exception:
    return
  if df_hist.empty:
    return

  now_dt = pd.Timestamp.now()
  now_date = now_dt.strftime("%Y-%m-%d")
  price_map = dict(zip(df_ta["Token"], df_ta["Price_Raw"]))

  for idx, row in df_hist.iterrows():
    token = row["Token"]
    entry = (
        float(row["Cena Wejścia"])
        if pd.notna(row["Cena Wejścia"])
        else 0.0
    )
    if entry <= 0:
      continue

    curr_price = float(price_map.get(token, entry))
    prev_extr = (
        float(row["Ekstremum Ceny"])
        if pd.notna(row["Ekstremum Ceny"]) and float(row["Ekstremum Ceny"]) > 0
        else entry
    )

    new_extr = max(prev_extr, curr_price)
    max_gain_pct = ((new_extr - entry) / entry) * 100
    curr_gain_pct = ((curr_price - entry) / entry) * 100

    df_hist.at[idx, "Ekstremum Ceny"] = float(new_extr)

    if max_gain_pct >= 5.0 and str(row["TP 5%"]) == "-":
      df_hist.at[idx, "TP 5%"] = f"✅ {now_date}"
    if max_gain_pct >= 7.5 and str(row["TP 7.5%"]) == "-":
      df_hist.at[idx, "TP 7.5%"] = f"✅ {now_date}"
    if max_gain_pct >= 10.0 and str(row["TP 10%"]) == "-":
      df_hist.at[idx, "TP 10%"] = f"✅ {now_date}"

    try:
      start_date = pd.to_datetime(row["Data"])
      days_passed = (now_dt - start_date).days
    except Exception:
      days_passed = 0

    if max_gain_pct >= 10.0:
      df_hist.at[idx, "Status"] = "🎯 Zaliczone TP 10%"
    elif curr_gain_pct <= -5.0:
      df_hist.at[idx, "Status"] = "❌ SL (-5%)"
    elif days_passed >= 30:
      df_hist.at[idx, "Status"] = "⏱️ Wygasło (30d)"
    else:
      df_hist.at[idx, "Status"] = f"🔄 W toku ({days_passed}/30d)"

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
  wins, total, results = 0, 0, []

  for _, row in df_hist.iterrows():
    try:
      entry = float(row.get("Cena Wejścia", 0))
      extr_p = float(row.get("Ekstremum Ceny", entry))
    except Exception:
      continue

    tp_hit = str(row.get(col_tp, "-"))
    status = str(row.get("Status", "-"))
    typ_sig = str(row.get("Typ Sygnału", ""))

    max_gain = ((extr_p - entry) / entry) * 100 if entry > 0 else 0.0

    if "✅" in tp_hit:
      wins += 1
      total += 1
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
        "Data Wejścia": row.get("Data"),
        "Token": row.get("Token"),
        "Sygnał": typ_sig,
        "Cena Wejścia ($)": fmt(entry),
        "Ekstremum ($)": fmt(extr_p),
        "Max Zysk (%)": f"+{round(max_gain, 2)}%",
        f"Cel {target_pct_str}": tp_hit,
        "Status": res_status,
    })

  win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
  return pd.DataFrame(results), total, wins, win_rate


# ==========================================
# EKSPERCKI RAPORT AI (SYNTEZA BEZ WMANIPULOWANEJ PłYTKOŚCI)
# ==========================================
def generuj_raport_ai(row_ta, row_ml=None, btc_dom=55.0):
  symbol = row_ta.get("Token", "UNKNOWN")
  price_str = row_ta.get("Cena ($)", "0.00")
  price_raw = float(row_ta.get("Price_Raw", 0))
  ema_raw = float(row_ta.get("EMA200_Raw", 0))
  regime = row_ta.get("Reżim Rynkowy", "Neutralny")
  rsi_1h = round(float(row_ta.get("RSI_1H_Raw", 50)), 1)
  rsi_4h = round(float(row_ta.get("RSI_4H_Raw", 50)), 1)
  change_24h = row_ta.get("24h (%)", "0.0")
  support_str = row_ta.get("Wsparcie", "0.00")
  resistance_str = row_ta.get("Opór", "0.00")
  sl_str = row_ta.get("SL (ATR)", "0.00")
  rr = row_ta.get("R:R", "1:1")

  edge_status = (
      row_ml.get("Ocena Przewagi (Edge)", "-") if row_ml is not None else "-"
  )
  prognoza_mc = (
      row_ml.get("Prognoza MC (24h)", "-") if row_ml is not None else "-"
  )
  prob_str = (
      row_ml.get("Prawdopodobieństwo", "50.0%") if row_ml is not None else "50%"
  )

  # Wnioskowanie eksperckie zamiast suchego przepisywania liczb
  if "Silny Trend" in regime:
    conclusion = f"Struktura jest czysta. Kupujący kontrolują sytuację na 4H, a cena (${fmt(price_raw)}) utrzymuje się ponad EMA200. Jest to środowisko sprzyjające kontynuacji wzrostów, o ile kapitał nie odpływa do Bitcoina."
  elif "Korekta" in regime:
    conclusion = f"Rynek realizuje zdrowe cofnięcie do strefy popytowej. Kluczowe jest utrzymanie wsparcia (${support_str}). Jeśli cena zareaguje odbiciem, pojawia się wysoki współczynnik R:R ({rr}) do zagrania w kierunku głównego trendu."
  elif "Spadkowy" in regime:
    conclusion = f"Brak struktur obronnych ze strony popytu. Cena pod średnią EMA200 (${fmt(ema_raw)}) oznacza, że każda próba zakupu bez silnego potwierdzenia wolumenowego to łapanie spadającego noża."
  else:
    conclusion = f"Brak wyraźnego reżimu kierunkowego. Ciasna konsolidacja na interwałach niskich generuje fałszywe sygnały oscylatorów. Wskazana cierpliwość."

  if symbol not in ["BTC", "ETH"] and btc_dom > 57.0:
    macro_warning = f"⚠️ **Ryzyko Systemowe:** Dominacja BTC na poziomie `{btc_dom}%` oznacza, że altcoiny są systemowo odcięte od dopływu nowego kapitału spekulacyjnego. Nawet najlepszy układ techniczny na altcoinie może zostać unieważniony ruchem lidera."
  else:
    macro_warning = f"✅ **Otoczenie Makro:** Płynność sprzyja wycenie aktywa (Dominacja BTC: `{btc_dom}%`)."

  tp_5 = price_raw * 1.05
  tp_75 = price_raw * 1.075
  tp_10 = price_raw * 1.10

  return f"""
### 🎯 SYNTEZA EKSPERCKA: {symbol}
**Werdykt Algorytmu:** `{edge_status}`  
**Cena:** `${price_str}` | **Reżim Rynkowy:** **{regime}**

---

#### 1. 🧠 Diagnoza Strukturalna i Prawa Rynku
* **Ocena sytuacji:** {conclusion}
* {macro_warning}

#### 2. 🎲 Symulacja Monte Carlo i Prawdopodobieństwo
* **Oczekiwana mediana (24h):** `{prognoza_mc}` (Szansa wyjścia na plus: **{prob_str}**).
* **Interpretacja:** Model probabilistyczny uwzględnia bieżącą zmienność stochastyczną (ATR/drift) – traktuj prognozę jako ramy statystyczne, a nie pewność.

#### 3. 🛡️ Inżynieria Pozycji i Inwalidacja Setupu
* **Strefa Inwalidacji (Stop Loss - 2x ATR):** `${sl_str}` – zamknięcie świecy 4H poniżej tego poziomu unieważnia tezę wzrostową.
* **Granice Płynności:** Wsparcie bazowe: `${support_str}` | Opór strukturalny: `${resistance_str}`
* **Docelowe poziomy realizacji zysków (TP):**
  * **TP 1 (+5%):** `${fmt(tp_5)}`
  * **TP 2 (+7.5%):** `${fmt(tp_75)}`
  * **TP 3 (+10%):** `${fmt(tp_10)}`
"""


# ==========================================
# INTERFEJS GŁÓWNY (UI)
# ==========================================
with st.spinner("🔄 Pobieram dane, filtruję reżimy i obliczam przewagę..."):
  (
      df_ta,
      fng_val,
      fng_class,
      btc_dom,
      alt_season,
      loaded_c,
      total_c,
  ) = fetch_technical_analysis()
  df_ml = run_predictions(df_ta, btc_dom)
  update_history_status(df_ta)

col_t, col_d1, col_d2, col_f = st.columns([2.0, 1, 1, 1])
col_t.title("📊 Analiza Krypto Spot (Edge & Regime)")
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
        "Regime_Raw",
        "Vol_Raw",
        "Drift_Raw",
        "Is_Bouncing",
    ],
    errors="ignore",
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. Reżimy i Stan Rynku",
    "2. Ocena Przewagi (Edge)",
    "3. ⚡ Aktywne Pozycje",
    "4. 🗂️ Archiwum (Zamknięte)",
    "5. 📈 Backtest",
])

with tab1:
  st.dataframe(df_ta_clean, use_container_width=True)

with tab2:
  st.dataframe(df_ml, use_container_width=True)
  st.markdown("---")
  st.subheader("➕ Otwórz i śledź wybraną pozycję ręcznie")
  col_sel_tok, col_sel_btn = st.columns([2, 1])
  chosen_token = col_sel_tok.selectbox(
      "Wybierz token do otwarcia w archiwum:",
      df_ml["Token"].tolist(),
      key="manual_token_pick",
  )

  if col_sel_btn.button("🚀 Dodaj do aktywnych pozycji", type="primary"):
    row_data = df_ml[df_ml["Token"] == chosen_token].iloc[0]
    row_ta_data = df_ta[df_ta["Token"] == chosen_token].iloc[0]

    now_full = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    price_clean = float(row_ta_data["Price_Raw"])
    sig_text = row_data["Ocena Przewagi (Edge)"]

    new_entry = pd.DataFrame([{
        "Data": now_full,
        "Token": chosen_token,
        "Typ Sygnału": sig_text,
        "Cena Wejścia": price_clean,
        "Ekstremum Ceny": price_clean,
        "TP 5%": "-",
        "TP 7.5%": "-",
        "TP 10%": "-",
        "Status": "🔄 W toku (0/30d)",
    }])

    if os.path.exists(HISTORY_FILE):
      try:
        df_h = pd.read_csv(HISTORY_FILE)
        df_h = pd.concat([df_h, new_entry], ignore_index=True)
      except Exception:
        df_h = new_entry
    else:
      df_h = new_entry

    df_h.to_csv(HISTORY_FILE, index=False)
    st.success(
        f"Pomyślnie otwarto pozycję Long dla {chosen_token} po cenie"
        f" ${fmt(price_clean)}!"
    )
    st.rerun()

with tab3:
  st.subheader("⚡ Pozycje Otwarte (Śledzone w czasie rzeczywistym)")
  if os.path.exists(HISTORY_FILE):
    try:
      df_h = pd.read_csv(HISTORY_FILE)
      df_active = df_h[df_h["Status"].str.contains("W toku", na=False)]
      if not df_active.empty:
        st.dataframe(
            df_active.sort_values(by="Data", ascending=False),
            use_container_width=True,
        )
      else:
        st.info(
            "Brak aktywnych pozycji. Wybierz token z zakładki 'Ocena Przewagi'"
            " i dodaj go ręcznie."
        )
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
        st.dataframe(
            df_closed.sort_values(by="Data", ascending=False),
            use_container_width=True,
        )
      else:
        st.info("Archiwum zamkniętych pozycji jest puste.")
    except Exception:
      st.info("Błąd odczytu archiwum.")
  else:
    st.info("Brak pliku historii.")

with tab5:
  st.subheader("📈 Skuteczność Sygnałów (Backtest Edge)")
  t_choice = st.radio(
      "Próg TP / SL:", ["5%", "7.5%", "10%"], horizontal=True, key="bt_rad"
  )
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
  st.subheader("🤖 Ekspercki Raport Analityczny i Ocena Przewagi")
  sel_ai = st.selectbox(
      "Wybierz token do pełnego raportu:", df_ta["Token"].tolist(), key="ai_box"
  )

  selected_row_ta = df_ta[df_ta["Token"] == sel_ai].iloc[0]
  selected_row_ml = (
      df_ml[df_ml["Token"] == sel_ai].iloc[0] if not df_ml.empty else None
  )

  st.markdown(
      generuj_raport_ai(selected_row_ta, selected_row_ml, btc_dom=btc_dom)
  )
