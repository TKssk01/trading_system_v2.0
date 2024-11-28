# post_order_processor.py

import logging
import pandas as pd

class PostOrderProcessor:
    def __init__(self, init):
        """
        初期化メソッド
        
        Parameters:
            init (Initializations): 共有初期化インスタンス
        """
        self.init = init
        self.logger = self.init.logger 

    def calculate_trading_values(self, current_time):
        """
        シグナルに基づいてトレーディング状態（キャッシュ、ポジションなど）を更新します。
        注文の発注は行いません。
        
        Parameters:
            current_time (pd.Timestamp): 現在のタイムスタンプ
        """
        # interpolated_dataが空の場合は処理をスキップ
        if self.init.interpolated_data.empty:
            self.logger.warning("interpolated_dataが空のため、トレーディング値の計算をスキップしました。")
            return
        
        # 最新の行を取得（インデックスに依存しない）
        last_row = self.init.interpolated_data.iloc[-1]

        # シグナルを取得
        buy_signal = last_row.get('buy_signals', 0)
        buy_exit_signal = last_row.get('buy_exit_signals', 0)
        sell_signal = last_row.get('sell_signals', 0)
        sell_exit_signal = last_row.get('sell_exit_signals', 0)
        emergency_buy_exit_signal = last_row.get('emergency_buy_exit_signals', 0)
        emergency_sell_exit_signal = last_row.get('emergency_sell_exit_signals', 0)
        special_sell_signal = last_row.get('special_sell_signals', 0)
        special_sell_exit_signal = last_row.get('special_sell_exit_signals', 0)
        special_buy_signal = last_row.get('special_buy_signals', 0)
        special_buy_exit_signal = last_row.get('special_buy_exit_signals', 0)

        # 現在のクローズ価格を取得
        current_close_price = last_row['close']

        # 前回の値を取得
        previous_cash = self.init.cash
        previous_quantity = self.init.quantity
        previous_stock_value = self.init.stock_value

        # ExitシグナルとEntryシグナルが同時に発生した場合、Exitを優先
        # 緊急Exitシグナルが発生した場合、他のシグナルを無効化
        if emergency_buy_exit_signal == 1:
            buy_signal = 0
            sell_signal = 0
            buy_exit_signal = 0
            sell_exit_signal = 0
        if emergency_sell_exit_signal == 1:
            buy_signal = 0
            sell_signal = 0
            buy_exit_signal = 0
            sell_exit_signal = 0

        # Exitシグナルの処理（トレーディング状態の更新のみ）
        if emergency_buy_exit_signal == 1 and self.init.signal_position == 'buy':
            # ポジションを閉じる
            self.init.cash += self.init.quantity * current_close_price
            self.init.quantity = 0
            self.init.stock_value = 0
            self.init.signal_position = None
            self.init.entry_price = None
            self.init.position_entry_index = None


        if emergency_sell_exit_signal == 1 and self.init.signal_position == 'sell':
            # ポジションを閉じる
            profit = (-self.init.quantity) * (self.init.entry_price - current_close_price)
            self.init.cash += profit
            self.init.quantity = 0
            self.init.signal_position = None
            self.init.entry_price = None
            self.init.stock_value = 0
            self.init.position_entry_index = None

        if buy_exit_signal == 1 and self.init.signal_position == 'buy':
            # ポジションを閉じる
            self.init.cash += self.init.quantity * current_close_price
            self.init.quantity = 0
            self.init.stock_value = 0
            self.init.signal_position = None
            self.init.entry_price = None
            self.init.position_entry_index = None

        if sell_exit_signal == 1 and self.init.signal_position == 'sell':
            # ポジションを閉じる
            profit = (-self.init.quantity) * (self.init.entry_price - current_close_price)
            self.init.cash += profit
            self.init.quantity = 0
            self.init.signal_position = None
            self.init.entry_price = None
            self.init.stock_value = 0
            self.init.position_entry_index = None

        if special_sell_exit_signal == 1 and self.init.signal_position == 'special_sell':
            # 特別な売りポジションを閉じる
            profit = (-self.init.quantity) * (self.init.entry_price - current_close_price)
            self.init.cash += profit
            self.init.quantity = 0
            self.init.signal_position = None
            self.init.entry_price = None
            self.init.stock_value = 0
            self.init.position_entry_index = None

        if special_buy_exit_signal == 1 and self.init.signal_position == 'special_buy':
            # 特別な買いポジションを閉じる
            self.init.cash += self.init.quantity * current_close_price
            self.init.quantity = 0
            self.init.stock_value = 0
            self.init.signal_position = None
            self.init.entry_price = None
            self.init.position_entry_index = None

        # Entryシグナルの処理（トレーディング状態の更新のみ）
        if special_sell_signal == 1:
            # 新規特別売りポジションを建てる
            quantity_to_sell = -int((self.init.cash // (current_close_price * 100)) * 100)
            self.init.quantity = quantity_to_sell
            self.init.signal_position = 'special_sell'
            self.init.entry_price = current_close_price
            self.init.position_entry_index = len(self.init.interpolated_data)

        if special_buy_signal == 1:
            # 新規特別買いポジションを建てる
            quantity_to_buy = int((self.init.cash // (current_close_price * 100)) * 100)
            self.init.quantity = quantity_to_buy
            self.init.cash -= self.init.quantity * current_close_price
            self.init.stock_value = self.init.quantity * current_close_price
            self.init.signal_position = 'special_buy'
            self.init.entry_price = current_close_price
            self.init.position_entry_index = len(self.init.interpolated_data)

        if buy_signal == 1:
            if self.init.signal_position == 'sell':
                # 逆ポジションを閉じる
                profit = (-self.init.quantity) * (self.init.entry_price - current_close_price)
                self.init.cash += profit
                self.init.quantity = 0
                self.init.signal_position = None
                self.init.entry_price = None
                self.init.stock_value = 0
                self.init.position_entry_index = None
                
            # 新規ポジションを建てる
            quantity_to_buy = int((self.init.cash // (current_close_price * 100)) * 100)
            self.init.quantity += quantity_to_buy
            self.init.cash -= self.init.quantity * current_close_price
            self.init.stock_value = self.init.quantity * current_close_price
            self.init.signal_position = 'buy'
            self.init.entry_price = current_close_price
            self.init.position_entry_index = len(self.init.interpolated_data)

        if sell_signal == 1:
            if self.init.signal_position == 'buy':
                # 逆ポジションを閉じる
                self.init.cash += self.init.quantity * current_close_price
                self.init.quantity = 0
                self.init.signal_position = None
                self.init.entry_price = None
                self.init.stock_value = 0
                self.init.position_entry_index = None
                
            # 新規ポジションを建てる
            quantity_to_sell = -int((self.init.cash // (current_close_price * 100)) * 100)
            self.init.quantity += quantity_to_sell
            self.init.signal_position = 'sell'
            self.init.entry_price = current_close_price
            self.init.stock_value = 0
            self.init.position_entry_index = len(self.init.interpolated_data)
            

        # シグナルがない場合、前回の値を保持
        if buy_signal == 0 and sell_signal == 0 and buy_exit_signal == 0 and sell_exit_signal == 0 \
            and emergency_buy_exit_signal == 0 and emergency_sell_exit_signal == 0 \
            and special_buy_signal == 0 and special_sell_signal == 0 \
            and special_buy_exit_signal == 0 and special_sell_exit_signal == 0:
            self.init.quantity = previous_quantity
            self.init.cash = previous_cash
            self.init.stock_value = previous_stock_value
            # ポジションは変更なし
            self.init.signal_position = self.init.signal_position   

        # ポジションの評価額を更新
        if self.init.signal_position in ['buy', 'special_buy']:
            self.init.stock_value = self.init.quantity * current_close_price
        elif self.init.signal_position in ['sell', 'special_sell']:
            # ショートポジションの評価額は0としておく
            self.init.stock_value = (-self.init.quantity) * (self.init.entry_price - current_close_price)

        # trading_equityを計算
        trading_equity = self.init.cash + self.init.stock_value

        # interpolated_dataに値を追加
        self.init.interpolated_data.loc[last_row.name, 'cash'] = self.init.cash
        self.init.interpolated_data.loc[last_row.name, 'quantity'] = self.init.quantity
        self.init.interpolated_data.loc[last_row.name, 'stock_value'] = self.init.stock_value
        self.init.interpolated_data.loc[last_row.name, 'trading_equity'] = trading_equity

        # パフォーマンスの計算
        # エントリーシグナルが出たら、エントリー価格とタイプを記録
        if buy_signal == 1 or sell_signal == 1 or special_buy_signal == 1 or special_sell_signal == 1:
            self.init.performance_entry_price = current_close_price
            if buy_signal == 1 or special_buy_signal == 1:
                self.init.performance_entry_type = 'buy'
            elif sell_signal == 1 or special_sell_signal == 1:
                self.init.performance_entry_type = 'sell'

        # 累積スコアをinterpolated_dataに記録
        self.init.interpolated_data.loc[last_row.name, 'performance'] = self.init.cumulative_score

        # 前回の累積スコアを更新
        self.init.previous_cumulative_score = self.init.cumulative_score