"""
BTC 趋势跟踪策略
================
结合双均线交叉 + ATR 趋势过滤 + ML 信号确认

目标：
- 年化收益 10-20%
- 最大回撤 < 15%
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class TradeSignal:
    """交易信号"""
    direction: int  # 1=多, -1=空, 0=无
    strength: float  # 信号强度 0-1
    stop_loss: float  # 止损价
    take_profit: float  # 止盈价


class BTCTrendStrategy:
    """
    BTC 趋势跟踪策略
    
    规则:
    1. 趋势判断: EMA21 vs EMA55
    2. 入场确认: 价格突破 Donchian Channel
    3. ATR 过滤: 波动率合适才入场
    4. 仓位管理: 基于 ATR 的动态仓位
    5. 风控: 2ATR 止损, 3ATR 止盈
    """
    
    def __init__(
        self,
        ema_fast: int = 21,
        ema_slow: int = 55,
        donchian_period: int = 20,
        atr_period: int = 14,
        risk_per_trade: float = 0.02,  # 每笔交易风险 2%
        atr_sl_mult: float = 2.0,  # 止损 ATR 倍数
        atr_tp_mult: float = 3.0,  # 止盈 ATR 倍数
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.donchian_period = donchian_period
        self.atr_period = atr_period
        self.risk_per_trade = risk_per_trade
        self.atr_sl_mult = atr_sl_mult
        self.atr_tp_mult = atr_tp_mult
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = df.copy()
        
        # EMA
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # Donchian Channel
        df['donchian_high'] = df['high'].rolling(self.donchian_period).max()
        df['donchian_low'] = df['low'].rolling(self.donchian_period).min()
        df['donchian_mid'] = (df['donchian_high'] + df['donchian_low']) / 2
        
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(self.atr_period).mean()
        
        # 趋势方向
        df['trend'] = np.where(df['ema_fast'] > df['ema_slow'], 1, -1)
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 波动率过滤
        df['atr_pct'] = df['atr'] / df['close']
        df['vol_ok'] = (df['atr_pct'] > 0.01) & (df['atr_pct'] < 0.08)  # 1%-8% 波动
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, idx: int) -> TradeSignal:
        """生成交易信号"""
        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1] if idx > 0 else row
        
        direction = 0
        strength = 0.0
        
        # 趋势判断
        trend_up = row['ema_fast'] > row['ema_slow']
        trend_down = row['ema_fast'] < row['ema_slow']
        
        # 突破信号
        breakout_long = row['close'] > prev_row['donchian_high']
        breakout_short = row['close'] < prev_row['donchian_low']
        
        # RSI 过滤
        rsi_ok_long = 30 < row['rsi'] < 70  # 避免极端
        rsi_ok_short = 30 < row['rsi'] < 70
        
        # MACD 确认
        macd_bull = row['macd'] > row['macd_signal']
        macd_bear = row['macd'] < row['macd_signal']
        
        # 波动率过滤
        vol_ok = row['vol_ok']
        
        # 综合信号
        if trend_up and breakout_long and vol_ok and macd_bull:
            direction = 1
            strength = min(1.0, 0.5 + (row['macd_hist'] / row['atr'] * 10))
        elif trend_down and breakout_short and vol_ok and macd_bear:
            direction = -1
            strength = min(1.0, 0.5 + (-row['macd_hist'] / row['atr'] * 10))
        
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
            
        return TradeSignal(
            direction=direction,
            strength=max(0, min(1, strength)),
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def calculate_position_size(
        self, 
        capital: float, 
        entry_price: float, 
        stop_loss: float
    ) -> float:
        """基于风险计算仓位"""
        risk_amount = capital * self.risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return 0
            
        position = risk_amount / price_risk
        # 最大仓位限制: 20% 资本
        max_position = capital * 0.20 / entry_price
        
        return min(position, max_position)


class BTCBacktester:
    """BTC 策略回测器"""
    
    def __init__(self, strategy: BTCTrendStrategy, initial_capital: float = 100000):
        self.strategy = strategy
        self.initial_capital = initial_capital
        
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """运行回测"""
        # 计算指标
        df = self.strategy.calculate_indicators(df)
        
        # 初始化
        capital = self.initial_capital
        position = 0  # 持仓数量
        entry_price = 0
        stop_loss = 0
        take_profit = 0
        
        # 记录
        records = []
        equity_curve = []
        
        # 从足够的历史数据开始
        start_idx = max(self.strategy.ema_slow, self.strategy.donchian_period) + 10
        
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            date = df.index[i]
            
            # 检查止损止盈
            if position != 0:
                if position > 0:  # 多头
                    if row['low'] <= stop_loss:
                        # 止损触发
                        pnl = (stop_loss - entry_price) * position
                        capital += pnl
                        records.append({
                            'date': date,
                            'action': 'stop_loss',
                            'price': stop_loss,
                            'position': position,
                            'pnl': pnl,
                            'capital': capital
                        })
                        position = 0
                    elif row['high'] >= take_profit:
                        # 止盈触发
                        pnl = (take_profit - entry_price) * position
                        capital += pnl
                        records.append({
                            'date': date,
                            'action': 'take_profit',
                            'price': take_profit,
                            'position': position,
                            'pnl': pnl,
                            'capital': capital
                        })
                        position = 0
                else:  # 空头
                    if row['high'] >= stop_loss:
                        pnl = (entry_price - stop_loss) * abs(position)
                        capital += pnl
                        records.append({
                            'date': date,
                            'action': 'stop_loss',
                            'price': stop_loss,
                            'position': position,
                            'pnl': pnl,
                            'capital': capital
                        })
                        position = 0
                    elif row['low'] <= take_profit:
                        pnl = (entry_price - take_profit) * abs(position)
                        capital += pnl
                        records.append({
                            'date': date,
                            'action': 'take_profit',
                            'price': take_profit,
                            'position': position,
                            'pnl': pnl,
                            'capital': capital
                        })
                        position = 0
            
            # 生成新信号
            if position == 0:
                signal = self.strategy.generate_signal(df, i)
                
                if signal.direction != 0 and signal.strength > 0.3:
                    # 开仓
                    size = self.strategy.calculate_position_size(
                        capital, 
                        row['close'], 
                        signal.stop_loss
                    )
                    
                    if signal.direction == 1:
                        position = size
                    else:
                        position = -size
                        
                    entry_price = row['close']
                    stop_loss = signal.stop_loss
                    take_profit = signal.take_profit
                    
                    records.append({
                        'date': date,
                        'action': 'open_long' if signal.direction == 1 else 'open_short',
                        'price': entry_price,
                        'position': position,
                        'pnl': 0,
                        'capital': capital,
                        'strength': signal.strength
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
        
        self.trades = pd.DataFrame(records)
        self.equity = pd.DataFrame(equity_curve).set_index('date')
        
        return self.equity
    
    def get_stats(self) -> dict:
        """计算回测统计"""
        if len(self.equity) == 0:
            return {}
            
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
        
        # 夏普比率 (假设无风险利率 2%)
        daily_returns = equity.pct_change().dropna()
        sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
        
        # 胜率
        if len(self.trades) > 0:
            wins = self.trades[self.trades['pnl'] > 0]
            win_rate = len(wins) / len(self.trades[self.trades['action'].isin(['stop_loss', 'take_profit'])]) * 100 if len(self.trades) > 0 else 0
            total_trades = len(self.trades[self.trades['action'].str.startswith('open')])
        else:
            win_rate = 0
            total_trades = 0
        
        return {
            'total_return': round(total_return, 2),
            'annual_return': round(annual_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe, 2),
            'win_rate': round(win_rate, 2),
            'total_trades': total_trades,
            'final_capital': round(equity.iloc[-1], 2)
        }


def fetch_btc_data(start_date: str = '2020-01-01', end_date: str = '2026-02-01') -> pd.DataFrame:
    """获取 BTC 历史数据"""
    try:
        import yfinance as yf
        btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)
        
        # 处理 MultiIndex columns
        if isinstance(btc.columns, pd.MultiIndex):
            btc.columns = [c[0].lower() for c in btc.columns]
        else:
            btc.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in btc.columns]
        
        return btc
    except Exception as e:
        print(f"Error fetching data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


if __name__ == '__main__':
    print("=" * 60)
    print("BTC 趋势跟踪策略回测")
    print("=" * 60)
    
    # 获取数据
    print("\n📥 获取 BTC 历史数据...")
    df = fetch_btc_data('2020-01-01', '2026-02-01')
    
    if len(df) == 0:
        print("❌ 无法获取数据")
        exit(1)
        
    print(f"✅ 获取到 {len(df)} 条数据")
    print(f"   时间范围: {df.index[0]} 至 {df.index[-1]}")
    
    # 创建策略
    strategy = BTCTrendStrategy(
        ema_fast=21,
        ema_slow=55,
        donchian_period=20,
        atr_period=14,
        risk_per_trade=0.02,
        atr_sl_mult=2.0,
        atr_tp_mult=3.0
    )
    
    # 运行回测
    print("\n🔄 运行回测...")
    backtester = BTCBacktester(strategy, initial_capital=100000)
    equity = backtester.run(df)
    
    # 统计结果
    stats = backtester.get_stats()
    
    print("\n📊 回测结果:")
    print("-" * 40)
    print(f"总收益率:     {stats['total_return']:.2f}%")
    print(f"年化收益率:   {stats['annual_return']:.2f}%")
    print(f"最大回撤:     {stats['max_drawdown']:.2f}%")
    print(f"夏普比率:     {stats['sharpe_ratio']:.2f}")
    print(f"胜率:         {stats['win_rate']:.2f}%")
    print(f"交易次数:     {stats['total_trades']}")
    print(f"最终资金:     ${stats['final_capital']:,.2f}")
    print("-" * 40)
    
    # 保存结果
    equity.to_csv('backtest_results/btc_equity_curve.csv')
    backtester.trades.to_csv('backtest_results/btc_trades.csv', index=False)
    print("\n💾 结果已保存到 backtest_results/")
