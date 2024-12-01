    def execute_orders(self):
        """
        シグナルに基づいて注文を実行します。
        """

        # 注文の側面を数値で定義
        SIDE_BUY = "2"
        SIDE_SELL = "1"

        # 売りと買いの総数量を辞書で初期化
        total_qty = {'buy': 0.0, 'sell': 0.0}
        # side の初期値を設定
        side = None 

        # ポジション情報を取得
        positions_dict = self.get_positions()
        # ポジション情報が空かNoneの場合はゼロと見なして処理を続行
        if not positions_dict:
            print("ポジションデータが空です。総数量をゼロとして処理を続行します。")
            positions_dict = []  # 空のリストとして扱う

        pprint.pprint(positions_dict)  # デバッグ用にポジション情報を表示

        # ポジション情報をループして総数量を集計
        for position in positions_dict:
            side = position.get('Side')
            qty = position.get('LeavesQty', 0)
            
            if side == '2':  # 買い
                total_qty['buy'] += qty
            elif side == '1':  # 売り
                total_qty['sell'] += qty
            else:
                print(f"不明なSideのポジションが存在します: {position}")

        # 集計結果を出力
        print(f"総買い数量: {total_qty['buy']}")
        print(f"総売り数量: {total_qty['sell']}")

        if self.init.interpolated_data is None or self.init.interpolated_data.empty:
            print("補間データが存在しません。注文の実行をスキップします。")
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
        hedge_buy_signal = self.init.interpolated_data.iloc[-1].get('hedge_buy_signals', 0)
        hedge_buy_exit_signal = self.init.interpolated_data.iloc[-1].get('hedge_buy_exit_signals', 0)
        hedge_sell_signal = self.init.interpolated_data.iloc[-1].get('hedge_sell_signals', 0)
        hedge_sell_exit_signal = self.init.interpolated_data.iloc[-1].get('hedge_sell_exit_signals', 0)
        special_buy_signal = self.init.interpolated_data.iloc[-1].get('special_buy_signals', 0)
        special_buy_exit_signal = self.init.interpolated_data.iloc[-1].get('special_buy_exit_signals', 0)
        special_sell_signal = self.init.interpolated_data.iloc[-1].get('special_sell_signals', 0)
        special_sell_exit_signal = self.init.interpolated_data.iloc[-1].get('special_sell_exit_signals', 0)

        
        # エグジットシグナルの処理（信用売りの買い戻し） - IOC 指値注文
        if sell_exit_signal == 1 and (side == "1" and total_qty['sell'] == 100):
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
                        time.sleep(0.5)
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)

        # ポジション情報を取得
        positions_dict = self.get_positions()

        if (emergency_sell_exit_signal == 1 and (side == "1" and total_qty['sell'] == 100)) or (hedge_sell_exit_signal == 1 and (self.init.signal_position_prev2 == 'hedge_sell' and side == "1" and total_qty['sell'] == 100)) or (special_sell_exit_signal == 1 and (self.init.signal_position_prev == 'special_sell' and side == "1" and total_qty['sell'] == 100)):  # 成行注文
            self.logger.info("売りエグジットシグナル（緊急または特別）が検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_pay_close_position_order(SIDE_BUY, quantity)
                if response:
                    self.logger.info(f"売りポジションを閉じる注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"売りポジションを閉じる注文に失敗しました: {e}")
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)  # 適切な遅延を設定

        # エグジットシグナルの処理（信用買いの売り） - IOC 指値注文
        if buy_exit_signal == 1 and (side == "2" and total_qty['buy'] == 100):
            self.logger.info("買いエグジットシグナルが検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            order_price = self.init.buy_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_SELL, quantity, order_price)              
                self.logger.info(f"IOC指値注文レスポンス: {response}")
                time.sleep(0.3)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.3)
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3) 

        if (emergency_buy_exit_signal == 1 and (side == "2" and total_qty['buy'] == 100)) or (hedge_buy_exit_signal == 1 and (self.init.signal_position_prev2 == 'hedge_buy' and side == "2" and total_qty['buy'] == 100)) or (special_buy_exit_signal == 1 and (self.init.signal_position_prev == 'special_buy' and side == "2" and total_qty['buy'] == 100)):
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)  # 適切な遅延を設定

        # エントリーシグナルの処理（信用売りの売り） - 成行注文
        if (hedge_sell_signal == 1 and (side == "2" and total_qty['buy'] == 100)) or special_sell_signal == 1:
            self.logger.info("売り特殊エントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_new_order(SIDE_SELL, quantity)
                # response = self.margin_new_order(SIDE_SELL, quantity)
                if response:
                    self.logger.info(f"売りポジションをオープンする成行注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"売りポジションをオープンする成行注文に失敗しました: {e}")
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)  # 適切な遅延を設定

        # エントリーシグナルの処理（信用売りの売り） - 成行注文
        if (hedge_buy_signal == 1 and (side == "1" and total_qty['sell'] == 100)) or special_buy_signal == 1:
            self.logger.info("売り特殊エントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_new_order(SIDE_BUY, quantity)
                # response = self.margin_new_order(SIDE_SELL, quantity)
                if response:
                    self.logger.info(f"売りポジションをオープンする成行注文を送信しました。数量: {quantity}")
            except Exception as e:
                self.logger.error(f"売りポジションをオープンする成行注文に失敗しました: {e}")
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3) 

        # print('side')
        # print(side)
        # time.sleep(20)

        # エントリーシグナルの処理（信用売り） - IOC指値注文
        if sell_signal == 1 and (not positions_dict or positions_dict[-1].get('LeavesQty', 0) == 0):
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)

        # buy_signal の処理（信用買い） - IOC指値注文
        if buy_signal == 1 and (not positions_dict or positions_dict[-1].get('LeavesQty', 0) == 0):
            self.logger.info("買いエントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            order_price = self.init.buy_entry_price
            try:
                response = self.margin_new_ioc_order(SIDE_BUY, quantity, order_price)
                self.logger.info(f"IOC指値注文レスポンス: {response}")
                time.sleep(0.5)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.5)

                print(latest_order)
                time.sleep(100)

                # 最新の詳細情報からRecTypeをチェック
                if latest_order and 'Details' in latest_order:
                    details = latest_order['Details']
                    if details:
                        # 最新の詳細情報を取得（必要に応じてソート）
                        latest_detail = details[-1]
                        rec_type = latest_detail.get('RecType')
                        time.sleep(0.5)
                        if rec_type in (3, 7):
                            # リセット処理を実行
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals(current_index)
                            self.logger.info(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")
                            time.sleep(0.5)
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
                    self.logger.warning(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)






    def execute_orders(self):
        """
        シグナルに基づいて注文を実行します。
        """

        # 注文の側面を数値で定義
        SIDE_BUY = "2"
        SIDE_SELL = "1"

        # 売りと買いの総数量を辞書で初期化
        total_qty = {'buy': 0.0, 'sell': 0.0}
        # side の初期値を設定
        side = None 

        # ポジション情報を取得
        positions_dict = self.get_positions()
        # ポジション情報が空かNoneの場合はゼロと見なして処理を続行
        if not positions_dict:
            print("ポジションデータが空です。総数量をゼロとして処理を続行します。")
            positions_dict = []  # 空のリストとして扱う

        pprint.pprint(positions_dict)  # デバッグ用にポジション情報を表示

        # ポジション情報をループして総数量を集計
        for position in positions_dict:
            side = position.get('Side')
            qty = position.get('LeavesQty', 0)
            
            if side == '2':  # 買い
                total_qty['buy'] += qty
            elif side == '1':  # 売り
                total_qty['sell'] += qty
            else:
                print(f"不明なSideのポジションが存在します: {position}")

        # 集計結果を出力
        print(f"総買い数量: {total_qty['buy']}")
        print(f"総売り数量: {total_qty['sell']}")

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
            print("買いシグナルが検出されました。逆指値の買い注文を発行します。")
            quantity = 100  # 適切な数量に置き換える
            limit_price = self.init.buy_limit_price  # リミット価格を設定
            trigger_price = self.init.buy_trigger_price  # トリガー価格を設定
            order_price = self.buy_entry_price
            response = self.margin_new_reverse_limit_order(SIDE_BUY, quantity, order_price)
            if response and response.get('Result') == 0:
                print(f"逆指値買い注文が成功しました。OrderId: {response.get('OrderId')}")
            else:
                print("逆指値買い注文に失敗しました。")

            print("売りシグナルが検出されました。逆指値の売り注文を発行します。")
            quantity = 100  # 適切な数量に置き換える
            limit_price = self.init.sell_limit_price  # リミット価格を設定
            trigger_price = self.init.sell_trigger_price  # トリガー価格を設定
            order_price = self.buy_entry_price
            response = self.margin_new_reverse_limit_order(SIDE_SELL, quantity, order_price)
            if response and response.get('Result') == 0:
                print(f"逆指値売り注文が成功しました。OrderId: {response.get('OrderId')}")
            else:
                print("逆指値売り注文に失敗しました。")

        # 2. 市場価格の変動を検知
        current_price = self.trading_data.fetch_current_price()
        previous_price = self.trading_data.get_previous_price()
        price_change = current_price - previous_price

        print(f"現在の価格: {current_price}, 前回の価格: {previous_price}, 変動量: {price_change}")

        # 価格変動の閾値（例: 0.1円）
        price_threshold = 0.1

        if abs(price_change) >= price_threshold:
            print("[INFO] 価格変動が閾値を超えました。新規シグナルを発行します。")

            # 最新の2つの注文を取得
            params = {'product': 2, 'details': 'false'}
            latest_orders_response = self.order_manager.get_orders(params=params, limit=2)
            if latest_orders_response:
                # latest_orders_responseがリストでない場合はリストに変換
                latest_orders = latest_orders_response if isinstance(latest_orders_response, list) else [latest_orders_response]
                pprint.pprint(latest_orders)  # デバッグ用に最新注文を表示
            else:
                latest_orders = []
                print("[ERROR] 最新の注文情報の取得に失敗しました。")

            # シグナルを同時に発行
            if price_change > 0:
                # 売り方向の変動
                self.trading_data.set_signal('reverse_sell_repayment', 1)
                print("[INFO] 逆指値の売り返済シグナルを発行しました。")

                # 最新の2つの注文をキャンセル
                for order in latest_orders:
                    order_id = order.get('OrderID')
                    side = order.get('Side')  # '1' = 売, '2' = 買 と仮定
                    if side == SIDE_SELL and order_id:
                        self.order_manager.cancel_order(order_id)
                        self.trading_data.reset_signals(current_index)
                        print(f"[INFO] 売り注文 {order_id} をキャンセルしました。")
                    elif side == SIDE_BUY and order_id:
                        self.order_manager.cancel_order(order_id)
                        self.trading_data.reset_signals(current_index)
                        print(f"[INFO] 買い注文 {order_id} をキャンセルしました。")

            elif price_change < 0:
                # 買い方向の変動
                self.trading_data.set_signal('reverse_buy_repayment', 1)
                print("[INFO] 逆指値の買い返済シグナルを発行しました。")

                # 最新の2つの注文をキャンセル
                for order in latest_orders:
                    order_id = get_orders('OrderID')
                    side = order.get('Side')  # '1' = 売, '2' = 買 と仮定
                    if side == SIDE_BUY and order_id:
                        self.cancel_order(order_id)
                        self.trading_data.reset_signals(current_index)
                        print(f"[INFO] 買い注文 {order_id} をキャンセルしました。")
                    elif side == SIDE_SELL and order_id:
                        self.cancel_order(order_id)
                        self.trading_data.reset_signals(current_index)
                        print(f"[INFO] 売り注文 {order_id} をキャンセルしました。")
                # 価格変動後のシグナルの評価
                if price_change > 0:
                    print("[INFO] 価格が上昇方向に変動しました。売りシグナルを継続します。")
                    # 売りシグナルを継続するための追加処理があればここに記述
                elif price_change < 0:
                    print("[INFO] 価格が下降方向に変動しました。買いシグナルをキャンセルします。")
                    # 買いシグナルをキャンセル
                    self.trading_data.set_signal('reverse_buy_repayment', 0)
                    print("[INFO] 逆指値の買い返済シグナルをキャンセルしました。")

                    # キャンセル処理
                    self.cancel_order(order_id)
                    self.trading_data.reset_signals(current_index)

                # 価格のさらなる変動をチェック
                new_price = self.trading_data.fetch_current_price()
                print(f"新しい価格: {new_price}")

                if new_price > current_price:
                    print("[INFO] 価格がさらに上昇しました。既存のシステムに制御を委ねます。")
                    # 既存のシステムに制御を委ねるための追加処理があればここに記述
                elif new_price < current_price:
                    print("[INFO] 価格がさらに下降しました。新しい売買シグナルを発行します。")
                    # 再帰呼び出しで新しいシグナルを処理
                    if recursion_depth < max_recursion:
                        self.execute_orders(recursion_depth=recursion_depth + 1, max_recursion=max_recursion)
                    else:
                        print("[WARNING] 再帰の最大深度に達しました。処理を中断します。")
            else:
                print("[INFO] 価格変動が閾値未満のため、シグナルを発行しません。")







        # エグジットシグナルの処理（信用売りの買い戻し） - IOC 指値注文
        if sell_exit_signal == 1 and (side == "1" and total_qty['sell'] == 100):
            print("売りエグジットシグナルが検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            order_price = self.init.sell_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_BUY, quantity, order_price)
                print(f"IOC指値注文レスポンス: {response}")
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
                            # リセット処理を実行
                            current_index = self.init.interpolated_data.index[-1]
                            self.trading_data.reset_signals_2(current_index)
                            print(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")
                            time.sleep(1)
                        else:
                            print(f"RecTypeは{rec_type}です。リセットは不要です。")
                    else:
                        print("最新の注文にDetailsが存在しません。")
                else:
                    print("最新の注文情報が取得できませんでした。")
            except Exception as e:
                # スタックトレースをログに出力
                print(f"売りポジションをクローズするIOC指値注文に失敗しました: {e}")
                traceback_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
                print(f"スタックトレース:\n{traceback_str}")

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
                    print(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3)

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
            print("買いエグジットシグナルが検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            order_price = self.init.buy_entry_price
            try:
                response = self.margin_ioc_exit_order(SIDE_SELL, quantity, order_price)              
                print(f"IOC指値注文レスポンス: {response}")
                time.sleep(0.3)              
                # 注文を送信し、最新の注文を取得した後
                latest_order = self.get_orders()
                time.sleep(0.3)
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
                            print(f"RecTypeが{rec_type}のため、シグナルをリセットしました。OrderId: {latest_order.get('OrderId')}")
                            time.sleep(1)
                        else:
                            print(f"RecTypeは{rec_type}です。リセットは不要です。")
                    else:
                        print("最新の注文にDetailsが存在しません。")
                else:
                    print("最新の注文情報が取得できませんでした。")
            except Exception as e:
                # スタックトレースをログに出力
                print(f"買いポジションをクローズするIOC指値注文に失敗しました: {e}")
                traceback_str = ''.join(traceback.format_exception(None, e, e.__traceback__))
                print(f"スタックトレース:\n{traceback_str}")

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
                    print(f"不明なSideのポジションが存在します: {position}")
            time.sleep(0.3) 

        # 最後のシグナル処理部分を置き換え
        # 例:
        if (emergency_buy_exit_signal == 1 and (side == "2" and total_qty['buy'] == 100)) or \
        (hedge_buy_exit_signal == 1 and (self.init.signal_position_prev2 == 'hedge_buy' and side == "2" and total_qty['buy'] == 100)) or \
        (special_buy_exit_signal == 1 and (self.init.signal_position_prev == 'special_buy' and side == "2" and total_qty['buy'] == 100)):
            print("買いエグジットシグナル（緊急または特別）が検出されました。ポジションを閉じます。")
            # quantity = self.init.quantity  # 実際のポジション数量を使用
            quantity = 100  # 固定値として設定
            try:
                # time.sleep(10)
                response = self.margin_pay_close_position_order(SIDE_SELL, quantity)
                if response:
                    print(f"買いポジションを閉じる注文を送信しました。数量: {quantity}")
            except Exception as e:
                print(f"買いポジションを閉じる注文に失敗しました: {e}")
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

        # エントリーシグナルの処理（信用売りの売り） - 成行注文
        if (hedge_sell_signal == 1 and (side == "2" and total_qty['buy'] == 100)) or special_sell_signal == 1:
            print("売り特殊エントリーシグナルが検出されました。新規ポジションをオープンします。")
            quantity = 100  # 固定値として設定
            try:
                response = self.margin_new_order(SIDE_SELL, quantity)
                # response = self.margin_new_order(SIDE_SELL, quantity)
                if response:
                    print(f"売りポジションをオープンする成行注文を送信しました。数量: {quantity}")
            except Exception as e:
                print(f"売りポジションをオープンする成行注文に失敗しました: {e}")
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