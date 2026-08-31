from dataclasses import dataclass

@dataclass
class BotConfig:
    # OANDA
    api_token: str = ""
    account_id: str = ""
    environment: str = "practice"  # "practice" or "live"

    # Trading
    instrument: str = "EUR_USD"
    granularity: str = "M5"
    candle_count: int = 200

    # Risk
    risk_per_trade: float = 10.0
    max_daily_loss: float = 50.0
    max_trades_per_day: int = 5
    min_rr: float = 2.0
    max_units_cap: int = 5000

    # Sizing
    use_fixed_units: bool = True
    fixed_units: int = 1000

    # Strategy toggles
    enable_breakout: bool = True
    enable_pullback: bool = True
    enable_vwap_mr: bool = True

    # Breakout params
    breakout_range_bars: int = 20
    breakout_hold_bars: int = 2
    breakout_vol_mult: float = 1.5

    # Pullback params
    ema_fast: int = 9
    ema_slow: int = 20
    pullback_tolerance: float = 0.0005

    # VWAP MR params (IMPORTANT: realistic for M5)
    vwap_dist_threshold: float = 0.0015  # 0.15% ~ 18 pips on EURUSD

    # Execution
    poll_seconds: int = 10
    cooldown_seconds: int = 300
    one_trade_at_a_time: bool = True

    # Execution quality filters (EUR_USD defaults)
    max_spread: float = 0.00015          # 1.5 pips
    min_stop_distance: float = 0.00060   # 6 pips
    min_target_distance: float = 0.00100 # 10 pips

    # Intelligence gating
    min_quality_score: int = 70