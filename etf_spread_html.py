import akshare as ak
import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Line
from datetime import datetime
import warnings

# 忽略掉那个烦人的日期转换警告
warnings.filterwarnings("ignore")


def get_etf_history_premium(code, start_date, end_date):
    """
    获取 ETF 历史折溢价数据 (强力日期对齐版)
    """
    print(f"正在获取 {code} 的数据...")

    # 1. 获取价格数据
    df_price = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    if df_price.empty:
        print(f"警告：未获取到 {code} 的价格数据")
        return pd.DataFrame()

    df_price = df_price[['日期', '收盘']]
    # 强制转换日期格式为 datetime64[ns]
    df_price['日期'] = pd.to_datetime(df_price['日期'])

    # 2. 获取净值数据
    df_nav = ak.fund_etf_fund_info_em(fund=code)
    if df_nav.empty:
        print(f"警告：未获取到 {code} 的净值数据")
        return pd.DataFrame()

    df_nav = df_nav[['净值日期', '单位净值']]
    df_nav.columns = ['日期', '单位净值']
    # 【关键修正】：强制转换，避免 .dt.date 带来的类型冲突
    df_nav['日期'] = pd.to_datetime(df_nav['日期'])

    # 3. 合并数据
    df = pd.merge(df_price, df_nav, on='日期', how='inner')

    # 4. 计算溢价率
    if not df.empty:
        df[f'premium_{code}'] = (df['收盘'] / df['单位净值'] - 1) * 100
        # 按照 end_date 裁剪
        df = df[df['日期'] <= pd.to_datetime(end_date)]

    return df[['日期', f'premium_{code}']]


def plot_premium_comparison(code1, code2, start_date="20240101", end_date=None):
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    data1 = get_etf_history_premium(code1, start_date, end_date)
    data2 = get_etf_history_premium(code2, start_date, end_date)

    if data1.empty or data2.empty:
        print("❌ 错误：其中一个标的数据为空，无法生成图表。请检查代码或日期范围。")
        return

    # 合并两个基金的数据
    combined = pd.merge(data1, data2, on='日期', how='inner')
    combined = combined.sort_values('日期')

    if combined.empty:
        print("❌ 错误：合并后数据量为0。可能是价格日期与净值日期未对齐。")
        return

    # 计算差值 (Spread)
    combined['Spread'] = combined[f'premium_{code1}'] - combined[f'premium_{code2}']

    x_data = combined['日期'].dt.strftime('%Y-%m-%d').tolist()
    y1_data = combined[f'premium_{code1}'].round(2).tolist()
    y2_data = combined[f'premium_{code2}'].round(2).tolist()
    y_diff_data = combined['Spread'].round(2).tolist()

    line = (
        Line(init_opts=opts.InitOpts(width="100%", height="600px", theme="white"))
        .add_xaxis(xaxis_data=x_data)
        .add_yaxis(
            series_name=f"{code1} 溢价率%",
            y_axis=y1_data,
            is_smooth=True,
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name=f"{code2} 溢价率%",
            y_axis=y2_data,
            is_smooth=True,
            label_opts=opts.LabelOpts(is_show=False),
        )
        .add_yaxis(
            series_name="溢价差 (Spread) %",
            y_axis=y_diff_data,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=3, type_="solid"),
            label_opts=opts.LabelOpts(is_show=False),
            color="#d14a61"
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title=f"ETF 历史溢价对比: {code1} vs {code2}",
                                      subtitle=f"区间: {start_date} 至 {end_date}"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            datazoom_opts=[
                opts.DataZoomOpts(type_="slider", range_start=0, range_end=100),
                opts.DataZoomOpts(type_="inside")
            ],
            yaxis_opts=opts.AxisOpts(name="百分比 (%)", type_="value", splitline_opts=opts.SplitLineOpts(is_show=True)),
            legend_opts=opts.LegendOpts(pos_top="5%"),
        )
    )

    filename = f"premium_compare_{code1}_{code2}.html"
    line.render(filename)
    print(f"\n✅ 渲染完成！共 {len(combined)} 个交易日数据。请打开: {filename}")


if __name__ == "__main__":
    # 示例运行
    plot_premium_comparison("513300", "159941", "20241001", "20260106")