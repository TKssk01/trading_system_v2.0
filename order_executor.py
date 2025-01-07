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
import pprint
from pprint import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    def execute_orders(self):
        quantity=100
        fetch_interval = 0.3 
        price_threshold = 0.1  # 価格変動の閾値

        SIDE = {"BUY": "2", "SELL": "1"}

        # 補間データの存在確認
        if self.init.interpolated_data is None or self.init.interpolated_data.empty:
            print("補間データが存在しません。注文の実行をスキップします。")
            return

        # 最後の行を取得
        last_row = self.init.interpolated_data.iloc[-1]

        # シグナルを辞書で管理(辞書で管理ver)
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

        # シグナルのデバッグ表示（オプション）
        # self.logger.debug(f"取得したシグナル: {signals}")
        # self.logger.debug(f"取得したシグナル: {pprint.pformat(signals)}")
        self.logger.debug(f"取得したシグナル: {json.dumps(signals, ensure_ascii=False, indent=4)}")
        
        
        if signals.get('buy', 0) == 1 or signals.get('sell', 0) == 1:
            
            # # ロングとショートの同時エントリーを並行処理で実行
            # with ThreadPoolExecutor(max_workers=2) as executor:
            #     # 注文をスレッドに割り当て
            #     future_buy = executor.submit(self.new_order, SIDE["BUY"], quantity)
            #     future_sell = executor.submit(self.new_order, SIDE["SELL"], quantity)

            #     # `as_completed` を使用してタスクの完了を待つ
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
            #             if future == future_buy:
            #                 long_response = None
            #             elif future == future_sell:
            #                 short_response = None
                            
            # # time.sleep(1000)

            # # 例: レスポンスを返す、ログに記録するなど
            # return long_response, short_response
        
        # 約定価格を格納する辞書
        # execution_prices = {}
        # execution_prices['buy']
        
            # OrderExecutorクラス内またはインスタンスから直接
            history = self.get_orders_history(params=None, limit=2)
            # pprint("最新の2件の注文:", history)
            
            # 最新の2件の注文をそれぞれ買いと売りとする
            buy_order = history[1]
            sell_order = history[0]
            

            # SeqNumが5の詳細項目からPriceを抽出する関数
            def extract_price_for_seqnum5(order):
                for detail in order.get("Details", []):
                    if detail.get("SeqNum") == 5:
                        return detail.get("Price")
                return None

            # 買い注文と売り注文からそれぞれPriceを取得
            buy_price = extract_price_for_seqnum5(buy_order)
            sell_price = extract_price_for_seqnum5(sell_order)

            # 結果を表示
            # print("買いの価格:", buy_price)
            # print("売りの価格:", sell_price)
            
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                # 買い玉に対する逆指値注文を実行
                future_rev_buy = executor.submit(self.reverse_limit_order, SIDE["BUY"], 1, quantity, buy_price)
                # 売り玉に対する逆指値注文を実行
                future_rev_sell = executor.submit(self.reverse_limit_order, SIDE["SELL"], 2, quantity, sell_price)
                
                time.sleep(1000)


                # 各注文のレスポンスを取得
                try:
                    reverse_buy_response = future_rev_buy.result()
                    self.logger.debug(f"Reverse Buy Order Response: {reverse_buy_response}")
                except Exception as e:
                    self.logger.error(f"逆指値買い注文中にエラーが発生しました: {e}")
                    reverse_buy_response = None

                try:
                    reverse_sell_response = future_rev_sell.result()
                    self.logger.debug(f"Reverse Sell Order Response: {reverse_sell_response}")
                except Exception as e:
                    self.logger.error(f"逆指値売り注文中にエラーが発生しました: {e}")
                    reverse_sell_response = None
                    
                    
            import time
import json
from concurrent.futures import ThreadPoolExecutor

