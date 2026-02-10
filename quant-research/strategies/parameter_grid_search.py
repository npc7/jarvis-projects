"""
阶段 1: BTC 波动率策略参数网格搜索
==================================
时间: 2026-02-09 20:30-22:00

测试参数范围:
- 动量周期: 10, 14, 20, 30, 50, 100 天
- 目标波动率: 8%, 10%, 12%, 15%
- 止损比例: 2%, 3%, 5%, 8%

总组合数: 6 × 4 × 4 = 96 种
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import warnings
import json
from datetime import datetime
import itertools

warnings.filterwarnings('ignore')


@dataclass
class BacktestResult:
    """回测结果"""
    # 参数
    momentum_period: int
    target_volatility: float
    stop_loss_pct: float
    
    # 结果
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_return: float
    max_consecutive_losses: int
    max_drawdown_duration: int  # 天
    final_capital: float


class VolatilityTargetStrategy:
    """
    波动率目标策略
    
    核心思想：
    - 使用动量信号决定方向
    - 根据目标波动率动态调整仓位
    - 设置止损保护
    """
    
    def __init__(
        self,
        momentum_period: int = 20,
        target_volatility: float = 0.10,  # 10%
        stop_loss_pct: float = 0.05,  # 5%
        volatility_lookback: int = 20,
        rebalance_threshold: float = 0.1,  # 10% 偏离再平衡
        min_position: float = 0.1,
        max_position: float = 1.5,  # 允许适度杠杆
    ):
        self.momentum_period = momentum_period
        self.target_volatility = target_volatility
        self.stop_loss_pct = stop_loss_pct
        self.volatility_lookback = volatility_lookback
        self.rebalance_threshold = rebalance_threshold
        self.min_position = min_position
        self.max_position = max_position
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = df.copy()
        
        # 日收益率
        df['returns'] = df['close'].pct_change()
        
        # 动量信号 (过去 N 天收益)
        df['momentum'] = df['close'].pct_change(self.momentum_period)
        
        # 滚动波动率 (年化)
        df['volatility'] = df['returns'].rolling(self.volatility_lookback).std() * np.sqrt(252)
        
        # EMA (辅助趋势判断)
        df['ema_short'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=30, adjust=False).mean()
        df['trend'] = np.where(df['ema_short'] > df['ema_long'], 1, -1)
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_position_size(self, current_vol: float, signal: int) -> float:
        """根据波动率计算仓位"""
        if current_vol <= 0 or np.isnan(current_vol):
            return 0
            
        # 波动率目标调整
        raw_position = self.target_volatility / current_vol
        
        # 限制仓位范围
        position = np.clip(raw_position, self.min_position, self.max_position)
        
        return position * signal


def backtest_strategy(
    df: pd.DataFrame,
    strategy: VolatilityTargetStrategy,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, BacktestResult]:
    """运行回测"""
    
    # 计算指标
    df = strategy.calculate_indicators(df)
    
    # 初始化
    capital = initial_capital
    position = 0.0  # 仓位比例
    entry_price = 0.0
    peak_capital = initial_capital
    drawdown_start = None
    max_dd_duration = 0
    
    # 记录
    equity_curve = []
    trades = []
    
    # 从足够的历史数据开始
    start_idx = max(strategy.momentum_period, strategy.volatility_lookback) + 5
    
    consecutive_losses = 0
    max_consecutive_losses = 0
    
    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        date = df.index[i]
        
        current_price = row['close']
        
        # 计算当前权益
        if position != 0:
            pnl_pct = (current_price - entry_price) / entry_price * position
            current_equity = capital * (1 + pnl_pct)
        else:
            current_equity = capital
            
        # 止损检查
        if position != 0:
            if position > 0:
                loss_pct = (current_price - entry_price) / entry_price
                if loss_pct < -strategy.stop_loss_pct:
                    # 止损
                    realized_pnl = capital * position * loss_pct
                    capital += realized_pnl
                    trades.append({
                        'date': date,
                        'action': 'stop_loss',
                        'price': current_price,
                        'position': position,
                        'pnl': realized_pnl,
                        'pnl_pct': loss_pct * 100
                    })
                    position = 0
                    entry_price = 0
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:  # 空头
                loss_pct = -(current_price - entry_price) / entry_price
                if loss_pct < -strategy.stop_loss_pct:
                    realized_pnl = capital * abs(position) * loss_pct
                    capital += realized_pnl
                    trades.append({
                        'date': date,
                        'action': 'stop_loss',
                        'price': current_price,
                        'position': position,
                        'pnl': realized_pnl,
                        'pnl_pct': loss_pct * 100
                    })
                    position = 0
                    entry_price = 0
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        # 生成信号
        momentum = row['momentum']
        volatility = row['volatility']
        trend = row['trend']
        rsi = row['rsi']
        
        if pd.isna(momentum) or pd.isna(volatility) or volatility <= 0:
            equity_curve.append({
                'date': date,
                'equity': current_equity,
                'position': position,
                'close': current_price
            })
            continue
        
        # 动量信号
        if momentum > 0 and trend == 1 and rsi < 70:
            signal = 1
        elif momentum < 0 and trend == -1 and rsi > 30:
            signal = -1
        else:
            signal = 0
        
        # 计算目标仓位
        target_position = strategy.calculate_position_size(volatility, signal)
        
        # 检查是否需要再平衡
        position_diff = abs(target_position - position)
        should_rebalance = (
            position_diff > strategy.rebalance_threshold or
            (position == 0 and signal != 0) or
            (position != 0 and signal == 0)
        )
        
        if should_rebalance and position != target_position:
            # 平掉旧仓位
            if position != 0:
                if position > 0:
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = -(current_price - entry_price) / entry_price
                    
                realized_pnl = capital * abs(position) * pnl_pct
                capital += realized_pnl
                
                trades.append({
                    'date': date,
                    'action': 'close',
                    'price': current_price,
                    'position': position,
                    'pnl': realized_pnl,
                    'pnl_pct': pnl_pct * 100
                })
                
                if realized_pnl > 0:
                    consecutive_losses = 0
                else:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            
            # 开新仓位
            if target_position != 0:
                position = target_position
                entry_price = current_price
                trades.append({
                    'date': date,
                    'action': 'open',
                    'price': current_price,
                    'position': position,
                    'pnl': 0,
                    'pnl_pct': 0
                })
            else:
                position = 0
                entry_price = 0
        
        # 更新权益
        if position != 0:
            if position > 0:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = -(current_price - entry_price) / entry_price
            current_equity = capital * (1 + abs(position) * pnl_pct)
        else:
            current_equity = capital
        
        # 跟踪回撤
        if current_equity > peak_capital:
            peak_capital = current_equity
            drawdown_start = None
        else:
            if drawdown_start is None:
                drawdown_start = date
        
        if drawdown_start is not None:
            dd_duration = (date - drawdown_start).days
            max_dd_duration = max(max_dd_duration, dd_duration)
        
        equity_curve.append({
            'date': date,
            'equity': current_equity,
            'position': position,
            'close': current_price,
            'volatility': volatility
        })
    
    # 转换为 DataFrame
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    
    # 计算统计指标
    equity = equity_df['equity']
    
    # 基础收益
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    days = (equity_df.index[-1] - equity_df.index[0]).days
    years = days / 365
    annual_return = ((equity.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    # 最大回撤
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    # 日收益
    daily_returns = equity.pct_change().dropna()
    
    # 夏普比率
    rf = 0.02  # 无风险利率 2%
    excess_return = daily_returns.mean() * 252 - rf
    sharpe = excess_return / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    
    # Sortino 比率 (只计算下行风险)
    negative_returns = daily_returns[daily_returns < 0]
    downside_std = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0.01
    sortino = excess_return / downside_std if downside_std > 0 else 0
    
    # Calmar 比率
    calmar = abs(annual_return / max_drawdown) if max_drawdown != 0 else 0
    
    # 交易统计
    if len(trades_df) > 0:
        closed_trades = trades_df[trades_df['action'].isin(['close', 'stop_loss'])]
        if len(closed_trades) > 0:
            wins = closed_trades[closed_trades['pnl'] > 0]
            losses = closed_trades[closed_trades['pnl'] < 0]
            win_rate = len(wins) / len(closed_trades) * 100
            
            total_wins = wins['pnl'].sum() if len(wins) > 0 else 0
            total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 0.01
            profit_factor = total_wins / total_losses if total_losses > 0 else 999
            
            avg_trade_return = closed_trades['pnl_pct'].mean()
        else:
            win_rate = 0
            profit_factor = 0
            avg_trade_return = 0
        total_trades = len(trades_df[trades_df['action'] == 'open'])
    else:
        win_rate = 0
        profit_factor = 0
        avg_trade_return = 0
        total_trades = 0
    
    result = BacktestResult(
        momentum_period=strategy.momentum_period,
        target_volatility=strategy.target_volatility,
        stop_loss_pct=strategy.stop_loss_pct,
        total_return=round(total_return, 2),
        annual_return=round(annual_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        calmar_ratio=round(calmar, 3),
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        total_trades=total_trades,
        avg_trade_return=round(avg_trade_return, 2),
        max_consecutive_losses=max_consecutive_losses,
        max_drawdown_duration=max_dd_duration,
        final_capital=round(equity.iloc[-1], 2)
    )
    
    return equity_df, result


def fetch_btc_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取 BTC 数据"""
    try:
        import yfinance as yf
        btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)
        
        if isinstance(btc.columns, pd.MultiIndex):
            btc.columns = [c[0].lower() for c in btc.columns]
        else:
            btc.columns = [c.lower() for c in btc.columns]
        
        return btc
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()


