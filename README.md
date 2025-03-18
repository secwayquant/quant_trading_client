# quant_trading_client

## Requirements
```
Python 3.12
MySQL >= 8
```

## Setup
### Install Python 3.12 and pip
On Ubuntu/Debian:
```
sudo apt update && sudo apt install python3.12 python3-pip -y
```
On macOS (using Homebrew):
```
brew install python@3.12
```
On Windows:
- Download and install Python 3.12 from [python.org](https://www.python.org/downloads/)
- Ensure `pip` is installed by running:
  ```
  python -m ensurepip --default-pip
  ```

### Install MySQL 8.0
On Ubuntu/Debian:
```
sudo apt update && sudo apt install mysql-server -y
```
On macOS (using Homebrew):
```
brew install mysql@8.0
```
On Windows:
- Download and install MySQL 8.0 from [MySQL Downloads](https://dev.mysql.com/downloads/installer/)
- Follow the setup instructions to configure MySQL.

### Install dependencies
```
pip install -r requirements.txt
```

### Run the setup script
```
python setup.py
```

### Get your public IPv4 address
Visit: [WhatIsMyIP](https://www.whatismyip.com/)

### Enable Futures Trading on Binance
1. Go to **Account > API Management**
2. Create a new API key
3. Enable **Futures Trading**
4. Restrict access to **trusted IPs only** (Recommended) and add your IPv4

### Configure Environment Variables
Copy `.env.example` to `.env` and update the values:
```
# Binance API Config
BINANCE_API_KEY="your_api_key_here"
BINANCE_SECRET_KEY="your_secret_key_here"

# Trading Config
INVESTMENT_USD=10  # Amount in USD to invest per trade

# Database Config
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=

# WebSocket Decision URL
URL_WEBSOCKET_DECISION=get from coinlog wss url
```

## Run the application
```
python app.py
```

