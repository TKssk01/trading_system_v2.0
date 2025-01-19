# order_executor.py
import urllib.request
import datetime
import requests
import json
import pprint
import logging
import time
import ccxt
import os
import traceback
import urllib.parse
import heapq
# import pprint
from pprint import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque


"""
価格監視
wait_for_price_change(self, fetch_interval=1, price_threshold=0.1)
注文実行
execute_orders(self)
注文取消
cancel_order(self, order_id)
ポジション取得
get_positions(self, params=None)
注文履歴取得
get_orders_history(self, params=None, limit=2)
新規
new_order(self, side, quantity)
返済
exit_order(self, side, quantity)
逆指値返済
reverse_limit_order_exit(self, side, quantity, stop_price)
IOC
ioc_order(self, side, quantity, price)
IOC返済
ioc_exit_order(self, side, quantity, price)
"""


API_BASE_URL = "http://localhost:18080/kabusapi"


def get_token(api_password):
    url = f"{API_BASE_URL}/token"
    headers = {"Content-Type": "application/json"}
    data = {"APIPassword": api_password}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            token = response.json().get("Token")
            return token
        else:
            raise Exception(f"Failed to get token: {response.status_code} {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request exception occurred: {e}")
        raise


class OrderExecutor:
    def __init__(self, init, trading_data, token, order_password):
        self.init = init
        self.trading_data = trading_data
        self.token = token
        self.order_password = order_password
        self.base_price = None 
        self.logger = logging.getLogger(__name__)


    """
    価格監視
    """
    def wait_for_price_change(self, fetch_interval=1, price_threshold=0.1):
        
        while True:
            try:
                current_price = self.fetch_current_price()
                self.init.current_price = current_price  # 現在の価格を更新
                self.logger.info(f"取得した価格: {current_price}")

                if self.init.previous_price is not None:
                    price_change = current_price - self.init.previous_price

                    # 価格変動が閾値を超えた場合
                    if abs(price_change) >= price_threshold:
                        direction = 1 if price_change > 0 else -1
                        self.logger.info(f"価格変動を検知: 前回価格 {self.init.previous_price} -> 現在価格 {current_price} (変動: {price_change})")
                        return current_price, True, direction
                else:
                    self.logger.info("初回価格取得。前回価格を設定します。")

                # 前回価格を現在の価格に更新
                self.init.previous_price = current_price

                time.sleep(fetch_interval)
            except Exception as e:
                self.logger.error(f"価格取得中にエラーが発生: {e}")
                time.sleep(fetch_interval)

    """
    注文実行
    """
    # def execute_orders(self):
    #     quantity=100
    #     fetch_interval = 0.3 
    #     price_threshold = 0.1  # 価格変動の閾値

    #     SIDE = {"BUY": "2", "SELL": "1"}

    #     # 補間データの存在確認
    #     if self.init.interpolated_data is None or self.init.interpolated_data.empty:
    #         print("補間データが存在しません。注文の実行をスキップします。")
    #         return

    #     # 最後の行を取得
    #     last_row = self.init.interpolated_data.iloc[-1]

    #     # シグナルを辞書で管理(辞書で管理ver)
    #     signals = {
    #         "buy": last_row.get('buy_signals', 0),
    #         "buy_exit": last_row.get('buy_exit_signals', 0),
    #         "sell": last_row.get('sell_signals', 0),
    #         "sell_exit": last_row.get('sell_exit_signals', 0),
    #         "emergency_buy_exit": last_row.get('emergency_buy_exit_signals', 0),
    #         "emergency_sell_exit": last_row.get('emergency_sell_exit_signals', 0),
    #         "hedge_buy": last_row.get('hedge_buy_signals', 0),
    #         "hedge_buy_exit": last_row.get('hedge_buy_exit_signals', 0),
    #         "hedge_sell": last_row.get('hedge_sell_signals', 0),
    #         "hedge_sell_exit": last_row.get('hedge_sell_exit_signals', 0),
    #         "special_buy": last_row.get('special_buy_signals', 0),
    #         "special_buy_exit": last_row.get('special_buy_exit_signals', 0),
    #         "special_sell": last_row.get('special_sell_signals', 0),
    #         "special_sell_exit": last_row.get('special_sell_exit_signals', 0),
    #     }
        
    #     # Stage1
    #     if signals.get('buy', 0) == 1 or signals.get('sell', 0) == 1:
            
    #         # ロングとショートの同時エントリーを並行処理で実行
    #         with ThreadPoolExecutor(max_workers=2) as executor:
    #             # 注文をスレッドに割り当て
    #             future_buy = executor.submit(self.new_order, SIDE["BUY"], quantity)
    #             future_sell = executor.submit(self.new_order, SIDE["SELL"], quantity)
    #             # `as_completed` を使用してタスクの完了を待つ
    #             for future in as_completed([future_buy, future_sell]):
    #                 try:
    #                     response = future.result()
    #                     if future == future_buy:
    #                         long_response = response
    #                         self.logger.debug(f"Long Response: {long_response}")
    #                     elif future == future_sell:
    #                         short_response = response
    #                         self.logger.debug(f"Short Response: {short_response}")
    #                 except Exception as e:
    #                     self.logger.error(f"注文処理中にエラーが発生しました: {e}")
    #                     if future == future_buy:
    #                         long_response = None
    #                     elif future == future_sell:
    #                         short_response = None
            
    #         time.sleep(0.2)                
    #         position = self.get_positions(params=None)
                 
                        
    #         # 最新の2件の注文を含むリストからそれぞれ買いと売りの注文を判定して取得
    #         latest_two_orders = position[-2:]  # 最新の2件を取得

    #         buy_order = None
    #         sell_order = None

    #         for order in latest_two_orders:
    #             side = order.get('Side')
    #             if side == '1':
    #                 # 「Side」が '1' の場合は売り注文
    #                 sell_order = order
    #             elif side == '2':
    #                 # 「Side」が '2' の場合は買い注文
    #                 buy_order = order

    #         # 注文が正しく取得できたか確認（必要に応じて）
    #         if buy_order:
    #             print("買い注文:", buy_order)
    #         else:
    #             print("買い注文が見つかりませんでした。")

    #         if sell_order:
    #             print("売り注文:", sell_order)
    #         else:
    #             print("売り注文が見つかりませんでした。")
            
            
            
    #         time.sleep(0.2)
    #         # Priceを抽出する関数
    #         def extract_price_for_position(order):
    #             return order.get("Price")
    #         # 買い注文と売り注文からそれぞれPriceを取得
    #         buy_price = extract_price_for_position(buy_order)
    #         time.sleep(0.2)
    #         sell_price = extract_price_for_position(sell_order)
            
            
    #         # 価格を比較し、必要に応じて逆指値用の価格を入れ替える
    #         if buy_price > sell_price:
    #             # 買いの値段が売りよりも高い場合、逆指値で指定する価格を入れ替える
    #             reverse_buy_price = sell_price  # 売りの値段を買いの逆指値に使用
    #             reverse_sell_price = buy_price  # 買いの値段を売りの逆指値に使用
    #         else:
    #             # 通常の場合はそのまま使用
    #             reverse_buy_price = buy_price
    #             reverse_sell_price = sell_price
            
    #         with ThreadPoolExecutor(max_workers=2) as executor:
    #             # 買い玉に対する逆指値返済注文を実行（逆指値価格として reverse_buy_price を使用）
    #             future_rev_buy = executor.submit(
    #                 self.reverse_limit_order_exit, 
    #                 SIDE["BUY"], 
    #                 quantity, 
    #                 1, 
    #                 reverse_buy_price
    #             )
    #             # 売り玉に対する逆指値注文を実行（逆指値価格として reverse_sell_price を使用）
    #             future_rev_sell = executor.submit(
    #                 self.reverse_limit_order_exit, 
    #                 SIDE["SELL"], 
    #                 quantity, 
    #                 2, 
    #                 reverse_sell_price
    #             )
                
    #             # 各注文のレスポンスを取得
    #             try:
    #                 reverse_buy_response = future_rev_buy.result()
    #                 self.logger.debug(f"Reverse Buy Order Response: {reverse_buy_response}")
    #                 # 逆指値買い注文が成功した場合の処理
    #                 if reverse_buy_response is not None:
    #                     self.logger.info(f"逆指値買い注文が成功しました。新しい逆指値の価格は {buy_price} です。")
    #                     # 標準出力で表示する場合:
    #                     # print(f"逆指値買い注文が成功しました。新しい逆指値の価格は {buy_price} です。")
    #             except Exception as e:
    #                 self.logger.error(f"逆指値買い注文中にエラーが発生しました: {e}")
    #                 reverse_buy_response = None

    #             try:
    #                 reverse_sell_response = future_rev_sell.result()
    #                 self.logger.debug(f"Reverse Sell Order Response: {reverse_sell_response}")
    #                 # 逆指値売り注文が成功した場合の処理
    #                 if reverse_sell_response is not None:
    #                     self.logger.info(f"逆指値売り注文が成功しました。新しい逆指値の価格は {sell_price} です。")
    #                     # 標準出力で表示する場合:
    #                     # print(f"逆指値売り注文が成功しました。新しい逆指値の価格は {sell_price} です。")
    #             except Exception as e:
    #                 self.logger.error(f"逆指値売り注文中にエラーが発生しました: {e}")
    #                 reverse_sell_response = None
    #         time.sleep(0.2)
                    
    #         # ここで注文IDを取得
    #         reverse_buy_order_id = None
    #         reverse_sell_order_id = None
            
    #         # 最新の2件の注文を取得
    #         latest_orders = self.get_orders_history(limit=2)
            
    #         # 注文一覧が取得できていて、2件以上存在することを確認
    #         if latest_orders and len(latest_orders) >= 2:
    #             # 一番新しい注文を売り注文と仮定
    #             reverse_sell_order_id = latest_orders[-1]['ID']
    #             # 2番目に新しい注文を買い注文と仮定
    #             reverse_buy_order_id = latest_orders[-2]['ID']
    #         else:
    #             # 期待する注文が取得できなかった場合の処理
    #             reverse_sell_order_id = None
    #             reverse_buy_order_id = None
    #             self.logger.error("最新の注文が取得できなかったため、キャンセル処理を中止します。")
            
    #         # 逆指値注文が発注された場合、それぞれの注文の約定を監視する
    #         if reverse_buy_order_id or reverse_sell_order_id:
    #             while True:
    #                 # 約定状況を確認
    #                 buy_filled = reverse_buy_order_id and self.is_order_filled(reverse_buy_order_id)
    #                 sell_filled = reverse_sell_order_id and self.is_order_filled(reverse_sell_order_id)
                    
    #                 time.sleep(0.2)

    #                 # 買い注文が約定していたら売り注文をキャンセル
    #                 if buy_filled:
    #                     if reverse_sell_order_id:
    #                         self.logger.info(f"逆指値買い注文({reverse_buy_order_id})が約定しました。逆指値売り注文({reverse_sell_order_id})をキャンセルします。")
    #                         self.cancel_order(reverse_sell_order_id)
    #                     reverse_buy_order_id = None
                        
    #                 time.sleep(0.2)

    #                 # 売り注文が約定していたら買い注文をキャンセル
    #                 if sell_filled:
    #                     if reverse_buy_order_id:
    #                         self.logger.info(f"逆指値売り注文({reverse_sell_order_id})が約定しました。逆指値買い注文({reverse_buy_order_id})をキャンセルします。")
    #                         self.cancel_order(reverse_buy_order_id)
    #                     reverse_sell_order_id = None
                        
    #                 time.sleep(0.2)


    #     # Stage2
    #     # 価格履歴を保持する deque を初期化（最大長3）
    #     if not hasattr(self, "price_history") or self.price_history is None:
    #         self.price_history = deque(maxlen=3)

    #     fetch_interval = 0.2  # 適切な間隔を設定

    #     while True:
    #         try:
    #             # 最新価格取得と履歴更新
    #             current_price = self.fetch_current_price()
    #             self.price_history.append(current_price)
    #             self.logger.info(f"価格履歴: {list(self.price_history)}")

    #             # 最新の3価格が揃ったか確認
    #             if len(self.price_history) == 3:
    #                 price_t2, price_t1, price_t0 = self.price_history

    #                 # ここで売りポジションを保有しているかを確認
    #                 # 例: self.sell_position_active が True なら売りポジションを保有中とする
    #                 sell_position_active = getattr(self, "sell_position_active", False)
    #                 if sell_position_active and price_t2 > price_t1 and price_t0 > price_t1:
    #                     self.logger.info("売り決済条件成立。IOC指値注文を発行します。")
    #                     # 売りポジションの約定価格を利用してIOC注文を発行
    #                     # 例: response = self.place_ioc_order(..., limit_price=self.sell_fill_price)
    #                     # 実際の注文発行コードをここに挿入
    #                     # if response:
    #                     #     self.logger.info("売りポジションのIOC決済注文発行成功。")

    #                 # ここで買いポジションを保有しているかを確認
    #                 # 例: self.buy_position_active が True なら買いポジションを保有中とする
    #                 buy_position_active = getattr(self, "buy_position_active", False)
    #                 if buy_position_active and price_t2 < price_t1 and price_t0 < price_t1:
    #                     self.logger.info("買い決済条件成立。IOC指値注文を発行します。")
    #                     # 買いポジションの約定価格を利用してIOC注文を発行
    #                     # 例: response = self.place_ioc_order(..., limit_price=self.buy_fill_price)
    #                     # 実際の注文発行コードをここに挿入
    #                     # if response:
    #                     #     self.logger.info("買いポジションのIOC決済注文発行成功。")

    #             time.sleep(fetch_interval)

    #         except Exception as e:
    #             self.logger.error(f"フェーズ2でエラー発生: {e}")
    #             time.sleep(fetch_interval)
        
        




    def execute_orders(self):
        quantity = 100
        fetch_interval = 0.3 
        price_threshold = 0.1  # 価格変動の閾値
        SIDE = {"BUY": "2", "SELL": "1"}

        # 補間データの存在確認
        if self.init.interpolated_data is None or self.init.interpolated_data.empty:
            print("補間データが存在しません。注文の実行をスキップします。")
            return

        first_cycle = True  # 最初のサイクルを判定するフラグ

        # メインループ開始
        while True:
            # ======== Stage1 ========
            if first_cycle:
                # 最初のサイクルではシグナルをチェック
                last_row = self.init.interpolated_data.iloc[-1]
                signals = {
                    "buy": last_row.get('buy_signals', 0),
                    "buy_exit": last_row.get('buy_exit_signals', 0),
                    "sell": last_row.get('sell_signals', 0),
                    "sell_exit": last_row.get('sell_exit_signals', 0),
                    "emergency_buy_exit": last_row.get('emergency_buy_exit_signals', 0),
                    "emergency_sell_exit": last_row.get('emergency_sell_exit_signals', 0),
                    "hedge_buy": last_row.get('hedge_buy_signals', 0),
                    "hedge_buy_exit": last_row.get('hedge_buy_exit_signals', 0),
                    "hedge_sell": last_row.get('hedge_sell_signals', 0),
                    "hedge_sell_exit": last_row.get('hedge_sell_exit_signals', 0),
                    "special_buy": last_row.get('special_buy_signals', 0),
                    "special_buy_exit": last_row.get('special_buy_exit_signals', 0),
                    "special_sell": last_row.get('special_sell_signals', 0),
                    "special_sell_exit": last_row.get('special_sell_exit_signals', 0),
                }
                if signals.get('buy', 0) == 1 or signals.get('sell', 0) == 1:
                    # ロングとショートの同時エントリーを並行処理で実行
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        future_buy = executor.submit(self.new_order, SIDE["BUY"], quantity)
                        future_sell = executor.submit(self.new_order, SIDE["SELL"], quantity)
                        for future in as_completed([future_buy, future_sell]):
                            try:
                                response = future.result()
                                if future == future_buy:
                                    long_response = response
                                    self.logger.debug(f"Long Response: {long_response}")
                                elif future == future_sell:
                                    short_response = response
                                    self.logger.debug(f"Short Response: {short_response}")
                            except Exception as e:
                                self.logger.error(f"注文処理中にエラーが発生しました: {e}")
                    # 以下、Stage1の続きの処理を配置…
                else:
                    self.logger.info("最初のサイクルでシグナルがありませんでした。")
                # 最初のサイクル終了後、フラグを更新
                first_cycle = False  
            else:
                # 2回目以降のサイクルではシグナルチェックをスキップ
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_buy = executor.submit(self.new_order, SIDE["BUY"], quantity)
                    future_sell = executor.submit(self.new_order, SIDE["SELL"], quantity)
                    for future in as_completed([future_buy, future_sell]):
                        try:
                            response = future.result()
                            if future == future_buy:
                                long_response = response
                                self.logger.debug(f"Long Response: {long_response}")
                            elif future == future_sell:
                                short_response = response
                                self.logger.debug(f"Short Response: {short_response}")
                        except Exception as e:
                            self.logger.error(f"注文処理中にエラーが発生しました: {e}")
                # 以下、Stage1の続きの処理を配置…

            time.sleep(0.2)                
            position = self.get_positions(params=None)
            
            # 最新の2件の注文を含むリストからそれぞれ買いと売りの注文を判定して取得
            latest_two_orders = position[-2:]
            buy_order = None
            sell_order = None
            for order in latest_two_orders:
                side = order.get('Side')
                if side == '1':
                    sell_order = order
                elif side == '2':
                    buy_order = order

            if buy_order:
                print("買い注文:", buy_order)
            else:
                print("買い注文が見つかりませんでした。")

            if sell_order:
                print("売り注文:", sell_order)
            else:
                print("売り注文が見つかりませんでした。")
            
            time.sleep(0.2)
            def extract_price_for_position(order):
                return order.get("Price")
            buy_price = extract_price_for_position(buy_order)
            time.sleep(0.2)
            sell_price = extract_price_for_position(sell_order)

            if buy_price > sell_price:
                reverse_buy_price = sell_price
                reverse_sell_price = buy_price
            else:
                reverse_buy_price = buy_price
                reverse_sell_price = sell_price

            with ThreadPoolExecutor(max_workers=2) as executor:
                future_rev_buy = executor.submit(
                    self.reverse_limit_order_exit, 
                    SIDE["BUY"], 
                    quantity, 
                    1, 
                    reverse_buy_price
                )
                future_rev_sell = executor.submit(
                    self.reverse_limit_order_exit, 
                    SIDE["SELL"], 
                    quantity, 
                    2, 
                    reverse_sell_price
                )
                try:
                    reverse_buy_response = future_rev_buy.result()
                    self.logger.debug(f"Reverse Buy Order Response: {reverse_buy_response}")
                    if reverse_buy_response is not None:
                        self.logger.info(f"逆指値買い注文が成功しました。新しい逆指値の価格は {buy_price} です。")
                except Exception as e:
                    self.logger.error(f"逆指値買い注文中にエラーが発生しました: {e}")
                    reverse_buy_response = None

                try:
                    reverse_sell_response = future_rev_sell.result()
                    self.logger.debug(f"Reverse Sell Order Response: {reverse_sell_response}")
                    if reverse_sell_response is not None:
                        self.logger.info(f"逆指値売り注文が成功しました。新しい逆指値の価格は {sell_price} です。")
                except Exception as e:
                    self.logger.error(f"逆指値売り注文中にエラーが発生しました: {e}")
                    reverse_sell_response = None

            time.sleep(0.2)
            reverse_buy_order_id = None
            reverse_sell_order_id = None
            latest_orders = self.get_orders_history(limit=2)
            if latest_orders and len(latest_orders) >= 2:
                reverse_sell_order_id = latest_orders[-1]['ID']
                reverse_buy_order_id = latest_orders[-2]['ID']
            else:
                reverse_sell_order_id = None
                reverse_buy_order_id = None
                self.logger.error("最新の注文が取得できなかったため、キャンセル処理を中止します。")

            if reverse_buy_order_id or reverse_sell_order_id:
                while True:
                    buy_filled = reverse_buy_order_id and self.is_order_filled(reverse_buy_order_id)
                    sell_filled = reverse_sell_order_id and self.is_order_filled(reverse_sell_order_id)
                    
                    time.sleep(0.2)
                    if buy_filled:
                        if reverse_sell_order_id:
                            self.logger.info(f"逆指値買い注文({reverse_buy_order_id})が約定しました。逆指値売り注文({reverse_sell_order_id})をキャンセルします。")
                            self.cancel_order(reverse_sell_order_id)
                        reverse_buy_order_id = None
                        
                    time.sleep(0.2)
                    if sell_filled:
                        if reverse_buy_order_id:
                            self.logger.info(f"逆指値売り注文({reverse_sell_order_id})が約定しました。逆指値買い注文({reverse_buy_order_id})をキャンセルします。")
                            self.cancel_order(reverse_buy_order_id)
                        reverse_sell_order_id = None
                        
                    time.sleep(0.2)

            # ======== Stage2 ========
            # Stage2の処理部分（ループ内で価格監視と決済条件判定を行う）
            if not hasattr(self, "price_history") or self.price_history is None:
                self.price_history = deque(maxlen=3)

            fetch_interval = 0.2

            while True:
                try:
                    current_price = self.fetch_current_price()
                    self.price_history.append(current_price)
                    self.logger.info(f"価格履歴: {list(self.price_history)}")

                    if len(self.price_history) == 3:
                        price_t2, price_t1, price_t0 = self.price_history
                        # ここに決済条件判定とIOC注文発行のロジックを配置
                        # 条件に該当したらbreakしてStage2を終了
                        # 例: if favorable_condition: break
                        pass

                    time.sleep(fetch_interval)

                except Exception as e:
                    self.logger.error(f"フェーズ2でエラー発生: {e}")
                    time.sleep(fetch_interval)

                # 有利な決済条件でbreakするロジックを挿入

            # Stage2終了後、無限ループの先頭に戻り、再びStage1が実行される
 
        
        
        
        
    
    
    """
    約定判定
    """
    def is_order_filled(self, order_id):
        # 注文IDで履歴を取得
        params = {'order_id': order_id}
        history = self.get_orders_history(limit=1, params=params)

        if not history:
            self.logger.error(f"注文ID {order_id} の履歴が取得できませんでした。")
            return False

        # 履歴がリスト形式の場合、最初の注文情報を取り出す
        order_info = history[-1] if isinstance(history, list) else history

        # 注文情報の全内容を確認するために全フィールドをループで出力
        self.logger.debug(f"Order {order_id} の詳細:")
        for key, value in order_info.items():
            self.logger.debug(f"  {key}: {value}")
            # 必要に応じて print() を使うことも可能
            # print(f"{key}: {value}")

        # デバッグ：取得した注文情報のStateを表示
        state = order_info.get('State')
        self.logger.debug(f"Order {order_id}: State={state}")

        # Stateが1ならまだ予約中と判定
        return state != 1



    """
    注文取消
    """
    def cancel_order(self, order_id):
        
        obj = {
            'OrderID': order_id,
            'Password': self.order_password 
        }
        json_data = json.dumps(obj).encode('utf8')
        
        url = 'http://localhost:18080/kabusapi/cancelorder'
        req = urllib.request.Request(url, json_data, method='PUT')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)  
        
        try:
            with urllib.request.urlopen(req) as res:
                # print(res.status, res.reason)
                # for header in res.getheaders():
                #     print(header)
                # print()
                content = json.loads(res.read())
                # pprint(content)
        except urllib.error.HTTPError as e:
            print(e)
            content = json.loads(e.read())
            pprint(content)
        except Exception as e:
            print(e)

    """
    ポジション取得
    """
    def get_positions(self, params=None):        
        if params is None:
            params = {
                'product': 2,       # 0:すべて、1:現物、2:信用、3:先物、4:OP
                'symbol': '9432',   # 取得したいシンボル
                'addinfo': 'false'  # 追加情報の出力有無
            }

        url = f"{API_BASE_URL}/positions"
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(full_url, method='GET')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.token)

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"ポジション取得に成功しました: {res.status} {res.reason}")
                content = json.loads(res.read())

                # contentがリストであることを確認
                if not isinstance(content, list):
                    self.logger.error(f"期待していたリストではなく、{type(content)}が返されました。内容: {content}")
                    return None
                if not content:
                    self.logger.warning("ポジションデータが空です。")
                    return None
                return content
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラーが発生しました: {e}")
            try:
                error_content = json.loads(e.read())
                pprint(error_content)
            except Exception:
                self.logger.error("エラー内容の解析に失敗しました。")
            return None
        except Exception as e:
            self.logger.error(f"ポジション取得中に例外が発生しました: {e}")
            return None

    """
    注文履歴取得
    """
    def get_orders_history(self, limit, params=None):
        
        if params is None:
            params = {'product': 2}  # デフォルトでは信用を取得

        url = f"{API_BASE_URL}/orders"
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(full_url, method='GET')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.token)

        try:
            with urllib.request.urlopen(req) as res:
                # print(res.status, res.reason)
                # for header in res.getheaders():
                #     print(header)
                # print()

                # レスポンスを読み込み、JSONにパース
                content = json.loads(res.read())
                # 取得した注文履歴を整形して表示（デバッグ用）
                # pprint(content)

                # 正常に取得できた場合、注文履歴を返す
                return content

        except urllib.error.HTTPError as e:
            print("HTTPエラー:", e)
            try:
                # エラー時のレスポンスをパースして表示
                error_content = json.loads(e.read())
                pprint.pprint(error_content)
            except Exception:
                print("[ERROR] エラーレスポンスの解析に失敗しました。")
            return None

        except Exception as e:
            print("例外発生:", e)
            return None