def run_grid_search(df: pd.DataFrame) -> List[BacktestResult]:
    """运行完整的网格搜索"""
    
    # 参数网格
    momentum_periods = [10, 14, 20, 30, 50, 100]
    target_volatilities = [0.08, 0.10, 0.12, 0.15]
    stop_loss_pcts = [0.02, 0.03, 0.05, 0.08]
    
    total_combinations = len(momentum_periods) * len(target_volatilities) * len(stop_loss_pcts)
    
    print(f"\n🔍 开始网格搜索...")
    print(f"   动量周期: {momentum_periods}")
    print(f"   目标波动率: {[f'{v*100:.0f}%' for v in target_volatilities]}")
    print(f"   止损比例: {[f'{v*100:.0f}%' for v in stop_loss_pcts]}")
    print(f"   总组合数: {total_combinations}")
    print("-" * 60)
    
    results = []
    count = 0
    
    for momentum in momentum_periods:
        for target_vol in target_volatilities:
            for stop_loss in stop_loss_pcts:
                count += 1
                
                strategy = VolatilityTargetStrategy(
                    momentum_period=momentum,
                    target_volatility=target_vol,
                    stop_loss_pct=stop_loss
                )
                
                try:
                    _, result = backtest_strategy(df, strategy)
                    results.append(result)
                    
                    if count % 10 == 0:
                        print(f"   [{count}/{total_combinations}] 动量={momentum}, 波动率={target_vol*100:.0f}%, 止损={stop_loss*100:.0f}% -> 年化={result.annual_return:.1f}%, 回撤={result.max_drawdown:.1f}%")
                        
                except Exception as e:
                    print(f"   ❌ 错误: {e}")
    
    return results


