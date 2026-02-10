"""
BTC 简单趋势策略
================
使用最简单有效的趋势跟随方法

目标：年化 10-20%，回撤 < 20%
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


def fetch_btc_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取 BTC 数据"""
    try:
        import yfinance as yf
        btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)
        
        if isinstance(btc.columns, pd.MultiIndex):
            btc.columns = [c[0].lower() for c in btc.columns]
        else:
            btc.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in btc.columns]
        
        return btc
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()


def simple_ma_strategy(
    df: pd.DataFrame,
    fast_ma: int = 20,
    slow_ma: int = 50,
    position_size: float = 0.9,  # 90% 仓位
    initial_capital: float = 100000
) -> tuple:
    """
    简单双均线策略
    
    规则:
    - 快线 > 慢线: 做多
    - 快线 < 慢线: 空仓
    """
    df = df.copy()
    
    # 计算均线
    df['ma_fast'] = df['close'].rolling(fast_ma).mean()
    df['ma_slow'] = df['close'].rolling(slow_ma).mean()
    
    # 生成信号
    df['signal'] = np.where(df['ma_fast'] > df['ma_slow'], 1, 0)
    
    # 计算收益
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['signal'].shift(1) * df['returns'] * position_size
    
    # 计算权益曲线
    df['equity'] = initial_capital * (1 + df['strategy_returns'].fillna(0)).cumprod()
    
    # 计算买入持有
    df['buy_hold'] = initial_capital * (1 + df['returns'].fillna(0)).cumprod()
    
    return df


def donchian_breakout_strategy(
    df: pd.DataFrame,
    period: int = 20,
    position_size: float = 0.9,
    initial_capital: float = 100000
) -> tuple:
    """
    Donchian 突破策略 (海龟交易法简化版)
    
    规则:
    - 突破 N 日最高价: 做多
    - 跌破 N 日最低价: 平仓
    """
    df = df.copy()
    
    # 计算通道
    df['upper'] = df['high'].rolling(period).max().shift(1)
    df['lower'] = df['low'].rolling(period).min().shift(1)
    
    # 生成信号
    position = 0
    signals = []
    
    for i in range(len(df)):
        if i < period + 1:
            signals.append(0)
            continue
            
        row = df.iloc[i]
        
        if position == 0:
            if row['close'] > row['upper']:
                position = 1
        else:
            if row['close'] < row['lower']:
                position = 0
                
        signals.append(position)
    
    df['signal'] = signals
    
    # 计算收益
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['signal'].shift(1) * df['returns'] * position_size
    df['equity'] = initial_capital * (1 + df['strategy_returns'].fillna(0)).cumprod()
    
    return df


def momentum_strategy(
    df: pd.DataFrame,
    lookback: int = 30,
    threshold: float = 0.05,  # 5% 动量阈值
    position_size: float = 0.9,
    initial_capital: float = 100000
) -> tuple:
    """
    动量策略
    
    规则:
    - 过去 N 天收益 > 阈值: 做多
    - 否则: 空仓
    """
    df = df.copy()
    
    # 计算动量
    df['momentum'] = df['close'].pct_change(lookback)
    
    # 生成信号
    df['signal'] = np.where(df['momentum'] > threshold, 1, 0)
    
    # 计算收益
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['signal'].shift(1) * df['returns'] * position_size
    df['equity'] = initial_capital * (1 + df['strategy_returns'].fillna(0)).cumprod()
    
    return df


