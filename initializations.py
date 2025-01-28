# initializations.py

import pandas as pd
import logging

class Initializations:
    def __init__(self):
        # API関連の設定
        self.token = None
        #ソフトバンク 156.8
        # self.symbol = "9434"
        
        #ETCインデックス 295~300
        # self.symbol = "1579"
        
        #NTT 156.8
        # self.symbol = "9432"
        
        #Gunosy 648
        # self.symbol = "6047"
        
        # 住友化学
        # self.symbol = "4005"
        
        # 総医研HD
        # 163
        # self.symbol = "2385"
        
        # アイフル
        # 323
        # self.symbol = "8515"
        
        # 福島銀行
        # 223
        # self.symbol = "8562"
        
        # 板硝子
        # 411
        # self.symbol = "5202"
        
        # 三菱自
        # 368
        # self.symbol = "7211"
        
        # 東京電力HD
        # 430
        # self.symbol = "9501"
        
        # 日本M＆A
        # 707.5
        self.symbol = "2127"
        
        self.exchange = 1
        self.api_base_url = "http://localhost:18080/kabusapi"
        self.order_password = "1995tAkA@@"

        # ロギングの設定
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # データフレームの初期化
        self.prices = []
        self.df = pd.DataFrame(columns=['open', 'high', 'low', 'close'])
        # ピボットポイントの初期化
        self.P = self.R1 = self.R2 = self.R3 = self.S1 = self.S2 = self.S3 = 0

        # 最新データの初期化
        self.latest_data = {
            'band_width': [],
            'hist': [],
            'di_difference': [],
            'adx_difference': []
        }
        self.latest_data_1 = {
            'band_width': [],
            'hist': [],
            'di_difference': [],
            'adx_difference': []
        }
        self.latest_data_2 = {
            'band_width': [],
            'hist': [],
            'di_difference': [],
            'adx_difference': []
        }

        # Sパラメータの初期化
        self.s_parameters = {
            'band_width': 0.000185,
            'hist': 0.00000185,
            'di_difference': 18.5,
            'adx_difference': 1.85
        }

        # interpolated_data の初期化
        self.interpolated_data = pd.DataFrame(columns=[
            'close', 'buy_and_hold_equity', 'trading_equity', 'cash', 'stock_value', 'quantity',
            'buy_signals', 'sell_signals',
            'hedge_buy_signals', 'hedge_sell_signals',
            'special_buy_signals', 'special_sell_signals', 
            'sell_exit_signals', 'buy_exit_signals',
            'emergency_buy_exit_signals', 'emergency_sell_exit_signals',
            'hedge_buy_exit_signals', 'hedge_sell_exit_signals',
            'special_buy_exit_signals', 'special_sell_exit_signals',
            'band_width', 'hist', 'di_difference', 'adx_difference',
            'band_width_diff', 'hist_diff', 'di_difference_diff', 'adx_difference_diff',
            'performance', 'fitted_values', 'trend_check_data', 'trend_check_data2',
            'P', 'R1', 'R2', 'R3', 'S1', 'S2', 'S3'  # ピボットポイントのカラム
        ])
        
        # ポジション管理の初期化
        # self.position = None
        self.position_entry_index = None
        self.entry_price = None
        self.buy_entry_price = None
        self.sell_entry_price = None

        # ポジション管理の初期化
        self.position_entry_index_prev = None
        self.entry_price_prev = None
        self.buy_entry_price_prev = None
        self.sell_entry_price_prev = None

        # Buy and Hold の初期設定
        self.first_balance = 50000.0  # 初期資金
        self.first_quantity = 0
        self.first_cash = self.first_balance
        self.first_price = 0.0
        self.initial_stock_value = 0

        # パフォーマンス計算の初期化
        self.cumulative_score = 0
        self.previous_cumulative_score = 0
        self.swap_signals = False

        # 前回パフォーマンス計算の初期化
        self.cumulative_score_prev = 0
        self.previous_cumulative_score_prev = 0
        self.swap_signals_prev = False


        # 特別シグナルの初期化
        self.special_sell_active = False
        self.special_buy_active = False
        self.signal_position = None
        self.signal_position1 = None
        self.signal_position2 = None
        self.signal_position_prev = None
        self.signal_position_prev2 = None
        self.signal_position1_prev = None
        self.signal_position1_prev2 = None
        self.signal_position2_prev = None
        self.signal_position2_prev2 = None

        # 前回の特別シグナルの初期化
        self.special_sell_active_prev = False
        self.special_buy_active_prev = False


        # 注文関連のパラメータの初期化
        self.security_type = 1  # 商品種別 (1: 株式)
        self.side = None        # 売買区分 (1: 売, 2: 買)
        self.cash_margin = 1    # 信用区分 (1: 現物)
        self.account_type = 4    # 口座種別 (4: 特定)
        self.qty = 0           # 注文数量
        self.front_order_type = 'MARKET'  # 執行条件
        self.price = None        # 注文価格 (指値の場合)
        self.expire_day = 0      # 注文有効期限 (0: 当日)

        # Trading の初期設定
        self.cash = self.first_balance
        self.quantity = 0
        self.stock_value = 0.0
        self.entry_price = 0.0

        # パフォーマンス計算用の変数
        self.performance_entry_price = 0
        self.performance_entry_type = None  # エントリータイプ ('buy' or 'sell')

        # エントリー価格を保持
        self.special_entry_price = 0.0
        self.original_entry_price = 0.0

        # 前回のエントリー価格を保持
        self.special_entry_price_prev = 0.0
        self.original_entry_price_prev = 0.0

        # 前回の特別シグナルのフラグ
        self.prev_special_sell_active = False
        self.prev_special_buy_active = False

        # 前回の前回の特別シグナルのフラグ
        self.prev_special_sell_active_prev = False
        self.prev_special_buy_active_prev = False

        # ★ 新たに追加する変数 ★
        self.previous_price = None  # 一つ前の価格
        self.current_price = None   # 現在の価格


        