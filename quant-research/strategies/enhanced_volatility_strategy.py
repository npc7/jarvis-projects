"""
增强版波动率目标策略
==================
基于网格搜索结果的优化版本

改进:
1. 加入 ADX 趋势强度过滤
2. 优化入场时机 (突破确认)
3. 动态波动率目标 (根据市场状态调整)
4. 改进止损机制 (移动止损)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
import warnings
from datetime import datetime
import json

warnings.filterwarnings('ignore')


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
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
    max_drawdown_duration: int
    final_capital: float


class EnhancedVolatilityStrategy:
    """
    增强版波动率目标策略
    
    核心改进:
    1. ADX 过滤弱趋势
    2. 动态波动率目标
    3. 移动止损保护盈利
    4. 突破确认入场
    """
    
    def __init__(
        self,
        # 核心参数 (来自网格搜索最优)
        momentum_period: int = 30,
        base_target_volatility: float = 0.12,
        stop_loss_pct: float = 0.03,
        
        # 趋势过滤
        adx_period: int = 14,
        adx_threshold: float = 20,
        
        # 动态波动率
        vol_lookback: int = 20,
        vol_scale_factor: float = 1.5,  # 高波动时降低仓位
        
        # 移动止损
        trailing_stop_pct: float = 0.05,
        
        # 突破确认
        breakout_lookback: int = 20,
        breakout_confirm_days: int = 2,
        
        # 仓位限制
        min_position: float = 0.1,
        max_position: float = 1.2,
    ):
        self.momentum_period = momentum_period
        self.base_target_volatility = base_target_volatility
        self.stop_loss_pct = stop_loss_pct
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.vol_lookback = vol_lookback
        self.vol_scale_factor = vol_scale_factor
        self.trailing_stop_pct = trailing_stop_pct
        self.breakout_lookback = breakout_lookback
        self.breakout_confirm_days = breakout_confirm_days
        self.min_position = min_position
        self.max_position = max_position
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有指标"""
        df = df.copy()
        
        # 基础
        df['returns'] = df['close'].pct_change()
        df['momentum'] = df['close'].pct_change(self.momentum_period)
        
        # 波动率
        df['volatility'] = df['returns'].rolling(self.vol_lookback).std() * np.sqrt(252)
        df['vol_percentile'] = df['volatility'].rolling(252).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        
        # EMA
        df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema_30'] = df['close'].ewm(span=30, adjust=False).mean()
        df['ema_60'] = df['close'].ewm(span=60, adjust=False).mean()
        
        # ADX
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(self.adx_period).mean()
        
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
        
        df['di_plus'] = 100 * df['dm_plus'].rolling(self.adx_period).mean() / (df['atr'] + 1e-10)
        df['di_minus'] = 100 * df['dm_minus'].rolling(self.adx_period).mean() / (df['atr'] + 1e-10)
        df['dx'] = 100 * abs(df['di_plus'] - df['di_minus']) / (df['di_plus'] + df['di_minus'] + 1e-10)
        df['adx'] = df['dx'].rolling(self.adx_period).mean()
        
        # 突破
        df['high_breakout'] = df['high'].rolling(self.breakout_lookback).max()
        df['low_breakout'] = df['low'].rolling(self.breakout_lookback).min()
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        return df
    
    def get_dynamic_target_vol(self, vol_percentile: float) -> float:
        """根据市场波动率百分位动态调整目标波动率"""
        if pd.isna(vol_percentile):
            return self.base_target_volatility
            
        # 高波动环境降低目标
        if vol_percentile > 0.8:
            return self.base_target_volatility * 0.6
        elif vol_percentile > 0.6:
            return self.base_target_volatility * 0.8
        elif vol_percentile < 0.3:
            return self.base_target_volatility * 1.2
        else:
            return self.base_target_volatility
    
    def calculate_position_size(self, current_vol: float, target_vol: float, signal: int) -> float:
        """计算仓位"""
        if current_vol <= 0 or np.isnan(current_vol):
            return 0
            
        raw_position = target_vol / current_vol
        position = np.clip(raw_position, self.min_position, self.max_position)
        
        return position * signal


