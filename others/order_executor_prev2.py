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



#本番用
API_BASE_URL = "http://localhost:18080/kabusapi"
#検証用
# API_BASE_URL = "http://localhost:18081/kabusapi"


def get_token(api_password):
    url = f"{API_BASE_URL}/token"
    headers = {"Content-Type": "application/json"}
    data = {"APIPassword": api_password}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            token = response.json().get("Token")
            # print(f"取得したトークン: {token}")
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

        
    def execute_orders(self):
        """
        シグナルに基づいて注文を実行します。
        """

        # 注文状態を確認
        # latest_order = self.get_orders()
        # time.sleep(100)

        if self.init.interpolated_data is None or self.init.interpolated_data.empty:
            self.logger.warning("補間データが存在しません。注文の実行をスキップします。")
            return

        # 最後の行を取得
        last_row = self.init.interpolated_data.iloc[-1]

        # シグナルを取得
        buy_signal = self.init.interpolated_data.iloc[-1].get('buy_signals', 0)
        buy_exit_signal = self.init.interpolated_data.iloc[-1].get('buy_exit_signals', 0)
        sell_signal = self.init.interpolated_data.iloc[-1].get('sell_signals', 0)
        sell_exit_signal = self.init.interpolated_data.iloc[-1].get('sell_exit_signals', 0)
        emergency_buy_exit_signal = self.init.interpolated_data.iloc[-1].get('emergency_buy_exit_signals', 0)
        emergency_sell_exit_signal = self.init.interpolated_data.iloc[-1].get('emergency_sell_exit_signals', 0)
        special_sell_signal = self.init.interpolated_data.iloc[-1].get('special_sell_signals', 0)
        special_sell_exit_signal = self.init.interpolated_data.iloc[-1].get('special_sell_exit_signals', 0)
        special_buy_signal = self.init.interpolated_data.iloc[-1].get('special_buy_signals', 0)
        special_buy_exit_signal = self.init.interpolated_data.iloc[-1].get('special_buy_exit_signals', 0)

        # 注文の側面を数値で定義
        SIDE_BUY = "2"
        SIDE_SELL = "1"

        # エグジットシグナルの処理（信用売りの買い戻し） - IOC 指値注文
        if sell_exit_signal == 1:
            self.logger.info("売りエグジットシグナルが検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            order_price = self.init.sell_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_BUY, quantity, order_price)
                self.logger.info(f"IOC指値注文レスポンス: {response}")
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
                        time.sleep(1)
                        if rec_type in (3, 7):
                            # リセット処理を実行
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals_2(current_index)
                            self.logger.info(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")

                            time.sleep(1)
                        else:
                            self.logger.info(f"RecTypeは{rec_type}です。リセットは不要です。")
                    else:
                        self.logger.warning("最新の注文にDetailsが存在しません。")
                else:
                    self.logger.warning("最新の注文情報が取得できませんでした。")
            except Exception as e:
                # スタックトレースをログに出力
                self.logger.error(f"売りポジションをクローズするIOC指値注文に失敗しました: {e}")
                traceback_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
                self.logger.error(f"スタックトレース:\n{traceback_str}")

                self.init.signal_position = self.init.signal_position_prev2

                # 最新の注文が辞書型であるか確認
                if 'latest_order' in locals() and latest_order and isinstance(latest_order, dict):
                    order_id = latest_order.get('ID') or latest_order.get('OrderId')
                    self.logger.info(f"注文がキャンセルされたため、シグナルをリセットしました。OrderId: {order_id}")
                else:
                    self.logger.info("注文がキャンセルされたため、シグナルをリセットしました。")
            time.sleep(0.5)





        if emergency_sell_exit_signal == 1 or special_sell_exit_signal == 1:  # 成行注文
            self.logger.info("売りエグジットシグナル（緊急または特別）が検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_pay_close_position_order(SIDE_BUY, quantity)
                if response:
                    self.logger.info(f"売りポジションを閉じる注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"売りポジションを閉じる注文に失敗しました: {e}")
            time.sleep(0.5)  # 適切な遅延を設定







        # エグジットシグナルの処理（信用買いの売り） - IOC 指値注文
        if buy_exit_signal == 1:
            self.logger.info("買いエグジットシグナルが検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            order_price = self.init.buy_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_SELL, quantity, order_price)              
                self.logger.info(f"IOC指値注文レスポンス: {response}")
                time.sleep(0.5)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.5)
                # 最新の詳細情報からRecTypeをチェック
                if latest_order and 'Details' in latest_order:
                    details = latest_order['Details']
                    if details:
                        # 最新の詳細情報を取得（必要に応じてソート）
                        latest_detail = details[-1]
                        rec_type = latest_detail.get('RecType')
                        time.sleep(1)
                        if rec_type in (3, 7):
                            # リセット処理を実行
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals_2(current_index)
                            self.logger.info(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")
                            time.sleep(1)
                        else:
                            self.logger.info(f"RecTypeは{rec_type}です。リセットは不要です。")
                    else:
                        self.logger.warning("最新の注文にDetailsが存在しません。")
                else:
                    self.logger.warning("最新の注文情報が取得できませんでした。")
            except Exception as e:
                # スタックトレースをログに出力
                self.logger.error(f"買いポジションをクローズするIOC指値注文に失敗しました: {e}")
                traceback_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
                self.logger.error(f"スタックトレース:\n{traceback_str}")

                self.init.signal_position = self.init.signal_position_prev2
              
                # 最新の注文が辞書型であるか確認
                if 'latest_order' in locals() and latest_order and isinstance(latest_order, dict):
                    order_id = latest_order.get('ID') or latest_order.get('OrderId')
                    self.logger.info(f"注文がキャンセルされたため、シグナルをリセットしました。OrderId: {order_id}")
                else:
                    self.logger.info("注文がキャンセルされたため、シグナルをリセットしました。")
            time.sleep(0.5) 






        if emergency_buy_exit_signal == 1 or special_buy_exit_signal == 1:  # 成行注文
            self.logger.info("買いエグジットシグナル（緊急または特別）が検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            try:
                # time.sleep(10)
                response = self.margin_pay_close_position_order(SIDE_SELL, quantity)
                if response:
                    self.logger.info(f"買いポジションを閉じる注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"買いポジションを閉じる注文に失敗しました: {e}")
            time.sleep(0.5)  # 適切な遅延を設定

        # エントリーシグナルの処理（信用売りの売り） - 成行注文
        if special_sell_signal == 1:
            self.logger.info("売り特殊エントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_new_order(SIDE_SELL, quantity, self.init.sell_entry_price)
                # response = self.margin_new_order(SIDE_SELL, quantity)
                if response:
                    self.logger.info(f"売りポジションをオープンする成行注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"売りポジションをオープンする成行注文に失敗しました: {e}")
            time.sleep(0.5)  # 適切な遅延を設定

        # エントリーシグナルの処理（信用売りの売り） - 成行注文
        if special_buy_signal == 1:
            self.logger.info("売り特殊エントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_new_order(SIDE_BUY, quantity, self.init.buy_entry_price)
                # response = self.margin_new_order(SIDE_SELL, quantity)
                if response:
                    self.logger.info(f"売りポジションをオープンする成行注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"売りポジションをオープンする成行注文に失敗しました: {e}")
            time.sleep(0.5)  # 適切な遅延を設定






        # エントリーシグナルの処理（信用売り） - IOC指値注文
        if sell_signal == 1:
            self.logger.info("売りエントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            order_price = self.init.sell_entry_price
            try:
                response = self.margin_new_ioc_order(SIDE_SELL, quantity, order_price)              
                self.logger.info(f"IOC指値注文レスポンス: {response}")
                time.sleep(0.5)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.5)

                # 最新の詳細情報からRecTypeをチェック
                if latest_order and 'Details' in latest_order:
                    details = latest_order['Details']
                    if details:
                        # 最新の詳細情報を取得（必要に応じてソート）
                        latest_detail = details[-1]
                        rec_type = latest_detail.get('RecType')
                        time.sleep(1)
                        if rec_type in (3, 7):
                            # リセット処理を実行
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals(current_index)
                            self.logger.info(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")
                            time.sleep(1)
                        else:
                            self.logger.info(f"RecTypeは{rec_type}です。リセットは不要です。")
                    else:
                        self.logger.warning("最新の注文にDetailsが存在しません。")
                else:
                    self.logger.warning("最新の注文情報が取得できませんでした。")
            except Exception as e:
                # スタックトレースをログに出力
                self.logger.error(f"売りポジションをオープンするIOC指値注文に失敗しました: {e}")
                traceback_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
                self.logger.error(f"スタックトレース:\n{traceback_str}")

                self.init.signal_position = self.init.signal_position_prev

                # 最新の注文が辞書型であるか確認
                if 'latest_order' in locals() and latest_order and isinstance(latest_order, dict):
                    order_id = latest_order.get('ID') or latest_order.get('OrderId')
                    self.logger.info(f"注文がキャンセルされたため、シグナルをリセットしました。OrderId: {order_id}")
                else:
                    self.logger.info("注文がキャンセルされたため、シグナルをリセットしました。")
            time.sleep(0.3) 


        # buy_signal の処理（信用買い） - IOC指値注文
        if buy_signal == 1:
            self.logger.info("買いエントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            order_price = self.init.buy_entry_price
            try:
                response = self.margin_new_ioc_order(SIDE_BUY, quantity, order_price)
                self.logger.info(f"IOC指値注文レスポンス: {response}")
                # time.sleep(0.5)
                time.sleep(0.5)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                # time.sleep(0.5)
                time.sleep(0.5)

                # 最新の詳細情報からRecTypeをチェック
                if latest_order and 'Details' in latest_order:
                    details = latest_order['Details']
                    if details:
                        # 最新の詳細情報を取得（必要に応じてソート）
                        latest_detail = details[-1]
                        rec_type = latest_detail.get('RecType')
                        time.sleep(1)
                        if rec_type in (3, 7):
                            # リセット処理を実行
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals(current_index)
                            self.logger.info(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")
                            time.sleep(1)
                        else:
                            self.logger.info(f"RecTypeは{rec_type}です。リセットは不要です。")
                    else:
                        self.logger.warning("最新の注文にDetailsが存在しません。")
                else:
                    self.logger.warning("最新の注文情報が取得できませんでした。")
            except Exception as e:
                # スタックトレースをログに出力
                self.logger.error(f"買いポジションをオープンするIOC指値注文に失敗しました: {e}")
                traceback_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
                self.logger.error(f"スタックトレース:\n{traceback_str}")

                self.init.signal_position = self.init.signal_position_prev

                # 最新の注文が辞書型であるか確認
                if 'latest_order' in locals() and latest_order and isinstance(latest_order, dict):
                    order_id = latest_order.get('ID') or latest_order.get('OrderId')
                    self.logger.info(f"注文がキャンセルされたため、シグナルをリセットしました。OrderId: {order_id}")
                else:
                    self.logger.info("注文がキャンセルされたため、シグナルをリセットしました。")
            time.sleep(0.3)



    # def get_orders(self, params=None, count=1):
    #     """
    #     最新の注文を取得するメソッド。
    #     count: 取得する最新の注文数（デフォルトは2）
    #     """
    #     if params is None:
    #         params = {'product': 2}  # デフォルトではすべてのプロダクトを取得 2で信用

    #     url = f"{API_BASE_URL}/orders"
    #     query_string = urllib.parse.urlencode(params)
    #     full_url = f"{url}?{query_string}"
    #     req = urllib.request.Request(full_url, method='GET')
    #     req.add_header('Content-Type', 'application/json')
    #     req.add_header('X-API-KEY', self.token)

    #     try:
    #         with urllib.request.urlopen(req) as res:
    #             self.logger.info(f"注文履歴の取得に成功しました: {res.status} {res.reason}")
    #             content = json.loads(res.read())
                
    #             # contentがリストであることを確認
    #             if not isinstance(content, list):
    #                 self.logger.error(f"期待していたリストではなく、{type(content)}が返されました。内容: {content}")
    #                 return None
                
    #             if not content:
    #                 self.logger.warning("注文データが空です。")
    #                 return None
                
    #             # 受信時間でソートして最新の注文を取得
    #             try:
    #                 # 最新の 'count' 件を取得
    #                 latest_orders = heapq.nlargest(count, content, key=lambda x: x.get('RecvTime', ''))
                    
    #                 if len(latest_orders) < count:
    #                     self.logger.warning(f"要求された数の注文が存在しません。取得された注文数: {len(latest_orders)}")
                    
    #             except KeyError as e:
    #                 self.logger.error(f"RecvTimeが存在しない注文が含まれています: {e}")
    #                 return None
    #             except Exception as e:
    #                 self.logger.error(f"最新の注文を取得中にエラーが発生しました: {e}")
    #                 return None
                
    #             # 最新の注文を表示
    #             for order in latest_orders:
    #                 pprint.pprint(order)
                
    #             return latest_orders
    #     except urllib.error.HTTPError as e:
    #         self.logger.error(f"HTTPエラーが発生しました: {e}")
    #         try:
    #             content = json.loads(e.read())
    #             pprint.pprint(content)
    #         except Exception:
    #             pass
    #         return None
    #     except Exception as e:
    #         self.logger.error(f"注文履歴の取得中に例外が発生しました: {e}")
    #         return None




    def get_orders(self, params=None):
        """
        最新の注文を取得するメソッド。
        """
        if params is None:
            params = {'product': 2}  # デフォルトではすべてのプロダクトを取得 2で信用

        url = f"{API_BASE_URL}/orders"
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(full_url, method='GET')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.token)

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"注文履歴の取得に成功しました: {res.status} {res.reason}")
                content = json.loads(res.read())
                
                # contentがリストであることを確認
                if not isinstance(content, list):
                    self.logger.error(f"期待していたリストではなく、{type(content)}が返されました。内容: {content}")
                    return None
                
                if not content:
                    self.logger.warning("注文データが空です。")
                    return None
                
                # 受信時間でソートして最新の注文を取得
                try:
                    latest_order = max(content, key=lambda x: x.get('RecvTime', ''))
                except KeyError as e:
                    self.logger.error(f"RecvTimeが存在しない注文が含まれています: {e}")
                    return None
                except Exception as e:
                    self.logger.error(f"最新の注文を取得中にエラーが発生しました: {e}")
                    return None
                
                # 最新の注文を表示
                pprint.pprint(latest_order)
                return latest_order
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTPエラーが発生しました: {e}")
            try:
                content = json.loads(e.read())
                pprint.pprint(content)
            except Exception:
                pass
            return None
        except Exception as e:
            self.logger.error(f"注文履歴の取得中に例外が発生しました: {e}")
            return None




    def margin_new_ioc_order(self, side, quantity, price):
        """
        信用取引新規注文をIOC指値で発注する関数。
        """
        obj = {
            'Password': self.order_password,
            'Symbol': self.init.symbol,
            'Exchange': 1,
            'SecurityType': 1,
            'Side': side,
            'CashMargin': 2,               
            'MarginTradeType': 3,                  # 信用取引の種類（1は新規）
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

        # pprint.pprint(json_data)

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


    

    def margin_ioc_exit_order(self, side, quantity, price):
        """
        信用取引指値返済注文をIOC指値で発注する関数。
        
        Parameters:
            side (str): '1' = 売, '2' = 買
            quantity (int): 注文数量
            price (float): 指値価格

        Returns:
            dict: APIからのレスポンス
        """
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
            'Price': price,  # 返済時の指値価格を指定
            'ExpireDay': 0  # 当日注文
            # 'ReverseLimitOrder': 0                      # 逆指値注文のフラグ（0は無効）
        }

        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-API-KEY', self.init.token)

        # pprint.pprint(json_data)

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


    




    def margin_new_order(self, side, quantity):
        """
        信用取引新規注文を成行で発注する関数。
        
        Parameters:
            side (str): '1' = 売, '2' = 買
            quantity (int): 注文数量
        """
        obj = {
            'Password': self.order_password,        # 注文に使用するパスワード
            'Symbol': self.init.symbol,             # 銘柄シンボル
            'Exchange': 1,                          # 取引所コード（例: 1は特定の取引所）
            'SecurityType': 1,                      # 証券種別（例: 1は株式）
            'Side': side,                           # 売買の方向（'1' = 売, '2' = 買）
            'CashMargin': 2,                        # 現金・信用取引の区分（2は信用取引）
            'MarginTradeType': 3,                   
            'DelivType': 0,                         # 配送方法の指定（0は指定なし）
            'AccountType': 4,                       # 口座種別コード（例: 4は特定の口座）
            'Qty': quantity,                        # 注文数量
            'FrontOrderType': 10,                   # 執行条件コード（10は成行）
            'Price': 0,                             # 注文価格（成行の場合は0）
            'ExpireDay': 0                          # 注文有効期限（日数、0は当日）
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

        
    def margin_pay_close_position_order(self, side, quantity):
        """
        信用取引返済注文を発注する関数。
        
        Parameters:
            side (str): '1' = 売, '2' = 買
            quantity (int): 注文数量

        Returns:
            dict: APIからのレスポンス
        """
        obj = {
            'Password': self.order_password,            # 注文に使用するパスワード
            'Symbol': self.init.symbol,                  # 銘柄シンボル
            'Exchange': 1,                              # 取引所コード（例: 1は特定の取引所）
            'SecurityType': 1,                          # 証券種別（例: 1は株式）
            'Side': side,                               # 売買の方向（'1' = 売, '2' = 買）
            'CashMargin': 3,                            # 現金・信用取引の区分（3は信用返済）
            'MarginTradeType': 3,                       
            'DelivType': 2,                             # 配送方法の指定（2は特定の配送方法）
            'AccountType': 4,                           # 口座種別コード（例: 4は特定の口座）
            'Qty': quantity,                            # 注文数量
            'ClosePositionOrder': 1,                    # ポジションクローズのフラグ
            'FrontOrderType': 10,                       # 執行条件コード（10は成行）
            'Price': 0,                                 # 注文価格（成行の場合は0）
            'ExpireDay': 0                              # 注文有効期限（日数、0は当日）
            # 'ReverseLimitOrder': 0                      # 逆指値注文のフラグ（0は無効）
        }

        # JSONデータのエンコード
        json_data = json.dumps(obj).encode('utf-8')

        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        # コンテンツタイプを指定
        req.add_header('Content-Type', 'application/json') 
        # APIキーをヘッダーに追加 
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