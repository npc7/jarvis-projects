"""
BTC 优化版趋势跟踪策略
======================
通过参数优化和更激进的仓位管理追求更高收益

目标：
- 年化收益 15-25%
- 最大回撤 < 20%
"""

import pandas as pd
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    final_capital: float


class BTCOptimizedStrategy:
    """
    BTC 优化版趋势策略
    
    改进:
    1. 更快的均线参数
    2. 更激进的仓位管理
    3. 动态止损止盈
    4. 加入 ADX 趋势强度过滤
    """
    
    def __init__(
        self,
        ema_fast: int = 12,
        ema_slow: int = 26,
        donchian_period: int = 15,
        atr_period: int = 14,
        risk_per_trade: float = 0.03,  # 每笔交易风险 3%
        atr_sl_mult: float = 1.5,  # 更紧的止损
        atr_tp_mult: float = 4.0,  # 更大的盈亏比
        adx_threshold: float = 25,  # ADX 趋势强度阈值
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.donchian_period = donchian_period
        self.atr_period = atr_period
        self.risk_per_trade = risk_per_trade
        self.atr_sl_mult = atr_sl_mult
        self.atr_tp_mult = atr_tp_mult
        self.adx_threshold = adx_threshold
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = df.copy()
        
        # EMA
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # Donchian Channel
        df['donchian_high'] = df['high'].rolling(self.donchian_period).max()
        df['donchian_low'] = df['low'].rolling(self.donchian_period).min()
        
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(self.atr_period).mean()
        
        # ADX (简化版)
        df['dm_plus'] = np.where(
            (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
            np.maximum(df['high'] - df['high'].shift(1), 0),
            0
        )
        df['dm_minus'] = np.where(
            (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
            np.maximum(df['low'].shift(1) - df['low'], 0),
            0
        )
        
        df['di_plus'] = 100 * df['dm_plus'].rolling(14).mean() / df['atr']
        df['di_minus'] = 100 * df['dm_minus'].rolling(14).mean() / df['atr']
        df['dx'] = 100 * abs(df['di_plus'] - df['di_minus']) / (df['di_plus'] + df['di_minus'] + 0.0001)
        df['adx'] = df['dx'].rolling(14).mean()
        
        # 趋势方向
        df['trend'] = np.where(df['ema_fast'] > df['ema_slow'], 1, -1)
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 0.0001)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 波动率百分比
        df['atr_pct'] = df['atr'] / df['close']
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, idx: int) -> Tuple[int, float, float, float]:
        """
        生成交易信号
        
        Returns:
            direction: 1=多, -1=空, 0=无
            strength: 信号强度
            stop_loss: 止损价
            take_profit: 止盈价
        """
        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1] if idx > 0 else row
        
        direction = 0
        strength = 0.0
        
        # 趋势判断
        trend_up = row['ema_fast'] > row['ema_slow']
        trend_down = row['ema_fast'] < row['ema_slow']
        
        # ADX 趋势强度
        strong_trend = row['adx'] > self.adx_threshold
        
        # 突破信号
        breakout_long = row['close'] > prev_row['donchian_high']
        breakout_short = row['close'] < prev_row['donchian_low']
        
        # MACD 确认
        macd_bull = row['macd'] > row['macd_signal'] and row['macd_hist'] > prev_row.get('macd_hist', 0)
        macd_bear = row['macd'] < row['macd_signal'] and row['macd_hist'] < prev_row.get('macd_hist', 0)
        
        # RSI 过滤 (避免极端)
        rsi_ok_long = 25 < row['rsi'] < 75
        rsi_ok_short = 25 < row['rsi'] < 75
        
        # 综合信号
        if trend_up and breakout_long and strong_trend and macd_bull and rsi_ok_long:
            direction = 1
            strength = min(1.0, row['adx'] / 50)
        elif trend_down and breakout_short and strong_trend and macd_bear and rsi_ok_short:
            direction = -1
            strength = min(1.0, row['adx'] / 50)
        
        # 止损止盈
        atr = row['atr']
        if direction == 1:
            stop_loss = row['close'] - self.atr_sl_mult * atr
            take_profit = row['close'] + self.atr_tp_mult * atr
        elif direction == -1:
            stop_loss = row['close'] + self.atr_sl_mult * atr
            take_profit = row['close'] - self.atr_tp_mult * atr
        else:
            stop_loss = 0
            take_profit = 0
            
        return direction, max(0, min(1, strength)), stop_loss, take_profit


