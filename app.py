import json
import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv()
URL_WEBSOCKET_DECISION = os.getenv("URL_WEBSOCKET_DECISION", "ws://localhost:1122/decision/ws")
INVESTMENT_USD = os.getenv("INVESTMENT_USD", 10)

import sys
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_path)
from libs.trade import closed_current_position, created_order, count_quantity, calculate_stoploss, adjust_precision


async def listen():
    uri = URL_WEBSOCKET_DECISION
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        try:
            async for message in websocket:
                print("Raw message:", message)
                try:
                    data = json.loads(message)
                    print("Decoded message:", data)

                    current_price = data.get("current_price")
                    decision = data.get("decision")
                    predicted_result = data.get("predicted_result")
                    symbol = data.get("symbol")
                    timeframe = data.get("timeframe")
                    type_field = data.get("type")
                    
                    if decision in ["BUY", "SELL", "CLOSED"]:
                        try:
                            print("Closed")
                            closed_current_position(symbol)
                            # Close SL order luon
                        except Exception as e:
                            print(f"closed_current_position {e}")
                        
                        if decision != "CLOSED":
                            try:
                                quantity, step_size = count_quantity(INVESTMENT_USD, current_price, symbol)
                                print(quantity)
                            except Exception as e:
                                print(f"count_quantity {e}")
                                quantity = 0
                                step_size = 0
                                
                            try:
                                stopPrice = calculate_stoploss(current_price=current_price, side=decision)
                                try:
                                    stopPrice  = adjust_precision(stopPrice, step_size)
                                except Exception as e:
                                    print(f'stop_price {e}')
                                    
                            except Exception as e:
                                print(f"calculate_stoploss {e}")
                                stopPrice = 0
                                return
                                
                            try:
                                order = created_order(symbol, decision, quantity, stopPrice)
                            except Exception as e:
                                print(f"created_order {e}")
                        
                            print(f"Symbol: {symbol}, Current Price: {current_price}, Decision: {decision} stopPrice {stopPrice}")
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
        except websockets.exceptions.ConnectionClosed as e:
            print("Connection closed:", e)

if __name__ == '__main__':
    asyncio.run(listen())
