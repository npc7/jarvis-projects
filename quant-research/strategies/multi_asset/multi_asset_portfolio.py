"""
阶段 3: 多资产组合策略
======================
时间: 2026-02-09 (阶段3)

资产:
- BTC (比特币)
- ETH (以太坊)
- SPY (美股 S&P500)
- GLD (黄金)
- TLT (美国长期国债)

策略:
1. 风险平价 (Risk Parity)
2. 均值方差优化 (MVO)
3. 动态配置 (基于动量)
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
    weights: Dict[str, float]
    final_capital: float


def fetch_multi_asset_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取多资产数据"""
    import yfinance as yf
    
    tickers = {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
        'SPY': 'SPY',
        'GLD': 'GLD',
        'TLT': 'TLT'
    }
    
    print("\n📥 获取多资产数据...")
    
    all_data = {}
    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [c[0].lower() for c in data.columns]
            else:
                data.columns = [c.lower() for c in data.columns]
            
            all_data[name] = data['close']
            print(f"   ✅ {name}: {len(data)} 条数据")
        except Exception as e:
            print(f"   ❌ {name}: 获取失败 - {e}")
    
    # 合并数据
    prices = pd.DataFrame(all_data)
    prices = prices.dropna()
    
    print(f"\n   合并后: {len(prices)} 条数据 ({prices.index[0].strftime('%Y-%m-%d')} ~ {prices.index[-1].strftime('%Y-%m-%d')})")
    
    return prices


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """计算收益率"""
    return prices.pct_change().dropna()


def calculate_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """计算相关性矩阵"""
    return returns.corr()


def risk_parity_weights(returns: pd.DataFrame) -> np.ndarray:
    """
    风险平价权重计算
    
    每个资产对组合风险的贡献相等
    """
    cov = returns.cov() * 252  # 年化协方差
    n = len(returns.columns)
    
    def risk_contribution(weights, cov):
        portfolio_vol = np.sqrt(weights @ cov @ weights)
        marginal_contrib = cov @ weights
        risk_contrib = weights * marginal_contrib / portfolio_vol
        return risk_contrib
    
    def objective(weights, cov):
        # 目标: 最小化风险贡献的方差 (即让所有资产风险贡献相等)
        rc = risk_contribution(weights, cov)
        target_rc = np.ones(n) / n
        return np.sum((rc - target_rc) ** 2)
    
    # 约束
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # 权重和为1
    ]
    bounds = [(0.05, 0.5) for _ in range(n)]  # 每个资产 5%-50%
    
    # 初始权重
    init_weights = np.ones(n) / n
    
    result = minimize(
        objective,
        init_weights,
        args=(cov.values,),
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )
    
    return result.x