def analyze_results(results: List[BacktestResult]) -> Dict:
    """分析网格搜索结果"""
    
    df = pd.DataFrame([asdict(r) for r in results])
    
    # 筛选达标策略
    qualified = df[
        (df['annual_return'] >= 10) & 
        (df['max_drawdown'] >= -15) &
        (df['sharpe_ratio'] >= 0.8)
    ]
    
    # 最优策略 (夏普最高)
    best_sharpe = df.loc[df['sharpe_ratio'].idxmax()]
    
    # 最优收益 (在回撤可控下)
    controlled_dd = df[df['max_drawdown'] >= -15]
    if len(controlled_dd) > 0:
        best_return = controlled_dd.loc[controlled_dd['annual_return'].idxmax()]
    else:
        best_return = None
    
    # 最优风险调整 (Calmar)
    best_calmar = df.loc[df['calmar_ratio'].idxmax()]
    
    # 参数敏感性分析
    momentum_analysis = df.groupby('momentum_period').agg({
        'annual_return': 'mean',
        'max_drawdown': 'mean',
        'sharpe_ratio': 'mean',
        'calmar_ratio': 'mean'
    }).round(2)
    
    volatility_analysis = df.groupby('target_volatility').agg({
        'annual_return': 'mean',
        'max_drawdown': 'mean',
        'sharpe_ratio': 'mean',
        'calmar_ratio': 'mean'
    }).round(2)
    
    stop_loss_analysis = df.groupby('stop_loss_pct').agg({
        'annual_return': 'mean',
        'max_drawdown': 'mean',
        'sharpe_ratio': 'mean',
        'calmar_ratio': 'mean'
    }).round(2)
    
    return {
        'all_results': df,
        'qualified': qualified,
        'best_sharpe': best_sharpe,
        'best_return': best_return,
        'best_calmar': best_calmar,
        'momentum_analysis': momentum_analysis,
        'volatility_analysis': volatility_analysis,
        'stop_loss_analysis': stop_loss_analysis
    }


