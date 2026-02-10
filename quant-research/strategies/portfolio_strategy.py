"""
组合投资策略 - 港股 + BTC
===========================
通过分散化投资和风险管理，追求稳定收益

目标：
- 年化收益 10-20%
- 最大回撤 < 15%
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class PortfolioStats:
    """组合统计"""
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    volatility: float
    calmar_ratio: float


class RiskManager:
    """风险管理器"""
    
    def __init__(
        self,
        max_drawdown_limit: float = 0.15,  # 最大回撤限制
        position_limit: float = 0.20,  # 单一资产最大仓位
        daily_loss_limit: float = 0.03,  # 日内最大亏损
        vol_target: float = 0.15  # 目标年化波动率
    ):
        self.max_drawdown_limit = max_drawdown_limit
        self.position_limit = position_limit
        self.daily_loss_limit = daily_loss_limit
        self.vol_target = vol_target
        
    def calculate_vol_adjusted_weight(
        self, 
        returns: pd.Series, 
        base_weight: float,
        lookback: int = 60
    ) -> float:
        """基于波动率调整权重"""
        if len(returns) < lookback:
            return base_weight
            
        realized_vol = returns.iloc[-lookback:].std() * np.sqrt(252)
        
        if realized_vol <= 0:
            return base_weight
            
        # 波动率调整
        vol_scalar = self.vol_target / realized_vol
        adjusted_weight = base_weight * min(vol_scalar, 1.5)  # 最多放大 1.5 倍
        
        return min(adjusted_weight, self.position_limit)
    
    def should_reduce_risk(
        self, 
        equity_curve: pd.Series,
        current_date_idx: int
    ) -> Tuple[bool, float]:
        """判断是否应该降低风险"""
        if current_date_idx < 20:
            return False, 1.0
            
        # 计算回撤
        equity = equity_curve.iloc[:current_date_idx+1]
        rolling_max = equity.expanding().max()
        drawdown = (equity.iloc[-1] - rolling_max.iloc[-1]) / rolling_max.iloc[-1]
        
        # 如果接近最大回撤限制，降低仓位
        if drawdown < -self.max_drawdown_limit * 0.7:
            # 线性降低仓位
            risk_scalar = max(0.3, 1 - abs(drawdown) / self.max_drawdown_limit)
            return True, risk_scalar
            
        return False, 1.0


class PortfolioBacktester:
    """组合策略回测器"""
    
    def __init__(
        self,
        initial_capital: float = 100000,
        hk_weight: float = 0.5,  # 港股基础权重
        btc_weight: float = 0.5,  # BTC 基础权重
        rebalance_freq: str = 'M',  # 再平衡频率
        transaction_cost: float = 0.001
    ):
        self.initial_capital = initial_capital
        self.hk_weight = hk_weight
        self.btc_weight = btc_weight
        self.rebalance_freq = rebalance_freq
        self.transaction_cost = transaction_cost
        self.risk_manager = RiskManager()
        
    def run(
        self,
        hk_equity: pd.DataFrame,
        btc_equity: pd.DataFrame
    ) -> pd.DataFrame:
        """
        基于子策略的权益曲线进行组合回测
        
        简化方法：按照配置权重组合两个子策略的收益
        """
        # 对齐日期
        common_dates = hk_equity.index.intersection(btc_equity.index)
        hk_equity = hk_equity.loc[common_dates]
        btc_equity = btc_equity.loc[common_dates]
        
        # 计算各子策略的日收益率
        hk_returns = hk_equity['equity'].pct_change().fillna(0)
        btc_returns = btc_equity['equity'].pct_change().fillna(0)
        
        # 初始化
        equity_curve = []
        portfolio_value = self.initial_capital
        
        # 动态权重
        current_hk_weight = self.hk_weight
        current_btc_weight = self.btc_weight
        
        # 生成再平衡日期
        temp_df = pd.DataFrame({'date': common_dates}, index=common_dates)
        rebalance_dates = temp_df.resample(self.rebalance_freq).last().index.tolist()
        
        for i, date in enumerate(common_dates):
            # 检查风险
            if i > 0:
                temp_equity = pd.Series([e['equity'] for e in equity_curve])
                reduce_risk, risk_scalar = self.risk_manager.should_reduce_risk(temp_equity, i-1)
                
                if reduce_risk:
                    current_hk_weight = self.hk_weight * risk_scalar
                    current_btc_weight = self.btc_weight * risk_scalar
            
            # 再平衡日调整权重
            if date in rebalance_dates and i > 60:
                # 基于波动率调整
                current_hk_weight = self.risk_manager.calculate_vol_adjusted_weight(
                    hk_returns.iloc[:i], self.hk_weight
                )
                current_btc_weight = self.risk_manager.calculate_vol_adjusted_weight(
                    btc_returns.iloc[:i], self.btc_weight
                )
                
                # 归一化
                total_weight = current_hk_weight + current_btc_weight
                if total_weight > 1:
                    current_hk_weight /= total_weight
                    current_btc_weight /= total_weight
            
            # 计算当日组合收益
            portfolio_return = (
                current_hk_weight * hk_returns.iloc[i] +
                current_btc_weight * btc_returns.iloc[i]
            )
            
            # 更新组合价值
            portfolio_value *= (1 + portfolio_return)
            
            equity_curve.append({
                'date': date,
                'equity': portfolio_value,
                'hk_weight': current_hk_weight,
                'btc_weight': current_btc_weight,
                'hk_return': hk_returns.iloc[i],
                'btc_return': btc_returns.iloc[i],
                'portfolio_return': portfolio_return
            })
        
        self.equity = pd.DataFrame(equity_curve).set_index('date')
        return self.equity
    
    def get_stats(self) -> PortfolioStats:
        """计算组合统计"""
        equity = self.equity['equity']
        
        # 收益
        total_return = (equity.iloc[-1] / self.initial_capital - 1) * 100
        
        # 年化收益
        days = (self.equity.index[-1] - self.equity.index[0]).days
        years = days / 365
        annual_return = ((equity.iloc[-1] / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # 最大回撤
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()
        
        # 年化波动率
        daily_returns = equity.pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252) * 100
        
        # 夏普比率
        sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
        
        # Calmar 比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        return PortfolioStats(
            total_return=round(total_return, 2),
            annual_return=round(annual_return, 2),
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=round(sharpe, 2),
            volatility=round(volatility, 2),
            calmar_ratio=round(calmar, 2)
        )


def load_backtest_results() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """加载子策略回测结果"""
    try:
        hk_equity = pd.read_csv('backtest_results/hk_equity_curve.csv', 
                                parse_dates=['date'], index_col='date')
        btc_equity = pd.read_csv('backtest_results/btc_equity_curve.csv', 
                                 parse_dates=['date'], index_col='date')
        return hk_equity, btc_equity
    except FileNotFoundError as e:
        print(f"❌ 找不到回测结果文件: {e}")
        print("   请先运行 btc_trend_strategy.py 和 hk_multifactor_strategy.py")
        return None, None


def optimize_weights(
    hk_equity: pd.DataFrame,
    btc_equity: pd.DataFrame,
    target_return: float = 0.15,
    max_drawdown: float = 0.15
) -> Tuple[float, float, PortfolioStats]:
    """
    网格搜索最优权重
    """
    best_sharpe = -np.inf
    best_weights = (0.5, 0.5)
    best_stats = None
    
    for hk_w in np.arange(0.2, 0.81, 0.1):
        for btc_w in np.arange(0.2, 0.81 - hk_w + 0.01, 0.1):
            if hk_w + btc_w > 1.0:
                continue
                
            backtester = PortfolioBacktester(
                initial_capital=100000,
                hk_weight=hk_w,
                btc_weight=btc_w,
                rebalance_freq='M'
            )
            
            equity = backtester.run(hk_equity.copy(), btc_equity.copy())
            stats = backtester.get_stats()
            
            # 满足约束条件
            if abs(stats.max_drawdown) <= max_drawdown * 100:
                if stats.sharpe_ratio > best_sharpe:
                    best_sharpe = stats.sharpe_ratio
                    best_weights = (hk_w, btc_w)
                    best_stats = stats
    
    return best_weights[0], best_weights[1], best_stats


if __name__ == '__main__':
    print("=" * 60)
    print("组合投资策略回测 - 港股 + BTC")
    print("=" * 60)
    
    # 加载子策略结果
    print("\n📥 加载子策略回测结果...")
    hk_equity, btc_equity = load_backtest_results()
    
    if hk_equity is None or btc_equity is None:
        exit(1)
    
    print(f"✅ 港股策略: {len(hk_equity)} 条记录")
    print(f"✅ BTC 策略: {len(btc_equity)} 条记录")
    
    # 基础组合 (50/50)
    print("\n🔄 运行基础组合回测 (50/50)...")
    backtester = PortfolioBacktester(
        initial_capital=100000,
        hk_weight=0.5,
        btc_weight=0.5,
        rebalance_freq='M'
    )
    equity = backtester.run(hk_equity, btc_equity)
    stats = backtester.get_stats()
    
    print("\n📊 基础组合结果 (港股50% + BTC50%):")
    print("-" * 40)
    print(f"总收益率:     {stats.total_return:.2f}%")
    print(f"年化收益率:   {stats.annual_return:.2f}%")
    print(f"最大回撤:     {stats.max_drawdown:.2f}%")
    print(f"年化波动率:   {stats.volatility:.2f}%")
    print(f"夏普比率:     {stats.sharpe_ratio:.2f}")
    print(f"Calmar 比率:  {stats.calmar_ratio:.2f}")
    print("-" * 40)
    
    # 优化权重
    print("\n🔍 搜索最优权重...")
    opt_hk, opt_btc, opt_stats = optimize_weights(
        hk_equity, btc_equity, 
        target_return=0.15, 
        max_drawdown=0.15
    )
    
    if opt_stats:
        print(f"\n📊 最优组合结果 (港股{opt_hk*100:.0f}% + BTC{opt_btc*100:.0f}%):")
        print("-" * 40)
        print(f"总收益率:     {opt_stats.total_return:.2f}%")
        print(f"年化收益率:   {opt_stats.annual_return:.2f}%")
        print(f"最大回撤:     {opt_stats.max_drawdown:.2f}%")
        print(f"年化波动率:   {opt_stats.volatility:.2f}%")
        print(f"夏普比率:     {opt_stats.sharpe_ratio:.2f}")
        print(f"Calmar 比率:  {opt_stats.calmar_ratio:.2f}")
        print("-" * 40)
    else:
        print("⚠️ 在约束条件下未找到满足要求的组合")
        print("   尝试放宽最大回撤限制...")
        opt_hk, opt_btc, opt_stats = optimize_weights(
            hk_equity, btc_equity, 
            target_return=0.15, 
            max_drawdown=0.20  # 放宽到 20%
        )
        if opt_stats:
            print(f"\n📊 次优组合结果 (港股{opt_hk*100:.0f}% + BTC{opt_btc*100:.0f}%):")
            print("-" * 40)
            print(f"总收益率:     {opt_stats.total_return:.2f}%")
            print(f"年化收益率:   {opt_stats.annual_return:.2f}%")
            print(f"最大回撤:     {opt_stats.max_drawdown:.2f}%")
            print(f"年化波动率:   {opt_stats.volatility:.2f}%")
            print(f"夏普比率:     {opt_stats.sharpe_ratio:.2f}")
            print(f"Calmar 比率:  {opt_stats.calmar_ratio:.2f}")
            print("-" * 40)
    
    # 保存最终组合结果
    equity.to_csv('backtest_results/portfolio_equity_curve.csv')
    
    print("\n💾 结果已保存到 backtest_results/portfolio_equity_curve.csv")
    
    # 检查是否达标
    print("\n" + "=" * 60)
    print("📋 目标达成检查:")
    print("-" * 40)
    target_annual = (10, 20)
    target_drawdown = 15
    
    final_stats = opt_stats if opt_stats else stats
    
    annual_ok = target_annual[0] <= final_stats.annual_return <= target_annual[1]
    drawdown_ok = abs(final_stats.max_drawdown) <= target_drawdown
    
    print(f"年化收益 {target_annual[0]}-{target_annual[1]}%: {final_stats.annual_return:.2f}% {'✅' if annual_ok else '❌'}")
    print(f"最大回撤 <{target_drawdown}%:       {final_stats.max_drawdown:.2f}% {'✅' if drawdown_ok else '❌'}")
    
    if annual_ok and drawdown_ok:
        print("\n🎉 全部目标达成！")
    else:
        print("\n⚠️ 部分目标未达成，需要进一步优化")
    print("=" * 60)
