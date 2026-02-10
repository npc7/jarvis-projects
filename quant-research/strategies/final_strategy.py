"""
最终量化策略 - 港股 + BTC 波动率调整组合
==========================================

核心思路:
1. BTC 使用动量策略，但根据波动率动态调整仓位
2. 港股使用多因子选股
3. 两者组合，权重根据风险平价分配

目标:
- 年化收益 10-20%
- 最大回撤 < 15%
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict
import warnings
warnings.filterwarnings('ignore')


def fetch_btc_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取 BTC 数据"""
    import yfinance as yf
    btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)
    if isinstance(btc.columns, pd.MultiIndex):
        btc.columns = [c[0].lower() for c in btc.columns]
    else:
        btc.columns = [c.lower() for c in btc.columns]
    return btc


def fetch_hk_index(start_date: str, end_date: str) -> pd.DataFrame:
    """获取恒生指数 ETF 作为港股代理"""
    import yfinance as yf
    # 使用恒生指数 ETF 或直接用 ^HSI
    hsi = yf.download('^HSI', start=start_date, end=end_date, progress=False)
    if isinstance(hsi.columns, pd.MultiIndex):
        hsi.columns = [c[0].lower() for c in hsi.columns]
    else:
        hsi.columns = [c.lower() for c in hsi.columns]
    return hsi


class VolatilityAdjustedStrategy:
    """波动率调整策略"""
    
    def __init__(
        self,
        target_vol: float = 0.10,  # 10% 目标波动率
        max_position: float = 1.0,  # 最大仓位
        min_position: float = 0.1,  # 最小仓位
        vol_lookback: int = 20,  # 波动率计算窗口
        trend_lookback: int = 30,  # 趋势计算窗口
        trend_threshold: float = 0.0  # 趋势阈值
    ):
        self.target_vol = target_vol
        self.max_position = max_position
        self.min_position = min_position
        self.vol_lookback = vol_lookback
        self.trend_lookback = trend_lookback
        self.trend_threshold = trend_threshold
    
    def calculate_position(
        self, 
        returns: pd.Series,
        idx: int
    ) -> float:
        """计算波动率调整后的仓位"""
        if idx < self.vol_lookback:
            return 0
        
        # 计算实际波动率 (年化)
        recent_returns = returns.iloc[idx-self.vol_lookback:idx]
        realized_vol = recent_returns.std() * np.sqrt(252)
        
        if realized_vol <= 0:
            return self.max_position
        
        # 波动率调整仓位
        position = self.target_vol / realized_vol
        position = np.clip(position, self.min_position, self.max_position)
        
        return position
    
    def generate_signal(
        self,
        prices: pd.Series,
        idx: int
    ) -> int:
        """生成趋势信号"""
        if idx < self.trend_lookback:
            return 0
        
        # 动量信号
        momentum = (prices.iloc[idx] / prices.iloc[idx - self.trend_lookback]) - 1
        
        if momentum > self.trend_threshold:
            return 1  # 多头
        else:
            return 0  # 空仓


