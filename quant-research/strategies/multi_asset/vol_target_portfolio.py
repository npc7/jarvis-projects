"""
波动率目标多资产组合
====================
结合风险平价 + 波动率目标

核心思想:
1. 使用风险平价确定资产权重
2. 动态调整总仓位以达到目标波动率
3. 加入动量过滤减少熊市损失
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
import warnings
from datetime import datetime
import json
from scipy.optimize import minimize

warnings.filterwarnings('ignore')


@dataclass
class PortfolioResult:
    """组合回测结果"""
    strategy_name: str
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility: float
    avg_position: float
    final_capital: float


def fetch_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取数据"""
    import yfinance as yf
    
    tickers = {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
        'SPY': 'SPY',
        'GLD': 'GLD',
        'TLT': 'TLT'
    }
    
    all_data = {}
    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [c[0].lower() for c in data.columns]
            else:
                data.columns = [c.lower() for c in data.columns]
            all_data[name] = data['close']
        except:
            pass
    
    prices = pd.DataFrame(all_data).dropna()
    return prices


def risk_parity_weights(cov: pd.DataFrame) -> np.ndarray:
    """风险平价权重"""
    n = len(cov)
    
    def risk_contribution(weights, cov):
        portfolio_vol = np.sqrt(weights @ cov @ weights)
        marginal_contrib = cov @ weights
        risk_contrib = weights * marginal_contrib / (portfolio_vol + 1e-10)
        return risk_contrib
    
    def objective(weights, cov):
        rc = risk_contribution(weights, cov.values)
        target_rc = np.ones(n) / n
        return np.sum((rc - target_rc) ** 2)
    
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = [(0.05, 0.5) for _ in range(n)]
    init_weights = np.ones(n) / n
    
    result = minimize(objective, init_weights, args=(cov,), method='SLSQP', 
                      bounds=bounds, constraints=constraints)
    return result.x


