from ib_insync import *
import warnings
import argparse
from trading import TradingBot
warnings.filterwarnings("ignore")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--client-id", help="The client id", type=int, required=True)
    parser.add_argument("--ticker", help="The ticker to trade", type=str, required=True)

    args = parser.parse_args()

    print("Connecting to client", args.client_id)

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId = args.client_id)

    # Define bot parameters
    params = {
        # Stochastic RSI Attributes
        'rsi_period': 14,
        'stochastic_period': 9,

        # Bollinger Band Attributes
        'simple_moving_average_period': 21,
        'bollinger_band_standard_deviation': 1.5,

        # Buy and Sell Attributes
        'ticker': args.ticker,
        'stochastic_upper_band': 70,
        'stochastic_lower_band': 30,
        'time_look_back':  '1 D',  
        'asset_interval': '5 mins', 
        'buy_quantity': 1, 
        'show_times': 500,
        'mode': 'trade',
        'limit_percent': 0.015,
        'initial_cash': 1e4,
    }

    print("Trading", args.ticker)

    # Create and run bot
    bot = TradingBot(ib, params)
    while True:
        bot.backtest()
        ib.sleep(5*60)