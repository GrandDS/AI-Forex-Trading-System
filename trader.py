import time
from typing import Callable, Optional
import pandas as pd

from config import BotConfig
from oanda_client import OandaClient
from indicators import to_df, atr, adx
from strategies import breakout_strategy, pullback_strategy, vwap_mean_reversion_strategy, Signal
from risk import RiskManager

LogFn = Callable[[str], None]


class DayTradingBot:
    def __init__(self, cfg: BotConfig, log: LogFn):
        self.cfg = cfg
        self.log = log
        self.client = OandaClient(cfg.api_token, cfg.environment)
        self.risk = RiskManager(cfg.risk_per_trade, cfg.max_daily_loss, cfg.max_trades_per_day)

        self._running = False
        self._last_trade_time = 0.0

        # Transactions monitoring
        self._last_tx_id: Optional[str] = None
        self._seen_trade_ids = set()

        # Only evaluate once per new candle
        self._last_candle_time: Optional[str] = None

    def stop(self):
        self._running = False

    def _cooldown_active(self) -> bool:
        return (time.time() - self._last_trade_time) < self.cfg.cooldown_seconds

    def run_forever(self):
        self._running = True
        self.log("Bot started (24/5). I will trade only when conditions are good.")
        self.log("Important: no bot can guarantee profit on every trade.")

        try:
            self._last_tx_id = self.client.get_last_transaction_id(self.cfg.account_id)
            self.log(f"Transaction monitor armed from transaction ID {self._last_tx_id}.")
        except Exception as e:
            self.log(f"Warning: transaction monitor could not start: {e!r}")

        while self._running:
            try:
                self._iteration()
            except Exception as e:
                self.log(f"Cycle error: {e!r}")
            time.sleep(self.cfg.poll_seconds)

        self.log("Bot stopped.")

    # ---------- Intelligence ----------
    def _detect_regime(self, df: pd.DataFrame) -> str:
        a = atr(df, period=14).iloc[-1]
        x = adx(df, period=14).iloc[-1]
        if pd.isna(a) or pd.isna(x):
            return "UNKNOWN"

        price = float(df.iloc[-1]["close"])
        rel_atr = float(a) / price

        if rel_atr > 0.0012:
            return "HIGH_VOL"
        if x >= 22:
            return "TREND"
        return "RANGE"

    def _trade_quality_score(
        self,
        spread: float,
        stop_dist: float,
        target_dist: Optional[float],
        rr_ok: bool,
        regime: str
    ) -> int:
        score = 50

        if spread <= self.cfg.max_spread * 0.8:
            score += 15
        elif spread <= self.cfg.max_spread:
            score += 5
        else:
            score -= 30

        score += 10 if stop_dist >= self.cfg.min_stop_distance else -25
        score += 10 if (target_dist is not None and target_dist >= self.cfg.min_target_distance) else -25
        score += 10 if rr_ok else -20

        if regime == "HIGH_VOL":
            score -= 40
        elif regime in ("TREND", "RANGE"):
            score += 5

        return max(0, min(100, score))

    # ---------- Transactions ----------
    def _process_new_transactions(self):
        if not self._last_tx_id:
            return

        resp = self.client.get_transactions_since(self.cfg.account_id, self._last_tx_id)
        txs = resp.get("transactions", [])
        last = resp.get("lastTransactionID")

        if not txs:
            self._last_tx_id = last or self._last_tx_id
            return

        for tx in txs:
            if tx.get("type") != "ORDER_FILL":
                continue

            instrument = tx.get("instrument", "")
            price = tx.get("price")
            reason = tx.get("reason", "")
            time_ = tx.get("time", "")

            opened_obj = tx.get("tradeOpened")
            if opened_obj:
                trade_id = opened_obj.get("tradeID")
                units = float(opened_obj.get("units", "0"))
                side = "BUY" if units > 0 else "SELL"
                if trade_id and trade_id not in self._seen_trade_ids:
                    self._seen_trade_ids.add(trade_id)
                    self.log(f"✅ Started a trade: {side} {abs(units):.0f} {instrument} @ {float(price):.5f} | {reason} | ID {trade_id}")

            for closed in tx.get("tradesClosed", []):
                trade_id = closed.get("tradeID")
                realized = float(closed.get("realizedPL", "0"))
                outcome = "PROFIT ✅" if realized > 0 else ("LOSS ❌" if realized < 0 else "BREAKEVEN")
                self.log(f"🏁 Closed trade: {instrument} ID {trade_id} → {outcome} {realized:.2f} | time {time_}")

            for reduced in tx.get("tradesReduced", []):
                trade_id = reduced.get("tradeID")
                realized = float(reduced.get("realizedPL", "0"))
                outcome = "PROFIT ✅" if realized > 0 else ("LOSS ❌" if realized < 0 else "BREAKEVEN")
                self.log(f"➗ Partial close: {instrument} ID {trade_id} → {outcome} {realized:.2f} | time {time_}")

        self._last_tx_id = last or self._last_tx_id

    # ---------- Signal selection ----------
    def _find_signal(self, df: pd.DataFrame) -> Optional[Signal]:
        regime = self._detect_regime(df)
        self.log(f"Market regime: {regime}")

        if regime == "HIGH_VOL":
            self.log("High volatility detected. Pausing.")
            return None

        if regime == "TREND":
            if self.cfg.enable_pullback:
                self.log("TREND → checking PULLBACK…")
                s = pullback_strategy(df, self.cfg.ema_fast, self.cfg.ema_slow, self.cfg.pullback_tolerance)
                if s:
                    return s
            if self.cfg.enable_breakout:
                self.log("TREND → checking BREAKOUT…")
                s = breakout_strategy(df, self.cfg.breakout_range_bars, self.cfg.breakout_hold_bars, self.cfg.breakout_vol_mult)
                if s:
                    return s
            return None

        if regime == "RANGE":
            if self.cfg.enable_vwap_mr:
                self.log("RANGE → checking VWAP_MR…")
                s = vwap_mean_reversion_strategy(df, self.cfg.vwap_dist_threshold)
                if s:
                    return s
            if self.cfg.enable_breakout:
                self.log("RANGE → checking BREAKOUT (secondary)…")
                s = breakout_strategy(df, self.cfg.breakout_range_bars, self.cfg.breakout_hold_bars, self.cfg.breakout_vol_mult)
                if s:
                    return s
            return None

        self.log("Regime unknown; standing by.")
        return None

    # ---------- Trade plan adjustment ----------
    def _apply_atr_trade_plan(self, df: pd.DataFrame, signal: Signal, real_entry: float) -> Signal:
        """
        Replace fragile strategy stop/target with ATR-based professional planning.
        """
        df = df.copy()
        current_atr = atr(df, period=14).iloc[-1]
        if pd.isna(current_atr) or current_atr <= 0:
            return signal

        current_atr = float(current_atr)

        # Professional defaults:
        atr_stop_mult = 1.2
        atr_target_mult = 2.0

        stop_dist = max(self.cfg.min_stop_distance, current_atr * atr_stop_mult)
        target_dist = max(self.cfg.min_target_distance, current_atr * atr_target_mult)

        # Enforce minimum RR as well
        target_dist = max(target_dist, stop_dist * self.cfg.min_rr)

        if signal.side == "buy":
            signal.stop = real_entry - stop_dist
            signal.target = real_entry + target_dist
        else:
            signal.stop = real_entry + stop_dist
            signal.target = real_entry - target_dist

        self.log(
            f"ATR plan applied: ATR={current_atr:.5f}, stop_dist={stop_dist:.5f}, "
            f"target_dist={target_dist:.5f}"
        )
        return signal

    # ---------- Main loop ----------
    def _iteration(self):
        self._process_new_transactions()

        self.log(f"Fetching {self.cfg.candle_count} candles for {self.cfg.instrument} ({self.cfg.granularity})…")
        resp = self.client.get_candles(self.cfg.instrument, self.cfg.granularity, self.cfg.candle_count)
        df = to_df(resp)

        if df.empty or len(df) < 80:
            self.log("Not enough candle data yet.")
            return

        # Only act on a new closed candle
        latest_candle_time = str(df.iloc[-1]["time"])
        if self._last_candle_time == latest_candle_time:
            self.log("No new closed candle yet. Waiting.")
            return
        self._last_candle_time = latest_candle_time

        if not self.risk.can_trade():
            self.log("Risk rules block new trades right now.")
            return

        if self._cooldown_active():
            remaining = int(self.cfg.cooldown_seconds - (time.time() - self._last_trade_time))
            self.log(f"Cooldown active: wait {remaining}s.")
            return

        if self.cfg.one_trade_at_a_time:
            pos = self.client.get_open_positions(self.cfg.account_id)
            for p in pos.get("positions", []):
                if p.get("instrument") == self.cfg.instrument:
                    self.log("Open position exists; not opening another.")
                    return

        signal = self._find_signal(df)
        if signal is None:
            self.log("No signal. Standing by.")
            return

        self.log(f"Signal: {signal.strategy} {signal.side.upper()} | {signal.reason}")
        self.log(
            f"Original plan: entry~{signal.entry:.5f} stop={signal.stop:.5f} "
            f"target={signal.target if signal.target else 'None'}"
        )

        # Live execution pricing
        bid, ask = self.client.get_bid_ask(self.cfg.account_id, self.cfg.instrument)
        spread = ask - bid
        if spread > self.cfg.max_spread:
            self.log(f"Skip: spread too wide ({spread:.5f} > {self.cfg.max_spread:.5f}).")
            return

        real_entry = ask if signal.side == "buy" else bid
        self.log(f"Live pricing: bid={bid:.5f}, ask={ask:.5f}, spread={spread:.5f}, entry={real_entry:.5f}")

        # Replace fragile stop/target with ATR-based plan
        signal = self._apply_atr_trade_plan(df, signal, real_entry)

        stop_dist = abs(real_entry - signal.stop)
        target_dist = abs(signal.target - real_entry) if signal.target is not None else None

        rr_ok = True
        if signal.target is not None:
            rr_ok = self.risk.validate_rr(real_entry, signal.stop, signal.target, self.cfg.min_rr)

        regime = self._detect_regime(df)
        score = self._trade_quality_score(spread, stop_dist, target_dist, rr_ok, regime)

        self.log(
            f"Final plan: stop={signal.stop:.5f}, target={signal.target:.5f}, "
            f"stop_dist={stop_dist:.5f}, target_dist={target_dist:.5f}, RR_ok={rr_ok}, score={score}/100"
        )

        if stop_dist < self.cfg.min_stop_distance:
            self.log("Skip: stop still too tight after ATR adjustment.")
            return

        if target_dist is not None and target_dist < self.cfg.min_target_distance:
            self.log("Skip: target still too close after ATR adjustment.")
            return

        if score < self.cfg.min_quality_score:
            self.log(f"Skip: quality score below {self.cfg.min_quality_score}.")
            return

        if signal.target is not None and not rr_ok:
            self.log("Skip: RR too low after ATR/live pricing.")
            return

        units = self._compute_units(signal)
        units_signed = units if signal.side == "buy" else -units

        self.log(f"Placing order: {units_signed} units with ATR-based SL/TP…")
        order_resp = self.client.place_market_order(
            account_id=self.cfg.account_id,
            instrument=self.cfg.instrument,
            units=units_signed,
            stop_loss=signal.stop,
            take_profit=signal.target,
            client_tag=f"DayBot_{signal.strategy}"
        )

        self.risk.mark_trade()
        self._last_trade_time = time.time()

        self.log("Order sent. Broker summary:")
        self.log(str({k: order_resp.get(k) for k in ["orderCreateTransaction", "orderFillTransaction", "errorMessage"] if k in order_resp}))

    def _compute_units(self, signal: Signal) -> int:
        if self.cfg.use_fixed_units:
            units = int(self.cfg.fixed_units)
            units = max(1, min(units, self.cfg.max_units_cap))
            self.log(f"Position size: FIXED {units} units.")
            return units

        units = self.risk.estimate_units_from_stop(signal.entry, signal.stop, self.cfg.max_units_cap)
        self.log(f"Position size: RISK-based approx {units} units.")
        return units