def calculate_stats(equity: pd.Series, initial_capital: float) -> dict:
    """计算统计指标"""
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    
    days = len(equity)
    years = days / 252
    annual_return = ((equity.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    daily_returns = equity.pct_change().dropna()
    sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    
    return {
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe, 2)
    }


def test_all_strategies(df: pd.DataFrame, initial_capital: float = 100000):
    """测试所有策略"""
    results = {}
    
    # 策略1: 简单双均线
    print("\n📈 策略1: 双均线策略 (MA20/50)")
    df_ma = simple_ma_strategy(df, fast_ma=20, slow_ma=50, position_size=0.9, initial_capital=initial_capital)
    stats = calculate_stats(df_ma['equity'], initial_capital)
    results['双均线 20/50'] = stats
    print(f"   年化: {stats['annual_return']:.2f}%, 回撤: {stats['max_drawdown']:.2f}%, 夏普: {stats['sharpe_ratio']:.2f}")
    
    # 策略2: 更快的均线
    print("\n📈 策略2: 双均线策略 (MA10/30)")
    df_ma2 = simple_ma_strategy(df, fast_ma=10, slow_ma=30, position_size=0.9, initial_capital=initial_capital)
    stats = calculate_stats(df_ma2['equity'], initial_capital)
    results['双均线 10/30'] = stats
    print(f"   年化: {stats['annual_return']:.2f}%, 回撤: {stats['max_drawdown']:.2f}%, 夏普: {stats['sharpe_ratio']:.2f}")
    
    # 策略3: Donchian 突破
    print("\n📈 策略3: Donchian 突破 (20日)")
    df_donchian = donchian_breakout_strategy(df, period=20, position_size=0.9, initial_capital=initial_capital)
    stats = calculate_stats(df_donchian['equity'], initial_capital)
    results['Donchian 20'] = stats
    print(f"   年化: {stats['annual_return']:.2f}%, 回撤: {stats['max_drawdown']:.2f}%, 夏普: {stats['sharpe_ratio']:.2f}")
    
    # 策略4: 动量策略
    print("\n📈 策略4: 动量策略 (30日)")
    df_momentum = momentum_strategy(df, lookback=30, threshold=0.05, position_size=0.9, initial_capital=initial_capital)
    stats = calculate_stats(df_momentum['equity'], initial_capital)
    results['动量 30日'] = stats
    print(f"   年化: {stats['annual_return']:.2f}%, 回撤: {stats['max_drawdown']:.2f}%, 夏普: {stats['sharpe_ratio']:.2f}")
    
    # 策略5: 买入持有
    print("\n📈 策略5: 买入持有 (基准)")
    df['returns'] = df['close'].pct_change()
    df['buy_hold'] = initial_capital * (1 + df['returns'].fillna(0)).cumprod()
    stats = calculate_stats(df['buy_hold'], initial_capital)
    results['买入持有'] = stats
    print(f"   年化: {stats['annual_return']:.2f}%, 回撤: {stats['max_drawdown']:.2f}%, 夏普: {stats['sharpe_ratio']:.2f}")
    
    return results, df_ma, df_donchian


if __name__ == '__main__':
    print("=" * 60)
    print("BTC 简单趋势策略对比")
    print("=" * 60)
    
    # 获取数据
    print("\n📥 获取 BTC 历史数据...")
    df = fetch_btc_data('2020-01-01', '2026-02-01')
    
    if len(df) == 0:
        print("❌ 无法获取数据")
        exit(1)
        
    print(f"✅ 获取到 {len(df)} 条数据")
    print(f"   时间范围: {df.index[0]} 至 {df.index[-1]}")
    
    # 测试所有策略
    results, df_ma, df_donchian = test_all_strategies(df, initial_capital=100000)
    
    # 找出最佳策略
    print("\n" + "=" * 60)
    print("📊 策略对比总结")
    print("-" * 60)
    
    best_strategy = None
    best_score = -np.inf
    
    for name, stats in results.items():
        # 综合评分: 年化/回撤比 + 夏普
        if stats['max_drawdown'] != 0:
            score = stats['annual_return'] / abs(stats['max_drawdown']) + stats['sharpe_ratio']
        else:
            score = stats['sharpe_ratio']
            
        print(f"{name:15} | 年化: {stats['annual_return']:6.2f}% | 回撤: {stats['max_drawdown']:7.2f}% | 夏普: {stats['sharpe_ratio']:.2f} | 评分: {score:.2f}")
        
        if score > best_score:
            best_score = score
            best_strategy = name
    
    print("-" * 60)
    print(f"🏆 最佳策略: {best_strategy}")
    
    # 检查目标
    print("\n📋 目标检查 (年化 10-20%, 回撤 < 15%):")
    for name, stats in results.items():
        annual_ok = 10 <= stats['annual_return'] <= 20
        drawdown_ok = abs(stats['max_drawdown']) <= 15
        
        if annual_ok and drawdown_ok:
            print(f"   ✅ {name} 达标!")
        elif annual_ok:
            print(f"   ⚠️ {name} 收益达标但回撤过大")
        elif drawdown_ok:
            print(f"   ⚠️ {name} 回撤达标但收益不足")
    
    # 保存最佳结果
    df_donchian[['equity', 'signal', 'close']].to_csv('backtest_results/btc_simple_equity.csv')
    print("\n💾 结果已保存")
