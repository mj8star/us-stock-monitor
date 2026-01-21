# /// script
# dependencies = [
#   "yfinance",
#   "pandas",
#   "streamlit",
#   "plotly",
# ]
# ///

import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# 配置监控名单
INDICES = {
    '^GSPC': '标普500',
    '^IXIC': '纳斯达克100',
    '^RUT': '罗素2000'
}
WATCH_LIST = ['QQQ', 'VOO', 'AAPL', 'TSLA', 'NVDA', 'QCOM', 'SMCI', 'AMD', 'CRWV', 'TSM', 'TSLA', 'UNH', 'NFLX', 'GTLB', 'MP', 'SOFI', 'BMR', 'AI', 'AMBQ', 'META', 'HIMS', 'RKLB', 'SNDK'] # 可自行添加ETF和个股

class StockDB:
    def __init__(self, db_name='stocks.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        """初始化数据库表结构"""
        query = '''
        CREATE TABLE IF NOT EXISTS daily_quotes (
            symbol TEXT,
            date TEXT,
            close REAL,
            pct_change REAL,
            volume REAL,
            amount REAL,
            turnover REAL,
            amplitude REAL,
            vol_ratio REAL,
            pe_ratio REAL,
            PRIMARY KEY (symbol, date)
        )
        '''
        self.conn.execute(query)
        self.conn.commit()

    def fetch_data(self, symbols, period="max", start=None, end=None):
        """采集并计算指标"""
        for symbol in symbols:
            print(f"正在采集: {symbol}...")
            ticker = yf.Ticker(symbol)
            # 获取历史数据
            df = ticker.history(period=period, start=start, end=end)
            if df.empty: continue
            
            # 基础指标计算
            df['pct_change'] = df['Close'].pct_change() * 100
            df['amplitude'] = (df['High'] - df['Low']) / df['Close'].shift(1) * 100
            df['amount'] = df['Close'] * df['Volume']
            
            # 量比计算 (当日成交量 / 过去5日平均成交量)
            df['vol_ratio'] = df['Volume'] / df['Volume'].rolling(window=5).mean()
            
            # 市盈率 (yfinance 实时PE)
            info = ticker.info
            pe = info.get('trailingPE', 0)

            # 数据清洗与存储
            df = df.reset_index()
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
            
            for _, row in df.iterrows():
                if pd.isna(row['pct_change']): continue
                self.conn.execute('''
                    INSERT OR REPLACE INTO daily_quotes 
                    (symbol, date, close, pct_change, volume, amount, amplitude, vol_ratio, pe_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, row['Date'], row['Close'], row['pct_change'], 
                      row['Volume'], row['amount'], row['amplitude'], row['vol_ratio'], pe))
            self.conn.commit()

# 使用示例
if __name__ == "__main__":
    db = StockDB()
    all_symbols = list(INDICES.keys()) + WATCH_LIST
    # 首次运行使用 period="1y" 补录一年数据，日常运行使用 period="2d" 即可
    db.fetch_data(all_symbols, period="1y")