def backtest_btc(
    df: pd.DataFrame,
    strategy: BTCOptimizedStrategy,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, BacktestResult]:
    """运行回测"""
    
    # 计算指标
    df = strategy.calculate_indicators(df)
    
    # 初始化
    capital = initial_capital
    position = 0
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    
    # 记录
    trades = []
    equity_curve = []
    
    # 从足够的历史数据开始
    start_idx = max(strategy.ema_slow, strategy.donchian_period, 28) + 10
    
    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        date = df.index[i]
        
        # 检查止损止盈
        if position != 0:
            if position > 0:
                if row['low'] <= stop_loss:
                    pnl = (stop_loss - entry_price) * position
                    capital += pnl
                    trades.append({'date': date, 'action': 'sl', 'pnl': pnl})
                    position = 0
                elif row['high'] >= take_profit:
                    pnl = (take_profit - entry_price) * position
                    capital += pnl
                    trades.append({'date': date, 'action': 'tp', 'pnl': pnl})
                    position = 0
            else:
                if row['high'] >= stop_loss:
                    pnl = (entry_price - stop_loss) * abs(position)
                    capital += pnl
                    trades.append({'date': date, 'action': 'sl', 'pnl': pnl})
                    position = 0
                elif row['low'] <= take_profit:
                    pnl = (entry_price - take_profit) * abs(position)
                    capital += pnl
                    trades.append({'date': date, 'action': 'tp', 'pnl': pnl})
                    position = 0
        
        # 生成新信号
        if position == 0:
            direction, strength, sl, tp = strategy.generate_signal(df, i)
            
            if direction != 0 and strength > 0.3:
                # 计算仓位
                risk_amount = capital * strategy.risk_per_trade
                price_risk = abs(row['close'] - sl)
                
                if price_risk > 0:
                    size = risk_amount / price_risk
                    max_size = capital * 0.25 / row['close']
                    size = min(size, max_size)
                    
                    if direction == 1:
                        position = size
                    else:
                        position = -size
                        
                    entry_price = row['close']
                    stop_loss = sl
                    take_profit = tp
                    
                    trades.append({
                        'date': date, 
                        'action': 'open',
                        'direction': direction,
                        'price': entry_price,
                        'pnl': 0
                    })
        
        # 记录每日权益
        if position != 0:
            unrealized_pnl = (row['close'] - entry_price) * position
            equity = capital + unrealized_pnl
        else:
            equity = capital
            
        equity_curve.append({
            'date': date,
            'equity': equity,
            'position': position,
            'close': row['close']
        })
    
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    trades_df = pd.DataFrame(trades)
    
    # 计算统计
    equity = equity_df['equity']
    
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    days = (equity_df.index[-1] - equity_df.index[0]).days
    years = days / 365
    annual_return = ((equity.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    daily_returns = equity.pct_change().dropna()
    sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    
    # 胜率
    if len(trades_df) > 0:
        closed_trades = trades_df[trades_df['action'].isin(['sl', 'tp'])]
        wins = closed_trades[closed_trades['pnl'] > 0]
        win_rate = len(wins) / len(closed_trades) * 100 if len(closed_trades) > 0 else 0
        total_trades = len(trades_df[trades_df['action'] == 'open'])
    else:
        win_rate = 0
        total_trades = 0
    
    result = BacktestResult(
        total_return=round(total_return, 2),
        annual_return=round(annual_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe, 2),
        win_rate=round(win_rate, 2),
        total_trades=total_trades,
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
            btc.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in btc.columns]
        
        return btc
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()


def optimize_parameters(df: pd.DataFrame) -> dict:
    """网格搜索最优参数"""
    print("\n🔍 参数优化中...")
    
    best_sharpe = -np.inf
    best_params = {}
    best_result = None
    
    param_grid = {
        'ema_fast': [8, 12, 15],
        'ema_slow': [21, 26, 34],
        'donchian_period': [10, 15, 20],
        'atr_sl_mult': [1.5, 2.0],
        'atr_tp_mult': [3.0, 4.0, 5.0],
        'adx_threshold': [20, 25, 30]
    }
    
    total_combinations = (
        len(param_grid['ema_fast']) * 
        len(param_grid['ema_slow']) * 
        len(param_grid['donchian_period']) *
        len(param_grid['atr_sl_mult']) *
        len(param_grid['atr_tp_mult']) *
        len(param_grid['adx_threshold'])
    )
    
    print(f"   测试 {total_combinations} 种参数组合...")
    
    count = 0
    for ema_fast in param_grid['ema_fast']:
        for ema_slow in param_grid['ema_slow']:
            if ema_fast >= ema_slow:
                continue
            for donchian in param_grid['donchian_period']:
                for sl_mult in param_grid['atr_sl_mult']:
                    for tp_mult in param_grid['atr_tp_mult']:
                        for adx in param_grid['adx_threshold']:
                            count += 1
                            
                            strategy = BTCOptimizedStrategy(
                                ema_fast=ema_fast,
                                ema_slow=ema_slow,
                                donchian_period=donchian,
                                atr_sl_mult=sl_mult,
                                atr_tp_mult=tp_mult,
                                adx_threshold=adx
                            )
                            
                            _, result = backtest_btc(df, strategy)
                            
                            # 选择夏普比率最高且回撤可控的参数
                            if result.sharpe_ratio > best_sharpe and result.max_drawdown > -20:
                                best_sharpe = result.sharpe_ratio
                                best_params = {
                                    'ema_fast': ema_fast,
                                    'ema_slow': ema_slow,
                                    'donchian_period': donchian,
                                    'atr_sl_mult': sl_mult,
                                    'atr_tp_mult': tp_mult,
                                    'adx_threshold': adx
                                }
                                best_result = result
    
    print(f"   完成！最优夏普比率: {best_sharpe:.2f}")
    return best_params, best_result


if __name__ == '__main__':
    print("=" * 60)
    print("BTC 优化版趋势策略回测")
    print("=" * 60)
    
    # 获取数据
    print("\n📥 获取 BTC 历史数据...")
    df = fetch_btc_data('2020-01-01', '2026-02-01')
    
    if len(df) == 0:
        print("❌ 无法获取数据")
        exit(1)
        
    print(f"✅ 获取到 {len(df)} 条数据")
    
    # 默认参数测试
    print("\n🔄 运行默认参数回测...")
    strategy = BTCOptimizedStrategy()
    equity, result = backtest_btc(df, strategy)
    
    print("\n📊 默认参数结果:")
    print("-" * 40)
    print(f"总收益率:     {result.total_return:.2f}%")
    print(f"年化收益率:   {result.annual_return:.2f}%")
    print(f"最大回撤:     {result.max_drawdown:.2f}%")
    print(f"夏普比率:     {result.sharpe_ratio:.2f}")
    print(f"胜率:         {result.win_rate:.2f}%")
    print(f"交易次数:     {result.total_trades}")
    print("-" * 40)
    
    # 参数优化
    best_params, best_result = optimize_parameters(df)
    
    if best_result:
        print(f"\n📊 最优参数结果:")
        print(f"   参数: {best_params}")
        print("-" * 40)
        print(f"总收益率:     {best_result.total_return:.2f}%")
        print(f"年化收益率:   {best_result.annual_return:.2f}%")
        print(f"最大回撤:     {best_result.max_drawdown:.2f}%")
        print(f"夏普比率:     {best_result.sharpe_ratio:.2f}")
        print(f"胜率:         {best_result.win_rate:.2f}%")
        print(f"交易次数:     {best_result.total_trades}")
        print("-" * 40)
        
        # 使用最优参数保存结果
        opt_strategy = BTCOptimizedStrategy(**best_params)
        equity, _ = backtest_btc(df, opt_strategy)
        equity.to_csv('backtest_results/btc_optimized_equity.csv')
        print("\n💾 最优结果已保存")