# ================================
# API パラメータ定義
# ================================

# 【ヘッダー パラメータ】
# X-API-KEY (必須, string): トークン発行メソッドで取得した文字列

# 【リクエストボディ スキーマ: application/json】
# Password (必須, string): 注文パスワード
# Symbol (必須, string): 銘柄コード
# Exchange (必須, integer <int32>): 市場コード
#   定義値:
#     1: 東証
#     3: 名証
#     5: 福証
#     6: 札証
# SecurityType (必須, integer <int32>): 商品種別
#   定義値:
#     1: 株式
# Side (必須, string): 売買区分
#   定義値:
#     1: 売
#     2: 買
# CashMargin (必須, integer <int32>): 信用区分
#   定義値:
#     1: 現物
#     2: 新規
#     3: 返済
# MarginTradeType (integer <int32>): 信用取引区分
#   ※現物取引の場合は指定不要。
#   ※信用取引の場合、必須。
#   定義値:
#     1: 制度信用
#     2: 一般信用（長期）
#     3: 一般信用（デイトレ）
# MarginPremiumUnit (number <double>): 1株あたりのプレミアム料(円)
#   ※プレミアム料の刻値は、プレミアム料取得APIのレスポンスにある"TickMarginPremium"にて確認。
#   ※入札受付中(19:30～20:30)プレミアム料入札可能銘柄の場合、「MarginPremiumUnit」は必須。
#   ※それ以外の場合、「MarginPremiumUnit」の記載は無視。
#   ※入札受付中以外の時間帯では、「MarginPremiumUnit」の記載は無視。
# DelivType (必須, integer <int32>): 受渡区分
#   ※現物買は指定必須。
#   ※現物売は「0(指定なし)」を設定。
#   ※信用新規は「0(指定なし)」を設定。
#   ※信用返済は指定必須。
#   ※auマネーコネクトが有効の場合にのみ、「3」を設定可能。
#   定義値:
#     0: 指定なし
#     2: お預り金
#     3: auマネーコネクト
# FundType (string): 資産区分（預り区分）
#   ※現物買は指定必須。
#   ※現物売は「  」（半角スペース2つ）を指定必須。
#   ※信用新規と信用返済は「11」を指定するか、指定なしでも可。指定しない場合は「11」が自動的にセットされます。
#   定義値:
#     (半角スペース2つ): 現物売の場合
#     02: 保護
#     AA: 信用代用
#     11: 信用取引
# AccountType (必須, integer <int32>): 口座種別
#   定義値:
#     2: 一般
#     4: 特定
#     12: 法人
# Qty (必須, integer <int32>): 注文数量
#   ※信用一括返済の場合、返済したい合計数量を入力。
# ClosePositionOrder (integer <int32>): 決済順序
#   ※信用返済の場合、必須。
#   ※ClosePositionOrderとClosePositionsはどちらか一方のみ指定可能。
#   ※ClosePositionOrderとClosePositionsを両方指定した場合、エラー。
#   定義値:
#     0: 日付（古い順）、損益（高い順）
#     1: 日付（古い順）、損益（低い順）
#     2: 日付（新しい順）、損益（高い順）
#     3: 日付（新しい順）、損益（低い順）
#     4: 損益（高い順）、日付（古い順）
#     5: 損益（高い順）、日付（新しい順）
#     6: 損益（低い順）、日付（古い順）
#     7: 損益（低い順）、日付（新しい順）
# ClosePositions (Array of objects): 返済建玉指定
#   ※信用返済の場合、必須。
#   ※ClosePositionOrderとClosePositionsはどちらか一方のみ指定可能。
#   ※ClosePositionOrderとClosePositionsを両方指定した場合、エラー。
#   ※信用一括返済の場合、各建玉IDと返済したい数量を入力。
#   ※建玉IDは「E」から始まる番号です。
# FrontOrderType (必須, integer <int32>): 執行条件
#   定義値:
#     10: 成行 (Price: 0)
#     13: 寄成（前場） (Price: 0)
#     14: 寄成（後場） (Price: 0)
#     15: 引成（前場） (Price: 0)
#     16: 引成（後場） (Price: 0)
#     17: IOC成行 (Price: 0)
#     20: 指値 (発注金額を指定)
#     21: 寄指（前場） (発注金額を指定)
#     22: 寄指（後場） (発注金額を指定)
#     23: 引指（前場） (発注金額を指定)
#     24: 引指（後場） (発注金額を指定)
#     25: 不成（前場） (発注金額を指定)
#     26: 不成（後場） (発注金額を指定)
#     27: IOC指値 (発注金額を指定)
#     30: 逆指値 (Priceは指定なし、AfterHitPriceで指定)
#   ※AfterHitPriceで指定ください
# Price (必須, number <double>): 注文価格
#   ※FrontOrderTypeで成行を指定した場合、0を指定。
#   ※FrontOrderTypeに応じた価格指定が必要。
# ExpireDay (必須, integer <int32>): 注文有効期限
#   yyyyMMdd形式。
#   0: 本日 (引けまでの間は当日、引け後は翌取引所営業日、休前日は休日明けの取引所営業日)
#   ※ 日替わりはkabuステーションが日付変更通知を受信したタイミングです。
# ReverseLimitOrder (object): 逆指値条件
#   ※FrontOrderTypeで逆指値を指定した場合のみ必須。


    """
    新規
    """
    def new_order(self, side, quantity):
        
        start_time = datetime.datetime.now()
        self.logger.debug(f"{side} order started at {start_time.strftime('%H:%M:%S.%f')}")
        
        obj = {
            'Password': self.order_password,
            'Symbol': self.init.symbol,
            'Exchange': 1,
            'SecurityType': 1,                      # 証券種別（例: 1は株式）
            'Side': side,
            'CashMargin': 2,                        # 信用区分（2：信用取引）
            'MarginTradeType': 3,                   
            'DelivType': 0,
            'AccountType': 4,
            'Qty': quantity, 
            'FrontOrderType': 10,                   # 執行条件コード（10：成行、27:IOC指値、30：逆指値）
            'Price': 0, 
            'ExpireDay': 0                          # 注文有効期限（日数、0は当日）
        }
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json') 
        req.add_header('X-API-KEY', self.init.token)    

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"新規注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except Exception as e:
            self.logger.error(f"新規注文送信中にエラーが発生しました: {e}")
            content = None
            
        end_time = datetime.datetime.now()
        self.logger.debug(f"{side} order finished at {end_time.strftime('%H:%M:%S.%f')}")
            
        return content
        

    """
    返済
    """    
    def exit_order(self, side, quantity):
        obj = {
            'Password': self.order_password,
            'Symbol': self.init.symbol,
            'Exchange': 1,  
            'SecurityType': 1,   
            'Side': side,
            'CashMargin': 3,
            'MarginTradeType': 3,                       
            'DelivType': 2, 
            'AccountType': 4,
            'Qty': quantity,
            'ClosePositionOrder': 1,
            'FrontOrderType': 10,
            'Price': 0,                   
            'ExpireDay': 0 
        }
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json') 
        req.add_header('X-API-KEY', self.init.token)       

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"返済注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except Exception as e:
            self.logger.error(f"返済注文送信中にエラーが発生しました: {e}")
            return None

    """
    逆指値返済
    """
    def reverse_limit_order_exit(self, side, quantity, underover, limit_price):
        obj = {
            'Password': self.order_password,
            'Symbol': self.init.symbol,
            'Exchange': 1,
            'SecurityType': 1,      
            'Side': side,           
            'CashMargin': 3,     
            'MarginTradeType': 3,                   
            'DelivType': 0,                 
            'AccountType': 4,                   
            'Qty': quantity,         
            'FrontOrderType': 30,
            'Price': 0,                      
            'ExpireDay': 0,                
            'ReverseLimitOrder': {
                'TriggerSec': 1,         # 1.発注銘柄 2.NK225指数 3.TOPIX指数
                'TriggerPrice': limit_price,
                'UnderOver': underover,  # 1.以下 2.以上
                'AfterHitOrderType': 2,  # 1.成行 2.指値 3.不成
                'AfterHitPrice': limit_price
            }
        }
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json') 
        req.add_header('X-API-KEY', self.init.token)    

        try:
            with urllib.request.urlopen(req) as res:
                # self.logger.info(f"逆指値注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except urllib.error.HTTPError as e:
            error_content = e.read().decode('utf-8')
            self.logger.error(f"HTTPError: {e.code} {e.reason}")
            self.logger.error(f"レスポンス内容: {error_content}")
            return None
        except Exception as e:
            self.logger.error(f"逆指値注文送信中にエラーが発生しました: {e}")
            return None

    """
    IOC注文
    """
    def ioc_order(self, side, quantity, price):
        obj = {
            'Password': self.order_password,
            'Symbol': self.init.symbol,
            'Exchange': 1,
            'SecurityType': 1,
            'Side': side,
            'CashMargin': 2,               
            'MarginTradeType': 3,
            'DelivType': 0,
            'AccountType': 4,
            'Qty': quantity,
            'FrontOrderType': 27,  
            'Price': price,  
            'ExpireDay': 0  
        }
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"IOC注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except Exception as e:
            self.logger.error(f"IOC注文送信中にエラーが発生しました: {e}")
            return None

    """
    IOC返済
    """
    def exit_ioc_order(self, side, quantity, price):
        obj = {
            'Password': self.order_password,
            'Symbol': self.init.symbol,
            'Exchange': 1,
            'SecurityType': 1,
            'Side': side,
            'CashMargin': 3, 
            'MarginTradeType': 3,  
            'DelivType': 2, 
            'AccountType': 4,
            'Qty': quantity,
            'ClosePositionOrder': 0,  # 日付（古い順）、損益（高い順）で決済
            'FrontOrderType': 27,  # IOC指値（返済時のみ）
            'Price': price,
            'ExpireDay': 0 
        }
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"IOC返済注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except Exception as e:
            self.logger.error(f"IOC返済注文送信中にエラーが発生しました: {e}")
            return None