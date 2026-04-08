class SimpleStrategy:
    def __init__(self, threshold_high=1.1050, threshold_low=1.0950):
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low

    def generate_signal(self, price):
        if price > self.threshold_high:
            return "SELL"
        if price < self.threshold_low:
            return "BUY"
        return "HOLD"
