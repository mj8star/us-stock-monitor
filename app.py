import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from database import INDICES, WATCH_LIST

# --- 页面配置 ---
st.set_page_config(page_title="XX美股监控系统", layout="wide")

# --- 自定义工具函数：中文单位转换 ---
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

# --- 侧边栏 ---
st.sidebar.title("🛠️ 监控台")
all_options = list(INDICES.keys()) + WATCH_LIST
selected_symbols = st.sidebar.multiselect("1. 选择监控对象", options=all_options, default=["^GSPC", "AAPL", "NVDA"])
history_days = st.sidebar.slider("2. 时间回溯 (天)", 7, 365, 60)

# 指标配置字典 (Key: 数据库字段, Value: [中文名, 单位])
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

# --- 主界面 ---
st.title("📊 XX美股量化监控看板")

if not selected_symbols:
    st.info("请在左侧勾选需要监控的股票或指数。")
elif not selected_metrics:
    st.warning("请至少选择一个指标进行可视化对比。")
else:
    df = load_data(selected_symbols, history_days)
    
    if not df.empty:
        # 遍历用户勾选的每一个指标，动态生成图表
        for metric in selected_metrics:
            st.divider()
            name_cn, unit = METRICS_MAP[metric]
            
            # 数据预处理
            plot_df = df.copy()
            
            # 特殊逻辑：收盘价进行归一化处理以便对比走势
            if metric == "close":
                plot_df['display_val'] = plot_df.groupby('symbol')['close'].transform(lambda x: (x / x.iloc[0]) * 100)
                chart_title = "累计收益表现对比 (基准 100)"
                y_label = "归一化指数"
            else:
                plot_df['display_val'] = plot_df[metric]
                chart_title = f"{name_cn} 历史对比"
                y_label = f"{name_cn} ({unit})"

            # 针对大数值指标（如成交额）生成中文标签供悬浮显示
            if metric == "amount":
                plot_df['cn_label'] = plot_df['display_val'].apply(format_cn_units)
            else:
                plot_df['cn_label'] = plot_df['display_val'].map(lambda x: f"{x:.2f}{unit}")

            # 每一天内部按数值降序，确保悬浮框排序
            plot_df = plot_df.sort_values(['date', 'display_val'], ascending=[True, False])

            # 绘图
            fig = px.line(
                plot_df,
                x='date',
                y='display_val',
                color='symbol',
                title=chart_title,
                labels={'display_val': y_label, 'date': '日期', 'symbol': '代码'},
                custom_data=['cn_label'] # 传入自定义中文标签
            )

            # 优化悬浮窗显示
            fig.update_traces(
                hovertemplate="<b>%{symbol}</b>: %{customdata[0]}<extra></extra>"
            )

            fig.update_layout(
                hovermode="x unified",
                height=400,
                xaxis_title=None,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            # 辅助基准线
            if metric == "close": fig.add_hline(y=100, line_dash="dot", line_color="gray")
            if metric == "pct_change": fig.add_hline(y=0, line_color="white", opacity=0.3)

            st.plotly_chart(fig, use_container_width=True)

        # --- 底部详细数据表格 ---
        st.subheader("📋 实时明细数据 (中文单位)")
        table_df = df.sort_values(['date', 'symbol'], ascending=[False, True]).copy()
        
        # 转换成交额单位
        table_df['amount'] = table_df['amount'].apply(format_cn_units)
        
        # 渲染表格
        st.dataframe(
            table_df,
            column_config={
                "date": "日期",
                "symbol": "代码",
                "close": st.column_config.NumberColumn("收盘价", format="$%.2f"),
                "pct_change": st.column_config.NumberColumn("涨跌幅", format="%.2f%%"),
                "amount": "成交额",
                "vol_ratio": "量比",
                "amplitude": st.column_config.NumberColumn("振幅", format="%.2f%%"),
                "pe_ratio": "市盈率"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.error("数据库为空，请先运行采集脚本 `uv run python database.py`。")