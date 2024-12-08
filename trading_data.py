# trading_data.py

from initializations import Initializations
from order_executor import API_BASE_URL
import requests
import json
import pandas as pd
import numpy as np
import datetime
import holidays
import time
from scipy.interpolate import UnivariateSpline
import logging
import urllib.request
import pprint
import yfinance as yf
from zoneinfo import ZoneInfo
from IPython.display import clear_output
from IPython.display import display

class TradingData:
    def __init__(self, init: Initializations, token):
        self.init = init
        self.init.token = token

        # ロギングの設定
        self.logger = self.init.logger

        # 列の定義
        self.signal_columns = [
            'buy_signals', 'sell_signals',
            'buy_exit_signals', 'buy_exit_signals_lc',
            'sell_exit_signals', 'sell_exit_signals_lc'
            'hedge_buy_signals', 'hedge_buy_exit_signals',
            'hedge_sell_signals', 'hedge_sell_exit_signals',
            'emergency_buy_exit_signals', 'emergency_sell_exit_signals',
            'special_sell_signals', 'special_sell_exit_signals',
            'special_buy_signals', 'special_buy_exit_signals'
        ]

    def safe_concat(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
        """
        空または全てNAの行・列を除外してデータフレームを連結します。

        Parameters:
            df1 (pd.DataFrame): 連結元のデータフレーム
            df2 (pd.DataFrame): 連結対象のデータフレーム

        Returns:
            pd.DataFrame: 連結後のデータフレーム
        """
        if df2.empty:
            self.logger.warning("連結対象のデータフレームが空のため、連結をスキップしました。")
            return df1
        # 全てNAの列・行を除外
        df2_cleaned = df2.dropna(axis=1, how='all').dropna(axis=0, how='all')
        if df2_cleaned.empty:
            self.logger.warning("連結対象のデータフレームが全てNAのため、連結をスキップしました。")
            return df1
        return pd.concat([df1, df2_cleaned], ignore_index=False)


    # データの表示
    def display_interpolated_data(self):
        """
        補間データとOHLCデータをグループごとに表示します。
        JupyterLabで見やすく表示するためにMarkdownとdisplayを使用します。
        """
        from IPython.display import display, Markdown
        import pandas as pd
        import datetime

        # Clear the current output in JupyterLab
        clear_output(wait=True)
        # Display the main header
        # display(Markdown("## Interpolated Data (Grouped):\n"))
        # Check if 'interpolated_data' exists and is not empty
        if hasattr(self.init, 'interpolated_data') and not self.init.interpolated_data.empty:
            # Define the groups and their corresponding columns
            groups = {
                '価格': ['close'],
                'エクイティ': ['buy_and_hold_equity', 'trading_equity', 'cash', 'stock_value', 'quantity'],
                'シグナル': [
                    'buy_signals', 'sell_signals',
                    'hedge_buy_signals', 'hedge_sell_signals',
                    'special_buy_signals','special_sell_signals',
                    'sell_exit_signals','buy_exit_signals',
                    'emergency_buy_exit_signals', 'emergency_sell_exit_signals',
                    'hedge_buy_exit_signals', 'hedge_sell_exit_signals',
                    'special_buy_exit_signals','special_sell_exit_signals',
                ]
                # 'テクニカル指標': [
                #     'band_width', 'hist', 'di_difference', 'adx_difference',
                #     'band_width_diff', 'hist_diff', 'di_difference_diff', 'adx_difference_diff'
                # ],
                # 'パフォーマンス': ['performance'],
                # 'トレンドデータ': ['fitted_values', 'trend_check_data', 'trend_check_data2'],
                # 'ピボットポイント': ['P', 'R1', 'R2', 'R3', 'S1', 'S2', 'S3']
            }
            # Iterate through each group and display its DataFrame
            for group_name, columns in groups.items():
                # Select only the columns that exist in 'interpolated_data'
                available_columns = [col for col in columns if col in self.init.interpolated_data.columns]
                if available_columns:
                    # Display the group name as a subheader
                    display(Markdown(f"### {group_name} ###"))
                    # Select the relevant columns and the last 5 rows
                    group_df = self.init.interpolated_data[available_columns].tail(20)
                    # Display the DataFrame
                    display(group_df)
                    # Add some spacing
                    display(Markdown("\n"))
        else:
            # Log an error if 'interpolated_data' does not exist or is empty
            self.init.logger.error("データフレーム 'interpolated_data' が存在しないか、空です。")

        print("buy_entry_price")
        print(self.init.buy_entry_price)
        print("")

        print("sell_entry_price")
        print(self.init.sell_entry_price)
        print("")

        print("original_entry_price")
        print(self.init.original_entry_price)
        print("")

        print("special_entry_price")
        print(self.init.special_entry_price)
        print("")
        
        print("signal_position_prev2")
        print(self.init.signal_position_prev2)
        print("")

        print("signal_position_prev")
        print(self.init.signal_position_prev)
        print("")

        print("signal_position")
        print(self.init.signal_position)
        print("")
        
        print("signal_position2_prev2")
        print(self.init.signal_position2_prev2)
        print("")
        
        print("signal_position2_prev")
        print(self.init.signal_position2_prev)
        print("")
        
        print("signal_position2")
        print(self.init.signal_position2)
        print("")
        

    def reset_signals(self, index):
        # リセットするシグナル列をリスト化
        signal_columns = [
            'buy_signals',
            'buy_exit_signals',
            'hedge_buy_exit_signals',
            'special_buy_exit_signals',
            'sell_signals',
            'hedge_sell_signals',
            'sell_exit_signals',
            'special_sell_exit_signals'     
        ]

        # データフレームに存在するシグナル列のみを選択
        existing_signal_columns = [col for col in signal_columns if col in self.init.interpolated_data.columns]

        if existing_signal_columns:
            # 指定されたインデックスのシグナル列を0にリセット
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            print(f"インデックス {index} のシグナルをリセットしました。")
        else:
            print("リセット対象のシグナル列が見つかりませんでした。")

        # 前回の値を現在の値に戻す
        reset_variables = [
            ('special_sell_active', 'special_sell_active_prev'),
            ('special_buy_active', 'special_buy_active_prev'),
            ('buy_entry_price', 'buy_entry_price_prev'),
            ('sell_entry_price', 'sell_entry_price_prev'),
            ('cumulative_score', 'cumulative_score_prev'),
            ('previous_cumulative_score', 'previous_cumulative_score_prev'),
            ('special_entry_price', 'special_entry_price_prev'),
            ('original_entry_price', 'original_entry_price_prev'),
            ('signal_position', 'signal_position_prev'),
            ('signal_position2', 'signal_position2_prev'),
        ]

        for current, prev in reset_variables:
            if hasattr(self.init, current) and hasattr(self.init, prev):
                setattr(self.init, current, getattr(self.init, prev))
                print(f"{current} を {prev} の値でリセットしました。")
            else:
                print(f"属性 {current} または {prev} が存在しません。")
                
    def reset_signals1(self, index):
        # リセットするシグナル列をリスト化
        signal_columns = [
            'buy_signals',
            'buy_exit_signals',
            'hedge_buy_exit_signals',
            'special_buy_exit_signals',
            'sell_signals',
            'hedge_sell_signals',
            'sell_exit_signals',
            'special_sell_exit_signals'     
        ]

        # データフレームに存在するシグナル列のみを選択
        existing_signal_columns = [col for col in signal_columns if col in self.init.interpolated_data.columns]

        if existing_signal_columns:
            # 指定されたインデックスのシグナル列を0にリセット
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            print(f"インデックス {index} のシグナルをリセットしました。")
        else:
            print("リセット対象のシグナル列が見つかりませんでした。")

        # 前回の値を現在の値に戻す
        reset_variables = [
            ('special_sell_active', 'special_sell_active_prev'),
            ('special_buy_active', 'special_buy_active_prev'),
            ('buy_entry_price', 'buy_entry_price_prev'),
            ('sell_entry_price', 'sell_entry_price_prev'),
            ('cumulative_score', 'cumulative_score_prev'),
            ('previous_cumulative_score', 'previous_cumulative_score_prev'),
            ('special_entry_price', 'special_entry_price_prev'),
            ('original_entry_price', 'original_entry_price_prev'),
            ('signal_position1', 'signal_position1_prev'),
            ('signal_position2', 'signal_position2_prev'),
        ]

        for current, prev in reset_variables:
            if hasattr(self.init, current) and hasattr(self.init, prev):
                setattr(self.init, current, getattr(self.init, prev))
                print(f"{current} を {prev} の値でリセットしました。")
            else:
                print(f"属性 {current} または {prev} が存在しません。")
    
    def reset_signals_2(self, index):
        # リセットするシグナル列をリスト化
        signal_columns = [
            'buy_signals',
            'buy_exit_signals',
            'hedge_buy_exit_signals',
            'special_buy_exit_signals',
            'sell_signals',
            'sell_exit_signals',
            'hedge_sell_exit_signals',
            'special_sell_exit_signals'
        ]

        # データフレームに存在するシグナル列のみを選択
        existing_signal_columns = [col for col in signal_columns if col in self.init.interpolated_data.columns]

        if existing_signal_columns:
            # 指定されたインデックスのシグナル列を0にリセット
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            print(f"インデックス {index} のシグナルをリセットしました。")
        else:
            print("リセット対象のシグナル列が見つかりませんでした。")

        # 前回の値を現在の値に戻す
        reset_variables = [
            ('special_sell_active', 'special_sell_active_prev'),
            ('special_buy_active', 'special_buy_active_prev'),
            ('buy_entry_price', 'buy_entry_price_prev'),
            ('sell_entry_price', 'sell_entry_price_prev'),
            ('cumulative_score', 'cumulative_score_prev'),
            ('previous_cumulative_score', 'previous_cumulative_score_prev'),
            ('special_entry_price', 'special_entry_price_prev'),
            ('original_entry_price', 'original_entry_price_prev'),
            ('signal_position', 'signal_position_prev2'),
            ('signal_position2', 'signal_position2_prev2'),
        ]

        for current, prev in reset_variables:
            if hasattr(self.init, current) and hasattr(self.init, prev):
                setattr(self.init, current, getattr(self.init, prev))
                print(f"{current} を {prev} の値でリセットしました。")
            else:
                print(f"属性 {current} または {prev} が存在しません。")
                
    def reset_signals1_2(self, index):
        # リセットするシグナル列をリスト化
        signal_columns = [
            'buy_signals',
            'buy_exit_signals',
            'hedge_buy_exit_signals',
            'special_buy_exit_signals',
            'sell_signals',
            'sell_exit_signals',
            'hedge_sell_exit_signals',
            'special_sell_exit_signals'
        ]

        # データフレームに存在するシグナル列のみを選択
        existing_signal_columns = [col for col in signal_columns if col in self.init.interpolated_data.columns]

        if existing_signal_columns:
            # 指定されたインデックスのシグナル列を0にリセット
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            self.init.interpolated_data.loc[index, existing_signal_columns] = 0
            print(f"インデックス {index} のシグナルをリセットしました。")
        else:
            print("リセット対象のシグナル列が見つかりませんでした。")

        # 前回の値を現在の値に戻す
        reset_variables = [
            ('special_sell_active', 'special_sell_active_prev'),
            ('special_buy_active', 'special_buy_active_prev'),
            ('buy_entry_price', 'buy_entry_price_prev'),
            ('sell_entry_price', 'sell_entry_price_prev'),
            ('cumulative_score', 'cumulative_score_prev'),
            ('previous_cumulative_score', 'previous_cumulative_score_prev'),
            ('special_entry_price', 'special_entry_price_prev'),
            ('original_entry_price', 'original_entry_price_prev'),
            ('signal_position1', 'signal_position1_prev2'),
            ('signal_position2', 'signal_position2_prev2'),
        ]

        for current, prev in reset_variables:
            if hasattr(self.init, current) and hasattr(self.init, prev):
                setattr(self.init, current, getattr(self.init, prev))
                print(f"{current} を {prev} の値でリセットしました。")
            else:
                print(f"属性 {current} または {prev} が存在しません。")


    # 最新価格の取得
    def fetch_current_price(self):
        """
        最新の価格をAPIから取得し、pricesリストに追加します。
        """
        board_url = f"{self.init.api_base_url}/board/{self.init.symbol}@{self.init.exchange}"
        headers = {'X-API-KEY': self.init.token}
        try:
            response = requests.get(board_url, headers=headers)
            if response.status_code == 200:
                board = response.json()
                current_price = board.get('CurrentPrice')
                if current_price is not None:
                    self.init.prices.append(current_price)
                    self.logger.info(f"取得した価格: {current_price}")
                    return current_price
                else:
                    self.logger.warning("取得した価格が None です。")
                    return None
            else:
                self.logger.error(f"ボードデータの取得に失敗しました: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"価格取得中に例外が発生しました: {e}")
            return None

    # 価格リストを作成し、OHLCデータを生成
    def create_ohlc(self):
        if len(self.init.prices) == 4:
            current_time = datetime.datetime.now()
            ohlc = {
                'open': self.init.prices[0],
                'high': max(self.init.prices),
                'low': min(self.init.prices),
                'close': self.init.prices[-1]
            }
            new_data = pd.DataFrame([ohlc], index=[current_time])
            # if not new_data.empty and not new_data.isna().all().all():
            #     self.init.df = pd.concat([self.init.df, new_data], ignore_index=False)
            # else:
            #     self.logger.warning("新しいOHLCデータが空または全てNAのため、連結をスキップしました。")
            # self.init.prices = []  # 価格リストをリセット

            # ヘルパー関数を使用して安全に連結
            self.init.df = self.safe_concat(self.init.df, new_data)
            self.init.prices = []  # 価格リストをリセット

    def calculate_buy_and_hold_equity(self):
        """
        Buy and Hold のエクイティカーブを計算します。
        初期投資額に対する現在の株価の割合を基に計算します。
        """
        if self.init.first_quantity == 0:
            # 初期設定
            self.init.first_price = self.init.df['close'].iloc[0]  # 初期価格を設定
            self.init.first_quantity = (self.init.first_balance // (self.init.first_price * 100)) * 100  # 100株単位で購入
            self.init.initial_stock_value = self.init.first_quantity * self.init.first_price
            self.init.first_cash = self.init.first_balance - self.init.initial_stock_value

            # Buy and Hold Equityの初期値を設定
            self.init.buy_and_hold_equity = self.init.initial_stock_value + self.init.first_cash

            # 初期エクイティカーブを interpolated_data に追加
            if not self.init.interpolated_data.empty:
                self.init.interpolated_data.loc[self.init.interpolated_data.index[-1], 'buy_and_hold_equity'] = self.init.buy_and_hold_equity
            else:
                # interpolated_data が空の場合、新しい行を追加
                current_time = datetime.datetime.now()
                new_row = {'buy_and_hold_equity': self.init.buy_and_hold_equity}
                new_row_df = pd.DataFrame([new_row], index=[current_time])
                # new_row_dfが空でない場合のみ結合
                # if not new_row_df.empty:
                #     self.init.interpolated_data = pd.concat([self.init.interpolated_data, new_row_df])

                # ヘルパー関数を使用して安全に連結
                self.init.interpolated_data = self.safe_concat(self.init.interpolated_data, new_row_df)
        else:
            # Buy and Hold Equityを更新
            if not self.init.interpolated_data.empty:
                latest_close = self.init.interpolated_data['close'].iloc[-1]
                self.init.buy_and_hold_equity = self.init.first_quantity * latest_close + self.init.first_cash

                # 最新の行にエクイティカーブを追加
                self.init.interpolated_data.loc[self.init.interpolated_data.index[-1], 'buy_and_hold_equity'] = self.init.buy_and_hold_equity
            else:
                self.logger.warning("interpolated_data が空のため、Buy and Hold Equity を更新できません。")

    # ピボットポイントの計算
    def calculate_pivot_points(self):
        """
        ピボットポイントを計算し、データフレームに追加または更新します。
        """
        # ピボットポイントのカラム
        pivot_columns = ['P', 'R1', 'R2', 'R3', 'S1', 'S2', 'S3']

        # メソッド呼び出しの確認
        self.init.logger.debug("calculate_pivot_points メソッドが呼び出されました。")

        # 日本のタイムゾーンを設定
        jst = ZoneInfo('Asia/Tokyo')
        # 日本時間で現在の日付を取得
        today = datetime.datetime.now(jst).date()
        # 日本の祝日を取得
        jp_holidays = holidays.Japan()
        # 土日祝日を除外して直近の営業日を取得
        while today.weekday() >= 5 or today in jp_holidays:  # 土日または祝日の場合
            today -= datetime.timedelta(days=1)

        self.init.logger.debug(f"Today after adjusting for weekends/holidays: {today}")

        # 前営業日を取得
        yesterday = today - datetime.timedelta(days=1)
        while yesterday.weekday() >= 5 or yesterday in jp_holidays:
            yesterday -= datetime.timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')

        self.init.logger.debug(f"Yesterday (trading day): {yesterday_str}")
        self.init.logger.debug(f"Today (trading day): {today_str}")

        # ティッカーシンボルを動的に生成
        symbol = str(self.init.symbol)
        ticker = f"{symbol}.T"

        self.init.logger.debug(f"Ticker: {ticker}")

        # カラムが存在しない場合、NaNで追加（念のため）
        for col in pivot_columns:
            if col not in self.init.interpolated_data.columns:
                self.init.interpolated_data[col] = pd.NA
                self.init.logger.debug(f"カラム '{col}' を interpolated_data に追加しました。")

        try:
            data = yf.download(
                ticker,
                start=yesterday_str,
                end=(yesterday + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                progress=False
            )

        except Exception as e:
            self.init.logger.error(f"Error downloading data for {ticker} from {yesterday_str}: {e}")
            P = R1 = R2 = R3 = S1 = S2 = S3 = 0
            return P, R1, R2, R3, S1, S2, S3

        if not data.empty:
            if isinstance(data, pd.DataFrame):
                data = data.iloc[0]  # 最初の行を選択
                self.init.logger.debug("DataFrame からデータを選択")
            elif isinstance(data, pd.Series):
                self.init.logger.debug("Series からデータを選択")
            else:
                self.init.logger.error("取得したデータの形式が不正です。")
                P = R1 = R2 = R3 = S1 = S2 = S3 = 0
                return P, R1, R2, R3, S1, S2, S3
        else:
            # データが取得できなかった場合、過去5営業日のデータを試みる
            self.init.logger.warning(f"Data for {yesterday_str} is empty. Trying to download data for the past 5 days.")
            data = None
            for i in range(1, 6):
                attempt_date = yesterday - datetime.timedelta(days=i)
                if attempt_date.weekday() >= 5 or attempt_date in jp_holidays:
                    self.init.logger.debug(f"Skipping non-trading day: {attempt_date}")
                    continue
                attempt_date_str = attempt_date.strftime('%Y-%m-%d')
                try:
                    temp_data = yf.download(
                        ticker,
                        start=attempt_date_str,
                        end=(attempt_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
                        interval='1d',
                        progress=False
                    )
                    if not temp_data.empty:
                        data = temp_data.iloc[0]
                        self.init.logger.debug(f"取得したデータの日付: {attempt_date_str}")
                        break
                    else:
                        self.init.logger.debug(f"No data for {attempt_date_str}")
                except Exception as e:
                    self.init.logger.error(f"Error downloading data for {ticker} from {attempt_date_str}: {e}")
            else:
                self.init.logger.error(f"Yahoo Financeから{ticker}のデータを取得できませんでした。")
                P = R1 = R2 = R3 = S1 = S2 = S3 = 0
                return P, R1, R2, R3, S1, S2, S3

        if data is not None:
            # 高値、安値、終値を取得
            high = data['High']
            low = data['Low']
            close = data['Close']
            self.init.logger.debug(f"High: {high}, Low: {low}, Close: {close}")

            # ピボットポイントの計算
            P = (high + low + close) / 3
            R1 = 2 * P - low
            S1 = 2 * P - high
            R2 = P + (high - low)
            S2 = P - (high - low)
            R3 = high + 2 * (P - low)
            S3 = low - 2 * (high - P)

            self.init.logger.debug(f"P: {P}, R1: {R1}, R2: {R2}, R3: {R3}, S1: {S1}, S2: {S2}, S3: {S3}")

            # ピボットポイントをinterpolated_dataに追加または更新
            new_row = {
                'P': P,
                'R1': R1,
                'R2': R2,
                'R3': R3,
                'S1': S1,
                'S2': S2,
                'S3': S3
            }

            # データフレームのカラムを確認
            self.init.logger.debug(f"interpolated_data のカラム: {self.init.interpolated_data.columns.tolist()}")

            if not self.init.interpolated_data.empty:
                # 最新行のインデックスを取得
                latest_index = self.init.interpolated_data.index[-1]
                self.init.logger.debug(f"最新行のインデックス: {latest_index}")

                # 最新行のピボットポイントカラムを更新
                try:
                    self.init.interpolated_data.loc[latest_index, pivot_columns] = list(new_row.values())
                    self.init.logger.debug(f"最新行 ({latest_index}) のピボットポイントを更新しました。")
                except Exception as e:
                    self.init.logger.error(f"最新行の更新中にエラーが発生しました: {e}")
            else:
                # データフレームが空の場合、新しい行を追加
                try:
                    # 新しい行に日付をインデックスとして設定
                    self.init.interpolated_data.loc[yesterday_str] = list(new_row.values())
                    self.init.logger.debug(f"新しいピボットポイントをinterpolated_dataに追加しました。日付: {yesterday_str}")
                except Exception as e:
                    self.init.logger.error(f"新しい行の追加中にエラーが発生しました: {e}")

            # 行数の確認
            self.init.logger.debug(f"interpolated_dataの現在の行数: {len(self.init.interpolated_data)}")

        else:
            # データが取得できなかった場合、すでに0を返している
            pass

        return P, R1, R2, R3, S1, S2, S3


    # ボリンジャーバンドの計算
    def calculate_bollinger_bands(self, window=20, num_std=1.96):
        """
        ボリンジャーバンドを計算し、データフレームに追加します。
        """
        rolling_mean = self.init.df['close'].rolling(window=window, min_periods=1).mean()
        rolling_std = self.init.df['close'].rolling(window=window, min_periods=1).std()
        upper_band = rolling_mean + (rolling_std * num_std)
        lower_band = rolling_mean - (rolling_std * num_std)
        band_width = (upper_band - lower_band) / rolling_mean
        band_width.bfill(inplace=True)
        self.init.df['upper_band'] = upper_band
        self.init.df['lower_band'] = lower_band
        self.init.df['band_width'] = band_width

    # MACDの計算
    def calculate_macd(self, short_window=5, middle_window=20, long_window=40, signal_window=9):
        """
        MACDを計算し、データフレームに追加します。
        """
        short_ema = self.init.df['close'].ewm(span=short_window, min_periods=1, adjust=False).mean()
        middle_ema = self.init.df['close'].ewm(span=middle_window, min_periods=1, adjust=False).mean()
        long_ema = self.init.df['close'].ewm(span=long_window, min_periods=1, adjust=False).mean()
        macd_3 = middle_ema - long_ema
        signal = macd_3.ewm(span=signal_window, adjust=False).mean()
        hist = (macd_3 - signal) / self.init.df['close']
        self.init.df['hist'] = hist


    # DMIの計算
    def calculate_dmi_adx(self, window=14):
        """
        DMIとADXを計算し、データフレームに追加します。
        """
        up_move = self.init.df['high'].diff()
        down_move = -self.init.df['low'].diff()
        plus_dm = up_move.where((up_move > 0) & (up_move > down_move), 0)
        minus_dm = down_move.where((down_move > 0) & (down_move > up_move), 0)
        tr1 = self.init.df['high'] - self.init.df['low']
        tr2 = abs(self.init.df['high'] - self.init.df['close'].shift(1))
        tr3 = abs(self.init.df['low'] - self.init.df['close'].shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=window, min_periods=1).sum()
        plus_di = 100 * (plus_dm.rolling(window=window, min_periods=1).sum() / atr)
        minus_di = 100 * (minus_dm.rolling(window=window, min_periods=1).sum() / atr)
        di_difference = (plus_di - minus_di) / atr
        di_difference.bfill(inplace=True)
        self.init.df['di_difference'] = di_difference

        # ADXの計算
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(span=window, min_periods=1, adjust=False).mean()
        adxr = adx.ewm(span=window, min_periods=1, adjust=False).mean()
        adx_difference = (adx - adxr) / atr
        adx_difference.bfill(inplace=True)
        self.init.df['adx_difference'] = adx_difference

    # テクニカル指標の計算
    def calculate_technical_indicators(self):
        """
        ボリンジャーバンド、
        ピボットポイント、
        MACD、
        DMI・ADX
        のテクニカル指標を計算し、データフレームに追加します。
        """
        self.calculate_bollinger_bands()
        self.calculate_macd()
        self.calculate_dmi_adx()
        self.calculate_pivot_points()

    # 最新のテクニカル指標データを更新
    def update_latest_9_data(self, band_width, hist, di_difference, adx_difference):
        """
        最新の9データを更新し、補間データを計算してinterpolated_dataに追加します。
        """
        # 最新の各指標データを最新データリストに追加
        for key, value in zip(['band_width', 'hist', 'di_difference', 'adx_difference'],
                              [band_width, hist, di_difference, adx_difference]):
            self.init.latest_data[key].append(value.iloc[-1])
            if len(self.init.latest_data[key]) > 9:
                self.init.latest_data[key].pop(0)

        # 最新データが9件に達したら補間と導関数の計算を実施
        if len(self.init.latest_data['band_width']) >= 9:
            # 最新データをlatest_data_1とlatest_data_2に分割
            for key in self.init.latest_data_1.keys():
                self.init.latest_data_1[key] = self.init.latest_data[key][:8]
            for key in self.init.latest_data_2.keys():
                self.init.latest_data_2[key] = self.init.latest_data[key][1:9]

            # 各データについて区間中間点の補間データを計算し、データフレームに追加
            interpolated_row = {}
            derivative_row = {}
            for key in ['band_width', 'hist', 'di_difference', 'adx_difference']:
                spline_1 = self.apply_spline(self.init.latest_data_1[key], self.init.s_parameters[key])
                spline_2 = self.apply_spline(self.init.latest_data_2[key], self.init.s_parameters[key])

                interpolation, derivative = self.calculate_interpolated_data(
                    spline_1[5],
                    spline_2[6],
                    np.gradient(spline_1)[5],
                    np.gradient(spline_2)[6],
                    np.gradient(np.gradient(spline_1))[5],
                    np.gradient(np.gradient(spline_2))[6]
                )
                interpolated_row[key] = interpolation * 10000  # 補間データを10000倍にする
                derivative_row[key + '_diff'] = derivative

            # インデックスを時刻に変更（マイクロ秒を含む）
            current_time = datetime.datetime.now()

            # 新しい行を作成して追加
            new_row = {
                'close': self.init.df['close'].iloc[-1],
                'upper_band': self.init.df['upper_band'].iloc[-1],
                'lower_band': self.init.df['lower_band'].iloc[-1],
                'R1': self.init.R1,
                'R2': self.init.R2,
                'R3': self.init.R3,
                'S1': self.init.S1,
                'S2': self.init.S2,
                'S3': self.init.S3
            }

            # 補間値を追加
            new_row.update(interpolated_row)
            # 導関数の値を追加
            new_row.update(derivative_row)

            # シグナル列が存在しない場合は初期化
            signal_columns = [
                'buy_signals', 'sell_signals'
                'buy_exit_signals', 'sell_exit_signals',
                'buy_exit_signals_lc', 'sell_exit_signals_lc',
                'hedge_buy_signals', 'hedge_buy_exit_signals',
                'hedge_sell_signals', 'hedge_sell_exit_signals',
                'emergency_buy_exit_signals', 'emergency_sell_exit_signals',
                'special_buy_signals', 'special_buy_exit_signals',
                'special_sell_signals', 'special_sell_exit_signals',
                'buy_and_hold_equity', 'trading_equity', 'cash', 'stock_value', 'quantity', 'performance'
            ]
            for signal_col in signal_columns:
                if signal_col not in new_row:
                    new_row[signal_col] = 0

            # 新しい行のDataFrameを作成
            new_row_df = pd.DataFrame([new_row], index=[current_time])
            # new_row_dfが空でないかつ全てNAでない場合のみ結合
            if not new_row_df.empty and not new_row_df.isna().all().all():
                self.init.interpolated_data = pd.concat([self.init.interpolated_data, new_row_df], ignore_index=False)
            else:
                self.logger.warning("新しい行データが空または全てNAのため、連結をスキップしました。")

            # trend_check_data の更新
            if len(self.init.interpolated_data) >= 3:
                close_values = self.init.interpolated_data['close'].iloc[-3:]
                x = np.arange(len(close_values))
                y = close_values.values

                # 次数2の多項式近似を適用
                coeffs = np.polyfit(x, y, 2)
                fitted_values = np.polyval(coeffs, x)

                # 微分値を算出
                derivative_coeffs = [2 * coeffs[0], coeffs[1]]
                derivative_values = np.polyval(derivative_coeffs, x)

                # 列が存在しない場合は作成
                for col in ['fitted_values', 'trend_check_data', 'trend_check_data2']:
                    if col not in self.init.interpolated_data.columns:
                        self.init.interpolated_data[col] = np.nan

                # 最新の行のみを更新
                latest_index = self.init.interpolated_data.index[-1]
                self.init.interpolated_data.at[latest_index, 'fitted_values'] = fitted_values[-1]
                self.init.interpolated_data.at[latest_index, 'trend_check_data'] = derivative_values[-1]
                self.init.interpolated_data.at[latest_index, 'trend_check_data2'] = coeffs[0]



    # スプライン補間の適用
    def apply_spline(self, data, s_value):
        """
        データにスプライン補間を適用します。

        Parameters:
            data (array-like): 補間対象のデータ
            s_value (float): スムージングパラメータ

        Returns:
            array-like: 補間されたデータ
        """
        x = np.arange(len(data))
        spline = UnivariateSpline(x, data, s=s_value)
        return spline(x)

    # スプラインの補間点と導関数の計算
    def calculate_interpolated_data(self, spline_start, spline_end, diff1_start, diff1_end, diff2_start, diff2_end):
        """
        スプラインの補間点とその導関数を計算します。

        Parameters:
            spline_start (float): スプラインの開始値
            spline_end (float): スプラインの終了値
            diff1_start (float): 一次導関数の開始値
            diff1_end (float): 一次導関数の終了値
            diff2_start (float): 二次導関数の開始値
            diff2_end (float): 二次導関数の終了値

        Returns:
            tuple: 補間値と導関数値
        """
        A = np.array([
            [1, 0, 0, 0, 0, 0],
            [1, 2, 2**2, 2**3, 2**4, 2**5],
            [0, 1, 0, 0, 0, 0],
            [0, 1, 2*2, 3*2**2, 4*2**3, 5*2**4],
            [0, 0, 2, 0, 0, 0],
            [0, 0, 2, 6*2, 12*2**2, 20*2**3]
        ])

        B = np.array([spline_start, spline_end, diff1_start, diff1_end, diff2_start, diff2_end])
        coefficients = np.linalg.solve(A, B)
        interpolation = np.polyval(coefficients[::-1], 1)
        # 導関数の計算
        derivative_coeffs = np.polyder(coefficients[::-1])
        derivative_value = np.polyval(derivative_coeffs, 1)
        return interpolation, derivative_value

    # スペシャルシグナルのexitの場合のみに使用
    def check_spline_condition(self, key, s_param, comparison):
        if len(self.init.latest_data[key]) < 9:
            return False
        x = np.arange(9)
        y = self.init.latest_data[key][-9:]
        spline = UnivariateSpline(x, y, s=s_param)
        spline_values = spline(x)
        gradient_values = np.gradient(spline_values)
        gradient = gradient_values[-1]
        if comparison == '<= 0':
            return gradient <= 0
        elif comparison == '>= 0':
            return gradient >= 0
        else:
            return False

    # 売買シグナルの生成
    def generate_signals(self, data, R1, R2, R3, S1, S2, S3):
        """
        売買シグナルを生成します。

        Parameters:
            data (DataFrame): シグナルを生成するデータフレーム
            R1, R2, R3, S1, S2, S3 (float): ピボットポイント
        """
        # データが十分に存在するか確認
        if len(data) < 2:
            return  # データが不足している場合は終了

        

        # 前回の値を保持
        self.init.special_sell_active_prev = self.init.special_sell_active
        self.init.special_buy_active_prev = self.init.special_buy_active
        self.init.signal_position_prev = self.init.signal_position
        self.init.signal_position_prev2 = self.init.signal_position_prev
        self.init.signal_position1_prev = self.init.signal_position1
        self.init.signal_position1_prev2 = self.init.signal_position1_prev
        self.init.signal_position2_prev = self.init.signal_position2
        self.init.signal_position2_prev2 = self.init.signal_position2_prev
        self.init.entry_price_prev = self.init.entry_price
        self.init.buy_entry_price_prev = self.init.buy_entry_price
        self.init.sell_entry_price_prev = self.init.sell_entry_price
        self.init.cumulative_score_prev = self.init.cumulative_score
        self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
        self.init.special_entry_price_prev = self.init.special_entry_price
        self.init.original_entry_price_prev = self.init.original_entry_price

        current_index = data.index[-1]
        current_close = data.at[current_index, 'close']
        
        current_index_prev = data.index[-2]
        current_close_prev = data.at[current_index_prev, 'close']
        
        print("current_index")
        print(current_index)
        print("current_close")
        print(current_close)

        # time.sleep(10)

        # メソッド開始時に前回の状態を保存
        prev_special_sell = self.init.prev_special_sell_active
        prev_special_buy = self.init.prev_special_buy_active

        # シグナル列の存在確認と初期化
        signal_columns = [
            'buy_signals', 'sell_signals',
            'buy_exit_signals', 'sell_exit_signals',
            'buy_exit_signals_lc', 'sell_exit_signals_lc',
            'emergency_buy_exit_signals', 'emergency_sell_exit_signals',
            'hedge_buy_signals', 'hedge_buy_exit_signals',
            'hedge_sell_signals', 'hedge_sell_exit_signals',
            'special_buy_signals', 'special_buy_exit_signals',
            'special_sell_signals', 'special_sell_exit_signals'
        ]

        for col in signal_columns:
            if col not in data.columns:
                data[col] = 0
                
        # ヘッジ売りポジション生成シグナルの生成
        if self.init.position_entry_index is not None and \
            len(self.init.interpolated_data) - self.init.position_entry_index >= 30 and \
                self.init.signal_position2 is None:
            if self.init.signal_position == 'buy' and not self.init.special_sell_active:
                if np.log(current_close / self.init.buy_entry_price) < -0.00158:
                    
                    data.at[current_index, 'hedge_sell_signals'] = 1
                    self.init.signal_position2 = 'hedge_sell'
                    
        # ヘッジ買いポジション生成シグナルの生成
        if self.init.position_entry_index is not None and \
            len(self.init.interpolated_data) - self.init.position_entry_index >= 30 and \
                self.init.signal_position2 is None:
            if self.init.signal_position == 'sell' and not self.init.special_buy_active:
                if np.log(current_close / self.init.sell_entry_price) > 0.00158:
                   
                    data.at[current_index, 'hedge_buy_signals'] = 1
                    self.init.signal_position2 = 'hedge_buy'

        # 緊急買いポジション決済シグナルと特別売りポジション生成シグナルの生成
        if self.init.position_entry_index is not None and \
            len(self.init.interpolated_data) - self.init.position_entry_index >= 60:
            if self.init.signal_position == 'buy' and not self.init.special_sell_active:
                if np.log(current_close / self.init.buy_entry_price) < -0.005:
                    
                    data.at[current_index, 'emergency_buy_exit_signals'] = 1
                    self.init.special_sell_active = True
                    self.init.signal_position = None
                    self.init.special_entry_price = current_close
                    self.init.original_entry_price = self.init.buy_entry_price
                    # self.init.buy_entry_price = None
                    
                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                    self.init.signal_position2 = None
                    
                    data.at[current_index, 'special_sell_signals'] = 1
                    self.init.signal_position = 'special_sell'
                    self.init.sell_entry_price = current_close

        # 緊急売りポジション決済シグナルと特別買いポジション生成シグナルの生成
        if self.init.position_entry_index is not None and \
            len(self.init.interpolated_data) - self.init.position_entry_index >= 60:
            if self.init.signal_position == 'sell' and not self.init.special_buy_active:
                if np.log(current_close / self.init.sell_entry_price) > 0.005:
                    
                    data.at[current_index, 'emergency_sell_exit_signals'] = 1
                    self.init.special_buy_active = True
                    self.init.signal_position = None
                    self.init.special_entry_price = current_close
                    self.init.original_entry_price = self.init.sell_entry_price
                    # self.init.sell_entry_price = None
                    
                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                    self.init.signal_position2 = None
                    
                    data.at[current_index, 'special_buy_signals'] = 1
                    self.init.signal_position = 'special_buy'
                    self.init.buy_entry_price = current_close

        # 特別売りポジション解消シグナルと通常の買いポジション生成シグナルの生成
        if self.init.special_sell_active and prev_special_sell:
            condition1 = self.check_spline_condition('band_width', 0.000185, '<= 0')
            condition2 = self.check_spline_condition('adx_difference', 1.85, '<= 0')
            condition3 = self.check_spline_condition('hist', 0.00000185, '>= 0')
            condition4 = self.check_spline_condition('di_difference', 18.5, '>= 0')
            K = -0.005 + np.log(self.init.original_entry_price / self.init.special_entry_price)
            if self.init.signal_position == 'special_sell' and \
                ((condition1 and condition2 and condition3 and condition4) or \
                np.log(current_close / self.init.sell_entry_price) < K):
                   
                data.at[current_index, 'special_sell_exit_signals'] = 1
                self.init.special_sell_active = False
                self.init.signal_position = None
                # self.init.special_entry_price = None
                # self.init.original_entry_price = None
                # self.init.sell_entry_price = None

                # イグジットシグナル直後の値を保持 20241103
                self.init.special_sell_active_prev = self.init.special_sell_active
                self.init.signal_position_prev = self.init.signal_position

                # 失効した場合、ポジション = None         
                data.at[current_index, 'buy_signals'] = 1
                self.init.buy_entry_price = current_close
                self.init.signal_position = 'buy'
                self.init.position_entry_index = len(self.init.interpolated_data)

        # 特別買いポジション解消シグナルと通常の売りポジション生成シグナルの生成
        if self.init.special_buy_active and prev_special_buy:
            condition1 = self.check_spline_condition('band_width', 0.000185, '<= 0')
            condition2 = self.check_spline_condition('adx_difference', 1.85, '<= 0')
            condition3 = self.check_spline_condition('hist', 0.00000185, '<= 0')
            condition4 = self.check_spline_condition('di_difference', 18.5, '<= 0')
            K = 0.005 + np.log(self.init.original_entry_price / self.init.special_entry_price)
            if self.init.signal_position == 'special_buy' and \
                ((condition1 and condition2 and condition3 and condition4) or \
                np.log(current_close / self.init.buy_entry_price) > K):
                
                data.at[current_index, 'special_buy_exit_signals'] = 1
                self.init.special_buy_active = False
                self.init.signal_position = None
                # self.init.special_entry_price = None
                # self.init.original_entry_price = None
                # self.init.buy_entry_price = None

                # イグジットシグナル直後の値を保持
                self.init.special_buy_active_prev = self.init.special_buy_active
                self.init.signal_position_prev = self.init.signal_position

                data.at[current_index, 'sell_signals'] = 1
                self.init.sell_entry_price = current_close
                self.init.signal_position = 'sell'
                self.init.position_entry_index = len(self.init.interpolated_data)

        # 通常のシグナルの生成
        if not self.init.special_sell_active and not self.init.special_buy_active and \
            not prev_special_sell and not prev_special_buy:
            if 'trend_check_data' not in data.columns or 'trend_check_data2' not in data.columns:
                return  # 必要な列がない場合は終了

            if len(data) < 3:
                return  # データが不足している場合は終了

            # インデックスリストを取得
            index_list = data.index.tolist()

            # 最新のデータを取得
            i = len(data) - 1  # 最新の位置インデックス
            current_index = index_list[i]

            # 前回と前々回のデータを取得
            if i - 2 >= 0:
                trend_check_data_prev = data.at[index_list[i - 2], 'trend_check_data']
            else:
                trend_check_data_prev = data.at[index_list[0], 'trend_check_data']

            # トレンドの方向を判定
            trend_positive1 = trend_check_data_prev >= 0 and \
                            data.at[current_index, 'trend_check_data'] > 0 and \
                            data.at[current_index, 'trend_check_data2'] > 0

            trend_positive2 = (
                (trend_check_data_prev < 0 and
                data.at[current_index, 'trend_check_data'] <= 0 and
                data.at[current_index, 'trend_check_data2'] > 0) or
                (trend_check_data_prev <= 0 and
                data.at[current_index, 'trend_check_data'] >= 0 and
                data.at[current_index, 'trend_check_data2'] > 0)
            )

            trend_negative1 = trend_check_data_prev <= 0 and \
                            data.at[current_index, 'trend_check_data'] < 0 and \
                            data.at[current_index, 'trend_check_data2'] < 0

            trend_negative2 = (
                (trend_check_data_prev > 0 and
                data.at[current_index, 'trend_check_data'] >= 0 and
                data.at[current_index, 'trend_check_data2'] < 0) or
                (trend_check_data_prev >= 0 and
                data.at[current_index, 'trend_check_data'] <= 0 and
                data.at[current_index, 'trend_check_data2'] < 0)
            )

            # ヒストグラムのクロスオーバーを判定
            if i - 1 >= 0:
                hist_diff_prev = data.at[index_list[i - 1], 'hist_diff']
            else:
                hist_diff_prev = data.at[index_list[0], 'hist_diff']

            hist_crossover_up1 = data.at[current_index, 'hist_diff'] > 0 and \
                                data.at[current_index, 'di_difference_diff'] > 0
            hist_crossover_up2 = hist_diff_prev < 0 and \
                                data.at[current_index, 'hist_diff'] >= 0

            hist_crossover_down1 = data.at[current_index, 'hist_diff'] < 0 and \
                                data.at[current_index, 'di_difference_diff'] < 0
            hist_crossover_down2 = hist_diff_prev > 0 and \
                                data.at[current_index, 'hist_diff'] <= 0

            # 価格がピボットポイントをクロスしたかを判定
            if i - 1 >= 0:
                close_prev = data.at[index_list[i - 1], 'close']
            else:
                close_prev = data.at[index_list[0], 'close']

            close_crosses_above1 = (
                (close_prev < R1 and current_close > R1) or
                (close_prev < R2 and current_close > R2) or
                (close_prev < R3 and current_close > R3)
            )

            close_crosses_above2 = (
                (close_prev < S1 and current_close > S1) or
                (close_prev < S2 and current_close > S2) or
                (close_prev < S3 and current_close > S3)
            )

            close_crosses_below1 = (
                (close_prev > S1 and current_close < S1) or
                (close_prev > S2 and current_close < S2) or
                (close_prev > S3 and current_close < S3)
            )

            close_crosses_below2 = (
                (close_prev > R1 and current_close < R1) or
                (close_prev > R2 and current_close < R2) or
                (close_prev > R3 and current_close < R3)
            )

            # position = self.init.signal_position

            # シグナルの生成
            if self.init.signal_position == 'sell' and self.init.signal_position1 == 'buy' and \
                current_close != self.init.entry_price:
                    data.at[current_index, 'sell_exit_signals_lc'], data.at[current_index, 'buy_exit_signals_lc'] = 1, 1
                    self.init.signal_position, self.init.signal_position1 = None, None
                    self.init.sell_entry_price, self.init.buy_entry_price = current_close
            
            if self.init.signal_position == 'buy' and self.init.signal_position1 == 'sell' and \
                current_close != self.init.entry_price:
                    data.at[current_index, 'buy_exit_signals_lc'], data.at[current_index, 'sell_exit_signals_lc'] = 1, 1
                    self.init.signal_position, self.init.signal_position1 = None, None
                    self.init.sell_entry_price, self.init.buy_entry_price = current_close, current_close
            
            if self.init.signal_position == 'sell' and self.init.signal_position1 is None and \
                current_close == self.init.entry_price and current_close > current_close_prev:
                    data.at[current_index, 'buy_signals'] = 1
                    self.init.signal_position1 = 'buy'
                    self.init.entry_price = current_close
                    self.init.position_entry_index = len(self.init.interpolated_data)
            
            if self.init.signal_position == 'buy' and self.init.signal_position1 is None and \
                current_close == self.init.entry_price and current_close < current_close_prev:
                    data.at[current_index, 'sell_signals'] = 1
                    self.init.signal_position1 = 'sell'
                    self.init.entry_price = current_close
                    self.init.position_entry_index = len(self.init.interpolated_data)
                    
            if self.init.signal_position is None and self.init.signal_position1 == 'sell' and \
                current_close == self.init.entry_price and current_close > current_close_prev:
                    data.at[current_index, 'buy_signals'] = 1
                    self.init.signal_position = 'buy'
                    self.init.entry_price = current_close
                    self.init.position_entry_index = len(self.init.interpolated_data)
            
            if self.init.signal_position is None and self.init.signal_position1 == 'buy' and \
                current_close == self.init.entry_price and current_close < current_close_prev:
                    data.at[current_index, 'sell_signals'] = 1
                    self.init.signal_position = 'sell'
                    self.init.entry_price = current_close
                    self.init.position_entry_index = len(self.init.interpolated_data)
            
            # if self.init.signal_position == 'sell' and self.init.signal_position1 == 'buy':
            #     if current_close > self.init.entry_price:
            #         data.at[current_index, 'sell_exit_signals_lc'] = 1
            #         self.init.signal_position = None
            #         self.init.buy_entry_price = current_close
            #     if current_close < self.init.entry_price:
            #         data.at[current_index, 'buy_exit_signals_lc'] = 1
            #         self.init.signal_position1 = None
            #         self.init.sell_entry_price = current_close
                    
            # if self.init.signal_position == 'buy' and self.init.signal_position1 == 'sell':
            #     if current_close < self.init.entry_price:
            #         data.at[current_index, 'buy_exit_signals_lc'] = 1
            #         self.init.signal_position = None
            #         self.init.sell_entry_price = current_close
            #     if current_close > self.init.entry_price:
            #         data.at[current_index, 'sell_exit_signals_lc'] = 1
            #         self.init.signal_position1 = None
            #         self.init.buy_entry_price = current_close
                    
            
            if not self.init.swap_signals:
                if data.at[current_index, 'adx_difference_diff'] > 0 or data.at[current_index, 'band_width_diff'] > 0:
                    if (trend_positive1 or trend_positive2) and \
                    (hist_crossover_up1 or hist_crossover_up2 or close_crosses_above1 or close_crosses_above2):
                        if self.init.signal_position == 'sell' and self.init.signal_position1 is None:
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy':  
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                    
                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 =='sell':
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy':  
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                    
                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'sell_exit_signals'] != 1 and data.at[current_index, 'buy_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                            self.init.position_entry_index = len(self.init.interpolated_data)

                    elif (trend_negative1 or trend_negative2) and \
                    (hist_crossover_down1 or hist_crossover_down2 or close_crosses_below1 or close_crosses_below2):
                        if self.init.signal_position == 'buy' and self.init.signal_position1 is None:
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 == 'buy':
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'buy_exit_signals'] != 1 and data.at[current_index, 'sell_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                            self.init.position_entry_index = len(self.init.interpolated_data)

                elif data.at[current_index, 'adx_difference_diff'] < 0 and data.at[current_index, 'band_width_diff'] < 0:
                    if (trend_positive1 or trend_positive2) and \
                    (hist_crossover_up1 or hist_crossover_up2 or close_crosses_below1 or close_crosses_below2):
                        if self.init.signal_position == 'sell' and self.init.signal_position1 is None:
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy': 
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 == 'sell':
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy': 
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'sell_exit_signals'] != 1 and data.at[current_index, 'buy_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                            self.init.position_entry_index = len(self.init.interpolated_data)

                    elif (trend_negative1 or trend_negative2) and \
                            (hist_crossover_down1 or hist_crossover_down2 or close_crosses_above1 or close_crosses_above2):
                        if self.init.signal_position == 'buy' and self.init.signal_position1 is None:
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 == 'buy':
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'buy_exit_signals'] != 1 and data.at[current_index, 'sell_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                            self.init.position_entry_index = len(self.init.interpolated_data)

            else:
                # シグナルの条件を入れ替える
                if data.at[current_index, 'adx_difference_diff'] > 0 or data.at[current_index, 'band_width_diff'] > 0:
                    if (trend_positive1 or trend_positive2) and \
                    (hist_crossover_up1 or hist_crossover_up2 or close_crosses_above1 or close_crosses_above2):
                        if self.init.signal_position == 'buy' and self.init.signal_position1 is None:
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 == 'buy':
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'buy_exit_signals'] != 1 and data.at[current_index, 'sell_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                            self.init.position_entry_index = len(self.init.interpolated_data)

                    elif (trend_negative1 or trend_negative2) and \
                            (hist_crossover_down1 or hist_crossover_down2 or close_crosses_below1 or close_crosses_below2):
                        if self.init.signal_position == 'sell'  and self.init.signal_position1 is None:
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy':
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 == 'sell':
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy':
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                
                                data.loc[current_index, ['sell_signals', 'buy_signals']] = [1, 1]

                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'sell_exit_signals'] != 1 and data.at[current_index, 'buy_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                            self.init.position_entry_index = len(self.init.interpolated_data)

                elif data.at[current_index, 'adx_difference_diff'] < 0 and data.at[current_index, 'band_width_diff'] < 0:
                    if (trend_positive1 or trend_positive2) and \
                    (hist_crossover_up1 or hist_crossover_up2 or close_crosses_below1 or close_crosses_below2):
                        if self.init.signal_position == 'buy' and self.init.signal_position1 is None:
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position1 == 'buy':
                            # Buy Exit Signal Logic with price condition
                            if current_close > self.init.buy_entry_price:
                                data.at[current_index, 'buy_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.buy_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_sell':
                                    data.at[current_index, 'hedge_sell_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.buy_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close < self.init.buy_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'buy_exit_signals'] != 1 and data.at[current_index, 'sell_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                            self.init.position_entry_index = len(self.init.interpolated_data)

                    elif (trend_negative1 or trend_negative2) and \
                        (hist_crossover_down1 or hist_crossover_down2 or close_crosses_above1 or close_crosses_above2):
                        if self.init.signal_position == 'sell' and self.init.signal_position is None:
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position_prev, self.init.signal_position1_prev = self.init.signal_position, self.init.signal_position1
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy':
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score
                                
                        if self.init.signal_position is None and self.init.signal_position == 'sell':
                            # Sell Exit Signal Logic with price condition
                            if current_close < self.init.sell_entry_price:
                                data.at[current_index, 'sell_exit_signals'] = 1
                                self.init.signal_position1 = None
                                # self.init.sell_entry_price = None

                                # イグジットシグナル直後の値を保持
                                self.init.signal_position1_prev, self.init.signal_position_prev = self.init.signal_position1, self.init.signal_position
                                self.init.cumulative_score_prev = self.init.cumulative_score
                                self.init.previous_cumulative_score_prev = self.init.previous_cumulative_score
                                
                                if self.init.signal_position2 == 'hedge_buy':
                                    data.at[current_index, 'hedge_buy_exit_signals'] = 1
                                    self.init.signal_position2 = None
                                    self.init.signal_position2_prev = self.init.signal_position2

                                self.init.entry_price = current_close
                                data.at[current_index, 'sell_signals'], data.at[current_index, 'buy_signals'] = 1, 1
                                self.init.signal_position, self.init.signal_position1 = 'sell', 'buy'
                                self.init.position_entry_index = len(self.init.interpolated_data)

                                # Score calculation
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score += 1
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close == self.init.sell_entry_price:
                                # Score 0, do not swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                            elif current_close > self.init.sell_entry_price:
                                # Score -1, swap signals
                                self.init.previous_cumulative_score = self.init.cumulative_score
                                self.init.cumulative_score -= 1
                                self.init.swap_signals = not self.init.swap_signals
                                data.at[current_index, 'performance'] = self.init.cumulative_score

                        if self.init.signal_position is None and self.init.signal_position1 is None and \
                            data.at[current_index, 'sell_exit_signals'] != 1 and data.at[current_index, 'buy_exit_signals'] != 1:
                            self.init.entry_price = current_close
                            data.at[current_index, 'buy_signals'], data.at[current_index, 'sell_signals'] = 1, 1
                            self.init.signal_position, self.init.signal_position1 = 'buy', 'sell'
                            self.init.position_entry_index = len(self.init.interpolated_data)

        # メソッドの最後で現在の状態を前回の状態として更新
        self.init.prev_special_sell_active = self.init.special_sell_active
        self.init.prev_special_buy_active = self.init.special_buy_active