def backtest_vol_target_portfolio(
    prices: pd.DataFrame,
    target_volatility: float = 0.10,
    vol_lookback: int = 20,
    momentum_lookback: int = 60,
    rebalance_freq: int = 21,
    use_momentum_filter: bool = True,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, PortfolioResult]:
    """
    波动率目标组合回测
    """
    
    returns = prices.pct_change().dropna()
    
    equity = initial_capital
    equity_curve = []
    positions = []
    
    start_idx = max(252, vol_lookback, momentum_lookback) + 10
    last_rebalance = start_idx
    
    # 初始权重
    cov = returns.iloc[:start_idx].cov() * 252
    base_weights = risk_parity_weights(cov)
    
    for i in range(start_idx, len(returns)):
        date = returns.index[i]
        
        # 定期再平衡
        if i - last_rebalance >= rebalance_freq:
            # 更新风险平价权重
            cov = returns.iloc[i-252:i].cov() * 252
            base_weights = risk_parity_weights(cov)
            last_rebalance = i
        
        # 计算当前组合波动率
        recent_returns = returns.iloc[i-vol_lookback:i]
        
        # 组合收益（使用当前权重）
        portfolio_returns = (recent_returns * base_weights).sum(axis=1)
        current_vol = portfolio_returns.std() * np.sqrt(252)
        
        # 计算仓位乘数（波动率目标）
        if current_vol > 0:
            position_mult = target_volatility / current_vol
            position_mult = np.clip(position_mult, 0.2, 1.5)  # 限制范围
        else:
            position_mult = 1.0
        
        # 动量过滤
        if use_momentum_filter:
            # 检查组合动量
            momentum = prices.iloc[i-momentum_lookback:i].pct_change(momentum_lookback).iloc[-1]
            portfolio_momentum = (momentum * base_weights).sum()
            
            if portfolio_momentum < -0.05:  # 组合下跌超过5%，减仓
                position_mult *= 0.5
            elif portfolio_momentum < 0:  # 微跌，轻微减仓
                position_mult *= 0.8
        
        # 最终仓位
        final_position = position_mult
        positions.append(final_position)
        
        # 计算收益
        daily_return = (returns.iloc[i] * base_weights).sum() * final_position
        equity = equity * (1 + daily_return)
        
        equity_curve.append({
            'date': date,
            'equity': equity,
            'position': final_position,
            'vol': current_vol
        })
    
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    
    # 统计
    equity_series = equity_df['equity']
    
    total_return = (equity_series.iloc[-1] / initial_capital - 1) * 100
    days = (equity_df.index[-1] - equity_df.index[0]).days
    years = days / 365
    annual_return = ((equity_series.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    rolling_max = equity_series.expanding().max()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    daily_returns = equity_series.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252) * 100
    
    rf = 0.02
    excess_return = daily_returns.mean() * 252 - rf
    sharpe = excess_return / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    
    negative_returns = daily_returns[daily_returns < 0]
    downside_std = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0.01
    sortino = excess_return / downside_std if downside_std > 0 else 0
    
    calmar = abs(annual_return / max_drawdown) if max_drawdown != 0 else 0
    
    result = PortfolioResult(
        strategy_name=f'VolTarget_{int(target_volatility*100)}%',
        total_return=round(total_return, 2),
        annual_return=round(annual_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        calmar_ratio=round(calmar, 3),
        volatility=round(volatility, 2),
        avg_position=round(np.mean(positions), 2),
        final_capital=round(equity_series.iloc[-1], 2)
    )
    
    return equity_df, result


def main():
    print("=" * 70)
    print("🎯 波动率目标多资产组合")
    print("=" * 70)
    
    prices = fetch_data('2018-01-01', '2026-02-01')
    print(f"数据: {len(prices)} 条 ({prices.index[0].strftime('%Y-%m-%d')} ~ {prices.index[-1].strftime('%Y-%m-%d')})")
    
    results = []
    
    # 测试不同目标波动率
    for target_vol in [0.08, 0.10, 0.12, 0.15]:
        print(f"\n--- 目标波动率 {target_vol*100:.0f}% ---")
        
        # 有动量过滤
        equity, result = backtest_vol_target_portfolio(
            prices,
            target_volatility=target_vol,
            use_momentum_filter=True
        )
        
        print(f"   有动量过滤: 年化={result.annual_return:.1f}%, 回撤={result.max_drawdown:.1f}%, 夏普={result.sharpe_ratio:.2f}")
        results.append(result)
        
        # 无动量过滤
        equity_no_mom, result_no_mom = backtest_vol_target_portfolio(
            prices,
            target_volatility=target_vol,
            use_momentum_filter=False
        )
        result_no_mom.strategy_name = f'VolTarget_{int(target_vol*100)}%_NoMom'
        print(f"   无动量过滤: 年化={result_no_mom.annual_return:.1f}%, 回撤={result_no_mom.max_drawdown:.1f}%, 夏普={result_no_mom.sharpe_ratio:.2f}")
        results.append(result_no_mom)
    
    # 总结
    print("\n" + "=" * 70)
    print("📊 策略对比")
    print("=" * 70)
    print(f"{'策略':<25} {'年化收益':>10} {'最大回撤':>10} {'夏普比率':>10} {'达标':>8}")
    print("-" * 65)
    
    for r in results:
        meets = r.annual_return >= 10 and r.max_drawdown >= -15 and r.sharpe_ratio >= 0.8
        status = "✅" if meets else "❌"
        print(f"{r.strategy_name:<25} {r.annual_return:>9.1f}% {r.max_drawdown:>9.1f}% {r.sharpe_ratio:>10.2f} {status:>8}")
    
    # 找最优
    qualified = [r for r in results if r.annual_return >= 10 and r.max_drawdown >= -15]
    if qualified:
        best = max(qualified, key=lambda x: x.sharpe_ratio)
        print(f"\n🏆 最优达标策略: {best.strategy_name}")
        print(f"   年化收益: {best.annual_return:.1f}%")
        print(f"   最大回撤: {best.max_drawdown:.1f}%")
        print(f"   夏普比率: {best.sharpe_ratio:.2f}")
    else:
        print("\n⚠️ 没有完全达标的策略")
        # 找最接近的
        best_sharpe = max(results, key=lambda x: x.sharpe_ratio)
        print(f"   夏普最高: {best_sharpe.strategy_name} (夏普={best_sharpe.sharpe_ratio:.2f}, 回撤={best_sharpe.max_drawdown:.1f}%)")
    
    # 保存
    with open('backtest_results/vol_target_portfolio_results.json', 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    
    print("\n💾 结果已保存")


if __name__ == '__main__':
    main()
