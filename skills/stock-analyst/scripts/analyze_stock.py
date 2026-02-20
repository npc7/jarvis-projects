#!/usr/bin/env python3
"""
股票投资价值分析脚本
基于四步法：业绩分析 → 财务结构 → 估值分析 → 综合评级

用法:
  python3 analyze_stock.py AAPL
  python3 analyze_stock.py 0700.HK
  python3 analyze_stock.py 600519.SS
"""

import sys
import json
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("请安装依赖: pip install yfinance")
    sys.exit(1)


def format_number(n, unit="亿"):
    """格式化大数字"""
    if n is None or n != n:  # None or NaN
        return "N/A"
    if unit == "亿":
        return f"{n/1e8:.1f}亿"
    if unit == "M":
        return f"{n/1e6:.1f}M"
    if unit == "%":
        return f"{n*100:.1f}%"
    return f"{n:.2f}"


def analyze_performance(info, financials):
    """第一步：业绩分析 - 营收增速、净利润增速"""
    print("\n" + "="*60)
    print("📈 第一步：业绩分析")
    print("="*60)

    # 基础指标
    rev_growth = info.get("revenueGrowth")
    earn_growth = info.get("earningsGrowth")
    market_cap = info.get("marketCap")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    print(f"  当前股价:     {current_price}")
    print(f"  市值:         {format_number(market_cap)}")
    print(f"  营收增速(YoY): {format_number(rev_growth, '%') if rev_growth else 'N/A'}")
    print(f"  利润增速(YoY): {format_number(earn_growth, '%') if earn_growth else 'N/A'}")

    # 多年营收趋势
    if financials is not None and not financials.empty:
        print("\n  📊 历年营收趋势:")
        rev_row = None
        for label in ["Total Revenue", "Revenue"]:
            if label in financials.index:
                rev_row = financials.loc[label]
                break
        if rev_row is not None:
            cols = list(rev_row.index)[:4]  # 最近4年
            for col in cols:
                year = str(col)[:4] if hasattr(col, '__str__') else str(col)
                val = rev_row[col]
                print(f"    {year}: {format_number(val)}")

    # 评级
    score = 0
    reasons = []
    if rev_growth and rev_growth > 0.15:
        score += 2; reasons.append("营收高增速(>15%)")
    elif rev_growth and rev_growth > 0.05:
        score += 1; reasons.append("营收稳健增长(5-15%)")
    elif rev_growth and rev_growth <= 0:
        score -= 1; reasons.append("⚠️ 营收负增长")

    if earn_growth and earn_growth > 0.15:
        score += 2; reasons.append("利润高增速(>15%)")
    elif earn_growth and earn_growth > 0:
        score += 1; reasons.append("利润正增长")
    elif earn_growth and earn_growth <= 0:
        score -= 1; reasons.append("⚠️ 利润下滑")

    print(f"\n  业绩评分: {score}/4  {'✅' if score >= 2 else '⚠️' if score >= 0 else '❌'}")
    for r in reasons:
        print(f"  → {r}")
    return score


def analyze_business(info):
    """第二步：业务理解 - 商业模式、竞争壁垒"""
    print("\n" + "="*60)
    print("🏢 第二步：业务与商业模式")
    print("="*60)

    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    biz_summary = info.get("longBusinessSummary", "")
    gross_margin = info.get("grossMargins")
    profit_margin = info.get("profitMargins")
    roe = info.get("returnOnEquity")

    print(f"  行业:       {sector} / {industry}")
    print(f"  毛利率:     {format_number(gross_margin, '%') if gross_margin else 'N/A'}")
    print(f"  净利率:     {format_number(profit_margin, '%') if profit_margin else 'N/A'}")
    print(f"  净资产收益(ROE): {format_number(roe, '%') if roe else 'N/A'}")

    if biz_summary:
        # 简要显示业务描述前200字
        print(f"\n  业务描述:\n  {biz_summary[:300]}...")

    # 放弃标准检查
    score = 0
    reasons = []
    if gross_margin and gross_margin > 0.40:
        score += 2; reasons.append("高毛利率(>40%) — 定价权强")
    elif gross_margin and gross_margin > 0.20:
        score += 1; reasons.append("中等毛利率(20-40%)")
    elif gross_margin and gross_margin < 0.10:
        score -= 1; reasons.append("⚠️ 低毛利率(<10%) — 定价权弱")

    if roe and roe > 0.20:
        score += 2; reasons.append("高ROE(>20%) — 资本利用效率高")
    elif roe and roe > 0.10:
        score += 1; reasons.append("ROE(10-20%) — 尚可")
    elif roe and roe <= 0:
        score -= 1; reasons.append("⚠️ ROE为负 — 资产回报差")

    print(f"\n  业务评分: {score}/4  {'✅' if score >= 2 else '⚠️' if score >= 0 else '❌'}")
    for r in reasons:
        print(f"  → {r}")
    return score


