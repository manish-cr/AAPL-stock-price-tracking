# trading_analysis.py
import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
import os
from pathlib import Path

# --- Configuration ---
# Load environment variables
env_paths = [
    Path(__file__).parent.parent / "config" / ".env",  # ../config/.env
    Path.home() / ".alpaca.env",  # ~/.alpaca.env
    ".env"  # Current directory
]

for path in env_paths:
    if path.exists():
        load_dotenv(path)
        break
else:
    raise FileNotFoundError("No .env file found")

API_KEY_ID = os.getenv('API_KEY')
API_SECRET_KEY = os.getenv('SECRET_KEY')
BASE_URL = "https://data.alpaca.markets/v2"
ENDPOINT = "/stocks/trades"

headers = {
    "APCA-API-KEY-ID": API_KEY_ID,
    "APCA-API-SECRET-KEY": API_SECRET_KEY,
}

# --- Core Functions ---
def fetch_all_trades(symbol: str, start: datetime, end: datetime) -> list:
    """Fetch all trades with pagination handling"""
    all_trades = []
    params = {
        "symbols": symbol,
        "start": start.isoformat() + "Z",
        "end": end.isoformat() + "Z",
        "limit": 10000,
        "feed": "sip",
        "sort": "asc"
    }
    
    while True:
        response = requests.get(BASE_URL + ENDPOINT, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code} - {response.text}")
            break
            
        data = response.json()
        all_trades.extend(data["trades"][symbol])
        
        if "next_page_token" in data and data["next_page_token"]:
            params["page_token"] = data["next_page_token"]
        else:
            break
            
    return all_trades

def process_to_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Convert raw trades to OHLC with technical indicators"""
    # Resample to 1-minute OHLC
    ohlc = df.set_index('Timestamp').resample('1T').agg({
        'Price': ['first', 'max', 'min', 'last']
    })
    ohlc.columns = ['Open', 'High', 'Low', 'Close']
    
    # Add volume
    volume = df.set_index('Timestamp').resample('1T')['Size'].sum()
    ohlc = ohlc.merge(volume.rename('Volume'), left_index=True, right_index=True)
    
    # Technical indicators
    ohlc['VWAP'] = (ohlc['Close'] * ohlc['Volume']).cumsum() / ohlc['Volume'].cumsum()
    ohlc['Donchian_High'] = ohlc['High'].rolling(20).max()
    ohlc['Donchian_Low'] = ohlc['Low'].rolling(20).min()
    
    return ohlc

def create_plot(ohlc: pd.DataFrame) -> go.Figure:
    """Generate interactive Plotly chart"""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.05,
                       row_heights=[0.7, 0.3])

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=ohlc.index,
        open=ohlc['Open'],
        high=ohlc['High'],
        low=ohlc['Low'],
        close=ohlc['Close'],
        name='Price',
        increasing_line_color='green',
        decreasing_line_color='red'
    ), row=1, col=1)
    
    # Indicators
    fig.add_trace(go.Scatter(
        x=ohlc.index, y=ohlc['VWAP'], 
        line=dict(color='cyan'), name='VWAP'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=ohlc.index, y=ohlc['Donchian_High'],
        line=dict(color='blue', dash='dot'), name='Donchian High'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=ohlc.index, y=ohlc['Donchian_Low'],
        line=dict(color='blue', dash='dot'), name='Donchian Low'
    ), row=1, col=1)
    
    # Volume
    fig.add_trace(go.Bar(
        x=ohlc.index, y=ohlc['Volume'],
        name='Volume',
        marker_color='rgba(100, 100, 255, 0.4)'
    ), row=2, col=1)
    
    # Layout
    fig.update_layout(
        title='AAPL Trading Analysis',
        height=800,
        template='plotly_white',
        xaxis_rangeslider_visible=False
    )
    
    return fig

# --- Main Execution ---
if __name__ == "__main__":
    # 1. Fetch data
    end_time = datetime.now() - timedelta(days=2)
    start_time = end_time - timedelta(days=1)
    
    print(f"Fetching trades from {start_time} to {end_time}")
    trades = fetch_all_trades("AAPL", start_time, end_time)
    
    # 2. Process data
    df = pd.DataFrame([{
        "Timestamp": pd.to_datetime(trade["t"]).tz_localize(None),
        "Price": trade["p"],
        "Size": trade["s"],
        "Conditions": ",".join(trade["c"])
    } for trade in trades])
    
    df = df.sort_values("Timestamp").reset_index(drop=True)
    ohlc = process_to_ohlc(df)
    
    # 3. Visualize
    fig = create_plot(ohlc)
    fig.show()
    
    # 4. Save outputs
    fig.write_html("trading_analysis.html")
    ohlc.to_csv("data/ohlc_data.csv")
    print("Saved results to trading_analysis.html and ohlc_data.csv")