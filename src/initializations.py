from dataclasses import dataclass, field
from typing import Optional, List, Dict
from decimal import Decimal
import pandas as pd
import logging

@dataclass
class TradingState:
    # APIとトレーディング設定
    API_PASSWORD: str = "1995taka"
    ORDER_PASSWORD: str = "1995tAkA@@"
    SYMBOL: str = "1579"
    EXCHANGE: int = 1  # 東証プライム市場
    SLEEP_INTERVAL: float = 0.3
    
    # トレーディングパラメータ
    HEDGE_THRESHOLD: float = 0.00158
    EMERGENCY_THRESHOLD: float = 0.005
    POSITION_HOLD_PERIOD: int = 30
    EMERGENCY_POSITION_PERIOD: int = 60
    DEFAULT_QUANTITY: int = 100
    
    # 価格関連
    prices: List[float] = field(default_factory=list)
    buy_entry_price: Optional[Decimal] = None
    sell_entry_price: Optional[Decimal] = None
    original_entry_price: Decimal = Decimal('0')
    special_entry_price: Decimal = Decimal('0')
    
    # ポジション状態
    signal_position: Optional[str] = None
    signal_position_prev: Optional[str] = None
    signal_position_prev2: Optional[str] = None
    signal_position2: Optional[str] = None
    signal_position2_prev: Optional[str] = None
    signal_position2_prev2: Optional[str] = None
    
    # 資金管理
    cash: Decimal = Decimal('50000.0')
    stock_value: Decimal = Decimal('0')
    quantity: int = 0
    
    # データフレーム
    df: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    interpolated_data: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    
    # パフォーマンス計算用
    cumulative_score: int = 0
    previous_cumulative_score: int = 0
    cumulative_score_prev: int = 0
    previous_cumulative_score_prev: int = 0
    
    # ピボットポイント
    R1: Optional[float] = None
    R2: Optional[float] = None
    R3: Optional[float] = None
    S1: Optional[float] = None
    S2: Optional[float] = None
    S3: Optional[float] = None
    
    # その他の状態管理
    position_entry_index: Optional[int] = None
    swap_signals: bool = False
    special_sell_active: bool = False
    special_buy_active: bool = False
    prev_special_sell_active: bool = False
    prev_special_buy_active: bool = False
    
    # API関連
    token: Optional[str] = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger('TradingLogger'))
    
    def reset_signals(self):
        """シグナル関連の状態をリセットします"""
        self.signal_position = None
        self.signal_position2 = None
        self.buy_entry_price = None
        self.sell_entry_price = None
        self.special_entry_price = Decimal('0')
        self.quantity = 0
        
    def update_position_history(self):
        """ポジション履歴を更新します"""
        self.signal_position_prev2 = self.signal_position_prev
        self.signal_position_prev = self.signal_position
        self.signal_position2_prev2 = self.signal_position2_prev
        self.signal_position2_prev = self.signal_position2
        
    def calculate_trading_equity(self) -> Decimal:
        """現在のトレーディング資産を計算します"""
        return self.cash + self.stock_value

# グローバルな状態インスタンスを作成
trading_state = TradingState()