import os
import numpy as np
import pandas as pd
import requests
import gradio as gr

# ==========================================
# KONFIGURACJA I DANE RYNKOWE
# ==========================================
HISTORY_FILE = "signals_history.csv"

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
          "Vol_Raw": 0.015, "Drift_Raw": 0.0, "Is_Bouncing": False,
      })
      loaded_count += 1

  return pd.DataFrame(data), fng_val, fng_class, btc_dom, alt_season, loaded_count, len(TOKENS)

def run_predictions(df_ta, btc_dom, min_score_filter, max_rsi_filter, req_accumulation):
  if df_ta.empty: return pd.DataFrame()
  rng = np.random.default_rng(seed=int(pd.Timestamp.now().strftime("%Y%m%d%H")))

  def analyze_row(row):
    symbol = row["Token"]
    price = float(row["Price_Raw"])
    vol_1h = float(row.get("Vol_Raw", 0.015))
    drift_1h = float(row.get("Drift_Raw", 0.0))
    regime = row["Regime_Raw"]
    rsi_4h = float(row["RSI_4H_Raw"])
    obv_status = str(row.get("OBV_Raw", ""))
    rvol = float(row.get("RVOL_Raw", 1.0))

    adjusted_drift = drift_1h - (0.5 * (vol_1h**2))
    shocks = rng.normal(loc=adjusted_drift, scale=vol_1h, size=(5000, 24))
    final_prices = price * np.exp(np.cumsum(shocks, axis=1)[:, -1])
    target_price = float(np.median(final_prices))
    ci_lower = float(np.percentile(final_prices, 2.5))
    ci_upper = float(np.percentile(final_prices, 97.5))
    prob_up = float(np.mean(final_prices > price) * 100)

    score = 50.0 
    if "Silny Trend Wzrostowy" in regime: score += 30.0
    elif "Korekta" in regime: score += 15.0
    elif "Spadkowy" in regime: score -= 25.0

    if rvol >= 1.2: score += 10.0
    elif rvol < 0.6: score -= 10.0

    if "Akumulacja" in obv_status: score += 10.0
    elif "Dystrybucja" in obv_status: score -= 15.0

    if rsi_4h < 40: score += 10.0
    elif rsi_4h > 70: score -= 20.0

    score = max(0.0, min(100.0, score))

    is_altcoin = symbol not in ["BTC", "ETH"]
    macro_headwind = btc_dom > 59.0 and is_altcoin

    if macro_headwind:
      signal = "⏳ ODRZUCONY (Silna dominacja BTC)"
    elif score >= min_score_filter and rsi_4h <= max_rsi_filter:
      if req_accumulation and "Akumulacja" not in obv_status:
        signal = "🟡 NEUTRALNY (Brak akumulacji)"
      else:
        signal = "🟢 WYSOKI EDGE (Okazja)"
    elif score >= 55.0:
      signal = "🟡 NEUTRALNY (Obserwacja)"
    else:
      signal = "❌ ODRZUCONY (Słaba struktura)"

    return pd.Series([
        f"${fmt(target_price)}", f"${fmt(ci_lower)} - ${fmt(ci_upper)}",
        f"{round(prob_up, 1)}%", signal, score
    ])

  df_ml = df_ta.copy()
  df_ml[["Prognoza MC (24h)", "Zasięg Monte Carlo (95%)", "Prawdopodobieństwo", "Ocena Przewagi (Edge)", "Smart Score (%)"]] = df_ml.apply(analyze_row, axis=1)
  df_ml["Atrakcyjność (%)"] = df_ml["Smart Score (%)"]
  return df_ml[["Token", "Cena ($)", "Reżim Rynkowy", "Atrakcyjność (%)", "Smart Score (%)", "Prognoza MC (24h)", "Zasięg Monte Carlo (95%)", "Ocena Przewagi (Edge)", "Prawdopodobieństwo"]]

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