class YourOrderExecutor:
    def __init__(self, init, logger, trading_api):
        self.init = init
        self.logger = logger
        self.trading_api = trading_api

    def new_order(self, side, quantity):
        # (既存のコード)
        self.logger.info(f"新規注文を発注: side={side}, quantity={quantity}")
        return {"order_id": "dummy_new_order_id"}

    def get_orders_history(self, params=None, limit=2):
        # (既存のコード)
        return [
            {"Details": [{"SeqNum": 5, "Price": 100.0}]},
            {"Details": [{"SeqNum": 5, "Price": 99.0}]}
        ]

    def reverse_limit_order(self, side, trigger_sec, quantity, limit_price):
        underover = 2 if side == "2" else 1 # 買いなら以上、売りなら以下
        params = {
            'FrontOrderType': '1',  # 逆指値
            'ReverseLimitOrder': {
                'TriggerSec': trigger_sec,
                'TriggerPrice': limit_price,
                'UnderOver': underover,
                'AfterHitOrderType': 2,  # 指値
                'AfterHitPrice': limit_price
            },
            'Side': side,
            'Quantity': quantity,
            'Price': limit_price, # 指値価格も設定 (AfterHitOrderTypeが指値のため)
            'OrderType': '2' # 指値
        }
        self.logger.info(f"逆指値注文を発注: {params}")
        # ここで実際の発注処理を呼び出す (例: self.trading_api.place_order_with_params(params))
        order_response = {"order_id": f"dummy_reverse_limit_order_id_{side}"} # ダミー
        return order_response.get("order_id")

    def cancel_order(self, order_id):
        self.logger.info(f"注文をキャンセル: order_id={order_id}")
        # ここで実際のキャンセル処理を呼び出す (例: self.trading_api.cancel_order(order_id))
        return {"status": "success"} # ダミー

    def get_order_status(self, order_id):
        self.logger.info(f"注文ステータスを取得: order_id={order_id}")
        return {"status": "PENDING"} # ダミー

    def execute_orders(self):
        quantity=100
        SIDE = {"BUY": "2", "SELL": "1"}

        if self.init.interpolated_data is None or self.init.interpolated_data.empty:
            self.logger.info("補間データが存在しません。注文の実行をスキップします。")
            return

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
        self.logger.debug(f"取得したシグナル: {json.dumps(signals, ensure_ascii=False, indent=4)}")

        if signals.get('buy', 0) == 1 or signals.get('sell', 0) == 1:
            history = self.get_orders_history(params=None, limit=2)
            buy_order = history[1]
            sell_order = history[0]

            def extract_price_for_seqnum5(order):
                for detail in order.get("Details", []):
                    if detail.get("SeqNum") == 5:
                        return detail.get("Price")
                return None

            buy_price = extract_price_for_seqnum5(buy_order)
            sell_price = extract_price_for_seqnum5(sell_order)

            reverse_buy_order_id = None
            reverse_sell_order_id = None
            
            #逆指値注文の発行
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_rev_buy = executor.submit(self.reverse_limit_order, SIDE["BUY"], 1, quantity, buy_price)
                future_rev_sell = executor.submit(self.reverse_limit_order, SIDE["SELL"], 1, quantity, sell_price)

                try:
                    reverse_buy_order_id = future_rev_buy.result(timeout=60)
                    self.logger.debug(f"Reverse Buy Order ID: {reverse_buy_order_id}")
                except Exception as e:
                    self.logger.error(f"逆指値買い注文中にエラーが発生しました: {e}")

                try:
                    reverse_sell_order_id = future_rev_sell.result(timeout=60)
                    self.logger.debug(f"Reverse Sell Order ID: {reverse_sell_order_id}")
                except Exception as e:
                    self.logger.error(f"逆指値売り注文中にエラーが発生しました: {e}")



             # 逆指値注文が発注された場合、それぞれの注文の約定を監視する
            if reverse_buy_order_id:
                while True:
                    time.sleep(1)  # ポーリング間隔を短縮
                    buy_status = self.get_order_status(reverse_buy_order_id).get("status")
                    self.logger.debug(f"Reverse Buy Order Status: {buy_status}")
                    if buy_status == "FILLED":
                        if reverse_sell_order_id:
                            self.logger.info(f"逆指値買い注文({reverse_buy_order_id})が約定しました。逆指値売り注文({reverse_sell_order_id})をキャンセルします。")
                            self.cancel_order(reverse_sell_order_id)
                        break
                    elif buy_status in ["CANCELED", "REJECTED"]:
                        self.logger.info(f"逆指値買い注文({reverse_buy_order_id})がキャンセルまたは拒否されました。")
                        break

            if reverse_sell_order_id:
                while True:
                    time.sleep(1)  # ポーリング間隔を短縮
                    sell_status = self.get_order_status(reverse_sell_order_id).get("status")
                    self.logger.debug(f"Reverse Sell Order Status: {sell_status}")
                    if sell_status == "FILLED":
                        if reverse_buy_order_id:
                            self.logger.info(f"逆指値売り注文({reverse_sell_order_id})が約定しました。逆指値買い注文({reverse_buy_order_id})をキャンセルします。")
                            self.cancel_order(reverse_buy_order_id)
                        break
                    elif sell_status in ["CANCELED", "REJECTED"]:
                        self.logger.info(f"逆指値売り注文({reverse_sell_order_id})がキャンセルまたは拒否されました。")
                        break
                    
            
                

        
        
        # time.sleep(1000)




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
                    # pprint.pprint(latest_order)
                    return latest_order
                else:
                    print(f"[DEBUG] 最新の{limit}件の注文: {latest_orders}")
                    # pprint.pprint(latest_orders)
                    return latest_orders

        except urllib.error.HTTPError as e:
            print(f"[ERROR] HTTPエラーが発生しました: {e}")
            try:
                content = json.loads(e.read())
                # pprint.pprint(content)
            except Exception:
                print("[ERROR] エラーレスポンスの解析に失敗しました。")
            return None
        except Exception as e:
            print(f"[ERROR] 注文履歴の取得中に例外が発生しました: {e}")
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
    逆指値
    """
    def reverse_limit_order(self, side, quantity, underover, limit_price):
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
                            'TriggerSec': 1, #1.発注銘柄 2.NK225指数 3.TOPIX指数
                            'TriggerPrice': limit_price,
                            'UnderOver': underover, #1.以下 2.以上
                            'AfterHitOrderType': 2, #1.成行 2.指値 3. 不成
                            'AfterHitPrice': limit_price  # 逆指値価格
                
            }
        }
        json_data = json.dumps(obj).encode('utf-8')
        url = f"{API_BASE_URL}/sendorder"
        req = urllib.request.Request(url, json_data, method='POST')
        req.add_header('Content-Type', 'application/json') 
        req.add_header('X-API-KEY', self.init.token)    

        try:
            with urllib.request.urlopen(req) as res:
                self.logger.info(f"逆指値注文送信成功: {res.status} {res.reason}")
                content = json.loads(res.read())
                return content
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