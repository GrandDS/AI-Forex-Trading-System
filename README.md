# AI Forex Trading System

A Python desktop trading system for OANDA market data and order execution. The project combines indicator calculation, strategy logic, risk controls, execution, and a PyQt5 graphical interface.

## Features

- OANDA API client for pricing, positions, transactions, and orders
- Strategy and technical-indicator modules
- Position/risk controls
- PyQt5 desktop interface
- Runtime transaction monitoring and trading workflow

## Project structure

```text
main.py          Application entry point
gui.py           PyQt5 user interface
trader.py        Core trading orchestration
strategies.py    Trading strategy logic
indicators.py    Technical indicators
risk.py          Risk-management helpers
oanda_client.py  OANDA API integration
config.py        Application configuration model
```

## Installation

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

## Credentials

The repository intentionally contains no OANDA credentials. Enter the API token and account ID through the application interface. Never commit live credentials, tokens, or account secrets to GitHub.

## Disclaimer

This project is software/research work and is not financial advice. Test with an OANDA practice account before considering any live use.
