import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from database import INDICES, WATCH_LIST

# --- 页面配置 ---
st.set_page_config(page_title="XX美股监控系统", layout="wide")

# --- 1. 配置：代码与中文名称映射 ---
# 你可以在这里持续添加需要监控的股票中文名
STOCKS_NAME_MAP = {
    "^GSPC": "标普500指数",
    "^IXIC": "纳斯达克指数",
    "^RUT": "罗素2000指数",
    "AAPL": "苹果",
    "NVDA": "英伟达",
    "TSLA": "特斯拉",
    "GOOGL": "谷歌",
    "MSFT": "微软",
    "AMZN": "亚马逊",
    "META": "梅塔",
    "QQQ": "纳指100ETF",
    "SPY": "标普500ETF"
}

# --- 2. 工具函数：单位转换 ---
def format_cn_units(num):
    if num is None or pd.isna(num): return "N/A"
    abs_num = abs(num)
    if abs_num >= 1e8:
        return f"{num / 1e8:.2f}亿"
    elif abs_num >= 1e4:
        return f"{num / 1e4:.2f}万"
    else:
        return f"{num:.2f}"

@st.cache_data
def load_data(symbols, days=30):
    if not symbols: return pd.DataFrame()
    try:
        conn = sqlite3.connect('stocks.db')
        placeholders = ','.join(['?'] * len(symbols))
        query = f"""
            SELECT * FROM daily_quotes 
            WHERE symbol IN ({placeholders}) 
            AND date >= date('now', '-{days} day')
            ORDER BY date ASC
        """
        df = pd.read_sql(query, conn, params=symbols)
        conn.close()
        return df
    except Exception as e:
        st.error(f"数据库读取失败: {e}")
        return pd.DataFrame()

# --- 3. 侧边栏 ---
st.sidebar.title("🛠️ 监控台")
all_options = list(INDICES.keys()) + WATCH_LIST
selected_symbols = st.sidebar.multiselect("1. 选择监控对象", options=all_options, default=["^GSPC", "^IXIC", "^RUT"])
history_days = st.sidebar.slider("2. 时间回溯 (天)", 7, 365, 60)

METRICS_MAP = {
    "close": ["收盘价", "USD"],
    "pct_change": ["涨跌幅", "%"],
    "vol_ratio": ["量比", "倍"],
    "amplitude": ["日内振幅", "%"],
    "amount": ["成交额", "元"],
    "pe_ratio": ["市盈率", "倍"]
}

selected_metrics = st.sidebar.multiselect(
    "3. 勾选对比指标",
    options=list(METRICS_MAP.keys()),
    default=["close", "pct_change", "amount"],
    format_func=lambda x: METRICS_MAP[x][0]
)

# --- 4. 主界面 ---
st.title("📊 XX美股量化监控看板")

if not selected_symbols:
    st.info("请在左侧勾选需要监控的股票或指数。")
elif not selected_metrics:
    st.warning("请至少选择一个指标进行可视化对比。")
else:
    df = load_data(selected_symbols, history_days)
    
    if not df.empty:
        # 注入中文名称
        df['display_name'] = df['symbol'].map(lambda x: STOCKS_NAME_MAP.get(x, x))
        
        # 遍历指标生成图表
        for metric in selected_metrics:
            st.divider()
            name_cn, unit = METRICS_MAP[metric]
            
            plot_df = df.copy()
            
            # 指标逻辑处理
            if metric == "close":
                # 归一化计算
                plot_df['plot_val'] = plot_df.groupby('symbol')['close'].transform(lambda x: (x / x.iloc[0]) * 100)
                chart_title = "累计收益表现对比 (基准 100)"
                y_label = "归一化指数"
            else:
                plot_df['plot_val'] = plot_df[metric]
                chart_title = f"{name_cn} 历史对比"
                y_label = f"{name_cn} ({unit})"

            # 准备悬浮框显示的格式化标签
            if metric == "amount":
                plot_df['hover_val'] = plot_df['plot_val'].apply(format_cn_units)
            else:
                plot_df['hover_val'] = plot_df['plot_val'].map(lambda x: f"{x:.2f}{unit}")

            # 按照数值倒序排序，优化悬浮框显示顺序
            plot_df = plot_df.sort_values(['date', 'plot_val'], ascending=[True, False])

            # 绘图
            fig = px.line(
                plot_df,
                x='date',
                y='plot_val',
                color='symbol',
                title=chart_title,
                labels={'plot_val': y_label, 'date': '日期', 'symbol': '代码'},
                custom_data=['display_name', 'hover_val'] # 传入中文名和格式化后的数值
            )

            # --- 核心改进：悬浮窗显示中文名 ---
            fig.update_traces(
                hovertemplate="<b>%{customdata[0]}</b> (%{symbol})<br>数值: %{customdata[1]}<extra></extra>"
            )

            fig.update_layout(
                hovermode="x unified",
                height=450,
                xaxis_title=None,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hoverlabel=dict(bgcolor="rgba(255, 255, 255, 0.9)", font_size=13)
            )

            if metric == "close": fig.add_hline(y=100, line_dash="dot", line_color="gray")
            if metric == "pct_change": fig.add_hline(y=0, line_color="white", opacity=0.3)

            st.plotly_chart(fig, use_container_width=True)

        # --- 底部数据明细 ---
        with st.expander("查看原始明细数据"):
            table_df = df.sort_values(['date', 'symbol'], ascending=[False, True]).copy()
            table_df['amount'] = table_df['amount'].apply(format_cn_units)
            st.dataframe(
                table_df[['date', 'display_name', 'symbol', 'close', 'pct_change', 'amount', 'vol_ratio', 'amplitude']],
                column_config={
                    "date": "日期",
                    "display_name": "标的名称",
                    "symbol": "代码",
                    "close": st.column_config.NumberColumn("收盘价", format="$%.2f"),
                    "pct_change": st.column_config.NumberColumn("涨跌幅", format="%.2f%%"),
                    "amount": "成交额",
                    "vol_ratio": "量比",
                    "amplitude": "振幅"
                },
                hide_index=True,
                use_container_width=True
            )
    else:
        st.error("未找到数据。请确保 GitHub Action 已运行或本地 database.py 已执行。")