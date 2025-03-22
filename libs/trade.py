from binance.um_futures import UMFutures
import os
import sys
import math

project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_path)

from libs.mysql_funcs import  handle_new_order, close_position, get_current_status, store_step_size, get_step_size

import os
from dotenv import load_dotenv

load_dotenv()
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
INVESTMENT_USD = float(os.getenv("INVESTMENT_USD", 50))

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def reverse_or_create_order(symbol, current_price, default_side="BUY", investment_usd=10, new_order=False):
    try:
        balance_info = client.balance()
        usdt_balance = next((float(b["availableBalance"]) for b in balance_info if b["asset"] == "USDT"), 0)
    except Exception as e:
        print(f"❌ Error fetching balance: {e}")
        return

    if usdt_balance < investment_usd:
        print(f"❌ Insufficient funds! Balance: {usdt_balance} USDT, required: {investment_usd} USDT")
        return

    try:
        current_price = float(current_price)
    except Exception as e:
        print(f"❌ Error fetching price: {e}")
        return

    quantity = round(investment_usd / current_price, 6)
    if quantity <= 0:
        print("❌ Invalid order quantity!")
        return
    
    if new_order is False:
        try:
            positions = client.get_position_risk(symbol=symbol)
            print(positions)
        except Exception as e:
            print(f"❌ Error fetching position: {e}")
            return

        for pos in positions:
            if float(pos["positionAmt"]) != 0:
                position_amt = abs(float(pos["positionAmt"]))
                current_side = "BUY" if pos["positionSide"] == "LONG" else "SELL"
                reverse_side = "SELL" if current_side == "BUY" else "BUY"

                try:
                    close_order = client.new_order(symbol=symbol, side=reverse_side, type="MARKET", quantity=position_amt)
                    print(f"🔴 Closed position: {close_order}")
                    handle_new_order(close_order)
                    close_position(symbol)

                    reverse_order = client.new_order(symbol=symbol, side=current_side, type="MARKET", quantity=position_amt)
                    print(f"🟢 Opened reverse position: {reverse_order}")
                    handle_new_order(reverse_order)
                except Exception as e:
                    print(f"❌ Order placement error: {e}")
                return

    try:
        new_order = client.new_order(symbol=symbol, side=default_side, type="MARKET", quantity=quantity)
        print(f"🟢 Created new order: {new_order}")
        handle_new_order(new_order)
    except Exception as e:
        print(f"❌ Error placing new order: {e}")


def handle_signal(symbol, signal, current_price):
    """Process trading signals based on current status"""
    try:
        current_status = get_current_status(symbol)
    except:
        print("❌ Error fetching current status")
        return None

    size = None
    try:
        positions = client.get_position_risk(symbol=symbol)
        for pos in positions:
            position_amt = float(pos["positionAmt"])
            if position_amt != 0:
                size = "SELL" if position_amt < 0 else "BUY"
    except Exception as e:
        print(f"get_position_risk failed {e}")
        
    
    if current_status is not None or size is not None:
        if signal == 1 and (current_status == "BUY" or size == "BUY"):
            print(f"✅ [BUY] Already in a BUY order, no action needed.")
            return

        if signal == -1 and (current_status == "SELL" or size == "SELL"):
            print(f"✅ [SELL] Already in a SELL order, no action needed.")
            return

        if signal == 0:
            print(f"⚠️ [CANCEL] Closing order for {symbol}")
            try:
                positions = client.get_position_risk(symbol=symbol)
                for pos in positions:
                    position_amt = float(pos["positionAmt"])
                    if position_amt != 0:
                        close_side = "SELL" if pos["positionSide"] == "LONG" else "BUY"
                        close_quantity = abs(position_amt)

                        close_order = client.new_order(
                            symbol=symbol,
                            side=close_side,
                            type="MARKET",
                            quantity=close_quantity
                        )
                        print(f"🔴 Closed position: {close_order}")
                        handle_new_order(close_order)

                close_position(symbol)
            except Exception as e:
                print(f"❌ Error closing position: {e}")
            return

        if (signal == 1 and current_status == "SELL") or (signal == -1 and current_status == "BUY"):
            print(f"🔄 [REVERSE] Reversing order for {symbol}")
            reverse_or_create_order(symbol, current_price)
            return
    else:
        if signal == 1:
            print(f"📈 [BUY] Opening BUY order for {symbol}")
            reverse_or_create_order(symbol, current_price, default_side="BUY", new_order=True)
            return

        if signal == -1:
            print(f"📉 [SELL] Opening SELL order for {symbol}")
            reverse_or_create_order(symbol, current_price, default_side="SELL", new_order=True)
            return

    print("❌ [ERROR] Invalid signal!")
    
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


def created_order(symbol, side, quantity, stopPrice):
    order = None
    try:
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
        )
    except Exception as e:
        print(f"new_order {e}")
        return None
        
    # SL
    try:
        stop_side = "SELL" if side == "BUY" else "BUY"
        stop_order = client.new_order(
            symbol=symbol,
            side=stop_side,
            type="STOP_MARKET",
            quantity=quantity,
            stopPrice=stopPrice
        )
        print(f"✅ Stop order created: {stop_order}")
    except Exception as e:
        print(f"SL error {e}")
        
    if order:
        print(order)
        try:
            order_info = client.get_orders(symbol=symbol, orderId=order.get("orderId"))
            filled_price = float(order_info["avgPrice"])
            order["price"] = filled_price
            order["stop_price"] = stopPrice

            handle_new_order(order)
        except Exception as e:
            print(f"handle_new_order {e}")
    
    return order

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
            handle_new_order(close_order)

        except Exception as e:
            print(f"❌ Error closing position: {e}")
            return
        
        try:
            close_position(symbol)
        except Exception as e:
            print(f"close position failed {e}")     


def init_step_size():
    data = client.exchange_info()
    store_step_size(data)
    
def get_step_size_by_symbol(symbol):
    return get_step_size(symbol)

# 🛠️ Test the function
if __name__ == '__main__':
    handle_signal("BTCUSDT", 1)
