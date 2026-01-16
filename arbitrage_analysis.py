import akshare as ak
import pandas as pd
import numpy as np
from pyecharts import options as opts
from pyecharts.charts import Line, Bar, Grid
from datetime import datetime
import warnings

# 彻底忽略所有警告
warnings.filterwarnings("ignore")

def get_etf_history_premium(code, start_date, end_date):
    """获取数据并对齐价格与净值"""
    try:
        df_price = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date,
                                       adjust="qfq")
        if df_price.empty: return pd.DataFrame()
        df_price = df_price[['日期', '收盘']]
        df_price['日期'] = pd.to_datetime(df_price['日期'])

        df_nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        df_nav = df_nav[['净值日期', '单位净值']]
        df_nav.columns = ['日期', '单位净值']
        df_nav['日期'] = pd.to_datetime(df_nav['日期'])

        df = pd.merge(df_price, df_nav, on='日期', how='inner')
        if df.empty: return pd.DataFrame()

        df[f'premium_{code}'] = (df['收盘'] / df['单位净值'] - 1) * 100
        return df[['日期', f'premium_{code}']]
    except Exception as e:
        print(f"❌ 数据源错误: {e}")
        return pd.DataFrame()

def plot_full_arbitrage_report(code1, code2, start_date="20240101", end_date=None):
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    data1 = get_etf_history_premium(code1, start_date, end_date)
    data2 = get_etf_history_premium(code2, start_date, end_date)

    if data1.empty or data2.empty:
        print("❌ 数据缺失，无法生成报表。")
        return

    combined = pd.merge(data1, data2, on='日期', how='inner').sort_values('日期')
    combined['Spread'] = combined[f'premium_{code1}'] - combined[f'premium_{code2}']

    # --- 统计指标 ---
    latest_spread = combined['Spread'].iloc[-1]
    avg_spread = combined['Spread'].mean()
    p5 = combined['Spread'].quantile(0.05)
    p95 = combined['Spread'].quantile(0.95)
    percentile = (combined['Spread'] < latest_spread).mean() * 100
    expected_return = abs(latest_spread - avg_spread)

    # --- 数据准备 ---
    x_dates = combined['日期'].dt.strftime('%Y-%m-%d').tolist()
    y1 = combined[f'premium_{code1}'].round(2).tolist()
    y2 = combined[f'premium_{code2}'].round(2).tolist()
    y_diff = combined['Spread'].round(2).tolist()

    # --- 直方图数据 ---
    counts, bin_edges = np.histogram(combined['Spread'], bins=30)
    bar_data = []
    for i in range(len(counts)):
        is_highlight = bin_edges[i] <= latest_spread <= bin_edges[i + 1]
        bar_data.append(
            opts.BarItem(
                name=f"{bin_edges[i]:.2f}",
                value=int(counts[i]),
                itemstyle_opts=opts.ItemStyleOpts(color="#E5989B" if is_highlight else "#A3B18A")
            )
        )
    bin_labels = [f"{(bin_edges[i] + bin_edges[i + 1]) / 2:.2f}" for i in range(len(bin_edges) - 1)]

    # --- 1. 趋势图配置 (将所有关键数据合并进标题) ---
    line = (
        Line()
        .add_xaxis(xaxis_data=x_dates)
        .add_yaxis(f"{code1} 溢价%", y1, is_smooth=True, symbol="none", label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(f"{code2} 溢价%", y2, is_smooth=True, symbol="none", label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis(
            "溢价差 (Spread) %",
            y_diff,
            is_smooth=True,
            symbol="none",
            linestyle_opts=opts.LineStyleOpts(width=3, color="#6B705C"),
            # 【核心修改点】使用字典结构配置 MarkLine，兼容性最强
            markline_opts=opts.MarkLineOpts(
                symbol=["none", "none"], # 去掉两端箭头
                data=[
                    # 中枢线 - 灰色
                    {"yAxis": round(avg_spread, 2), "name": "中枢", "lineStyle": {"color": "gray", "type": "dashed"}},
                    # 低位线 - 绿色 (5%)
                    {"yAxis": round(p5, 2), "name": "低位 (5%)", "lineStyle": {"color": "#2ec7c9", "width": 2}},
                    # 高位线 - 红色 (95%)
                    {"yAxis": round(p95, 2), "name": "高位 (95%)", "lineStyle": {"color": "#d87a80", "width": 2}},
                ],
                label_opts=opts.LabelOpts(formatter="{b}: {c}%")
            ),
            label_opts=opts.LabelOpts(is_show=False)
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title=f"纳指ETF深度套利仪表盘 ({code1} vs {code2})",
                subtitle=f"最新价差: {latest_spread:.2f}% | 历史分位排名: {percentile:.2f}% | 🔥 预期回归收益: {expected_return:.2f}%",
                pos_left="center"
            ),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            datazoom_opts=[
                opts.DataZoomOpts(xaxis_index=[0], pos_top="72%", type_="slider", range_start=0, range_end=100),
                opts.DataZoomOpts(xaxis_index=[0], type_="inside", range_start=0, range_end=100)
            ],
            legend_opts=opts.LegendOpts(pos_top="10%"),
            yaxis_opts=opts.AxisOpts(name="溢价率 (%)", splitline_opts=opts.SplitLineOpts(is_show=True)),
        )
    )

    # --- 2. 柱状图配置 ---
    bar = (
        Bar()
        .add_xaxis(xaxis_data=bin_labels)
        .add_yaxis("频率", bar_data, category_gap=0, label_opts=opts.LabelOpts(is_show=False))
        .set_global_opts(
            title_opts=opts.TitleOpts(title="Spread 历史概率分布 (珊瑚粉为当前水位)", pos_top="78%", pos_left="center"),
            legend_opts=opts.LegendOpts(is_show=False),
            xaxis_opts=opts.AxisOpts(name="区间%"),
            yaxis_opts=opts.AxisOpts(name="天数"),
        )
    )

    # --- 3. 组合导出 ---
    grid = (
        Grid(init_opts=opts.InitOpts(width="100%", height="1000px", theme="white"))
        .add(line, grid_opts=opts.GridOpts(pos_top="15%", pos_bottom="32%"))
        .add(bar, grid_opts=opts.GridOpts(pos_top="82%", pos_bottom="5%"))
        .render("arbitrage_report_final.html")
    )

    print(f"✅ 报告已生成！请查看 arbitrage_report_final.html")
    print(f"预期回归收益已直接置于副标题显示: {expected_return:.2f}%")


if __name__ == "__main__":
    plot_full_arbitrage_report("513300", "159941", "20250101", None)