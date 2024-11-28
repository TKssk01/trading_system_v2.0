from initializations import trading_state

class SignalProcessor:
    def generate_signals(self) -> Dict[str, Any]:
        if trading_state.interpolated_data.empty:
            return {}
            
        current_price = Decimal(str(trading_state.interpolated_data.iloc[-1]['close']))
        signals = {}
        
        if trading_state.signal_position:
            signals.update(self._check_exit_signals(current_price))
        else:
            signals.update(self._check_entry_signals(current_price))
            
        return signals