import akshare as ak
# 获取 513300 在 2026 年 1 月的行情
test_df = ak.fund_etf_hist_em(symbol="513300", period="daily", start_date="20260101", end_date="20260106", adjust="qfq")
print(test_df)