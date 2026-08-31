from dataclasses import dataclass
from typing import Optional
import pandas as pd
from indicators import ema, vwap

@dataclass
class Signal:
    side: str              # "buy" or "sell"
    entry: float
    stop: float
    target: Optional[float]
    reason: str
    strategy: str

def breakout_strategy(df: pd.DataFrame, range_bars: int, hold_bars: int, vol_mult: float) -> Optional[Signal]:
    if len(df) < max(range_bars + hold_bars + 10, 60):
        return None

    recent = df.iloc[-(range_bars + hold_bars):-hold_bars]
    highs = recent["high"].max()
    lows = recent["low"].min()

    hold = df.iloc[-hold_bars:]
    last_close = float(df.iloc[-1]["close"])
    avg_vol = recent["volume"].mean()
    last_vol = float(df.iloc[-1]["volume"])

    if (hold["close"] > highs).all() and last_vol > avg_vol * vol_mult:
        entry = last_close
        stop = float(df.iloc[-1]["low"])
        target = entry + (highs - lows)
        return Signal("buy", entry, stop, target, f"Breakout above {highs:.5f} with volume expansion", "BREAKOUT")

    if (hold["close"] < lows).all() and last_vol > avg_vol * vol_mult:
        entry = last_close
        stop = float(df.iloc[-1]["high"])
        target = entry - (highs - lows)
        return Signal("sell", entry, stop, target, f"Breakdown below {lows:.5f} with volume expansion", "BREAKOUT")

    return None

def pullback_strategy(df: pd.DataFrame, ema_fast: int, ema_slow: int, tolerance: float) -> Optional[Signal]:
    if len(df) < 80:
        return None

    df = df.copy()
    df["ema_f"] = ema(df["close"], ema_fast)
    df["ema_s"] = ema(df["close"], ema_slow)
    df["vwap"] = vwap(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_up = last["ema_f"] > last["ema_s"] and last["close"] > last["vwap"]
    trend_dn = last["ema_f"] < last["ema_s"] and last["close"] < last["vwap"]

    near = abs(last["close"] - last["ema_f"]) <= tolerance or abs(last["close"] - last["vwap"]) <= tolerance

    if trend_up and near and last["close"] > last["open"] and last["close"] > prev["close"]:
        entry = float(last["close"])
        stop = float(min(last["low"], prev["low"]))
        target = entry + 2.0 * abs(entry - stop)
        return Signal("buy", entry, stop, target, "Uptrend + pullback to EMA/VWAP + bullish confirmation", "PULLBACK")

    if trend_dn and near and last["close"] < last["open"] and last["close"] < prev["close"]:
        entry = float(last["close"])
        stop = float(max(last["high"], prev["high"]))
        target = entry - 2.0 * abs(entry - stop)
        return Signal("sell", entry, stop, target, "Downtrend + pullback to EMA/VWAP + bearish confirmation", "PULLBACK")

    return None

def vwap_mean_reversion_strategy(df: pd.DataFrame, dist_threshold: float) -> Optional[Signal]:
    if len(df) < 80:
        return None

    df = df.copy()
    df["vwap"] = vwap(df)
    last = df.iloc[-1]
    price = float(last["close"])
    vw = float(last["vwap"])
    dist = (price - vw) / vw

    if dist > dist_threshold:
        entry = price
        stop = float(last["high"])
        target = vw
        return Signal("sell", entry, stop, target, f"Price is {dist:.2%} above VWAP; expecting snap-back", "VWAP_MR")

    if dist < -dist_threshold:
        entry = price
        stop = float(last["low"])
        target = vw
        return Signal("buy", entry, stop, target, f"Price is {abs(dist):.2%} below VWAP; expecting snap-back", "VWAP_MR")

    return None