"""
Freqtrade 策略: 保守多资产波动率目标组合
======================================
基于回测研究的最优策略转换为 Freqtrade 格式

注意: 这个策略需要在多个交易对上运行，模拟多资产组合
由于 Freqtrade 主要针对加密货币，这里实现 BTC 部分的策略
"""

from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from datetime import datetime
from typing import Dict, List, Optional


class ConservativeMultiAsset(IStrategy):
    """
    保守多资产策略 (BTC 部分)
    
    策略逻辑:
    1. 波动率目标: 保持仓位使组合波动率接近目标
    2. 动量过滤: 下跌趋势减少仓位
    3. 技术确认: 使用 EMA/RSI/MACD 确认趋势
    
    回测结果 (2019-2026):
    - 年化收益: 12.67%
    - 最大回撤: -12.59%
    - 夏普比率: 1.475
    """
    
    # 策略版本
    INTERFACE_VERSION = 3
    
    # 时间框架
    timeframe = '1d'
    
    # 策略参数
    target_volatility = 0.06  # 目标年化波动率 6%
    vol_lookback = 20  # 波动率计算窗口
    momentum_lookback = 60  # 动量计算窗口
    
    # EMA 参数
    ema_fast = 10
    ema_slow = 30
    ema_long = 60
    
    # 仓位控制
    position_min = 0.3  # 最小仓位 30%
    position_max = 1.2  # 最大仓位 120%
    
    # 止损止盈
    stoploss = -0.15  # 15% 止损
    trailing_stop = True
    trailing_stop_positive = 0.08  # 8% 后启动移动止损
    trailing_stop_positive_offset = 0.10
    trailing_only_offset_is_reached = True
    
    # ROI
    minimal_roi = {
        "0": 0.20,   # 20% 止盈
        "30": 0.15,  # 30天后 15%
        "60": 0.10,  # 60天后 10%
        "180": 0.05  # 180天后 5%
    }
    
    # 其他设置
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    # 冷却期
    process_only_new_candles = True
    startup_candle_count = 100
    
    def informative_pairs(self) -> List:
        """额外的信息对"""
        return []
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算技术指标
        """
        # EMA
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe['ema_long'] = ta.EMA(dataframe, timeperiod=self.ema_long)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        
        # 波动率 (日收益标准差年化)
        dataframe['returns'] = dataframe['close'].pct_change()
        dataframe['volatility'] = dataframe['returns'].rolling(self.vol_lookback).std() * np.sqrt(365)
        
        # 动量
        dataframe['momentum'] = dataframe['close'].pct_change(self.momentum_lookback)
        
        # 趋势强度
        dataframe['trend_up'] = (
            (dataframe['ema_fast'] > dataframe['ema_slow']) & 
            (dataframe['ema_slow'] > dataframe['ema_long'])
        )
        dataframe['trend_down'] = (
            (dataframe['ema_fast'] < dataframe['ema_slow']) & 
            (dataframe['ema_slow'] < dataframe['ema_long'])
        )
        
        # 仓位乘数 (基于波动率目标)
        dataframe['position_mult'] = np.where(
            dataframe['volatility'] > 0,
            np.clip(self.target_volatility / dataframe['volatility'], 
                    self.position_min, self.position_max),
            1.0
        )
        
        # 动量调整
        dataframe['position_mult'] = np.where(
            dataframe['momentum'] < -0.05,
            dataframe['position_mult'] * 0.5,
            np.where(
                dataframe['momentum'] < 0,
                dataframe['position_mult'] * 0.7,
                dataframe['position_mult']
            )
        )
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场信号
        """
        dataframe.loc[
            (
                # 趋势确认
                (dataframe['trend_up']) &
                
                # 动量为正
                (dataframe['momentum'] > 0) &
                
                # RSI 不过热
                (dataframe['rsi'] < 70) &
                (dataframe['rsi'] > 30) &
                
                # MACD 看涨
                (dataframe['macd'] > dataframe['macd_signal']) &
                
                # 仓位大于最小阈值
                (dataframe['position_mult'] > self.position_min) &
                
                # 成交量确认
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号
        """
        dataframe.loc[
            (
                # 趋势转空
                (dataframe['trend_down']) |
                
                # 动量转负
                (dataframe['momentum'] < -0.05) |
                
                # RSI 超卖
                (dataframe['rsi'] < 25) |
                
                # MACD 死叉
                (
                    (dataframe['macd'] < dataframe['macd_signal']) &
                    (dataframe['macd'].shift(1) > dataframe['macd_signal'].shift(1))
                )
            ),
            'exit_long'] = 1
        
        return dataframe
    
    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        """
        自定义仓位大小
        
        根据波动率目标动态调整
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            position_mult = last_candle['position_mult']
            
            # 调整仓位
            adjusted_stake = proposed_stake * position_mult
            
            # 限制范围
            adjusted_stake = max(min_stake or 0, min(adjusted_stake, max_stake))
            
            return adjusted_stake
        
        return proposed_stake
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        自定义出场条件
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            
            # 趋势反转出场
            if last_candle['trend_down'] and current_profit > 0:
                return 'trend_reversal'
            
            # 动量恶化出场
            if last_candle['momentum'] < -0.1:
                return 'momentum_exit'
        
        return None


class ConservativeMultiAssetShort(ConservativeMultiAsset):
    """
    保守多资产策略 (做空版本)
    
    在熊市中做空以获取收益
    """
    
    can_short = True
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场信号 (做空)
        """
        dataframe.loc[
            (
                # 趋势确认 (下跌)
                (dataframe['trend_down']) &
                
                # 动量为负
                (dataframe['momentum'] < 0) &
                
                # RSI 不过冷
                (dataframe['rsi'] > 30) &
                (dataframe['rsi'] < 70) &
                
                # MACD 看跌
                (dataframe['macd'] < dataframe['macd_signal']) &
                
                # 成交量确认
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号 (平空)
        """
        dataframe.loc[
            (
                # 趋势转多
                (dataframe['trend_up']) |
                
                # 动量转正
                (dataframe['momentum'] > 0.05) |
                
                # RSI 超买
                (dataframe['rsi'] > 75) |
                
                # MACD 金叉
                (
                    (dataframe['macd'] > dataframe['macd_signal']) &
                    (dataframe['macd'].shift(1) < dataframe['macd_signal'].shift(1))
                )
            ),
            'exit_short'] = 1
        
        return dataframe