def analyze_financials(info, balance_sheet, cashflow):
    """第三步：财务结构 - 现金/债务、应收款"""
    print("\n" + "="*60)
    print("💰 第三步：财务健康度")
    print("="*60)

    total_cash = info.get("totalCash")
    total_debt = info.get("totalDebt")
    current_ratio = info.get("currentRatio")
    quick_ratio = info.get("quickRatio")
    fcf = info.get("freeCashflow")

    print(f"  现金:         {format_number(total_cash)}")
    print(f"  总债务:       {format_number(total_debt)}")
    print(f"  自由现金流:   {format_number(fcf)}")
    print(f"  流动比率:     {current_ratio:.2f}" if current_ratio else "  流动比率:     N/A")
    print(f"  速动比率:     {quick_ratio:.2f}" if quick_ratio else "  速动比率:     N/A")

    # 净现金状态
    if total_cash and total_debt:
        net_cash = total_cash - total_debt
        status = "净现金" if net_cash > 0 else "净负债"
        print(f"  净现金状态:   {format_number(abs(net_cash))} ({status})")

    # 应收款分析（从资产负债表）
    receivable_ratio = None
    if balance_sheet is not None and not balance_sheet.empty:
        for label in ["Accounts Receivable", "Net Receivables"]:
            if label in balance_sheet.index:
                ar = balance_sheet.loc[label].iloc[0]
                rev = info.get("totalRevenue")
                if ar and rev:
                    receivable_ratio = ar / rev
                    print(f"  应收款/营收:   {receivable_ratio*100:.1f}%")
                break

    score = 0
    reasons = []

    # 现金vs债务
    if total_cash and total_debt:
        if total_cash > total_debt:
            score += 2; reasons.append("现金 > 总债务 — 财务极健康")
        elif total_cash > total_debt * 0.5:
            score += 1; reasons.append("现金覆盖50%以上债务")
        else:
            score -= 1; reasons.append("⚠️ 现金不足以覆盖债务")

    # 自由现金流
    if fcf and fcf > 0:
        score += 2; reasons.append("自由现金流为正 — 持续造血能力")
    elif fcf and fcf < 0:
        score -= 1; reasons.append("⚠️ 自由现金流为负 — 烧钱阶段")

    # 应收款
    if receivable_ratio:
        if receivable_ratio < 0.10:
            score += 1; reasons.append("应收款占比低(<10%) — 定价权强")
        elif receivable_ratio > 0.30:
            score -= 1; reasons.append("⚠️ 应收款占比高(>30%) — 回款风险")

    print(f"\n  财务评分: {score}/5  {'✅' if score >= 3 else '⚠️' if score >= 1 else '❌'}")
    for r in reasons:
        print(f"  → {r}")
    return score


def analyze_valuation(info):
    """第四步：估值分析 - PE、市值匹配度、分析师目标价"""
    print("\n" + "="*60)
    print("📊 第四步：估值分析")
    print("="*60)

    pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    pb = info.get("priceToBook")
    peg = info.get("pegRatio")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    target_mean = info.get("targetMeanPrice")
    target_high = info.get("targetHigh") or info.get("targetHighPrice")
    target_low = info.get("targetLow") or info.get("targetLowPrice")
    analyst_count = info.get("numberOfAnalystOpinions", 0)
    recommendation = info.get("recommendationMean")  # 1=强买, 5=强卖

    print(f"  市盈率(PE):        {pe:.1f}" if pe else "  市盈率(PE):        N/A")
    print(f"  预期PE(Forward):   {forward_pe:.1f}" if forward_pe else "  预期PE(Forward):   N/A")
    print(f"  市净率(PB):        {pb:.1f}" if pb else "  市净率(PB):        N/A")
    print(f"  PEG比率:           {peg:.2f}" if peg else "  PEG比率:           N/A")
    print(f"\n  当前价格:          {current_price}")
    if target_mean:
        upside = (target_mean - current_price) / current_price * 100 if current_price else None
        print(f"  分析师目标价:      {target_mean:.2f}  (共{analyst_count}位分析师)")
        print(f"  目标价区间:        {target_low:.2f} ~ {target_high:.2f}" if target_low and target_high else "")
        if upside:
            print(f"  潜在涨幅:          {upside:+.1f}%")

    # 推荐评级转换
    rec_map = {1: "强烈买入", 2: "买入", 3: "持有", 4: "卖出", 5: "强烈卖出"}
    if recommendation:
        rec_text = rec_map.get(round(recommendation), f"{recommendation:.1f}")
        print(f"  机构评级:          {rec_text} ({recommendation:.2f}/5)")

    score = 0
    reasons = []

    # PE估值
    earn_growth = info.get("earningsGrowth", 0) or 0
    if pe:
        if pe < 15:
            score += 2; reasons.append(f"PE({pe:.0f}) 偏低 — 可能低估")
        elif pe < 25:
            score += 1; reasons.append(f"PE({pe:.0f}) 合理")
        elif pe < 40:
            score += 0; reasons.append(f"PE({pe:.0f}) 偏高，需高增速支撑")
        else:
            score -= 1; reasons.append(f"⚠️ PE({pe:.0f}) 过高 — 存在泡沫风险")

    # 上涨空间
    if target_mean and current_price:
        upside = (target_mean - current_price) / current_price
        if upside > 0.20:
            score += 2; reasons.append(f"分析师目标价空间大(+{upside*100:.0f}%)")
        elif upside > 0.05:
            score += 1; reasons.append(f"分析师目标价有小幅空间(+{upside*100:.0f}%)")
        elif upside < -0.05:
            score -= 1; reasons.append(f"⚠️ 分析师目标价低于当前价({upside*100:.0f}%)")

    print(f"\n  估值评分: {score}/4  {'✅' if score >= 2 else '⚠️' if score >= 0 else '❌'}")
    for r in reasons:
        print(f"  → {r}")
    return score