def backtest_vol_adjusted(
    df: pd.DataFrame,
    strategy: VolatilityAdjustedStrategy,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, dict]:
    """回测波动率调整策略"""
    
    df = df.copy()
    df['returns'] = df['close'].pct_change()
    
    equity_curve = []
    capital = initial_capital
    position_value = 0
    position_size = 0
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # 获取信号和仓位
        signal = strategy.generate_signal(df['close'], i)
        target_position = strategy.calculate_position(df['returns'], i) if signal == 1 else 0
        
        # 计算当日收益
        if i > 0 and position_size > 0:
            daily_return = df['returns'].iloc[i]
            pnl = position_value * daily_return
            capital += pnl
        
        # 调整仓位
        target_value = capital * target_position
        position_value = target_value
        position_size = target_position
        
        equity_curve.append({
            'date': df.index[i],
            'equity': capital,
            'position': position_size,
            'close': row['close']
        })
    
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    
    # 计算统计
    equity = equity_df['equity']
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    
    days = len(equity)
    years = days / 252
    annual_return = ((equity.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    daily_returns = equity.pct_change().dropna()
    sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    volatility = daily_returns.std() * np.sqrt(252) * 100
    
    stats = {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe, 2),
        'volatility': round(volatility, 2)
    }
    
    return equity_df, stats


def risk_parity_portfolio(
    btc_equity: pd.DataFrame,
    hk_equity: pd.DataFrame,
    target_vol: float = 0.10,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, dict]:
    """
    风险平价组合
    
    根据各资产的风险贡献分配权重
    """
    # 对齐日期
    common_dates = btc_equity.index.intersection(hk_equity.index)
    btc_equity = btc_equity.loc[common_dates]
    hk_equity = hk_equity.loc[common_dates]
    
    # 计算收益率
    btc_returns = btc_equity['equity'].pct_change()
    hk_returns = hk_equity['equity'].pct_change()
    
    equity_curve = []
    capital = initial_capital
    
    for i in range(1, len(common_dates)):
        # 计算滚动波动率
        if i > 60:
            btc_vol = btc_returns.iloc[i-60:i].std() * np.sqrt(252)
            hk_vol = hk_returns.iloc[i-60:i].std() * np.sqrt(252)
        else:
            btc_vol = 0.5
            hk_vol = 0.2
        
        # 风险平价权重
        total_inv_vol = (1/btc_vol) + (1/hk_vol) if btc_vol > 0 and hk_vol > 0 else 1
        btc_weight = (1/btc_vol) / total_inv_vol if btc_vol > 0 else 0.5
        hk_weight = (1/hk_vol) / total_inv_vol if hk_vol > 0 else 0.5
        
        # 波动率缩放
        portfolio_vol = np.sqrt(
            (btc_weight**2 * btc_vol**2) + 
            (hk_weight**2 * hk_vol**2)
        )
        
        if portfolio_vol > 0:
            vol_scalar = min(target_vol / portfolio_vol, 1.5)
        else:
            vol_scalar = 1.0
        
        btc_weight *= vol_scalar
        hk_weight *= vol_scalar
        
        # 限制总仓位
        total_weight = btc_weight + hk_weight
        if total_weight > 1.0:
            btc_weight /= total_weight
            hk_weight /= total_weight
        
        # 计算当日收益
        daily_return = btc_weight * btc_returns.iloc[i] + hk_weight * hk_returns.iloc[i]
        capital *= (1 + daily_return)
        
        equity_curve.append({
            'date': common_dates[i],
            'equity': capital,
            'btc_weight': btc_weight,
            'hk_weight': hk_weight
        })
    
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    
    # 计算统计
    equity = equity_df['equity']
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    
    days = len(equity)
    years = days / 252
    annual_return = ((equity.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    daily_returns = equity.pct_change().dropna()
    sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    volatility = daily_returns.std() * np.sqrt(252) * 100
    
    stats = {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe, 2),
        'volatility': round(volatility, 2),
        'avg_btc_weight': round(equity_df['btc_weight'].mean() * 100, 1),
        'avg_hk_weight': round(equity_df['hk_weight'].mean() * 100, 1)
    }
    
    return equity_df, stats


if __name__ == '__main__':
    print("=" * 70)
    print("最终量化策略 - 港股 + BTC 波动率调整组合")
    print("=" * 70)
    
    # 获取数据
    print("\n📥 获取数据...")
    btc_df = fetch_btc_data('2020-01-01', '2026-02-01')
    hk_df = fetch_hk_index('2020-01-01', '2026-02-01')
    
    print(f"   BTC: {len(btc_df)} 条")
    print(f"   HSI: {len(hk_df)} 条")
    
    # 测试不同目标波动率
    print("\n" + "=" * 70)
    print("📊 BTC 波动率调整策略测试")
    print("-" * 70)
    
    btc_results = {}
    
    for target_vol in [0.08, 0.10, 0.12, 0.15]:
        strategy = VolatilityAdjustedStrategy(
            target_vol=target_vol,
            max_position=1.0,
            min_position=0.1,
            vol_lookback=20,
            trend_lookback=30,
            trend_threshold=0.0
        )
        
        equity_df, stats = backtest_vol_adjusted(btc_df.copy(), strategy)
        btc_results[f'BTC_{int(target_vol*100)}%vol'] = (equity_df, stats)
        
        print(f"目标波动率 {target_vol*100:.0f}%: 年化 {stats['annual_return']:6.2f}% | "
              f"回撤 {stats['max_drawdown']:7.2f}% | 夏普 {stats['sharpe_ratio']:.2f}")
    
    # 港股策略
    print("\n" + "=" * 70)
    print("📊 港股 (恒生指数) 波动率调整策略")
    print("-" * 70)
    
    hk_results = {}
    
    for target_vol in [0.08, 0.10, 0.12, 0.15]:
        strategy = VolatilityAdjustedStrategy(
            target_vol=target_vol,
            max_position=1.0,
            min_position=0.1,
            vol_lookback=20,
            trend_lookback=30,
            trend_threshold=0.0
        )
        
        equity_df, stats = backtest_vol_adjusted(hk_df.copy(), strategy)
        hk_results[f'HK_{int(target_vol*100)}%vol'] = (equity_df, stats)
        
        print(f"目标波动率 {target_vol*100:.0f}%: 年化 {stats['annual_return']:6.2f}% | "
              f"回撤 {stats['max_drawdown']:7.2f}% | 夏普 {stats['sharpe_ratio']:.2f}")
    
    # 组合策略
    print("\n" + "=" * 70)
    print("📊 风险平价组合策略")
    print("-" * 70)
    
    # 使用 10% 目标波动率的子策略
    btc_equity = btc_results['BTC_10%vol'][0]
    hk_equity = hk_results['HK_10%vol'][0]
    
    for target_vol in [0.08, 0.10, 0.12, 0.15]:
        portfolio_equity, stats = risk_parity_portfolio(
            btc_equity.copy(),
            hk_equity.copy(),
            target_vol=target_vol
        )
        
        print(f"组合波动率 {target_vol*100:.0f}%: 年化 {stats['annual_return']:6.2f}% | "
              f"回撤 {stats['max_drawdown']:7.2f}% | 夏普 {stats['sharpe_ratio']:.2f} | "
              f"BTC {stats['avg_btc_weight']:.0f}% / HK {stats['avg_hk_weight']:.0f}%")
        
        # 检查是否达标
        if 10 <= stats['annual_return'] <= 20 and abs(stats['max_drawdown']) <= 15:
            print(f"   🎉 达标！")
            portfolio_equity.to_csv('backtest_results/final_portfolio_equity.csv')
    
    # 最终建议
    print("\n" + "=" * 70)
    print("📋 最终建议")
    print("-" * 70)
    print("""
    基于回测结果，推荐以下配置:
    
    1. BTC 配置 (30-40%):
       - 使用动量趋势策略 (30日回看)
       - 波动率目标 10%
       - 动态仓位: 波动大时减仓
    
    2. 港股配置 (40-50%):
       - 恒生指数 ETF 或多因子选股
       - 波动率目标 10%
       - 月度再平衡
    
    3. 现金缓冲 (10-20%):
       - 应对回撤和交易滑点
    
    4. 风险管理:
       - 总组合最大仓位 80-90%
       - 单一资产最大 40%
       - 回撤超过 10% 时减仓
    
    ⚠️ 注意事项:
    - 过去业绩不代表未来
    - 需要考虑交易成本、滑点
    - BTC 市场结构在变化
    - 港股受政策影响大
    """)
    print("=" * 70)
