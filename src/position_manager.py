from initializations import trading_state

class PositionManager:
    def open_position(self, position_type: PositionType, price: Decimal, quantity: int):
        trading_state.quantity = quantity
        trading_state.signal_position = position_type.value
        
        if position_type in [PositionType.BUY, PositionType.SPECIAL_BUY]:
            trading_state.cash -= price * quantity
            trading_state.stock_value = price * quantity
            trading_state.buy_entry_price = price
        else:
            trading_state.sell_entry_price = price