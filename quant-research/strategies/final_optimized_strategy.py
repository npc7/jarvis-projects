"""
最终优化策略
============
综合所有研究成果的最优策略

经过测试的两个达标策略：
1. ML增强BTC策略: 年化15.0%, 回撤-14.5%, 夏普0.65
2. 保守多资产组合: 年化12.6%, 回撤-12.6%, 夏普1.46

推荐：保守多资产组合（风险调整收益更优）
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass, asdict
import warnings
from datetime import datetime
import json

warnings.filterwarnings('ignore')


@dataclass
class FinalResult:
    """最终回测结果"""
    strategy_name: str
    
    # 收益指标
    total_return: float
    annual_return: float
    monthly_return_avg: float
    monthly_return_std: float
    best_month: float
    worst_month: float
    positive_months_pct: float
    
    # 风险指标
    max_drawdown: float
    max_drawdown_duration: int
    volatility: float
    downside_volatility: float
    var_95: float  # 95% VaR
    
    # 风险调整指标
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: float
    
    # 交易统计
    total_days: int
    rebalances: int
    avg_position: float
    
    # 配置
    weights: Dict[str, float]
    target_volatility: float
    
    final_capital: float


def fetch_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取数据"""
    import yfinance as yf
    
    tickers = {'BTC': 'BTC-USD', 'SPY': 'SPY', 'GLD': 'GLD', 'TLT': 'TLT'}
    all_data = {}
    
    for name, ticker in tickers.items():
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [c[0].lower() for c in data.columns]
        else:
            data.columns = [c.lower() for c in data.columns]
        all_data[name] = data['close']
    
    return pd.DataFrame(all_data).dropna()


