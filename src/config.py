from dataclasses import dataclass
from typing import Optional, List
from decimal import Decimal

@dataclass
class Config:
    # API設定
    API_BASE_URL: str = "http://localhost:18080/kabusapi"
    API_PASSWORD: str = "1995taka"
    ORDER_PASSWORD: str = "1995tAkA@@"
    SYMBOL: str = "1579"
    EXCHANGE: int = 1
    
    # トレーディング設定
    SLEEP_INTERVAL: float = 0.3
    DEFAULT_QUANTITY: int = 100
    INITIAL_CASH: Decimal = Decimal('50000.0')
    
    # 価格データ
    prices: List[float] = None
    token: Optional[str] = None

    def __post_init__(self):
        self.prices = []

# グローバルなconfig インスタンスを作成
config = Config()