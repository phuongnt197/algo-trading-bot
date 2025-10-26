from ib_insync import *
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class TradingBot:

    def __init__(self, ib: IB, args):
        # IB connection
        self.ib = ib

        # Stoch RSI Information
        self.avg_gain, self.avg_loss = 0, 0
        self.rsi,  self.rsi_array = 0, []
        self.rsi_period, self.stoch_period = args['rsi_period'], args['stochastic_period']
        self.stoch_array = {'time':[],'stoch':[]}
        self.stoch_upper, self.stoch_lower = args['stochastic_upper_band'], args['stochastic_lower_band']
        self.mode = args['mode'] # either 'trade' or 'backtest'
        self.percent = args['limit_percent']
        self.initial_cash = args['initial_cash']

        # Store limit order and stop loss
        self.limit_orders = []
        self.stop_loss = []

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
        self.position = 0

        self.positions = [0]
        self.cash = [self.initial_cash]
        self.net_worth = [self.initial_cash]

    def simple_moving_average(self, arr, period):
        return np.sum(arr) / period

    def wilders_moving_average(self, period, close, prev_moving_average):
        return ((prev_moving_average * (period - 1)) + close) / period

    def rsi_calc(self, avg_gain, avg_loss):
        rs = avg_gain / (avg_loss + 0.00000001)
        return 100 - (100 / (1 + rs))

    def stoch_stoch(self, rsi_array):
        close = rsi_array[-1]
        high = np.amax(rsi_array)
        low = np.amin(rsi_array)
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
        print('Current Price', self.checked_prices[-1])
        print('RSI', self.rsi)
        print('Previous Stoch_RSI', self.stoch_array['stoch'][-1])
        print('Simple Moving Average', self.bb['sma'][-1], '\n')
        print('Bollinger Lower Band', self.bb['lower_band'][-1])
        print('Bollinger Upper Band', self.bb['upper_band'][-1])

    def backtest(self):
        end_time = ''
        
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
                    stoch = self.stoch_stoch(self.rsi_array[-self.stoch_period:])
                    self.stoch_array['stoch'].append(stoch)
                    self.stoch_array['time'].append(self.closing_times[x])
                    self.bollinger_bands(self.checked_prices, self.sma_period, self.deviation, self.checked_times[x])
                    if (self.mode == 'backtest'):
                        self.buy_sell(current_time=self.checked_times[-1])                   

                else:
                    self.positions.append(self.positions[-1])
                    self.cash.append(self.cash[-1])
                    self.net_worth.append(self.net_worth[-1])
            else:
                    self.positions.append(self.positions[-1])
                    self.cash.append(self.cash[-1])
                    self.net_worth.append(self.net_worth[-1])

        if (self.mode == 'backtest'):
            self.plot_orders()
        else: 
            self.buy_sell(current_time=self.checked_times[-1])

    def buy_sell(self, current_time):
        next_price = self.checked_prices[-1]
        # stock=Crypto(self.ticker, "Paxos", "USD") 
        stock=Stock(self.ticker, "SMART", "USD", primaryExchange='NASDAQ')
        if self.stoch_array['stoch'][-1] <= self.stoch_lower and next_price <= self.bb['lower_band'][-1] and self.cash[-1] > next_price * self.buy_quantity:
            self.buy_stock(current_time, next_price, stock)

        # If it touches the limit order and stop loss, sell
        elif self.stoch_array['stoch'][-1] >= self.stoch_upper and next_price >= self.bb['upper_band'][-1] and self.position > 0:
            self.sell_stock(current_time, next_price, stock)
            self.stop_loss.pop()
            self.limit_orders.pop()

        elif self.position > 0:
            limit_order_hit = False
            for i in range(len(self.limit_orders)):
                if next_price >= self.limit_orders[i] or next_price <= self.stop_loss[i]:
                    print("WOW, stop loss or limit order hit!", current_time, next_price, self.limit_orders[i], self.stop_loss[i])
                    self.sell_stock(current_time, next_price, stock)
                    self.limit_orders.pop(i)
                    self.stop_loss.pop(i)
                    limit_order_hit = True
                    break

            if not limit_order_hit:
                print("Hold position")
                self.print_values()
                self.orders['time'].append(current_time)
                self.orders['order_limit'].append(None)
                self.orders['order_type'].append('hold')
        else:
            print("Hold position")
            self.print_values()
            self.orders['time'].append(current_time)
            self.orders['order_limit'].append(None)
            self.orders['order_type'].append('hold')

        self.positions.append(self.position * next_price)

        # Assume if ticker's price > $100, fee will be $1, otherwise 1% of ticker's price
        fee = min(self.general_trade_fee * next_price , 1) 
        if self.orders["order_type"][-1] == 'buy':
            print(f"We are buying, fee: {fee}, next price: {next_price}, buy quantity: {self.buy_quantity}, cash: {self.cash[-1]}, position: {self.positions[-1]}")
            self.cash.append(self.cash[-1] - next_price * self.buy_quantity - fee)
        
        elif self.orders["order_type"][-1] == 'sell':
            self.cash.append(self.cash[-1] + next_price * self.buy_quantity - fee)
        
        else:
            self.cash.append(self.cash[-1])
        
        self.net_worth.append(self.cash[-1] + self.positions[-1])

        print(f"The fee is: {fee}")
        print(f"Net Worth: {self.net_worth[-1]}")
        print(f"Cash: {self.cash[-1]}")
        print(f"Position: {self.positions[-1]}")

        print("====================================")

    def sell_stock(self, current_time, next_price, stock):
        self.status = 0
        print(f"{current_time} Sell")
        if (self.mode == 'trade'):
            order = MarketOrder("Sell", self.buy_quantity)
            self.ib.placeOrder(stock, order)

        self.position -= 1
        self.orders['time'].append(current_time)
        self.orders['order_limit'].append(next_price)
        self.orders['order_type'].append('sell')
        self.print_values()

    def buy_stock(self, current_time, next_price, stock):
        self.status = 1
        print(f"{current_time} Buy")
        if (self.mode == 'trade'):
            order = MarketOrder("Buy", self.buy_quantity)
            self.ib.placeOrder(stock, order)

        self.position += 1
        self.orders['time'].append(current_time)
        self.orders['order_limit'].append(next_price)
        self.orders['order_type'].append('buy')
        self.print_values()

            # Set up stop loss and limit order
        stop_loss_price = next_price - next_price * self.percent
        limit_order_price = next_price + next_price * self.percent
        self.limit_orders.append(limit_order_price)
        self.stop_loss.append(stop_loss_price)

    def plot_orders(self):
        plot_data = [
            {'time': self.stoch_array['time'], 'values': self.stoch_array['stoch'], 'label': 'Stoch RSI', 'color': 'b', 'linestyle': 'dotted'},
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
        for data in plot_data[1:]:
            ax1.plot(data['time'], data['values'], label=data['label'], color=data['color'])
        ax1.legend(loc='upper left')

        ax2.set_title(f"{self.ticker} Stochastic RSI")
        data = plot_data[0]
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
        plt.tight_layout()
        plt.show()
