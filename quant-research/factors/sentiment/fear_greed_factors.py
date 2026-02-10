"""
情绪因子 - Sentiment Factors
============================
1. Crypto Fear & Greed Index
2. VIX (股市恐惧指标)
3. Put/Call Ratio
4. 情绪动量
"""

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import json


def fetch_crypto_fear_greed(days: int = 365) -> pd.DataFrame:
    """
    获取加密货币 Fear & Greed Index
    
    数据来源: alternative.me
    
    Parameters:
    -----------
    days : int
        获取天数
        
    Returns:
    --------
    pd.DataFrame : FNG 数据
    """
    url = f"https://api.alternative.me/fng/?limit={days}&format=json"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        records = []
        for item in data['data']:
            records.append({
                'date': datetime.fromtimestamp(int(item['timestamp'])),
                'fng_value': int(item['value']),
                'fng_classification': item['value_classification']
            })
        
        df = pd.DataFrame(records)
        df.set_index('date', inplace=True)
        df = df.sort_index()
        
        return df
    
    except Exception as e:
        print(f"获取 FNG 数据失败: {e}")
        return pd.DataFrame()


def fetch_vix_data(start_date: str = '2020-01-01') -> pd.Series:
    """
    获取 VIX 历史数据
    
    VIX < 15: 极度乐观
    15 < VIX < 20: 正常
    20 < VIX < 30: 恐惧
    VIX > 30: 极度恐惧
    
    Parameters:
    -----------
    start_date : str
        开始日期
        
    Returns:
    --------
    pd.Series : VIX 数据
    """
    vix = yf.download('^VIX', start=start_date, progress=False)
    return vix['Close'].squeeze()


def calculate_put_call_ratio() -> Dict:
    """
    计算 Put/Call 比率 (模拟)
    
    PCR > 1: 看跌情绪主导
    PCR < 0.7: 看涨情绪主导
    0.7 < PCR < 1: 中性
    
    Note: 实际需要期权数据 API
    """
    # 这里返回模拟值，实际需要接入期权数据
    return {
        'equity_pcr': 0.85,
        'index_pcr': 1.05,
        'total_pcr': 0.92
    }


def calculate_sentiment_momentum(fng_series: pd.Series, 
                                  windows: list = [7, 14, 30]) -> pd.DataFrame:
    """
    计算情绪动量因子
    
    Parameters:
    -----------
    fng_series : pd.Series
        FNG 序列
    windows : list
        动量窗口
        
    Returns:
    --------
    pd.DataFrame : 情绪动量
    """
    momentum = pd.DataFrame(index=fng_series.index)
    
    for w in windows:
        # 简单动量
        momentum[f'fng_mom_{w}d'] = fng_series - fng_series.shift(w)
        
        # 均值回归信号
        momentum[f'fng_zscore_{w}d'] = (
            (fng_series - fng_series.rolling(w).mean()) / 
            fng_series.rolling(w).std()
        )
    
    return momentum


def calculate_fear_greed_signal(fng_value: int) -> Dict:
    """
    根据 FNG 值生成交易信号
    
    Parameters:
    -----------
    fng_value : int
        当前 FNG 值 (0-100)
        
    Returns:
    --------
    Dict : 信号字典
    """
    if fng_value <= 20:
        signal = 'STRONG_BUY'
        description = '极度恐惧，反向买入机会'
        confidence = min(1.0, (25 - fng_value) / 25)
    elif fng_value <= 40:
        signal = 'BUY'
        description = '恐惧，逢低买入'
        confidence = (40 - fng_value) / 20 * 0.6
    elif fng_value <= 60:
        signal = 'NEUTRAL'
        description = '中性，观望'
        confidence = 0.3
    elif fng_value <= 80:
        signal = 'SELL'
        description = '贪婪，考虑减仓'
        confidence = (fng_value - 60) / 20 * 0.6
    else:
        signal = 'STRONG_SELL'
        description = '极度贪婪，减仓/做空'
        confidence = min(1.0, (fng_value - 75) / 25)
    
    return {
        'value': fng_value,
        'signal': signal,
        'description': description,
        'confidence': round(confidence, 2)
    }


