from binance.um_futures import UMFutures
import os
import sys
import math

project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_path)

from libs.mysql_funcs import  handle_new_order, close_position, store_step_size, get_step_size, get_latest_order_history_stopmarket_status

import os
from dotenv import load_dotenv

load_dotenv()
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
INVESTMENT_USD = float(os.getenv("INVESTMENT_USD", 50))

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

    
def created_order(symbol, side, quantity, stopLossPrice=None):
    order = None
    try:
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )
        
        if order:
            try:
                handle_new_order(order)
                print(f"Save order in mysql {order.get("orderId")}")
            except Exception as e:
                print(f"handle_new_order new order failed {e}")
    except Exception as e:
        print(e)
        
    if stopLossPrice is not None:
        try:
            stop_side = "SELL" if side == "BUY" else "BUY"
            stop_order = client.new_order(
                symbol=symbol,
                side=stop_side,
                type="STOP_MARKET",
                quantity=quantity,
                stopPrice=stopLossPrice
            )
            print(f"✅ Stop order created: {stop_order}")
            
            try:
                handle_new_order(stop_order)
            except Exception as e:
                print(f"handle_new_order for stoploss order {e}")
                
        except Exception as e:
            print(f"SL error {e}")
    
    return order

def calculate_stoploss(current_price, leverage: float = 20, loss_percent: float = 80, side: str = "BUY") -> float:
    current_price = float(current_price)
    adverse_move = (loss_percent / 100) / leverage 
    
    if side == "BUY":
        stoploss = current_price * (1 - adverse_move)
    elif side == "SELL":
        stoploss = current_price * (1 + adverse_move)
    else:
        raise ValueError("Side must be either 'long' or 'short'")
    
    return stoploss

def adjust_precision(value, step_size):
    step_str = f"{step_size:.10f}"
    if '.' in step_str:
        decimals = step_str.split('.')[1].rstrip('0')
        precision = len(decimals)
    else:
        precision = 0
    return round(value, precision)

def count_quantity(investment_usd, current_price, symbol, leverage=20):
    try:
        balance_info = client.balance()
        usdt_balance = next((float(b["availableBalance"]) for b in balance_info if b["asset"] == "USDT"), 0)
    except Exception as e:
        print(f"❌ Error fetching balance: {e}")
        return
    
    try:
        investment_usd = float(investment_usd)
        current_price = float(current_price)
        leverage = int(leverage)
    except ValueError as e:
        print(f"❌ Invalid input data: {e}")
        return
    
    print(f"💰 USDT Balance: {usdt_balance}, 📈 Price: {current_price}, ⚡ Leverage: {leverage}")

    if usdt_balance < investment_usd:
        print(f"❌ Insufficient funds! Balance: {usdt_balance} USDT, required: {investment_usd} USDT")
        return

    try:
        step_size = get_step_size(symbol)
    except Exception as e:
        print(f"step_size {e}")
    
    quantity = (investment_usd * leverage) / current_price
    rquantity = max(math.floor(quantity / step_size) * step_size, step_size)

    if rquantity <= 0:
        print("❌ Invalid order quantity!")
        return
    
    print(f"✅ Calculated Quantity: {rquantity}")
    return rquantity, step_size

def closed_current_position(symbol):
    try:
        positions = client.get_position_risk(symbol=symbol)
        print("📌 Current Positions:", positions)
    except Exception as e:
        print(f"❌ Error fetching position risk: {e}")
        return

    for pos in positions:
        position_amt = float(pos["positionAmt"])
        position_side = pos.get("positionSide", "BOTH")
        if position_amt == 0:
            continue

        if position_side == "BOTH":
            close_side = "SELL" if position_amt > 0 else "BUY"
            position_side_param = None
        else:
            close_side = "SELL" if position_side == "LONG" else "BUY"
            position_side_param = position_side

        close_quantity = abs(position_amt)

        try:
            order_params = {
                "symbol": symbol,
                "side": close_side,
                "type": "MARKET",
                "quantity": close_quantity,
                "reduceOnly": True,
            }
            if position_side_param:
                order_params["positionSide"] = position_side_param

            print(f"⚡ Closing Position: {order_params}")

            close_order = client.new_order(**order_params)
            close_order["price"] = pos["markPrice"]
            print(f"Save mysql in closed order ")
            handle_new_order(close_order)

        except Exception as e:
            print(f"❌ Error closing position: {e}")
            return
        
        latest_sl_order = get_latest_order_history_stopmarket_status(symbol=symbol)
        print(f'lasted {latest_sl_order}')
        if latest_sl_order:
            try:
                cancel_response = client.cancel_order(
                    symbol=symbol,
                    orderId=latest_sl_order["order_id"]
                )
                print(f"✅ Stop order canceled: {cancel_response}")
            except Exception as e:
                print(f"❌ Error canceling stop order: {e}")
        else:
            print("No stop order to cancel.")

        try:
            close_position(symbol)
        except Exception as e:
            print(f"close position failed {e}")     


def init_step_size():
    data = client.exchange_info()
    store_step_size(data)
    
def get_step_size_by_symbol(symbol):
    return get_step_size(symbol)

