from typing import Dict, Any, Optional, Tuple
from oandapyV20 import API

import oandapyV20.endpoints.instruments as instruments_ep
import oandapyV20.endpoints.orders as orders_ep
import oandapyV20.endpoints.positions as positions_ep
import oandapyV20.endpoints.transactions as transactions_ep
import oandapyV20.endpoints.pricing as pricing_ep


class OandaClient:
    def __init__(self, token: str, environment: str = "practice"):
        # oandapyV20 uses environment="practice" or "live"
        env = "practice" if environment == "practice" else "live"
        self.api = API(access_token=token, environment=env)

    def get_candles(self, instrument: str, granularity: str, count: int = 200) -> Dict[str, Any]:
        params = {"granularity": granularity, "count": count, "price": "M"}
        r = instruments_ep.InstrumentsCandles(instrument=instrument, params=params)
        return self.api.request(r)

    def get_bid_ask(self, account_id: str, instrument: str) -> Tuple[float, float]:
        r = pricing_ep.PricingInfo(accountID=account_id, params={"instruments": instrument})
        resp = self.api.request(r)
        prices = resp.get("prices", [])
        if not prices:
            raise RuntimeError("No pricing returned from OANDA")
        p = prices[0]
        bid = float(p["bids"][0]["price"])
        ask = float(p["asks"][0]["price"])
        return bid, ask

    def get_open_positions(self, account_id: str) -> Dict[str, Any]:
        r = positions_ep.OpenPositions(accountID=account_id)
        return self.api.request(r)

    # --- Transactions monitoring ---
    def get_last_transaction_id(self, account_id: str) -> str:
        # TransactionsLatest does not exist in oandapyV20. Use TransactionList.
        r = transactions_ep.TransactionList(accountID=account_id, params={"pageSize": 1})
        resp = self.api.request(r)
        return resp["lastTransactionID"]

    def get_transactions_since(self, account_id: str, since_id: str) -> Dict[str, Any]:
        r = transactions_ep.TransactionsSinceID(accountID=account_id, params={"id": since_id})
        return self.api.request(r)

    def place_market_order(
        self,
        account_id: str,
        instrument: str,
        units: int,
        stop_loss: float,
        take_profit: Optional[float],
        client_tag: str = "DayBot"
    ) -> Dict[str, Any]:
        order = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "clientExtensions": {"tag": client_tag},
                "stopLossOnFill": {"price": f"{stop_loss:.5f}"},
            }
        }
        if take_profit is not None:
            order["order"]["takeProfitOnFill"] = {"price": f"{take_profit:.5f}"}

        r = orders_ep.OrderCreate(accountID=account_id, data=order)
        return self.api.request(r)