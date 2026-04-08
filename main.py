from config import INITIAL_BALANCE, STEPS
from data import MarketData
from strategy import SimpleStrategy
from execution import ExecutionEngine
from logger import log
import time

def run_system(steps=STEPS):
    data = MarketData()
    strategy = SimpleStrategy()
    execution = ExecutionEngine(INITIAL_BALANCE)

    log("Starting AI Forex Trading System")

    for step in range(1, steps + 1):
        price = data.get_next_price()
        signal = strategy.generate_signal(price)
        log(f"Step {step} | Price: {price} | Signal: {signal}")
        execution.execute_trade(signal, price)
        time.sleep(0.1)

    log(f"Final Balance: {execution.get_balance()}")

if __name__ == "__main__":
    run_system()