def generuj_raport_ai(row_ta, row_ml=None, btc_dom=55.0):
  symbol = row_ta.get("Token", "UNKNOWN")
  price_raw = float(row_ta.get("Price_Raw", 0))
  ema_raw = float(row_ta.get("EMA200_Raw", 0))
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
  
  prognoza_mc = row_ml.get("Prognoza MC (24h)", "-") if row_ml is not None else "-"
  prob_up = row_ml.get("Prawdopodobieństwo", "-") if row_ml is not None else "-"

  if "Silny Trend" in regime: 
      struct_desc = f"Struktura rynkowa dla {symbol} jest wysoce optymistyczna. Cena (${fmt(price_raw)}) stabilnie utrzymuje się ponad długoterminową średnią kroczącą EMA200 (${fmt(ema_raw)}). Potwierdza to pełną dominację obozu kupujących."
  elif "Korekta" in regime: 
      struct_desc = f"Aktywo realizuje obecnie kontrolowane cofnięcie. Cena (${fmt(price_raw)}) schodzi w okolice poziomów popytowych, utrzymując się nad EMA200 (${fmt(ema_raw)}). Klasyczny układ 'buy the dip'."
  elif "Spadkowy" in regime: 
      struct_desc = f"Struktura cenowa pod presją podaży. Cena (${fmt(price_raw)}) poniżej EMA200 (${fmt(ema_raw)}). Kontrolę przejmują niedźwiedzie."
  else: 
      struct_desc = "Walor w fazie konsolidacji bocznej. Brak zdecydowanego kierunku generuje szum techniczny."

  is_altcoin = symbol not in ["BTC", "ETH"]
  if is_altcoin and btc_dom > 59.0:
      macro_desc = f"⚠️ Dominacja Bitcoina wynosi aż `{btc_dom}%`. Kapitał koncentruje się na BTC, odcinając altcoiny od płynności."
  else:
      macro_desc = f"✅ Dominacja Bitcoina na poziomie `{btc_dom}%` sprzyja rotacji kapitału na altcoiny."

  rvol_float = float(rvol_str.replace("x", "")) if "x" in rvol_str else 1.0
  if rvol_float >= 1.5: rvol_desc = "Wybitnie wysoki wolumen napędzany kapitałem instytucjonalnym."
  elif rvol_float >= 1.0: rvol_desc = "Wolumen w normie, stabilne zainteresowanie."
  else: rvol_desc = "Brak płynności i zaangażowania dużych graczy (ryzyko fałszywych wybić)."

  if "WYSOKI EDGE" in edge_status: final_reco = "**Rekomendacja:** Zdecydowane **Zezwolenie na handel (🟢)**. Wysoka przewaga statystyczna. Rozważ pozycję Long."
  elif "NEUTRALNY" in edge_status: final_reco = "**Rekomendacja:** Status **Obserwacja (🟡)**. Wymagane potwierdzenie struktury."
  else: final_reco = "**Rekomendacja:** Sygnał **Odrzucony (❌)**. Ochrona kapitału, pozostanie w gotówce."

  return f"""### 🎯 EKSPERCKA SYNTEZA MTF PRO: {symbol}
**Werdykt:** `{edge_status}` | **Smart Score:** **{smart_score}%** | **Cena:** `${fmt(price_raw)}` | **Reżim:** **{regime}**

---
#### 1. 🧠 Analiza Strukturalna i Makroekonomiczna
* **Price Action:** {struct_desc}
* **Otoczenie Makro:** {macro_desc}

#### 2. 📊 Płynność, Wolumen i Smart Money
* **RVOL (4H):** `{rvol_str}`. {rvol_desc}
* **OBV Status:** `{obv_status}`.
* **VWAP (4H):** `${fmt(vwap_val)}`.

#### 3. 📈 Wskaźniki Pędu (Multi-Timeframe)
* **RSI:** 1H (`{round(rsi_1h, 1)}`) | 4H (`{round(rsi_4h, 1)}`) | 1D (`{round(rsi_1d, 1)}`)
* **MACD Hist (4H):** `{fmt(macd_hist)}`

#### 4. 🎲 Analiza Stochastyczna (Monte Carlo 24h)
* **Prognoza Mediany:** `{prognoza_mc}` (Szansa na wzrost: `{prob_up}`).

#### 5. 🛡️ Inżynieria Ryzyka
* **Stop Loss:** `{sl_str}` | **R:R:** `{row_ta.get('R:R')}`
* **Poziomy:** Wsparcie: `{support_str}` | Opór: `{resistance_str}`
* **Cele TP:** TP1: `${fmt(price_raw * 1.05)}` | TP2: `${fmt(price_raw * 1.075)}` | TP3: `${fmt(price_raw * 1.10)}`

---
#### 🏁 6. Podsumowanie
{final_reco}"""

