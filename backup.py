from ib_insync import *
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as plt_dates
import datetime as dt
from matplotlib.lines import Line2D

class TradingBot:

    def __init__(self, ib: IB, args):
        # IB connection
        self.ib = ib

        # Stoch RSI Information
        self.avg_gain, self.avg_loss = 0, 0
        self.rsi,  self.rsi_array = 0, []
        self.rsi_period, self.stoch_period = args['rsi_period'], args['stochastic_period']
        self.k_slow_period, self.d_slow_period = args['k_slow_period'], args['d_slow_period']
        self.k_fast_array, self.k_slow_array, self.d_slow_array = {'time':[],'k_fast':[]}, {'time':[],'k_slow':[]}, {'time':[],'d_slow':[]}
        self.stoch_upper, self.stoch_lower = args['stochastic_upper_band'], args['stochastic_lower_band']

        # Bollinger Band Information
        self.sma_period, self.sma_array = args['simple_moving_average_period'], []
        self.deviation = args['bollinger_band_standard_deviation']
        self.bb = {'time':[],'sma': [],'lower_band': [],'upper_band': []}

        # Buy Sell Algorithm Information
        self.orders = {'time':[],'order_limit': [],'order_type': []}
        self.time_look_back = args['time_look_back']
        self.asset_interval = args['asset_interval']
        self.status = 0
        self.buy_quantity = args['buy_quantity']

        # IB trading fees and general information
        self.ticker = args['ticker']
        self.show_times = args['show_times']
        self.closing_price_array, self.closing_times = [], []
        self.checked_prices, self.checked_times = [], []
        self.general_trade_fee = 0.01 # commission fee
        self.position = 8

        self.positions = [0]
        self.cash = [1e6]
        self.net_worth = [1e6]

    def simple_moving_average(self, arr, period):
        return np.sum(arr) / period

    def wilders_moving_average(self, period, close, prev_moving_average):
        return ((prev_moving_average * (period - 1)) + close) / period

    def rsi_calc(self, avg_gain, avg_loss):
        # print("ris_calc", avg_gain, avg_loss)
        rs = avg_gain / (avg_loss + 0.00000001)
        return 100 - (100 / (1 + rs))

    def k_fast_stoch(self, rsi_array):
        close = rsi_array[-1]
        high = np.amax(rsi_array)
        low = np.amin(rsi_array)
        # print("k_fast_stoch", close, high, low)
        return abs(((close - low) / (high - low + 0.00000001))) * 100

    def bollinger_bands(self, kline_array, sma_period, deviation_number, time):
        recent_numbers = kline_array[len(kline_array) - sma_period:]
        sma = self.simple_moving_average(sum(recent_numbers), sma_period)
        self.bb['sma'].append(sma)
        squared_errors = [pow(x - sma, 2) for x in recent_numbers]
        standard_deviation = (sum(squared_errors) / len(squared_errors)) ** 0.5
        upper_band = sma + standard_deviation * deviation_number
        lower_band = sma - standard_deviation * deviation_number
        self.bb['lower_band'].append(lower_band)
        self.bb['upper_band'].append(upper_band)
        self.bb['time'].append(time)
        return sma, upper_band, lower_band, standard_deviation

    def print_values(self):
        print('Previous Stoch_RSI(%K_FAST)', self.k_fast_array['k_fast'][-1])
        print('Previous Stoch_RSI(%K_SLOW)', self.k_slow_array['k_slow'][-1])
        print('Previous Stoch_RSI(%D_SLOW)', self.d_slow_array['d_slow'][-1])
        print('RSI(Smoothed)', self.rsi)
        print('Bollinger Lower Band', self.bb['lower_band'][-1])
        print('Bollinger Upper Band', self.bb['upper_band'][-1])
        print('Simple Moving Average', self.bb['sma'][-1], '\n')

    def backtest(self):
        end_time = ''
        # start_time = end_time - dt.timedelta(days=int(self.time_look_back.split()[0]))
        
        bars = self.ib.reqHistoricalData(
            # contract=Crypto(self.ticker, "Paxos", "USD"), 
            contract=Stock(self.ticker, "SMART", "USD", primaryExchange='NASDAQ'),
            endDateTime=end_time,
            durationStr=self.time_look_back,
            barSizeSetting=self.asset_interval,
            whatToShow='MIDPOINT',
            useRTH=True, 
            formatDate = 2,
            keepUpToDate=True,
        )

        self.closing_times = [bar.date for bar in bars][:-1]
        self.closing_price_array = [bar.close for bar in bars][:-1]
        self.checked_prices = []

        gain, loss = 0, 0
        for x in range(0, len(self.closing_price_array)-1):
            change = self.closing_price_array[x+1] - self.closing_price_array[x]
            self.checked_prices.append(self.closing_price_array[x+1])
            self.checked_times.append(self.closing_times[x+1])
            if change > 0:
                gain += change
            elif change < 0:
                loss += abs(change)

            if x == self.rsi_period:
                self.avg_gain = self.simple_moving_average(gain, self.rsi_period)
                self.avg_loss = self.simple_moving_average(loss, self.rsi_period)
                self.rsi = self.rsi_calc(self.avg_gain, self.avg_loss)
                self.rsi_array.append(self.rsi)
                gain, loss = 0, 0

            elif x > self.rsi_period:
                self.avg_gain = self.wilders_moving_average(self.rsi_period, gain, self.avg_gain)
                self.avg_loss = self.wilders_moving_average(self.rsi_period, loss, self.avg_loss)
                self.rsi = self.rsi_calc(self.avg_gain, self.avg_loss)
                self.rsi_array.append(self.rsi)
                gain, loss = 0, 0

                if len(self.rsi_array) >= self.stoch_period:
                    k_fast = self.k_fast_stoch(self.rsi_array[-self.stoch_period:])
                    self.k_fast_array['k_fast'].append(k_fast)
                    self.k_fast_array['time'].append(self.closing_times[x])

                    if len(self.k_fast_array['k_fast']) >= self.k_slow_period:
                        k_slow = self.simple_moving_average(self.k_fast_array['k_fast'][-self.k_slow_period:], self.k_slow_period)
                        self.k_slow_array['k_slow'].append(k_slow)
                        self.k_slow_array['time'].append(self.closing_times[x])

                        if len(self.k_slow_array['k_slow']) >= self.d_slow_period:
                            d_slow = self.simple_moving_average(self.k_slow_array['k_slow'][-self.d_slow_period:], self.d_slow_period)
                            self.d_slow_array['d_slow'].append(d_slow)
                            self.d_slow_array['time'].append(self.closing_times[x])

                            self.bollinger_bands(self.checked_prices, self.sma_period, self.deviation, self.checked_times[x])

                            # self.buy_sell(current_time=self.checked_times[-1])
                        
                        else:
                            self.positions.append(self.positions[-1])
                            self.cash.append(self.cash[-1])
                            self.net_worth.append(self.net_worth[-1])
                    else:
                        self.positions.append(self.positions[-1])
                        self.cash.append(self.cash[-1])
                        self.net_worth.append(self.net_worth[-1])
                else:
                    self.positions.append(self.positions[-1])
                    self.cash.append(self.cash[-1])
                    self.net_worth.append(self.net_worth[-1])
            else:
                    self.positions.append(self.positions[-1])
                    self.cash.append(self.cash[-1])
                    self.net_worth.append(self.net_worth[-1])

        self.buy_sell(current_time=self.checked_times[-1])
        # self.plot_orders()

    def buy_sell(self, current_time):
        next_price = self.checked_prices[-1]
        # stock=Crypto(self.ticker, "Paxos", "USD") 
        stock=Stock(self.ticker, "SMART", "USD", primaryExchange='NASDAQ')
        print(f"Position: {self.position}")
        if self.k_fast_array['k_fast'][-1] <= self.stoch_lower and next_price <= self.bb['lower_band'][-1]:
            self.status = 1
            print(f"{current_time} Buy")
            order = MarketOrder("Buy", self.buy_quantity)
            self.ib.placeOrder(stock, order)
            print('Current Price:', next_price, '\nCreated Buy Order:', self.bb['lower_band'][-1], '\nQuantity:', self.buy_quantity, '\nTime:', current_time)
            self.position += 1
            self.orders['time'].append(current_time)
            self.orders['order_limit'].append(next_price)
            self.orders['order_type'].append('buy')
            self.print_values()

        elif self.k_fast_array['k_fast'][-1] >= self.stoch_upper and next_price >= self.bb['upper_band'][-1] and self.position > 0:
            self.status = 0
            print(f"{current_time} Sell")
            order = MarketOrder("Sell", self.buy_quantity)
            self.ib.placeOrder(stock, order)
            print('Current Price:', next_price, '\nCreated Sell Order:', self.bb['upper_band'][-1], '\nQuantity:', self.buy_quantity, '\nTime:', current_time)
            self.position -= 1
            self.orders['time'].append(current_time)
            self.orders['order_limit'].append(next_price)
            self.orders['order_type'].append('sell')
            self.print_values()

        else:
            print("Hold position")   
            self.print_values()
            self.orders['time'].append(current_time)
            self.orders['order_limit'].append(None)
            self.orders['order_type'].append('hold')

        self.positions.append(self.position * next_price)
        if self.orders["order_type"][-1] == 'buy':
            self.cash.append(self.cash[-1] - next_price * self.buy_quantity)
        elif self.orders["order_type"][-1] == 'sell':
            self.cash.append(self.cash[-1] + next_price * self.buy_quantity)
        else:
            self.cash.append(self.cash[-1])
        self.net_worth.append(self.cash[-1] + self.positions[-1])

    def plot_orders(self):
        plot_data = [
            {'time': self.k_fast_array['time'], 'values': self.k_fast_array['k_fast'], 'label': 'Stoch RSI K Fast', 'color': 'b', 'linestyle': 'dotted'},
            {'time': self.k_slow_array['time'], 'values': self.k_slow_array['k_slow'], 'label': 'Stoch RSI K Slow', 'color': 'b'},
            {'time': self.d_slow_array['time'], 'values': self.d_slow_array['d_slow'], 'label': 'Stoch RSI D Slow', 'color': 'r'},
            {'time': self.bb['time'], 'values': self.bb['sma'], 'label': 'SMA', 'color': 'black'},
            {'time': self.bb['time'], 'values': self.bb['lower_band'], 'label': 'Bollinger Lower Band', 'color': 'red'},
            {'time': self.bb['time'], 'values': self.bb['upper_band'], 'label': 'Bollinger Upper Band', 'color': 'green'},
        ]

        plt.figure(figsize=(16, 12))
        ax1 = plt.subplot(411)
        ax2 = plt.subplot(412)
        ax3 = plt.subplot(413)
        ax4 = plt.subplot(414)

        ax1.set_title(f"{self.ticker} Closing Price & Bollinger Bands")
        ax1.plot(self.checked_times, self.checked_prices, label='Closing Price')
        for data in plot_data[3:]:
            ax1.plot(data['time'], data['values'], label=data['label'], color=data['color'])
        ax1.legend(loc='upper left')

        ax2.set_title(f"{self.ticker} Stochastic RSI")
        for data in plot_data[:3]:
            ax2.plot(data['time'], data['values'], label=data['label'], color=data['color'], linestyle=data.get('linestyle'))
        ax2.axhline(y=self.stoch_lower, color='r', linestyle='-')
        ax2.axhline(y=self.stoch_upper, color='g', linestyle='-')
        ax2.legend(loc='upper left')

        ax3.set_title(f"{self.ticker} Buy/Sell Orders")
        ax3.plot(self.checked_times, self.checked_prices, label='Closing Price')
        colors = {'buy': 'blue', 'sell': 'orange'}
        for order_time, order_price, order_type in zip(self.orders['time'], self.orders['order_limit'], self.orders['order_type']):
            if order_type == 'hold': continue
            ax3.plot(order_time, order_price, 'o', color=colors[order_type])
        circle_buy = Line2D([0],[0], color = "w", label="buy", marker='o', markerfacecolor='blue', markersize='7')
        circle_sell = Line2D([0],[0], color = "w", label="sell", marker='o', markerfacecolor='orange', markersize='7')
        ax3.legend(loc='upper left', handles=[circle_buy, circle_sell])

        ax4.set_title(f"Strategy Performance")
        print(len(self.checked_times), len(self.net_worth), len(self.cash), len(self.positions))
        ax4.plot(self.checked_times, self.net_worth, label='Net Worth')
        # ax4.plot(self.checked_times, self.cash, label='Cash')
        # ax4.plot(self.checked_times, self.positions, label='Positions')        
        plt.tight_layout()
        plt.show()


# Define bot parameters
args = {
    # Stochastic RSI Attributes
    'rsi_period': 14,
    'stochastic_period': 9,
    'k_slow_period': 3,
    'd_slow_period': 3,

    # Bollinger Band Attributes
    'simple_moving_average_period': 21,
    'bollinger_band_standard_deviation': 1.5,

    # Buy and Sell Attributes
    'ticker': 'COST',  
    'stochastic_upper_band': 70,
    'stochastic_lower_band': 30,
    'time_look_back':  f'1 D', 
    'asset_interval': '30 secs', 
    'buy_quantity': 1, 
    'show_times': 500
}

# Create and run bot
bot = TradingBot(ib, args)
while True:
    bot.backtest()
    ib.sleep(30)
    # break
