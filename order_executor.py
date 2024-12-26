# order_executor.py
import urllib.request
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
from pprint import pprint

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

逆指値
reverse_limit_order(self, side, quantity, stop_price)

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
    def execute_orders(self):
        
        fetch_interval = 0.3 
        price_threshold = 0.1  # 価格変動の閾値

        # 注文の側面を数値で定義
        SIDE_BUY = "2"
        SIDE_SELL = "1"

        if self.init.interpolated_data is None or self.init.interpolated_data.empty:
            print("補間データが存在しません。注文の実行をスキップします。")
            return

        # 最後の行を取得
        last_row = self.init.interpolated_data.iloc[-1]
        # シグナルを取得
        buy_signal = last_row.get('buy_signals', 0)
        buy_exit_signal = last_row.get('buy_exit_signals', 0)
        sell_signal = last_row.get('sell_signals', 0)
        sell_exit_signal = last_row.get('sell_exit_signals', 0)
        emergency_buy_exit_signal = last_row.get('emergency_buy_exit_signals', 0)
        emergency_sell_exit_signal = last_row.get('emergency_sell_exit_signals', 0)
        hedge_buy_signal = last_row.get('hedge_buy_signals', 0)
        hedge_buy_exit_signal = last_row.get('hedge_buy_exit_signals', 0)
        hedge_sell_signal = last_row.get('hedge_sell_signals', 0)
        hedge_sell_exit_signal = last_row.get('hedge_sell_exit_signals', 0)
        special_buy_signal = last_row.get('special_buy_signals', 0)
        special_buy_exit_signal = last_row.get('special_buy_exit_signals', 0)
        special_sell_signal = last_row.get('special_sell_signals', 0)
        special_sell_exit_signal = last_row.get('special_sell_exit_signals', 0)

        # 1. 新規シグナルの検知と逆指値注文の発行
        if buy_signal == 1 or sell_signal == 1:
            if buy_signal == 1:
                quantity = 100  # 適切な数量に置き換える
                order_price = self.init.buy_entry_price  # 指値価格を設定
                trigger_price = self.init.buy_trigger_price  # トリガー価格を設定
                response = self.reverse_limit_order(SIDE_BUY, quantity, order_price)
                # 必要に応じて trigger_price の使用方法を追加

            if sell_signal == 1:
                quantity = 100  # 適切な数量に置き換える
                order_price = self.init.sell_entry_price  # 指値価格を設定
                trigger_price = self.init.sell_trigger_price  # トリガー価格を設定
                response = self.reverse_limit_order(SIDE_SELL, quantity, order_price)
                # 必要に応じて trigger_price の使用方法を追加

        # 2. 市場価格の変動を検知

        # 価格が変動するまで待機
        new_price, price_changed, direction = self.wait_for_price_change(fetch_interval, price_threshold)

        if price_changed:
            price_change = new_price - self.init.previous_price
            print(f"価格が変動しました。前回価格: {self.init.previous_price}, 新価格: {new_price}, 変動額: {price_change}")

            # 価格変動の閾値を確認
            if abs(price_change) >= price_threshold:
                # 新規シグナルを発行

                # 最新の2つの注文を取得
                params = {'product': 2, 'details': 'false'}
                latest_orders_response = self.get_orders(params=params, limit=2)
                if latest_orders_response:
                    # latest_orders_responseがリストでない場合はリストに変換
                    latest_orders = latest_orders_response if isinstance(latest_orders_response, list) else [latest_orders_response]
                else:
                    latest_orders = []

                # シグナルを同時に発行
                if direction > 0:
                    # 売り方向の変動
                    self.init.logger.info("売り方向の価格変動を検知。reverse_sell_repayment シグナルを発行します。")
                    self.trading_data.set_signal('reverse_sell_repayment', 1)

                    # 最新の2つの注文をキャンセル
                    for order in latest_orders:
                        order_id = order.get('OrderID')
                        order_side = order.get('Side')  # '1' = 売, '2' = 買 と仮定
                        if order_side == SIDE_SELL and order_id:
                            self.cancel_order(order_id)
                            self.trading_data.reset_signals(current_index=None)
                        elif order_side == SIDE_BUY and order_id:
                            self.cancel_order(order_id)
                            self.trading_data.reset_signals(current_index=None)

                elif direction < 0:
                    # 買い方向の変動
                    self.init.logger.info("買い方向の価格変動を検知。reverse_buy_repayment シグナルを発行します。")
                    self.trading_data.set_signal('reverse_buy_repayment', 1)

                    # 最新の2つの注文をキャンセル
                    for order in latest_orders:
                        order_id = order.get('OrderID')
                        order_side = order.get('Side')  # '1' = 売, '2' = 買 と仮定
                        if order_side == SIDE_BUY and order_id:
                            self.cancel_order(order_id)
                            self.trading_data.reset_signals(current_index=None)
                        elif order_side == SIDE_SELL and order_id:
                            self.cancel_order(order_id)
                            self.trading_data.reset_signals(current_index=None)

                    # 価格変動後のシグナルの評価
                    if direction > 0:
                        pass  # 価格が上昇方向に変動しました。売りシグナルを継続します。
                    elif direction < 0:
                        self.trading_data.set_signal('reverse_buy_repayment', 0)
                        if latest_orders and 'OrderID' in latest_orders[0]:
                            self.cancel_order(latest_orders[0].get('OrderID'))
                        self.trading_data.reset_signals(current_index=None)

                    # 価格のさらなる変動をチェック
                    new_new_price = self.trading_data.fetch_current_price()

                    if new_new_price > new_price:
                        pass  # 価格がさらに上昇しました。既存のシステムに制御を委ねます。
                    elif new_new_price < new_price:
                        pass  # 価格がさらに下降しました。新しい売買シグナルを発行します。

        else:
            print(f"価格変動が検知されませんでした。")

        # 基準価格を更新
        self.init.previous_price = new_price
        self.init.logger.info(f"基準価格を更新しました。新価格: {new_price}")








        # エグジットシグナルの処理（信用売りの買い戻し） - IOC 指値注文
        if sell_exit_signal == 1 and (side == "1" and total_qty['sell'] == 100):
            quantity = 100  # 固定値として設定
            order_price = self.init.sell_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_BUY, quantity, order_price)
                time.sleep(0.1)              

                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.1)

                # 最新の詳細情報からRecTypeをチェック
                if latest_order and 'Details' in latest_order:
                    details = latest_order['Details']
                    if details:
                        # 最新の詳細情報を取得（必要に応じてソート）
                        latest_detail = details[-1]
                        rec_type = latest_detail.get('RecType')
                        time.sleep(0.5)
                        if rec_type in (3, 7):
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals_2(current_index)
                            time.sleep(1)
                        else:
                            pass  # RecTypeは3,7以外です。リセットは不要です。
                    else:
                        pass  # 最新の注文にDetailsが存在しません。
                else:
                    pass  # 最新の注文情報が取得できませんでした。
            except Exception as e:
                self.init.signal_position = self.init.signal_position_prev2

                # 最新の注文が辞書型であるか確認
                if 'latest_order' in locals() and latest_order and isinstance(latest_order, dict):
                    order_id = latest_order.get('ID') or latest_order.get('OrderId')
                    print(f"注文がキャンセルされたため、シグナルをリセットしました。OrderId: {order_id}")
                else:
                    print("注文がキャンセルされたため、シグナルをリセットしました。")

            # ポジション情報を取得
            positions_dict = self.get_positions()
            # 売りと買いの総数量を初期化
            total_qty['buy'] = 0.0
            total_qty['sell'] = 0.0
            # side の初期値を設定
            side = None 
            # ポジション情報をループして売りと買いを集計
            for position in positions_dict:
                side = position.get('Side')
                qty = position.get('LeavesQty', 0)
                
                if side == '2':  # 買い
                    total_qty['buy'] += qty
                elif side == '1':  # 売り
                    total_qty['sell'] += qty
                else:
                    pass  # 不明なSideの場合は無視
            time.sleep(0.3)  # 適切な遅延を設定



        # ポジション情報を取得
        positions_dict = self.get_positions()

        if (emergency_sell_exit_signal == 1 and (side == "1" and total_qty['sell'] == 100)) or \
        (hedge_sell_exit_signal == 1 and (self.init.signal_position_prev2 == 'hedge_sell' and side == "1" and total_qty['sell'] == 100)) or \
        (special_sell_exit_signal == 1 and (self.init.signal_position_prev == 'special_sell' and side == "1" and total_qty['sell'] == 100)):  # 成行注文
            print("売りエグジットシグナル（緊急または特別）が検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_pay_close_position_order(SIDE_BUY, quantity)
                if response:
                    print(f"売りポジションを閉じる注文を送信しました。数量: {quantity}")
            except Exception as e:
                print(f"売りポジションを閉じる注文に失敗しました: {e}")
            # ポジション情報を取得
            positions_dict = self.get_positions()
            # 売りと買いの総数量を初期化
            total_qty['buy'] = 0.0
            total_qty['sell'] = 0.0
            # side の初期値を設定
            side = None 
            # ポジション情報をループして売りと買いを集計
            for position in positions_dict:
                side = position.get('Side')
                qty = position.get('LeavesQty', 0)
                
                if side == '2':  # 買い
                    total_qty['buy'] += qty
                elif side == '1':  # 売り
                    total_qty['sell'] += qty
                else:
                    print(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)  # 適切な遅延を設定


        

        # エグジットシグナルの処理（信用買いの売り） - IOC 指値注文
        if buy_exit_signal == 1 and (side == "2" and total_qty['buy'] == 100):
            quantity = 100  # 固定値として設定
            order_price = self.init.buy_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_SELL, quantity, order_price)              
                time.sleep(0.3)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.3)
                # 最新の詳細情報からRecTypeをチェック
                if latest_order and 'Details' in latest_order:
                    details = latest_order['Details']
                    if details:
                        latest_detail = details[-1]
                        rec_type = latest_detail.get('RecType')
                        time.sleep(1)
                        if rec_type in (3, 7):
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals_2(current_index)
                            time.sleep(1)
                        else:
                            pass  # RecTypeは3,7以外です。リセットは不要です。
                    else:
                        pass  # 最新の注文にDetailsが存在しません。
                else:
                    pass  # 最新の注文情報が取得できませんでした。
            except Exception as e:
                self.init.signal_position = self.init.signal_position_prev2
                
                # 最新の注文が辞書型であるか確認
                if 'latest_order' in locals() and latest_order and isinstance(latest_order, dict):
                    order_id = latest_order.get('ID') or latest_order.get('OrderId')
                else:
                    pass  # 注文がキャンセルされたため、シグナルをリセットしました。
            # ポジション情報を取得
            positions_dict = self.get_positions()
            # 売りと買いの総数量を初期化
            total_qty['buy'] = 0.0
            total_qty['sell'] = 0.0
            # side の初期値を設定
            side = None 
            # ポジション情報をループして売りと買いを集計
            for position in positions_dict:
                side = position.get('Side')
                qty = position.get('LeavesQty', 0)
                
                if side == '2':  # 買い
                    total_qty['buy'] += qty
                elif side == '1':  # 売り
                    total_qty['sell'] += qty
                else:
                    pass  # 不明なSideの場合は無視
            time.sleep(0.3) 

        
        if (emergency_buy_exit_signal == 1 and (side == "2" and total_qty['buy'] == 100)) or \
           (hedge_buy_exit_signal == 1 and (self.init.signal_position_prev2 == 'hedge_buy' and side == "2" and total_qty['buy'] == 100)) or \
           (special_buy_exit_signal == 1 and (self.init.signal_position_prev == 'special_buy' and side == "2" and total_qty['buy'] == 100)):
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_pay_close_position_order(SIDE_SELL, quantity)
                if response:
                    pass  # 買いポジションを閉じる注文を送信しました。数量: {quantity}
            except Exception as e:
                pass  # 買いポジションを閉じる注文に失敗しました。
            # ポジション情報を取得
            positions_dict = self.get_positions()
            # 売りと買いの総数量を初期化
            total_qty['buy'] = 0.0
            total_qty['sell'] = 0.0
            # side の初期値を設定
            side = None 
            # ポジション情報をループして売りと買いを集計
            for position in positions_dict:
                side = position.get('Side')
                qty = position.get('LeavesQty', 0)
                
                if side == '2':  # 買い
                    total_qty['buy'] += qty
                elif side == '1':  # 売り
                    total_qty['sell'] += qty
                else:
                    pass  # 不明なSideの場合は無視
            time.sleep(0.3)  # 適切な遅延を設定

        # エントリーシグナルの処理（信用売りの売り） - 成行注文
        if (hedge_sell_signal == 1 and (side == "2" and total_qty['buy'] == 100)) or special_sell_signal == 1:
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_new_order(SIDE_SELL, quantity)
                if response:
                    pass  # 売りポジションをオープンする成行注文を送信しました。数量: {quantity}
            except Exception as e:
                pass  # 売りポジションをオープンする成行注文に失敗しました。
            # ポジション情報を取得
            positions_dict = self.get_positions()
            # 売りと買いの総数量を初期化
            total_qty['buy'] = 0.0
            total_qty['sell'] = 0.0
            # side の初期値を設定
            side = None 
            # ポジション情報をループして売りと買いを集計
            for position in positions_dict:
                side = position.get('Side')
                qty = position.get('LeavesQty', 0)
                
                if side == '2':  # 買い
                    total_qty['buy'] += qty
                elif side == '1':  # 売り
                    total_qty['sell'] += qty
                else:
                    pass  # 不明なSideの場合は無視
            time.sleep(0.3)  # 適切な遅延を設定        

    """
    注文取消
    """
    def cancel_order(self, order_id):
        
        obj = {
            'OrderID': order_id,
            'Password': self.order_password  # クラス内で定義されている注文パスワードを使用
        }
        json_data = json.dumps(obj).encode('utf8')
        
        url = 'http://localhost:18080/kabusapi/cancelorder'
        req = urllib.request.Request(url, json_data, method='PUT')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)  # クラス内で定義されているAPIキーを使用
        
        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"注文キャンセル成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                pprint.pprint(content)
                return content
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラー: {e}")
            try:
                content = json.loads(e.read())
                pprint.pprint(content)
            except Exception:
                self.logger.error("エラー内容の解析に失敗しました。")
            return None
        except Exception as e:
            self.logger.error(f"注文キャンセル中に例外が発生しました: {e}")
            return None

    """
    ポジション取得
    """
    def get_positions(self, params=None):        
        if params is None:
            params = {
                'product': 2,       # 0:すべて、1:現物、2:信用、3:先物、4:OP
                'symbol': '1579',   # 取得したいシンボル
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
                pprint.pprint(error_content)
            except Exception:
                self.logger.error("エラー内容の解析に失敗しました。")
            return None
        except Exception as e:
            self.logger.error(f"ポジション取得中に例外が発生しました: {e}")
            return None

    """
    注文履歴取得
    """
    def get_orders_history(self, params=None, limit=2):
        
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
                print(f"[INFO] 注文履歴の取得に成功しました: {res.status} {res.reason}")
                content = json.loads(res.read())

                # contentがリストであることを確認
                if not isinstance(content, list):
                    print(f"[ERROR] 期待していたリストではなく、{type(content)}が返されました。内容: {content}")
                    return None

                if not content:
                    print("[WARNING] 注文データが空です。")
                    return None

                # 受信時間でソートして最新の注文を取得
                try:
                    # RecvTimeをISOフォーマットとしてソート
                    sorted_orders = sorted(content, key=lambda x: x.get('RecvTime', ''), reverse=True)
                    latest_orders = sorted_orders[:limit]
                except KeyError as e:
                    print(f"[ERROR] RecvTimeが存在しない注文が含まれています: {e}")
                    return None
                except Exception as e:
                    print(f"[ERROR] 最新の注文を取得中にエラーが発生しました: {e}")
                    return None

                # 戻り値を決定
                if limit == 1:
                    latest_order = latest_orders[0]
                    print(f"[DEBUG] 最新の注文: {latest_order}")
                    pprint.pprint(latest_order)
                    return latest_order
                else:
                    print(f"[DEBUG] 最新の{limit}件の注文: {latest_orders}")
                    pprint.pprint(latest_orders)
                    return latest_orders

        except urllib.error.HTTPError as e:
            print(f"[ERROR] HTTPエラーが発生しました: {e}")
            try:
                content = json.loads(e.read())
                pprint.pprint(content)
            except Exception:
                print("[ERROR] エラーレスポンスの解析に失敗しました。")
            return None
        except Exception as e:
            print(f"[ERROR] 注文履歴の取得中に例外が発生しました: {e}")
            return None

    """
    新規
    """
    def new_order(self, side, quantity):
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
                self.logger.info(f"注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラー: {e}")
            try:
                content = json.loads(e.read())
            except Exception:
                pass
            return None
        except Exception as e:
            self.logger.error(f"注文送信中に例外が発生しました: {e}")
            return None

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
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラー: {e}")
            try:
                content = json.loads(e.read())
            except Exception:
                pass
            return None
        except Exception as e:
            self.logger.error(f"返済注文送信中に例外が発生しました: {e}")
            return None

    """
    逆指値
    """
    def reverse_limit_order(self, side, quantity, stop_price):
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
            'FrontOrderType': 30,
            'Price': 0,                      
            'ExpireDay': 0,                
            'ReverseLimitOrder': {
                'AfterHitPrice': stop_price  # 逆指値価格
            }
        }

        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json') 
        req.add_header('X-API-KEY', self.init.token)    

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラー: {e}")
            try:
                content = json.loads(e.read())
            except Exception:
                pass
            return None
        except Exception as e:
            self.logger.error(f"注文送信中に例外が発生しました: {e}")
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
                print("HTTPレスポンスステータス:", res.status, res.reason)
                content = json.loads(res.read())
                pprint.pprint(content) 
                if content.get('Result') == 0:
                    order_success = True
                    print("注文が成功しました。OrderId:", content.get('OrderId'))
                else:
                    order_success = False
                    print("注文が失敗しました。レスポンス内容:", content)
                return content
        except urllib.error.HTTPError as e:
            content = json.loads(e.read())
            pprint.pprint(content, indent=4) 
            return None
        except Exception as e:
            self.logger.error(f"注文送信中に例外が発生しました: {e}")
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
                print("HTTPレスポンスステータス:", res.status, res.reason)
                content = json.loads(res.read())
                pprint.pprint(content) 
                if content.get('Result') == 0:
                    order_success = True
                    print("注文が成功しました。OrderId:", content.get('OrderId'))
                else:
                    order_success = False
                    print("注文が失敗しました。レスポンス内容:", content)
                return content
        except urllib.error.HTTPError as e:
            content = json.loads(e.read())
            pprint.pprint(content, indent=4) 
            return None
        except Exception as e:
            self.logger.error(f"注文送信中に例外が発生しました: {e}")
            return None