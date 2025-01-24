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
                current_price = self.trading_data.fetch_current_price()
                # 現在の価格を更新
                self.init.current_price = current_price 
                # # self.logger.info(f"取得した価格: {current_price}")

                
                price_change = current_price - self.init.previous_price

                # 価格変動が閾値を超えた場合
                if abs(price_change) >= price_threshold:
                    direction = 1 if price_change > 0 else -1
                    # self.logger.info(f"価格変動を検知: 前回価格 {self.init.previous_price} -> 現在価格 {current_price} (変動: {price_change})")
                    return current_price, True, direction
                
                # 前回価格を現在の価格に更新
                self.init.previous_price = current_price

                time.sleep(fetch_interval)
            except Exception as e:
                self.logger.error(f"価格取得中にエラーが発生: {e}")
                time.sleep(fetch_interval)

    """
    注文実行
    """
    def execute_orders(self):
        buy_price = 0
        sell_price = 0
        quantity = 100
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
                    self.new_order(SIDE["BUY"], quantity)
                    self.new_order(SIDE["SELL"], quantity)
                    # ロングとショートの同時エントリーを並行処理で実行
                    # with ThreadPoolExecutor(max_workers=2) as executor:
                    #     future_buy = executor.submit(self.new_order, SIDE["BUY"], quantity)
                    #     future_sell = executor.submit(self.new_order, SIDE["SELL"], quantity)
                    #     for future in as_completed([future_buy, future_sell]):
                    #         try:
                    #             response = future.result()
                    #             if future == future_buy:
                    #                 long_response = response
                    #                 self.logger.debug(f"Long Response: {long_response}")
                    #             elif future == future_sell:
                    #                 short_response = response
                    #                 self.logger.debug(f"Short Response: {short_response}")
                    #         except Exception as e:
                    #             self.logger.error(f"注文処理中にエラーが発生しました: {e}")
                else:
                    return  # シグナルがなければ関数を終了
                # 最初のサイクル終了後、フラグを更新
                first_cycle = False  
            else:
                # 2回目以降のサイクルではシグナルチェックをスキップ
                self.new_order(SIDE["BUY"], quantity)
                time.sleep(0.2)
                self.new_order(SIDE["SELL"], quantity)
                # with ThreadPoolExecutor(max_workers=2) as executor:
                #     future_buy = executor.submit(self.new_order, SIDE["BUY"], quantity)
                #     future_sell = executor.submit(self.new_order, SIDE["SELL"], quantity)
                #     for future in as_completed([future_buy, future_sell]):
                #         try:
                #             response = future.result()
                #             if future == future_buy:
                #                 long_response = response
                #                 self.logger.debug(f"Long Response: {long_response}")
                #             elif future == future_sell:
                #                 short_response = response
                #                 self.logger.debug(f"Short Response: {short_response}")
                #         except Exception as e:
                #             self.logger.error(f"注文処理中にエラーが発生しました: {e}")

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
                    
            # print(latest_two_orders)
            
            
            sell_execution_id = None
            buy_execution_id = None
            
            time.sleep(0.15) 
            for order in latest_two_orders:
                if order.get('Side') == '1':  # Side が '1' の場合（売り注文）
                    sell_execution_id = order.get('ExecutionID')
                elif order.get('Side') == '2':  # Side が '2' の場合（買い注文）
                    buy_execution_id = order.get('ExecutionID')

            # 確認のために出力
            print("買いの建玉ID:", buy_execution_id)
            print("売りの建玉ID:", sell_execution_id)
            
            time.sleep(0.2)
            def extract_price_for_position(order):
                if order is None:
                    return None
                return order.get("Price")
            
            buy_price = extract_price_for_position(buy_order)
            time.sleep(0.2)
            sell_price = extract_price_for_position(sell_order)
            
            print("買い価格",buy_price)
            print("売り価格",sell_price)
            
            current_market_price = self.trading_data.fetch_current_price()
            print(f"新規発行時の市場価格: {current_market_price}")

           
            if buy_price > sell_price:
                # 買い価格が売り価格より高い場合
                # 売り決済は市場価格より低く、買い決済は市場価格より高く設定
                reverse_buy_exit_sell_order_price = current_market_price - 0.1
                reverse_sell_exit_buy_order_price = current_market_price + 0.1
                print("買のほうが売よりも価格が高い")
            else:
                # 売り価格が買い価格より高い場合
                # 同様に市場価格からずらして設定
                reverse_buy_exit_sell_order_price = min(buy_price, current_market_price - 0.1)
                reverse_sell_exit_buy_order_price = max(sell_price, current_market_price + 0.1)
                print("売のほうが買よりも価格が高い")
                
            # 価格を小数点第一位で丸める処理を追加
            reverse_buy_exit_sell_order_price = round(reverse_buy_exit_sell_order_price, 1)
            reverse_sell_exit_buy_order_price = round(reverse_sell_exit_buy_order_price, 1)

            # print("逆指値の買い決済価格", reverse_buy_exit_sell_order_price)
            # print("逆指値の売り決済価格", reverse_sell_exit_buy_order_price)
            
            time.sleep(0.2)
            
            # 買いポジションの決済（売り注文）の場合
            try:
                retry_count = 0
                while retry_count < 10:
                    try:
                        reverse_buy_exit_response = self.reverse_limit_order_exit(
                            SIDE["SELL"],  #1 売り  2買い 
                            buy_execution_id,
                            quantity, 
                            1,               # underover の値 (#1 以下 #2 以上
                            reverse_buy_exit_sell_order_price
                        )
                        
                        # レスポンスをチェック
                        if reverse_buy_exit_response is not None:
                            # print("逆指値買いの決済注文が成功しました")
                            break  # 成功した場合はループを抜ける
                        else:
                            retry_count += 1
                            if retry_count == 10:
                                print("最大再試行回数に達しました。処理を中止します。")
                                raise Exception("決済注文が失敗しました")
                            print(f"売り決済注文を0.3円下げて再試行します（試行回数: {retry_count}/{10})")
                            reverse_buy_exit_sell_order_price = round(reverse_buy_exit_sell_order_price - 0.3, 1)  # 売り注文の場合は価格を下げて小数点第1位に丸める
                            continue
                            
                    except urllib.error.HTTPError as e:
                        error_content = json.loads(e.read())
                        retry_count += 1
                        
                        if error_content.get('Code') == 100217:  # 即時約定エラーの場合
                            print(f"売り決済注文を0.3円下げて再試行します（試行回数: {retry_count}/{10})")
                            reverse_buy_exit_sell_order_price = round(reverse_buy_exit_sell_order_price - 0.3, 1)  # 売り注文の場合は価格を下げて小数点第1位に丸める
                            if retry_count == 3:
                                print("最大再試行回数に達しました。処理を中止します。")
                                raise
                            continue
                        else:
                            print(f"予期せぬエラーが発生しました: {error_content}")
                            raise
            except Exception as e:
                print(f"エラーが発生しました: {e}")
                raise
                                        
            time.sleep(0.2)    

            # 売りポジションの決済（買い注文）の場合
            try:
                retry_count = 0
                while retry_count < 10:
                    try:
                        reverse_sell_exit_response = self.reverse_limit_order_exit(
                            SIDE["BUY"],  #1 売り  2買い 
                            sell_execution_id,
                            quantity, 
                            2,               # underover の値 (#1 以下 #2 以上
                            reverse_sell_exit_buy_order_price
                        )
                        
                        # レスポンスをチェック
                        if reverse_sell_exit_response is not None:
                            # print("逆指値売りの決済注文が成功しました")
                            break  # 成功した場合はループを抜ける
                        else:
                            retry_count += 1
                            if retry_count == 10:
                                print("最大再試行回数に達しました。処理を中止します。")
                                raise Exception("決済注文が失敗しました")
                            print(f"買い決済注文を0.3円上げて再試行します（試行回数: {retry_count}/{10})")
                            reverse_sell_exit_buy_order_price = round(reverse_sell_exit_buy_order_price + 0.3, 1)  # 買い注文の場合は価格を上げて小数点第1位に丸める
                            continue
                    except urllib.error.HTTPError as e:
                        error_content = json.loads(e.read())
                        retry_count += 1
                        
                        if error_content.get('Code') == 100217:  # 即時約定エラーの場合
                            print(f"買い決済注文を0.3円上げて再試行します（試行回数: {retry_count}/{10})")
                            reverse_sell_exit_buy_order_price = round(reverse_sell_exit_buy_order_price + 0.3, 1)  # 買い注文の場合は価格を上げて小数点第1位に丸める
                            if retry_count == 3:
                                print("最大再試行回数に達しました。処理を中止します。")
                                raise
                            continue
                        else:
                            print(f"予期せぬエラーが発生しました: {error_content}")
                            raise
            except Exception as e:
                print(f"エラーが発生しました: {e}")
                raise
            
            time.sleep(0.2)
            # time.sleep(1000)
            
            reverse_buy_order_id = None
            reverse_sell_order_id = None
            latest_orders = self.get_orders_history(limit=2)
                        
            # 最新の2つの注文のIDを取得
            for order in latest_orders[-2:]:
                if order.get('Side') == '1':  # 売り注文
                    reverse_sell_order_id = order.get('ID')
                elif order.get('Side') == '2':  # 買い注文
                    reverse_buy_order_id = order.get('ID')
                
                
                
            if reverse_buy_order_id or reverse_sell_order_id:
                # ループ開始前の固定情報表示
                print(f"\n売り注文の逆指値返済注文ID(買い注文): {reverse_buy_order_id}")
                print(f"売り注文の逆指値返済注文価格(買い注文): {reverse_sell_exit_buy_order_price}")
                print(f"買い注文の逆指値返済注文ID(売り注文): {reverse_sell_order_id}")
                print(f"買い注文の逆指値返済注文価格(売り注文): {reverse_buy_exit_sell_order_price}")
                print("\n====== 逆指値注文の完了待機 ======")
            
                while True:
                    time.sleep(0.15)
                    # 注文履歴を取得
                    orders_history = self.get_orders_history(limit=2)
                    
                    # 約定状態の確認
                    buy_filled = False
                    sell_filled = False
                    
                    for order in orders_history:
                        order_id = order.get('ID')
                        state = order.get('State')
                        
                        # State != 1 の場合、約定済みと判断
                        if order_id == reverse_buy_order_id and state != 1:
                            buy_filled = True
                        elif order_id == reverse_sell_order_id and state != 1:
                            sell_filled = True
                    
                    # 買いポジションの逆指値注文が約定した場合
                    if buy_filled:
                        # print(f"\n買い注文 {reverse_buy_order_id} が約定")
                        print(f"買い注文が約定")
                        if reverse_sell_order_id:
                            # print(f"売り注文 {reverse_sell_order_id} をキャンセル実行")
                            print(f"売り注文をキャンセル実行")
                            cancel_result = self.cancel_order(reverse_sell_order_id)
                        reverse_buy_order_id = None
                        reverse_sell_order_id = None
                        break
                    
                    # 売りポジションの逆指値注文が約定した場合
                    if sell_filled:
                        # print(f"\n売り注文 {reverse_sell_order_id} が約定")
                        print(f"売り注文が約定")
                        if reverse_buy_order_id:
                            # print(f"買い注文 {reverse_buy_order_id} をキャンセル実行")
                            print(f"買い注文をキャンセル実行")
                            cancel_result = self.cancel_order(reverse_buy_order_id)
                        reverse_sell_order_id = None
                        reverse_buy_order_id = None
                        break
                    
                    time.sleep(0.2)
                
                # 監視終了時の表示
                print("====== 逆指値注文の監視終了 ======")
                    
            
            time.sleep(0.1)
            # ======== Stage2 ========
            # Stage2の処理部分（ループ内で価格監視と決済条件判定を行う）
            positions = self.get_positions()
            # print("取得したポジション:", positions)
            
            # 最後のポジション（最新のポジション）を取得
            active_positions = [p for p in positions if p.get('LeavesQty', 0) > 0]
            if not active_positions:
                print("アクティブなポジションが見つかりません")
                return
                
            position = active_positions[-1]  # 最後のアクティブなポジションを使用
            side = position.get('Side')
            # quantity = position.get('LeavesQty')
            execution_id = position.get('ExecutionID')
            position_price = float(position.get('Price', 0)) 
            
            print("\n監視対象ポジション:")
            print(f"タイプ: {'売り' if side == '1' else '買い'} (Side: {side})")
            print(f"ExecutionID: {execution_id}") 
            # print(f"ポジション約定価格: {position_price}")
            # 売りポジションの場合はsell_price、買いポジションの場合はbuy_priceを表示
            if side == '1':  # 売りポジション
                print(f"決済用IOC指値価格(sell_price): {position_price}")
            else:  # 買いポジション
                print(f"決済用IOC指値価格(buy_price): {position_price}")
            # print(f"数量: {quantity}")

            if not hasattr(self, "price_history") or self.price_history is None:
                self.price_history = deque(maxlen=3)

            while True:
                try:
                    # 現在の価格を取得
                    current_price = self.trading_data.fetch_current_price()
                    
                    # 価格が前回と異なる場合のみ処理を実行
                    if not self.price_history or current_price != self.price_history[-1]:
                        self.price_history.append(current_price)

                        # 3点の価格データが揃った場合に判定
                        if len(self.price_history) == 3:
                            price_t2, price_t1, price_t0 = self.price_history
                            
                            # 売りポジションの決済条件判定
                            if side == '1':  # 売りポジション
                                if price_t2 > price_t1 and price_t0 > price_t1:
                                    print("\n売りポジションの決済条件を検出")
                                    print(f"価格推移: {price_t2} > {price_t1} < {price_t0}")
                                    # ioc_price = reverse_sell_exit_buy_order_price
                                    ioc_price = position_price
                                    response = self.exit_ioc_order(
                                        side="2",  # 買い注文で決済
                                        quantity=quantity,
                                        HoldID=execution_id,
                                        price=ioc_price
                                    )
                                    # responseの結果に関わらずループを抜ける
                                    if response is not None:
                                        print("IOC指値決済完了 - 次の新規注文を入れます")
                                    else:
                                        print("IOC指値決済は失敗しましたが、次の新規注文に進みます")
                                    time.sleep(0.2)
                                    break  # responseの結果に関わらずbreakする
                            
                            # 買いポジションの決済条件判定
                            elif side == '2':  # 買いポジション
                                if price_t2 < price_t1 and price_t0 < price_t1:
                                    print("\n買いポジションの決済条件を検出")
                                    print(f"価格推移: {price_t2} < {price_t1} > {price_t0}")
                                    # ioc_price = reverse_buy_exit_sell_order_price
                                    ioc_price = position_price
                                    response = self.exit_ioc_order(
                                        side="1",  # 売り注文で決済
                                        quantity=quantity,
                                        HoldID=execution_id,
                                        price=ioc_price
                                    )
                                    if response is not None:
                                        print("IOC指値決済完了 - 次の新規注文を入れます")
                                    else:
                                        print("IOC指値決済は失敗しましたが、次の新規注文に進みます")
                                    time.sleep(0.2)
                                    break 

                    time.sleep(0.2)  # 短い間隔で価格チェック

                except Exception as e:
                    self.logger.error(f"価格監視中にエラーが発生: {e}")
                    time.sleep(0.2)
 
        
        
        
        
    
    
    """
    約定判定
    """
    def is_order_filled(self, order_id):
        # 注文IDで履歴を取得
        params = {'order_id': order_id}
        history = self.get_orders_history(limit=1, params=params)

        if not history:
            print(f"注文ID {order_id} の履歴が取得できませんでした。")
            return False

        # 履歴がリスト形式の場合、最初の注文情報を取り出す
        order_info = history[-1] if isinstance(history, list) else history

        # 注文情報の全内容を確認するために全フィールドをループで出力
        print(f"\nOrder {order_id} の詳細:")
        for key, value in order_info.items():
            print(f"  {key}: {value}")

        # 取得した注文情報のStateを表示
        state = order_info.get('State')
        print(f"Order {order_id}: State={state}")

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
                'symbol': self.init.symbol,   
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
                content = json.loads(res.read())

                # contentがリストであることを確認
                if not isinstance(content, list):
                    self.logger.error(f"期待していたリストではなく、{type(content)}が返されました。内容: {content}")
                    return []  # Noneではなく空リストを返す
                if not content:
                    self.logger.warning("ポジションデータが空です。")
                    return [] 
                return content
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラーが発生しました: {e}")
            try:
                error_content = json.loads(e.read())
                pprint(error_content)
            except Exception:
                self.logger.error("エラー内容の解析に失敗しました。")
            return []  # エラー発生時も空リストを返す
        except Exception as e:
            self.logger.error(f"ポジション取得中に例外が発生しました: {e}")
            return []  # 例外発生時も空リストを返す

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
                # レスポンスを読み込み、JSONにパース
                content = json.loads(res.read())
                
                # 注文履歴の詳細を表示
                # print("\n=== 注文履歴の詳細 ===")
                # for order in content:
                #     print("\n注文情報:")
                #     print(f"注文ID: {order.get('ID')}")
                #     print(f"状態: {order.get('State')}")
                #     print(f"サイド: {'売り' if order.get('Side') == '1' else '買い'}")
                #     print(f"価格: {order.get('Price')}")
                #     print(f"数量: {order.get('Qty')}")
                #     print(f"注文タイプ: {order.get('FrontOrderType')}")
                #     print(f"執行条件: {order.get('ExecutionCondition')}")
                #     print("-" * 40)

                # 正常に取得できた場合、注文履歴を返す
                return content

        except urllib.error.HTTPError as e:
            print("HTTPエラー:", e)
            try:
                error_content = json.loads(e.read())
                pprint.pprint(error_content)
            except Exception:
                print("[ERROR] エラーレスポンスの解析に失敗しました。")
            return None

        except Exception as e:
            print("例外発生:", e)
            return None


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
                content = json.loads(res.read())
                return content
                
        except urllib.error.HTTPError as e:
            self.logger.error(f"新規注文送信中にHTTPエラーが発生しました:")
            self.logger.error(f"ステータスコード: {e.code}")
            self.logger.error(f"理由: {e.reason}")
            try:
                # エラーレスポンスの本文を読み取り
                error_content = json.loads(e.read())
                self.logger.error(f"エラー詳細: {error_content}")
                if 'Code' in error_content:
                    self.logger.error(f"エラーコード: {error_content['Code']}")
                if 'Message' in error_content:
                    self.logger.error(f"エラーメッセージ: {error_content['Message']}")
            except json.JSONDecodeError:
                self.logger.error("エラーレスポンスのJSONパースに失敗しました")
            return None
                
        except Exception as e:
            self.logger.error(f"新規注文送信中にその他のエラーが発生しました: {str(e)}")
            self.logger.error(f"リクエスト内容: {obj}")
            return None
                
        finally:
            end_time = datetime.datetime.now()
            self.logger.debug(f"{side} order finished at {end_time.strftime('%H:%M:%S.%f')}")


    """
    逆指値返済
    """
    def reverse_limit_order_exit(self, side, HoldID, quantity, underover, limit_price):
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
            "ClosePositions": [
                {
                    "HoldID": HoldID,
                    "Qty": quantity
                }
            ],       
            'FrontOrderType': 30,                    
            'ExpireDay': 0,                
            'ReverseLimitOrder': {
                'TriggerSec': 1,         # 1.発注銘柄 2.NK225指数 3.TOPIX指数
                'TriggerPrice': limit_price,
                'UnderOver': underover,  # 1.以下 2.以上
                'AfterHitOrderType': 2,  # 1.成行 2.指値 3.不成
                'AfterHitPrice': limit_price
            }
        }
        
        # print("\n=== 逆指値返済注文パラメータ ===")
        # print(f"注文サイド: {'買い' if side == '2' else '売り'} (Side: {side})")
        # print(f"決済数量: {quantity}")
        # print(f"トリガー価格: {limit_price}")
        # print(f"執行条件: {'以下' if underover == 1 else '以上'}")
        # print(f"HoldID: {HoldID}")
        # print("================================\n")
        
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)
        
        try:
            with urllib.request.urlopen(req) as res:
                response_data = res.read().decode('utf-8')
                content = json.loads(response_data)
                return content

        except urllib.error.HTTPError as e:
            print("\n逆指値返済注文でエラーが発生しました")
            print(f"ステータスコード: {e.code}")
            print(f"エラーの理由: {e.reason}")
            
            try:
                error_body = e.read().decode('utf-8')
                error_details = json.loads(error_body)
                # print("\nエラーの詳細:")
                # print(f"エラーコード: {error_details.get('Code', 'N/A')}")
                print(f"エラーメッセージ: {error_details.get('Message', 'N/A')}")
                # print(f"その他の情報: {error_details}")
            except json.JSONDecodeError:
                print(f"エラーボディ(JSON解析不可): {error_body}")
            except Exception as read_err:
                print(f"エラー詳細の取得中に問題発生: {read_err}")
            
            print("\n送信しようとした注文内容:")
            print(json.dumps(obj, indent=2, ensure_ascii=False))
            print("================================\n")
            return None

        except Exception as e:
            print("\n❌ 予期せぬエラーが発生しました")
            print(f"エラーの種類: {type(e).__name__}")
            print(f"エラーの内容: {str(e)}")
            print("\n送信しようとした注文内容:")
            print(json.dumps(obj, indent=2, ensure_ascii=False))
            print("================================\n")
            return None
        
    
    """
    IOC返済(ClosePositions)
    """
    def exit_ioc_order(self, side, quantity, HoldID, price):
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
            "ClosePositions": [
                {
                    "HoldID": HoldID,
                    "Qty": quantity
                }
            ],      
            'FrontOrderType': 27,  # IOC指値（返済時のみ）
            'Price': price,
            'ExpireDay': 0 
        }
        
        # print("\n📋 注文パラメータ:")
        # for key, value in obj.items():
        #     if key != 'Password':  # パスワードは表示しない
        #         print(f"  {key}: {value}")
                
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)

        try:
            with urllib.request.urlopen(req) as res:
                response_body = res.read().decode('utf-8')
                content = json.loads(response_body)
                
                # レスポンスの解析
                if content.get('Result') == 0:
                    order_id = content.get('OrderId')
                else:
                    print(f"  エラーコード: {content.get('Result')}")
                    print(f"  エラーメッセージ: {content.get('Message')}")
                    print(f"  送信した注文内容: {json.dumps(obj, indent=2, ensure_ascii=False)}")

                return content

        except urllib.error.HTTPError as e:
            print(f"  ステータスコード: {e.code}")
            print(f"  理由: {e.reason}")

        except Exception as e:
            error_msg = f"IOC返済注文送信中にエラーが発生: {str(e)}"
            print(f"  {error_msg}")
            self.logger.error(error_msg, exc_info=True)
            print("====================\n")
            return None
        
        
        
    """
    IOC返済(ClosePositionOrder)
    """
    # def exit_ioc_order(self, side, quantity, HoldID, price):
    #     obj = {
    #         'Password': self.order_password,
    #         'Symbol': self.init.symbol,
    #         'Exchange': 1,
    #         'SecurityType': 1,
    #         'Side': side,
    #         'CashMargin': 3, 
    #         'MarginTradeType': 3,  
    #         'DelivType': 2, 
    #         'AccountType': 4,
    #         'Qty': quantity,
    #         'ClosePositionOrder': 1,
    #         # "ClosePositions": [
    #         #     {
    #         #         "HoldID": HoldID,
    #         #         "Qty": quantity
    #         #     }
    #         # ],      
    #         'FrontOrderType': 27,  # IOC指値（返済時のみ）
    #         'Price': price,
    #         'ExpireDay': 0 
    #     }
        
    #     # print("\n📋 注文パラメータ:")
    #     # for key, value in obj.items():
    #     #     if key != 'Password':  # パスワードは表示しない
    #     #         print(f"  {key}: {value}")
                
    #     json_data = json.dumps(obj).encode('utf-8')
    #     url = f"{API_BASE_URL}/sendorder"
    #     req = urllib.request.Request(url, json_data, method='POST')
    #     req.add_header('Content-Type', 'application/json')
    #     req.add_header('X-API-KEY', self.init.token)

    #     try:
    #         with urllib.request.urlopen(req) as res:
    #             response_body = res.read().decode('utf-8')
    #             content = json.loads(response_body)
                
    #             # レスポンスの解析
    #             if content.get('Result') == 0:
    #                 order_id = content.get('OrderId')
    #                 # print(f"✅ 注文送信成功: 注文ID: {order_id}")
    #             else:
    #                 print("❌ 注文送信失敗")
    #                 print(f"  エラーコード: {content.get('Result')}")
    #                 print(f"  エラーメッセージ: {content.get('Message')}")
    #                 print(f"  送信した注文内容: {json.dumps(obj, indent=2, ensure_ascii=False)}")

    #             return content

    #     except urllib.error.HTTPError as e:
    #         self.logger.error(f"HTTPエラーの詳細:\n"
    #                         # f"ステータスコード: {e.code}\n"
    #                         f"エラーの内容: {e.read().decode('utf-8')}\n")
    #                         # f"ヘッダー: {e.headers}")

    #     except Exception as e:
    #         error_msg = f"IOC返済注文送信中にエラーが発生: {str(e)}"
    #         print(f"  {error_msg}")
    #         self.logger.error(error_msg, exc_info=True)
    #         print("====================\n")
    #         return None