from dataclasses import dataclass

@dataclass
class RiskState:
    realized_pnl: float = 0.0
    trades_today: int = 0

class RiskManager:
    def __init__(self, risk_per_trade: float, max_daily_loss: float, max_trades: int):
        self.risk_per_trade = float(risk_per_trade)
        self.max_daily_loss = float(max_daily_loss)
        self.max_trades = int(max_trades)
        self.state = RiskState()

    def can_trade(self) -> bool:
        if self.state.trades_today >= self.max_trades:
            return False
        if self.state.realized_pnl <= -abs(self.max_daily_loss):
            return False
        return True

    def mark_trade(self):
        self.state.trades_today += 1

    def estimate_units_from_stop(self, entry: float, stop: float, max_units_cap: int) -> int:
        dist = abs(entry - stop)
        if dist <= 0:
            return 0
        units = int(self.risk_per_trade / dist)
        units = max(1, min(units, int(max_units_cap)))
        return units

    def validate_rr(self, entry: float, stop: float, target: float, min_rr: float) -> bool:
        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk <= 0:
            return False
        return (reward / risk) >= float(min_rr)