def main():
    """主函数"""
    print("=" * 70)
    print("🚀 BTC 波动率目标策略 - 参数网格搜索")
    print("=" * 70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取数据
    print("\n📥 获取 BTC 历史数据...")
    df = fetch_btc_data('2020-01-01', '2026-02-01')
    
    if len(df) == 0:
        print("❌ 无法获取数据")
        return
        
    print(f"✅ 获取到 {len(df)} 条数据 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
    
    # 网格搜索
    results = run_grid_search(df)
    
    # 分析结果
    print("\n" + "=" * 70)
    print("📊 网格搜索结果分析")
    print("=" * 70)
    
    analysis = analyze_results(results)
    
    # 打印达标策略
    print(f"\n✅ 达标策略数量: {len(analysis['qualified'])} / {len(results)}")
    print("   (年化>=10%, 回撤>=-15%, 夏普>=0.8)")
    
    if len(analysis['qualified']) > 0:
        print("\n   前 10 名达标策略:")
        print("-" * 90)
        top10 = analysis['qualified'].nlargest(10, 'sharpe_ratio')
        for idx, row in top10.iterrows():
            print(f"   动量={int(row['momentum_period']):3d}, 波动率={row['target_volatility']*100:4.0f}%, 止损={row['stop_loss_pct']*100:2.0f}% | "
                  f"年化={row['annual_return']:6.1f}%, 回撤={row['max_drawdown']:6.1f}%, 夏普={row['sharpe_ratio']:.2f}, Calmar={row['calmar_ratio']:.2f}")
    
    # 最优策略
    print("\n🏆 最优策略:")
    print("-" * 70)
    
    best = analysis['best_sharpe']
    print(f"\n   【夏普最高】")
    print(f"   参数: 动量={int(best['momentum_period'])}天, 波动率={best['target_volatility']*100:.0f}%, 止损={best['stop_loss_pct']*100:.0f}%")
    print(f"   表现: 年化={best['annual_return']:.2f}%, 回撤={best['max_drawdown']:.2f}%, 夏普={best['sharpe_ratio']:.3f}")
    print(f"   交易: 总计={int(best['total_trades'])}笔, 胜率={best['win_rate']:.1f}%, 盈亏比={best['profit_factor']:.2f}")
    
    if analysis['best_return'] is not None:
        best = analysis['best_return']
        print(f"\n   【收益最高 (回撤<=15%)】")
        print(f"   参数: 动量={int(best['momentum_period'])}天, 波动率={best['target_volatility']*100:.0f}%, 止损={best['stop_loss_pct']*100:.0f}%")
        print(f"   表现: 年化={best['annual_return']:.2f}%, 回撤={best['max_drawdown']:.2f}%, 夏普={best['sharpe_ratio']:.3f}")
    
    best = analysis['best_calmar']
    print(f"\n   【Calmar最高】")
    print(f"   参数: 动量={int(best['momentum_period'])}天, 波动率={best['target_volatility']*100:.0f}%, 止损={best['stop_loss_pct']*100:.0f}%")
    print(f"   表现: 年化={best['annual_return']:.2f}%, 回撤={best['max_drawdown']:.2f}%, Calmar={best['calmar_ratio']:.3f}")
    
    # 参数敏感性
    print("\n📈 参数敏感性分析:")
    print("-" * 70)
    
    print("\n   动量周期影响:")
    print(analysis['momentum_analysis'].to_string())
    
    print("\n   目标波动率影响:")
    print(analysis['volatility_analysis'].to_string())
    
    print("\n   止损比例影响:")
    print(analysis['stop_loss_analysis'].to_string())
    
    # 保存结果
    print("\n💾 保存结果...")
    analysis['all_results'].to_csv('backtest_results/parameter_grid/grid_search_results.csv', index=False)
    
    if len(analysis['qualified']) > 0:
        analysis['qualified'].to_csv('backtest_results/parameter_grid/qualified_strategies.csv', index=False)
    
    # 保存最优参数
    best_params = {
        'best_sharpe': {
            'momentum_period': int(analysis['best_sharpe']['momentum_period']),
            'target_volatility': float(analysis['best_sharpe']['target_volatility']),
            'stop_loss_pct': float(analysis['best_sharpe']['stop_loss_pct']),
            'annual_return': float(analysis['best_sharpe']['annual_return']),
            'max_drawdown': float(analysis['best_sharpe']['max_drawdown']),
            'sharpe_ratio': float(analysis['best_sharpe']['sharpe_ratio'])
        }
    }
    
    if analysis['best_return'] is not None:
        best_params['best_return'] = {
            'momentum_period': int(analysis['best_return']['momentum_period']),
            'target_volatility': float(analysis['best_return']['target_volatility']),
            'stop_loss_pct': float(analysis['best_return']['stop_loss_pct']),
            'annual_return': float(analysis['best_return']['annual_return']),
            'max_drawdown': float(analysis['best_return']['max_drawdown']),
            'sharpe_ratio': float(analysis['best_return']['sharpe_ratio'])
        }
    
    with open('backtest_results/parameter_grid/best_params.json', 'w') as f:
        json.dump(best_params, f, indent=2)
    
    print("✅ 结果已保存到 backtest_results/parameter_grid/")
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return analysis


if __name__ == '__main__':
    main()