# ==========================================
# INTERFEJS GRADIO Z WŁASNYM STYLIZOWANIEM CSS
# ==========================================
custom_css = """
/* Naprzemienne kolorowanie wierszy w tabelach Dataframe w motywie ciemnym Gradio */
.gradio-container table tbody tr:nth-child(odd) {
    background-color: var(--neutral-900) !important;
}
.gradio-container table tbody tr:nth-child(even) {
    background-color: var(--neutral-950) !important;
}
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
  gr.Markdown("# 📊 Analiza Krypto MTF Pro")
  
  # Pobranie danych początkowych
  df_ta, fng_val, fng_class, btc_dom, alt_season, loaded_c, total_c = fetch_technical_analysis()
  update_history_status(df_ta)
  
  with gr.Row():
    metric_btc = gr.Number(value=btc_dom, label="Dominacja BTC (%)", interactive=False)
    metric_alt = gr.Number(value=alt_season, label="Sezon Altcoinów (/100)", interactive=False)
    metric_fng = gr.Textbox(value=f"{fng_val}/100 ({fng_class})", label="Fear & Greed", interactive=False)

  min_smart_score = gr.Slider(0.0, 100.0, value=65.0, step=1.0, label="Minimalny Smart Score (%)")
  max_rsi_4h = gr.Slider(10.0, 90.0, value=60.0, step=1.0, label="Maksymalny RSI 4H")
  wymagaj_akumulacji = gr.Checkbox(value=True, label="Wymagaj Akumulacji (OBV)")
  
  df_ml = run_predictions(df_ta, btc_dom, min_smart_score.value, max_rsi_4h.value, wymagaj_akumulacji.value)

  with gr.Tabs():
    with gr.TabItem("1. Reżimy"):
      df_ta_clean = df_ta.drop(columns=["Price_Raw", "EMA200_Raw", "Support_Raw", "Resistance_Raw", "RSI_1H_Raw", "RSI_4H_Raw", "RSI_1D_Raw", "RVOL_Raw", "VWAP_Raw", "OBV_Raw", "Regime_Raw", "Vol_Raw", "Drift_Raw", "Is_Bouncing"], errors="ignore")
      table_rezimy = gr.DataFrame(value=df_ta_clean, interactive=False)
      
    with gr.TabItem("2. Ocena Przewagi (Smart Score)"):
      table_smart = gr.DataFrame(value=df_ml.drop(columns=["Prawdopodobieństwo"], errors="ignore"), interactive=False)
      
    with gr.TabItem("3. ⚡ Aktywne Pozycje"):
      if os.path.exists(HISTORY_FILE):
        df_act = pd.read_csv(HISTORY_FILE)
        df_active = df_act[df_act["Status"].str.contains("W toku", na=False)]
      else:
        df_active = pd.DataFrame()
      table_active = gr.DataFrame(value=df_active, interactive=False)
      
    with gr.TabItem("4. 🗂️ Archiwum"):
      if os.path.exists(HISTORY_FILE):
        df_all = pd.read_csv(HISTORY_FILE)
        df_closed = df_all[~df_all["Status"].str.contains("W toku", na=False)]
      else:
        df_closed = pd.DataFrame()
      table_closed = gr.DataFrame(value=df_closed, interactive=False)
      
    with gr.TabItem("5. 📈 Backtest"):
      t_choice = gr.Radio(["5%", "7.5%", "10%"], value="5%", label="Próg TP / SL")
      bt_df, tot, wins, wr = get_backtest_stats("5%")
      table_bt = gr.DataFrame(value=bt_df, interactive=False)
      
      def update_backtest(choice):
        b_df, t, w, rate = get_backtest_stats(choice)
        return b_df
      t_choice.change(update_backtest, inputs=t_choice, outputs=table_bt)

  gr.Markdown("---")
  gr.Markdown("### 🤖 Ekspercki Raport Analityczny Pro")
  token_dropdown = gr.Dropdown(choices=df_ta["Token"].tolist(), value=df_ta["Token"].iloc[0] if not df_ta.empty else "", label="Wybierz token do dogłębnej analizy")
  ai_report_output = gr.Markdown(value=generuj_raport_ai(df_ta.iloc[0], df_ml.iloc[0] if not df_ml.empty else None, btc_dom) if not df_ta.empty else "Brak danych")

  def update_report(selected_token):
    if df_ta.empty: return "Brak danych"
    row_t = df_ta[df_ta["Token"] == selected_token].iloc[0]
    row_m = df_ml[df_ml["Token"] == selected_token].iloc[0] if not df_ml.empty else None
    return generuj_raport_ai(row_t, row_m, btc_dom)

  token_dropdown.change(update_report, inputs=token_dropdown, outputs=ai_report_output)

  refresh_btn = gr.Button("🔄 Odśwież dane", variant="primary")
  
  def refresh_all(min_score, max_rsi, req_acc):
    d_ta, f_v, f_c, b_d, a_s, _, _ = fetch_technical_analysis()
    update_history_status(d_ta)
    d_ml = run_predictions(d_ta, b_d, min_score, max_rsi, req_acc)
    d_ta_cl = d_ta.drop(columns=["Price_Raw", "EMA200_Raw", "Support_Raw", "Resistance_Raw", "RSI_1H_Raw", "RSI_4H_Raw", "RSI_1D_Raw", "RVOL_Raw", "VWAP_Raw", "OBV_Raw", "Regime_Raw", "Vol_Raw", "Drift_Raw", "Is_Bouncing"], errors="ignore")
    
    act_df = pd.read_csv(HISTORY_FILE) if os.path.exists(HISTORY_FILE) else pd.DataFrame()
    active_res = act_df[act_df["Status"].str.contains("W toku", na=False)] if not act_df.empty else pd.DataFrame()
    closed_res = act_df[~act_df["Status"].str.contains("W toku", na=False)] if not act_df.empty else pd.DataFrame()
    
    first_tok = d_ta["Token"].iloc[0] if not d_ta.empty else ""
    rep = generuj_raport_ai(d_ta.iloc[0], d_ml.iloc[0] if not d_ml.empty else None, b_d) if not d_ta.empty else ""
    
    return b_d, a_s, f"{f_v}/100 ({f_c})", d_ta_cl, d_ml.drop(columns=["Prawdopodobieństwo"], errors="ignore"), active_res, closed_res, gr.update(choices=d_ta["Token"].tolist(), value=first_tok), rep

  refresh_btn.click(
      refresh_all,
      inputs=[min_smart_score, max_rsi_4h, wymagaj_akumulacji],
      outputs=[metric_btc, metric_alt, metric_fng, table_rezimy, table_smart, table_active, table_closed, token_dropdown, ai_report_output]
  )

if __name__ == "__main__":
  demo.launch()
