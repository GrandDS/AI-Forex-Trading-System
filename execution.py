class ExecutionEngine:
    def __init__(self, balance):
        self.balance = balance
        self.position = None

    def execute_trade(self, signal, price):
        if signal == "BUY" and self.position is None:
            self.position = price
            print(f"[EXECUTION] BUY at {price}")
        elif signal == "SELL" and self.position is not None:
            profit = price - self.position
            self.balance += profit
            print(f"[EXECUTION] SELL at {price} | Profit: {profit:.5f}")
            self.position = None

    def get_balance(self):
        return round(self.balance, 2)