def combine_sentiment_factors(crypto_fng: int, 
                               vix: float,
                               pcr: float = None) -> Dict:
    """
    综合情绪因子
    
    Parameters:
    -----------
    crypto_fng : int
        加密货币 FNG (0-100, 越低越恐惧)
    vix : float
        VIX 指数 (越高越恐惧)
    pcr : float, optional
        Put/Call 比率
        
    Returns:
    --------
    Dict : 综合情绪
    """
    # 归一化到 0-100 (100=极度恐惧)
    crypto_fear = 100 - crypto_fng  # 反转 FNG
    
    # VIX 归一化 (假设 10-50 范围)
    vix_normalized = min(100, max(0, (vix - 10) / 40 * 100))
    
    # PCR 归一化 (假设 0.5-1.5 范围)
    pcr_normalized = 0
    if pcr:
        pcr_normalized = min(100, max(0, (pcr - 0.5) / 1.0 * 100))
    
    # 加权平均
    weights = {'crypto': 0.5, 'vix': 0.35, 'pcr': 0.15}
    
    if pcr:
        combined = (
            crypto_fear * weights['crypto'] +
            vix_normalized * weights['vix'] +
            pcr_normalized * weights['pcr']
        )
    else:
        combined = (
            crypto_fear * weights['crypto'] / 0.85 +
            vix_normalized * weights['vix'] / 0.85
        )
    
    # 市场状态判断
    if combined >= 70:
        market_state = 'EXTREME_FEAR'
        action = '激进买入'
    elif combined >= 50:
        market_state = 'FEAR'
        action = '逢低买入'
    elif combined >= 30:
        market_state = 'NEUTRAL'
        action = '观望'
    elif combined >= 15:
        market_state = 'GREED'
        action = '谨慎减仓'
    else:
        market_state = 'EXTREME_GREED'
        action = '积极减仓'
    
    return {
        'combined_fear_index': round(combined, 1),
        'components': {
            'crypto_fear': round(crypto_fear, 1),
            'vix_normalized': round(vix_normalized, 1),
            'pcr_normalized': round(pcr_normalized, 1) if pcr else None
        },
        'market_state': market_state,
        'suggested_action': action
    }


# ============== 测试代码 ==============
if __name__ == "__main__":
    print("=" * 60)
    print("情绪因子测试")
    print("=" * 60)
    
    # 获取数据
    print("\n1. 获取 Crypto Fear & Greed Index...")
    fng_df = fetch_crypto_fear_greed(days=30)
    
    if not fng_df.empty:
        print(f"   最新日期: {fng_df.index[-1]}")
        print(f"   最新值: {fng_df['fng_value'].iloc[-1]} ({fng_df['fng_classification'].iloc[-1]})")
        print(f"   30日均值: {fng_df['fng_value'].mean():.1f}")
        print(f"   30日最低: {fng_df['fng_value'].min()}")
        print(f"   30日最高: {fng_df['fng_value'].max()}")
    
    print("\n2. 获取 VIX 数据...")
    vix = fetch_vix_data(start_date='2025-01-01')
    
    if not vix.empty:
        print(f"   最新日期: {vix.index[-1]}")
        print(f"   最新值: {vix.iloc[-1]:.2f}")
        print(f"   30日均值: {vix.tail(30).mean():.2f}")
    
    print("\n3. 生成交易信号...")
    if not fng_df.empty:
        current_fng = fng_df['fng_value'].iloc[-1]
        signal = calculate_fear_greed_signal(current_fng)
        print(f"   FNG = {signal['value']}")
        print(f"   信号: {signal['signal']}")
        print(f"   解读: {signal['description']}")
        print(f"   置信度: {signal['confidence']}")
    
    print("\n4. 综合情绪分析...")
    if not fng_df.empty and not vix.empty:
        combined = combine_sentiment_factors(
            crypto_fng=fng_df['fng_value'].iloc[-1],
            vix=vix.iloc[-1]
        )
        print(f"   综合恐惧指数: {combined['combined_fear_index']}")
        print(f"   市场状态: {combined['market_state']}")
        print(f"   建议操作: {combined['suggested_action']}")
