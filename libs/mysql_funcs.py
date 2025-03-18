import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "quant_trading_binance")

try:
    db = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = db.cursor()
    print("✅ Connected to MySQL!")
except mysql.connector.Error as err:
    print(f"❌ Error connecting to MySQL: {err}")
    exit(1)

# Create database if not exists
try:
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    print(f"✅ Database '{DB_NAME}' is ready!")
except mysql.connector.Error as err:
    print(f"❌ Error creating database: {err}")
    exit(1)

# Reconnect to MySQL with the newly created database
db = mysql.connector.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = db.cursor()

def setup_database():
    """Function to migrate database tables."""
    try:
        queries = [
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(20) UNIQUE NOT NULL,
                status VARCHAR(20),  -- OPEN, CLOSED, REVERSING
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS order_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(20) DEFAULT 'UNKNOWN',
                order_id BIGINT,
                side VARCHAR(10) DEFAULT 'UNKNOWN',
                type VARCHAR(20) DEFAULT 'MARKET',
                quantity DECIMAL(18,8) DEFAULT 0,
                price DECIMAL(18,8) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'UNKNOWN',  -- FILLED, CANCELED, PARTIALLY_FILLED
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS symbol_step_sizes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(50) UNIQUE NOT NULL,
                step_size DECIMAL(18,8) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """
        ]

        for query in queries:
            cursor.execute(query)
        
        db.commit()
        print("✅ Database setup completed successfully!")

    except mysql.connector.Error as err:
        print(f"❌ Error in setup: {err}")

def save_order_history(order):
    sql = """
        INSERT INTO order_history (symbol, order_id, side, type, quantity, price, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        order.get("symbol") or "UNKNOWN",
        order.get("orderId") or 0,
        order.get("side") or "UNKNOWN",
        order.get("type") or "MARKET",
        float(order.get("origQty") or 0),
        float(order.get("price") or 0),
        order.get("status") or "UNKNOWN",
    )
    cursor.execute(sql, values)
    db.commit()

def get_latest_order(symbol):
    query = """
    SELECT * FROM orders_system_histories 
    WHERE symbol = %s 
    ORDER BY created_at DESC 
    LIMIT 1
    """
    cursor.execute(query, (symbol,))
    return cursor.fetchone()

def insert_order_if_needed(symbol, decision_type, price)-> bool:
    latest_order = get_latest_order(symbol)
    flag = False

    if not latest_order or latest_order["type"] != decision_type:
        query = """
        INSERT INTO orders_system_histories (symbol, type, price) 
        VALUES (%s, %s, %s)
        """
        cursor.execute(query, (symbol, decision_type, price))
        db.commit()
        flag = True
        print(f"✅ New order inserted: {symbol} - {decision_type} - {price}")
        
    return flag

def update_order_status(symbol, status):
    try:
        sql = """
            INSERT INTO orders (symbol, status, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE 
                status = VALUES(status), 
                updated_at = CURRENT_TIMESTAMP
        """
        values = (symbol, status)
        
        cursor.execute(sql, values)
        db.commit()
        print(f"✅ Order {symbol} updated successfully with status: {status}")

    except Exception as e:
        print(f"❌ Error updating order status for {symbol}: {e}")


def close_position(symbol):
    update_order_status(symbol, "CLOSED")
    
def handle_new_order(order):
    try:
        save_order_history(order) 
    except Exception as e:
        print(f"❌ Error saving order history: {e}")
        return

    try:
        update_order_status(order.get("symbol"), order.get("side"))
    except KeyError as e:
        print(f"❌ Missing order data: {e} - {order}")
    except Exception as e:
        print(f"❌ Error updating order status: {e}")


def get_current_status(symbol):
    try:
        cursor.execute("SELECT status FROM orders WHERE symbol = %s", (symbol,))
        result = cursor.fetchone()
        current_status = result["status"] if result else None
        return current_status
    except mysql.connector.Error as err:
        print(f"❌ Lỗi DB khi lấy trạng thái: {err}")
        return
    

def store_step_size(data):
    for s in data["symbols"]:
        symbol = s["symbol"]
        step_size = None
        for f in s["filters"]:
            if f["filterType"] == "LOT_SIZE":
                step_size = f["stepSize"]
                break

        if step_size:
            query = """
            INSERT INTO symbol_step_sizes (symbol, step_size) 
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE step_size = VALUES(step_size), updated_at = CURRENT_TIMESTAMP
            """
            cursor.execute(query, (symbol, step_size))
            db.commit()
            print(f"✅ {symbol} - step_size: {step_size} inserted/updated")

    cursor.close()
    db.close()
    
def get_step_size(symbol):
    query = "SELECT step_size FROM symbol_step_sizes WHERE symbol = %s"
    cursor.execute(query, (symbol,))
    result = cursor.fetchone()
    return float(result["step_size"]) if result else None