def backtest_enhanced_strategy(
    df: pd.DataFrame,
    strategy: EnhancedVolatilityStrategy,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, BacktestResult]:
    """运行增强版策略回测"""
    
    df = strategy.calculate_indicators(df)
    
    capital = initial_capital
    position = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    trailing_stop = 0.0
    
    equity_curve = []
    trades = []
    
    start_idx = max(strategy.momentum_period, strategy.vol_lookback, 60, strategy.breakout_lookback) + 10
    
    consecutive_losses = 0
    max_consecutive_losses = 0
    peak_capital = initial_capital
    drawdown_start = None
    max_dd_duration = 0
    
    # 突破确认计数
    breakout_confirm_count = 0
    pending_signal = 0
    
    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        date = df.index[i]
        
        current_price = row['close']
        
        # 计算当前权益
        if position != 0:
            if position > 0:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = -(current_price - entry_price) / entry_price
            current_equity = capital * (1 + abs(position) * pnl_pct)
        else:
            current_equity = capital
        
        # 更新移动止损 (只对盈利仓位)
        if position > 0 and current_price > highest_since_entry:
            highest_since_entry = current_price
            trailing_stop = highest_since_entry * (1 - strategy.trailing_stop_pct)
        
        # 检查止损
        if position != 0:
            trigger_stop = False
            stop_price = 0
            
            if position > 0:
                # 多头
                initial_stop = entry_price * (1 - strategy.stop_loss_pct)
                effective_stop = max(initial_stop, trailing_stop)
                
                if current_price < effective_stop:
                    trigger_stop = True
                    stop_price = effective_stop
                    pnl_pct = (stop_price - entry_price) / entry_price
            else:
                # 空头止损
                initial_stop = entry_price * (1 + strategy.stop_loss_pct)
                if current_price > initial_stop:
                    trigger_stop = True
                    stop_price = initial_stop
                    pnl_pct = -(stop_price - entry_price) / entry_price
            
            if trigger_stop:
                realized_pnl = capital * abs(position) * pnl_pct
                capital += realized_pnl
                
                trades.append({
                    'date': date,
                    'action': 'stop_loss',
                    'price': stop_price,
                    'position': position,
                    'pnl': realized_pnl,
                    'pnl_pct': pnl_pct * 100
                })
                
                if realized_pnl > 0:
                    consecutive_losses = 0
                else:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                
                position = 0
                entry_price = 0
                highest_since_entry = 0
                trailing_stop = 0
        
        # 生成信号
        momentum = row['momentum']
        volatility = row['volatility']
        vol_percentile = row['vol_percentile']
        adx = row['adx']
        rsi = row['rsi']
        macd = row['macd']
        macd_signal = row['macd_signal']
        
        if pd.isna(momentum) or pd.isna(volatility) or volatility <= 0:
            equity_curve.append({
                'date': date,
                'equity': current_equity,
                'position': position,
                'close': current_price
            })
            continue
        
        # 趋势判断
        trend_up = row['ema_10'] > row['ema_30'] > row['ema_60']
        trend_down = row['ema_10'] < row['ema_30'] < row['ema_60']
        
        # 突破检测
        breakout_up = current_price > prev_row['high_breakout']
        breakout_down = current_price < prev_row['low_breakout']
        
        # ADX 过滤
        strong_trend = adx > strategy.adx_threshold
        
        # MACD 确认
        macd_bullish = macd > macd_signal
        macd_bearish = macd < macd_signal
        
        # RSI 过滤
        rsi_ok_long = 30 < rsi < 70
        rsi_ok_short = 30 < rsi < 70
        
        # 综合信号
        new_signal = 0
        
        if momentum > 0 and trend_up and strong_trend and macd_bullish and rsi_ok_long:
            if breakout_up:
                new_signal = 1
        elif momentum < 0 and trend_down and strong_trend and macd_bearish and rsi_ok_short:
            if breakout_down:
                new_signal = -1
        
        # 突破确认机制
        if new_signal != 0:
            if pending_signal == new_signal:
                breakout_confirm_count += 1
            else:
                pending_signal = new_signal
                breakout_confirm_count = 1
        else:
            breakout_confirm_count = 0
            pending_signal = 0
        
        # 确认后执行
        confirmed_signal = 0
        if breakout_confirm_count >= strategy.breakout_confirm_days:
            confirmed_signal = pending_signal
            breakout_confirm_count = 0
            pending_signal = 0
        
        # 执行交易
        if position == 0 and confirmed_signal != 0:
            # 计算目标波动率和仓位
            target_vol = strategy.get_dynamic_target_vol(vol_percentile)
            target_position = strategy.calculate_position_size(volatility, target_vol, confirmed_signal)
            
            position = target_position
            entry_price = current_price
            highest_since_entry = current_price
            trailing_stop = current_price * (1 - strategy.trailing_stop_pct) if position > 0 else 0
            
            trades.append({
                'date': date,
                'action': 'open',
                'price': current_price,
                'position': position,
                'pnl': 0,
                'pnl_pct': 0
            })
        
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
            'close': current_price
        })
    
    # 平掉最终仓位
    if position != 0:
        final_price = df.iloc[-1]['close']
        if position > 0:
            pnl_pct = (final_price - entry_price) / entry_price
        else:
            pnl_pct = -(final_price - entry_price) / entry_price
        realized_pnl = capital * abs(position) * pnl_pct
        capital += realized_pnl
        trades.append({
            'date': df.index[-1],
            'action': 'close',
            'price': final_price,
            'position': position,
            'pnl': realized_pnl,
            'pnl_pct': pnl_pct * 100
        })
    
    # 统计
    equity_df = pd.DataFrame(equity_curve).set_index('date')
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    
    equity = equity_df['equity']
    
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    days = (equity_df.index[-1] - equity_df.index[0]).days
    years = days / 365
    annual_return = ((equity.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    
    rolling_max = equity.expanding().max()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    daily_returns = equity.pct_change().dropna()
    
    rf = 0.02
    excess_return = daily_returns.mean() * 252 - rf
    sharpe = excess_return / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
    
    negative_returns = daily_returns[daily_returns < 0]
    downside_std = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0.01
    sortino = excess_return / downside_std if downside_std > 0 else 0
    
    calmar = abs(annual_return / max_drawdown) if max_drawdown != 0 else 0
    
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
        strategy_name='EnhancedVolatility',
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


def optimize_enhanced_strategy(df: pd.DataFrame) -> Tuple[Dict, BacktestResult]:
    """优化增强版策略参数"""
    
    print("\n🔍 优化增强版策略参数...")
    
    param_grid = {
        'adx_threshold': [15, 20, 25, 30],
        'trailing_stop_pct': [0.03, 0.05, 0.08],
        'breakout_confirm_days': [1, 2, 3],
        'vol_scale_factor': [1.0, 1.5, 2.0]
    }
    
    best_sharpe = -np.inf
    best_params = {}
    best_result = None
    
    from itertools import product
    
    total = len(param_grid['adx_threshold']) * len(param_grid['trailing_stop_pct']) * \
            len(param_grid['breakout_confirm_days']) * len(param_grid['vol_scale_factor'])
    
    print(f"   测试 {total} 种参数组合...")
    
    count = 0
    for adx, trailing, confirm, vol_scale in product(
        param_grid['adx_threshold'],
        param_grid['trailing_stop_pct'],
        param_grid['breakout_confirm_days'],
        param_grid['vol_scale_factor']
    ):
        count += 1
        
        strategy = EnhancedVolatilityStrategy(
            adx_threshold=adx,
            trailing_stop_pct=trailing,
            breakout_confirm_days=confirm,
            vol_scale_factor=vol_scale
        )
        
        try:
            _, result = backtest_enhanced_strategy(df, strategy)
            
            # 选择夏普最高且回撤可控
            if result.sharpe_ratio > best_sharpe and result.max_drawdown > -15:
                best_sharpe = result.sharpe_ratio
                best_params = {
                    'adx_threshold': adx,
                    'trailing_stop_pct': trailing,
                    'breakout_confirm_days': confirm,
                    'vol_scale_factor': vol_scale
                }
                best_result = result
                
        except Exception as e:
            pass
    
    return best_params, best_result


def main():
    """主函数"""
    print("=" * 70)
    print("🚀 增强版波动率目标策略回测")
    print("=" * 70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取数据
    print("\n📥 获取 BTC 历史数据...")
    df = fetch_btc_data('2020-01-01', '2026-02-01')
    
    if len(df) == 0:
        print("❌ 无法获取数据")
        return
        
    print(f"✅ 获取到 {len(df)} 条数据")
    
    # 默认参数测试
    print("\n🔄 运行默认参数回测...")
    strategy = EnhancedVolatilityStrategy()
    equity, result = backtest_enhanced_strategy(df, strategy)
    
    print("\n📊 默认参数结果:")
    print("-" * 50)
    print(f"年化收益率:   {result.annual_return:.2f}%")
    print(f"最大回撤:     {result.max_drawdown:.2f}%")
    print(f"夏普比率:     {result.sharpe_ratio:.3f}")
    print(f"Sortino比率:  {result.sortino_ratio:.3f}")
    print(f"Calmar比率:   {result.calmar_ratio:.3f}")
    print(f"胜率:         {result.win_rate:.1f}%")
    print(f"盈亏比:       {result.profit_factor:.2f}")
    print(f"交易次数:     {result.total_trades}")
    print("-" * 50)
    
    # 参数优化
    best_params, best_result = optimize_enhanced_strategy(df)
    
    if best_result:
        print(f"\n📊 最优参数结果:")
        print(f"   参数: {best_params}")
        print("-" * 50)
        print(f"年化收益率:   {best_result.annual_return:.2f}%")
        print(f"最大回撤:     {best_result.max_drawdown:.2f}%")
        print(f"夏普比率:     {best_result.sharpe_ratio:.3f}")
        print(f"Sortino比率:  {best_result.sortino_ratio:.3f}")
        print(f"Calmar比率:   {best_result.calmar_ratio:.3f}")
        print(f"胜率:         {best_result.win_rate:.1f}%")
        print(f"盈亏比:       {best_result.profit_factor:.2f}")
        print(f"交易次数:     {best_result.total_trades}")
        print("-" * 50)
        
        # 使用最优参数
        opt_strategy = EnhancedVolatilityStrategy(**best_params)
        equity, _ = backtest_enhanced_strategy(df, opt_strategy)
        equity.to_csv('backtest_results/parameter_grid/enhanced_equity.csv')
        
        # 保存参数
        with open('backtest_results/parameter_grid/enhanced_best_params.json', 'w') as f:
            json.dump({
                'params': best_params,
                'result': asdict(best_result)
            }, f, indent=2)
        
        print("\n💾 结果已保存")
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
