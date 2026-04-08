import random

class MarketData:
    def __init__(self, starting_price=1.1000):
        self.price = starting_price

    def get_next_price(self):
        change = random.uniform(-0.0020, 0.0020)
        self.price = round(self.price + change, 5)
        return self.price
