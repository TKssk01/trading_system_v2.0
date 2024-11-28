# HTTPリクエストを送信するためのライブラリをインポート
import requests
# 型ヒントのためにOptionalをインポート
from typing import Optional
# 設定情報を含むconfigモジュールをインポート
from config import config

class APIClient:
    def __init__(self):
        # configモジュールから設定を初期化
        self.config = config
    async def fetch_price(self) -> Optional[float]:
        """最新の価格をAPIから取得"""
        # APIのボードエンドポイントのURLを構築
        board_url = f"{self.config.API_BASE_URL}/board/{self.config.SYMBOL}@{self.config.EXCHANGE}"
        # 認証用ヘッダーを設定
        headers = {'X-API-KEY': self.config.token}
        try:
            # GETリクエストを送信
            response = requests.get(board_url, headers=headers)
            # レスポンスが成功の場合
            if response.status_code == 200:
                # レスポンスをJSONとして解析
                board = response.json()
                # 現在の価格を取得
                current_price = board.get('CurrentPrice')
                # 現在の価格が存在する場合
                if current_price is not None:
                    # 価格リストに追加
                    self.config.prices.append(current_price)
                    # 現在の価格を返す
                    return current_price
                # 現在の価格がない場合はNoneを返す
                return None
            # ステータスコードが200でない場合はNoneを返す
            return None
        except requests.exceptions.RequestException:
            # リクエスト中に例外が発生した場合はNoneを返す
            return None

    async def send_order(self, order_data: dict) -> Optional[dict]:
        """注文の送信"""
        # 注文送信エンドポイントのURLを構築
        url = f"{self.config.API_BASE_URL}/sendorder"
        # リクエストヘッダーを設定
        headers = {
            # コンテンツタイプをJSONに設定
            'Content-Type': 'application/json',
            # 認証用のAPIキーをヘッダーに設定
            'X-API-KEY': self.config.token
        }
        try:
            # POSTリクエストを送信
            response = requests.post(url, headers=headers, json=order_data)
            # ステータスコードがエラーの場合例外を発生させる
            response.raise_for_status()
            # レスポンスをJSONとして返す
            return response.json()
        except Exception:
            # リクエスト中に例外が発生した場合はNoneを返す
            return None