def comprehensive_rating(scores, ticker_symbol, info):
    """综合评级"""
    print("\n" + "="*60)
    print("🏆 综合投资评级")
    print("="*60)

    perf_score, biz_score, fin_score, val_score = scores
    total = perf_score + biz_score + fin_score + val_score
    max_total = 4 + 4 + 5 + 4  # 各项满分

    # 评级
    if total >= max_total * 0.75:
        rating = "⭐⭐⭐⭐⭐ 强烈推荐"
        action = "🟢 做多"
    elif total >= max_total * 0.55:
        rating = "⭐⭐⭐⭐ 推荐关注"
        action = "🟢 可考虑买入"
    elif total >= max_total * 0.35:
        rating = "⭐⭐⭐ 观望"
        action = "🟡 观望"
    elif total >= max_total * 0.15:
        rating = "⭐⭐ 谨慎"
        action = "🔴 谨慎/减仓"
    else:
        rating = "⭐ 回避"
        action = "🔴 做空/回避"

    company = info.get("longName") or info.get("shortName") or ticker_symbol
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    market_cap = info.get("marketCap")

    print(f"\n  公司:       {company} ({ticker_symbol})")
    print(f"  当前价格:   {current_price}")
    print(f"  市值:       {format_number(market_cap)}")
    print(f"\n  综合得分:   {total}/{max_total}")
    print(f"  评级:       {rating}")
    print(f"  操作建议:   {action}")
    print(f"\n  分项得分:")
    print(f"    业绩分析:   {perf_score}/4")
    print(f"    商业模式:   {biz_score}/4")
    print(f"    财务健康:   {fin_score}/5")
    print(f"    估值分析:   {val_score}/4")
    print("\n" + "="*60)
    print(f"  ⚠️  免责声明：本分析仅供参考，不构成投资建议。")
    print("="*60)

    return {
        "ticker": ticker_symbol,
        "company": company,
        "price": current_price,
        "market_cap": market_cap,
        "total_score": total,
        "max_score": max_total,
        "rating": rating,
        "action": action,
        "scores": {
            "performance": perf_score,
            "business": biz_score,
            "financials": fin_score,
            "valuation": val_score
        }
    }


def analyze_stock(ticker_symbol):
    """主入口：分析一只股票"""
    print(f"\n🔍 开始分析: {ticker_symbol.upper()}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    ticker = yf.Ticker(ticker_symbol)

    # 获取基础信息
    try:
        info = ticker.info
        if not info or "symbol" not in info and "shortName" not in info:
            print(f"❌ 无法获取 {ticker_symbol} 的数据，请检查股票代码")
            print("   美股: AAPL / 港股: 0700.HK / A股: 600519.SS")
            return None
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        return None

    # 获取财务报表
    try:
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow
    except Exception:
        financials = balance_sheet = cashflow = None

    # 四步分析
    perf_score = analyze_performance(info, financials)
    biz_score = analyze_business(info)
    fin_score = analyze_financials(info, balance_sheet, cashflow)
    val_score = analyze_valuation(info)

    # 综合评级
    result = comprehensive_rating(
        (perf_score, biz_score, fin_score, val_score),
        ticker_symbol.upper(),
        info
    )

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 analyze_stock.py <股票代码>")
        print("示例:")
        print("  python3 analyze_stock.py AAPL        # 苹果(美股)")
        print("  python3 analyze_stock.py 0700.HK     # 腾讯(港股)")
        print("  python3 analyze_stock.py 600519.SS   # 茅台(A股)")
        sys.exit(1)

    symbol = sys.argv[1]
    result = analyze_stock(symbol)