def mean_variance_weights(returns: pd.DataFrame, target_return: float = 0.12) -> np.ndarray:
    """
    均值方差优化
    
    在给定目标收益下最小化波动率
    """
    mean_returns = returns.mean() * 252
    cov = returns.cov() * 252
    n = len(returns.columns)
    
    def portfolio_volatility(weights):
        return np.sqrt(weights @ cov @ weights)
    
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # 权重和为1
        {'type': 'eq', 'fun': lambda w: w @ mean_returns - target_return}  # 目标收益
    ]
    bounds = [(0.0, 0.5) for _ in range(n)]
    
    init_weights = np.ones(n) / n
    
    try:
        result = minimize(
            portfolio_volatility,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        return result.x
    except:
        # 如果优化失败，返回等权重
        return np.ones(n) / n


def momentum_weights(prices: pd.DataFrame, lookback: int = 60) -> np.ndarray:
    """
    动量加权
    
    根据过去 N 天的表现动态分配权重
    """
    returns = prices.pct_change(lookback).iloc[-1]
    
    # 正动量资产
    positive_momentum = returns[returns > 0]
    
    if len(positive_momentum) == 0:
        # 如果没有正动量，等权重配置
        return np.ones(len(prices.columns)) / len(prices.columns)
    
    # 按动量分配权重
    weights = np.zeros(len(prices.columns))
    for i, asset in enumerate(prices.columns):
        if asset in positive_momentum.index:
            weights[i] = max(0, returns[asset])
    
    # 归一化
    if weights.sum() > 0:
        weights = weights / weights.sum()
    else:
        weights = np.ones(len(weights)) / len(weights)
    
    # 限制单一资产最大 40%
    weights = np.clip(weights, 0.05, 0.40)
    weights = weights / weights.sum()
    
    return weights


def backtest_portfolio(
    prices: pd.DataFrame,
    weights_func,
    strategy_name: str,
    rebalance_freq: int = 21,  # 每月再平衡
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, PortfolioResult]:
    """
    运行组合回测
    """
    returns = calculate_returns(prices)
    
    n_assets = len(prices.columns)
    
    # 初始权重
    if callable(weights_func):
        weights = weights_func(returns.iloc[:252])  # 用第一年数据初始化
    else:
        weights = weights_func
    
    # 回测
    equity = initial_capital
    equity_curve = []
    
    start_idx = 252  # 从1年后开始
    last_rebalance = start_idx
    
    for i in range(start_idx, len(returns)):
        date = returns.index[i]
        
        # 再平衡
        if i - last_rebalance >= rebalance_freq:
            if callable(weights_func):
                if 'momentum' in strategy_name.lower():
                    weights = weights_func(prices.iloc[:i])
                else:
                    weights = weights_func(returns.iloc[:i])
            last_rebalance = i
        
        # 计算收益
        daily_return = (returns.iloc[i] * weights).sum()
        equity = equity * (1 + daily_return)
        
        equity_curve.append({
            'date': date,
            'equity': equity,
            'daily_return': daily_return
        })
    
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    
    # 计算统计
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
    
    # 获取最终权重
    if callable(weights_func):
        if 'momentum' in strategy_name.lower():
            final_weights = weights_func(prices)
        else:
            final_weights = weights_func(returns)
    else:
        final_weights = weights_func
    
    weights_dict = dict(zip(prices.columns, final_weights.round(4)))
    
    result = PortfolioResult(
        strategy_name=strategy_name,
        total_return=round(total_return, 2),
        annual_return=round(annual_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        calmar_ratio=round(calmar, 3),
        volatility=round(volatility, 2),
        weights=weights_dict,
        final_capital=round(equity_series.iloc[-1], 2)
    )
    
    return equity_df, result


def main():
    """主函数"""
    print("=" * 70)
    print("🏦 多资产组合策略研究")
    print("=" * 70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取数据
    prices = fetch_multi_asset_data('2018-01-01', '2026-02-01')
    
    if len(prices) < 500:
        print("❌ 数据不足")
        return
    
    returns = calculate_returns(prices)
    
    # 1. 相关性分析
    print("\n" + "=" * 70)
    print("📊 资产相关性矩阵")
    print("=" * 70)
    corr = calculate_correlation_matrix(returns)
    print(corr.round(2).to_string())
    
    # 2. 资产统计
    print("\n" + "=" * 70)
    print("📊 资产历史表现 (年化)")
    print("=" * 70)
    for asset in prices.columns:
        asset_returns = returns[asset]
        ann_return = asset_returns.mean() * 252 * 100
        ann_vol = asset_returns.std() * np.sqrt(252) * 100
        sharpe = (ann_return/100 - 0.02) / (ann_vol/100)
        print(f"   {asset:4s}: 收益 {ann_return:6.1f}%, 波动率 {ann_vol:5.1f}%, 夏普 {sharpe:.2f}")
    
    results = []
    
    # 3. 等权重组合 (基准)
    print("\n" + "-" * 70)
    print("🧪 策略 1: 等权重组合 (基准)")
    print("-" * 70)
    
    equal_weights = np.ones(len(prices.columns)) / len(prices.columns)
    equity_eq, result_eq = backtest_portfolio(prices, equal_weights, 'Equal_Weight')
    
    print(f"   权重: {dict(zip(prices.columns, equal_weights.round(3)))}")
    print(f"   年化收益: {result_eq.annual_return:.1f}%, 回撤: {result_eq.max_drawdown:.1f}%, 夏普: {result_eq.sharpe_ratio:.2f}")
    results.append(result_eq)
    
    # 4. 风险平价组合
    print("\n" + "-" * 70)
    print("🧪 策略 2: 风险平价组合")
    print("-" * 70)
    
    equity_rp, result_rp = backtest_portfolio(prices, risk_parity_weights, 'Risk_Parity')
    
    print(f"   权重: {result_rp.weights}")
    print(f"   年化收益: {result_rp.annual_return:.1f}%, 回撤: {result_rp.max_drawdown:.1f}%, 夏普: {result_rp.sharpe_ratio:.2f}")
    results.append(result_rp)
    
    # 5. 动量加权组合
    print("\n" + "-" * 70)
    print("🧪 策略 3: 动量加权组合")
    print("-" * 70)
    
    equity_mom, result_mom = backtest_portfolio(prices, momentum_weights, 'Momentum_Weight')
    
    print(f"   当前权重: {result_mom.weights}")
    print(f"   年化收益: {result_mom.annual_return:.1f}%, 回撤: {result_mom.max_drawdown:.1f}%, 夏普: {result_mom.sharpe_ratio:.2f}")
    results.append(result_mom)
    
    # 6. BTC + 传统资产 (60/40 变体)
    print("\n" + "-" * 70)
    print("🧪 策略 4: BTC + 传统资产 (20% BTC, 40% SPY, 20% GLD, 20% TLT)")
    print("-" * 70)
    
    custom_weights = np.array([0.20, 0.0, 0.40, 0.20, 0.20])  # BTC, ETH, SPY, GLD, TLT
    equity_custom, result_custom = backtest_portfolio(prices, custom_weights, 'BTC_Traditional')
    
    print(f"   权重: {dict(zip(prices.columns, custom_weights.round(2)))}")
    print(f"   年化收益: {result_custom.annual_return:.1f}%, 回撤: {result_custom.max_drawdown:.1f}%, 夏普: {result_custom.sharpe_ratio:.2f}")
    results.append(result_custom)
    
    # 7. 加密重仓 (40% BTC + 20% ETH + 40% SPY)
    print("\n" + "-" * 70)
    print("🧪 策略 5: 加密重仓 (40% BTC, 20% ETH, 40% SPY)")
    print("-" * 70)
    
    crypto_heavy = np.array([0.40, 0.20, 0.40, 0.0, 0.0])
    equity_crypto, result_crypto = backtest_portfolio(prices, crypto_heavy, 'Crypto_Heavy')
    
    print(f"   权重: {dict(zip(prices.columns, crypto_heavy.round(2)))}")
    print(f"   年化收益: {result_crypto.annual_return:.1f}%, 回撤: {result_crypto.max_drawdown:.1f}%, 夏普: {result_crypto.sharpe_ratio:.2f}")
    results.append(result_crypto)
    
    # 总结
    print("\n" + "=" * 70)
    print("📈 策略对比总结")
    print("=" * 70)
    print(f"{'策略':<20} {'年化收益':>10} {'最大回撤':>10} {'夏普比率':>10} {'波动率':>10}")
    print("-" * 60)
    for r in results:
        print(f"{r.strategy_name:<20} {r.annual_return:>9.1f}% {r.max_drawdown:>9.1f}% {r.sharpe_ratio:>10.2f} {r.volatility:>9.1f}%")
    
    # 找出最优组合
    best_sharpe = max(results, key=lambda x: x.sharpe_ratio)
    best_return = max(results, key=lambda x: x.annual_return)
    best_drawdown = max(results, key=lambda x: x.max_drawdown)  # 回撤最小 (最大是最好的，因为是负数)
    
    print("\n🏆 最优策略:")
    print(f"   夏普最高: {best_sharpe.strategy_name} (夏普={best_sharpe.sharpe_ratio:.2f})")
    print(f"   收益最高: {best_return.strategy_name} (年化={best_return.annual_return:.1f}%)")
    print(f"   回撤最小: {best_drawdown.strategy_name} (回撤={best_drawdown.max_drawdown:.1f}%)")
    
    # 检查达标
    print("\n🎯 达标检查:")
    for r in results:
        meets = r.annual_return >= 10 and r.max_drawdown >= -15 and r.sharpe_ratio >= 0.8
        status = "✅ 达标" if meets else "❌ 未达标"
        print(f"   {r.strategy_name}: {status}")
    
    # 保存结果
    equity_rp.to_csv('backtest_results/multi_asset_risk_parity.csv')
    equity_mom.to_csv('backtest_results/multi_asset_momentum.csv')
    
    comparison = {
        'results': [asdict(r) for r in results],
        'correlation_matrix': corr.to_dict(),
        'timestamp': datetime.now().isoformat()
    }
    
    with open('backtest_results/multi_asset_comparison.json', 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"\n💾 结果已保存")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