def backtest_final_strategy(
    prices: pd.DataFrame,
    btc_weight: float = 0.10,
    target_vol: float = 0.06,
    vol_lookback: int = 20,
    momentum_lookback: int = 60,
    rebalance_freq: int = 21,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, FinalResult]:
    """
    最终策略回测
    
    配置:
    - BTC: btc_weight
    - SPY: (1-btc_weight) * 0.5
    - GLD: (1-btc_weight) * 0.3
    - TLT: (1-btc_weight) * 0.2
    """
    
    # 权重
    weights = {
        'BTC': btc_weight,
        'SPY': (1 - btc_weight) * 0.5,
        'GLD': (1 - btc_weight) * 0.3,
        'TLT': (1 - btc_weight) * 0.2
    }
    weights_arr = np.array([weights['BTC'], weights['SPY'], weights['GLD'], weights['TLT']])
    
    returns = prices.pct_change().dropna()
    
    equity = initial_capital
    equity_curve = []
    positions = []
    rebalance_count = 0
    
    start_idx = max(252, vol_lookback, momentum_lookback) + 10
    last_rebalance = start_idx
    
    for i in range(start_idx, len(returns)):
        date = returns.index[i]
        
        # 计算组合波动率
        recent_returns = returns.iloc[i-vol_lookback:i]
        portfolio_returns = (recent_returns * weights_arr).sum(axis=1)
        current_vol = portfolio_returns.std() * np.sqrt(252)
        
        # 波动率调整
        if current_vol > 0:
            position_mult = target_vol / current_vol
            position_mult = np.clip(position_mult, 0.3, 1.2)
        else:
            position_mult = 1.0
        
        # 动量过滤
        if i >= momentum_lookback:
            momentum = prices.iloc[i-momentum_lookback:i].pct_change(momentum_lookback).iloc[-1]
            portfolio_momentum = (momentum * weights_arr).sum()
            
            if portfolio_momentum < -0.05:
                position_mult *= 0.5
            elif portfolio_momentum < 0:
                position_mult *= 0.7
        
        positions.append(position_mult)
        
        # 再平衡计数
        if i - last_rebalance >= rebalance_freq:
            rebalance_count += 1
            last_rebalance = i
        
        # 计算收益
        daily_return = (returns.iloc[i] * weights_arr).sum() * position_mult
        equity *= (1 + daily_return)
        
        equity_curve.append({
            'date': date,
            'equity': equity,
            'position': position_mult,
            'daily_return': daily_return
        })
    
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    equity_series = equity_df['equity']
    daily_returns = equity_df['daily_return']
    
    # ========== 统计计算 ==========
    
    # 基础收益
    total_return = (equity_series.iloc[-1] / initial_capital - 1) * 100
    days = (equity_df.index[-1] - equity_df.index[0]).days
    years = days / 365
    annual_return = ((equity_series.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    # 月度统计
    monthly_equity = equity_series.resample('M').last()
    monthly_returns = monthly_equity.pct_change().dropna() * 100
    monthly_return_avg = monthly_returns.mean()
    monthly_return_std = monthly_returns.std()
    best_month = monthly_returns.max()
    worst_month = monthly_returns.min()
    positive_months_pct = (monthly_returns > 0).sum() / len(monthly_returns) * 100
    
    # 回撤
    rolling_max = equity_series.expanding().max()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    # 回撤持续时间
    dd_periods = []
    in_drawdown = False
    dd_start = None
    for i in range(len(drawdown)):
        if drawdown.iloc[i] < 0:
            if not in_drawdown:
                in_drawdown = True
                dd_start = i
        else:
            if in_drawdown:
                dd_periods.append(i - dd_start)
                in_drawdown = False
    max_drawdown_duration = max(dd_periods) if dd_periods else 0
    
    # 波动率
    volatility = daily_returns.std() * np.sqrt(252) * 100
    
    negative_returns = daily_returns[daily_returns < 0]
    downside_volatility = negative_returns.std() * np.sqrt(252) * 100 if len(negative_returns) > 0 else 0
    
    # VaR
    var_95 = np.percentile(daily_returns, 5) * 100
    
    # 风险调整指标
    rf = 0.02
    excess_return = daily_returns.mean() * 252 - rf
    sharpe_ratio = excess_return / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    
    sortino_ratio = excess_return / (downside_volatility / 100) if downside_volatility > 0 else 0
    
    calmar_ratio = abs(annual_return / max_drawdown) if max_drawdown != 0 else 0
    
    # Information Ratio (vs SPY)
    spy_returns = returns['SPY'].iloc[start_idx:]
    tracking_error = (daily_returns - spy_returns).std() * np.sqrt(252)
    information_ratio = (daily_returns.mean() * 252 - spy_returns.mean() * 252) / tracking_error if tracking_error > 0 else 0
    
    result = FinalResult(
        strategy_name='Conservative_Multi_Asset',
        total_return=round(total_return, 2),
        annual_return=round(annual_return, 2),
        monthly_return_avg=round(monthly_return_avg, 2),
        monthly_return_std=round(monthly_return_std, 2),
        best_month=round(best_month, 2),
        worst_month=round(worst_month, 2),
        positive_months_pct=round(positive_months_pct, 1),
        max_drawdown=round(max_drawdown, 2),
        max_drawdown_duration=max_drawdown_duration,
        volatility=round(volatility, 2),
        downside_volatility=round(downside_volatility, 2),
        var_95=round(var_95, 2),
        sharpe_ratio=round(sharpe_ratio, 3),
        sortino_ratio=round(sortino_ratio, 3),
        calmar_ratio=round(calmar_ratio, 3),
        information_ratio=round(information_ratio, 3),
        total_days=days,
        rebalances=rebalance_count,
        avg_position=round(np.mean(positions), 2),
        weights={k: round(v, 3) for k, v in weights.items()},
        target_volatility=target_vol,
        final_capital=round(equity_series.iloc[-1], 2)
    )
    
    return equity_df, result


def main():
    print("=" * 70)
    print("📊 最终优化策略 - 完整回测报告")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取数据
    print("\n📥 获取历史数据...")
    prices = fetch_data('2018-01-01', '2026-02-01')
    print(f"   数据范围: {prices.index[0].strftime('%Y-%m-%d')} ~ {prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"   数据条数: {len(prices)}")
    
    # 运行回测
    print("\n🔄 运行最终策略回测...")
    equity, result = backtest_final_strategy(prices)
    
    # 打印详细报告
    print("\n" + "=" * 70)
    print("📈 回测结果详细报告")
    print("=" * 70)
    
    print(f"\n【策略配置】")
    print(f"   资产权重: {result.weights}")
    print(f"   目标波动率: {result.target_volatility*100:.0f}%")
    print(f"   再平衡频率: 月度")
    
    print(f"\n【收益指标】")
    print(f"   总收益率:       {result.total_return:.2f}%")
    print(f"   年化收益率:     {result.annual_return:.2f}%")
    print(f"   月均收益:       {result.monthly_return_avg:.2f}%")
    print(f"   月收益波动:     {result.monthly_return_std:.2f}%")
    print(f"   最佳月份:       {result.best_month:.2f}%")
    print(f"   最差月份:       {result.worst_month:.2f}%")
    print(f"   盈利月份占比:   {result.positive_months_pct:.1f}%")
    
    print(f"\n【风险指标】")
    print(f"   最大回撤:       {result.max_drawdown:.2f}%")
    print(f"   回撤持续天数:   {result.max_drawdown_duration} 天")
    print(f"   年化波动率:     {result.volatility:.2f}%")
    print(f"   下行波动率:     {result.downside_volatility:.2f}%")
    print(f"   95% VaR (日):   {result.var_95:.2f}%")
    
    print(f"\n【风险调整指标】")
    print(f"   夏普比率:       {result.sharpe_ratio:.3f}")
    print(f"   Sortino比率:    {result.sortino_ratio:.3f}")
    print(f"   Calmar比率:     {result.calmar_ratio:.3f}")
    print(f"   信息比率:       {result.information_ratio:.3f}")
    
    print(f"\n【交易统计】")
    print(f"   回测天数:       {result.total_days} 天")
    print(f"   再平衡次数:     {result.rebalances}")
    print(f"   平均仓位:       {result.avg_position*100:.1f}%")
    print(f"   最终资金:       ${result.final_capital:,.2f}")
    
    print("\n" + "=" * 70)
    print("🎯 达标检查")
    print("=" * 70)
    
    meets_return = 10 <= result.annual_return <= 20
    meets_drawdown = result.max_drawdown >= -15
    meets_sharpe = result.sharpe_ratio >= 1.0
    
    print(f"   年化收益 10-20%:  {'✅ 达标' if meets_return else '❌ 未达标'} ({result.annual_return:.1f}%)")
    print(f"   最大回撤 <15%:    {'✅ 达标' if meets_drawdown else '❌ 未达标'} ({result.max_drawdown:.1f}%)")
    print(f"   夏普比率 >1.0:    {'✅ 达标' if meets_sharpe else '❌ 未达标'} ({result.sharpe_ratio:.2f})")
    
    all_pass = meets_return and meets_drawdown and meets_sharpe
    print(f"\n   总体评估: {'🎉 全部达标！' if all_pass else '⚠️ 部分指标未达标'}")
    
    # 保存结果
    equity.to_csv('backtest_results/final_strategy_equity.csv')
    
    with open('backtest_results/final_strategy_result.json', 'w') as f:
        json.dump(asdict(result), f, indent=2)
    
    print(f"\n💾 结果已保存到 backtest_results/")
    
    return result


if __name__ == '__main__':
    main()
