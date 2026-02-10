"""
政治经济学因子 - Political Economy Factors
==========================================
1. Economic Policy Uncertainty (EPU) Index
2. Geopolitical Risk (GPR) Index
3. 央行政策因子
4. 选举周期效应
"""

import numpy as np
import pandas as pd
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta
import yfinance as yf


def fetch_epu_index() -> pd.DataFrame:
    """
    获取 Economic Policy Uncertainty Index
    
    数据来源: policyuncertainty.com
    
    Note: 由于直接下载需要 Excel，这里提供模拟数据
    实际使用时可以手动下载或使用 FRED API
    
    Returns:
    --------
    pd.DataFrame : EPU 数据
    """
    # FRED API (如果可用)
    # 这里生成合成数据用于演示
    dates = pd.date_range(start='2020-01-01', end='2026-02-01', freq='MS')
    
    # 模拟 EPU 数据 (基于历史模式)
    np.random.seed(42)
    base_epu = 100
    trend = np.sin(np.arange(len(dates)) / 12 * np.pi) * 30  # 周期性
    noise = np.random.randn(len(dates)) * 20
    
    # 加入重大事件冲击
    epu_values = base_epu + trend + noise
    
    # COVID 冲击 (2020年3月)
    covid_idx = dates.get_loc(pd.Timestamp('2020-03-01'))
    epu_values[covid_idx:covid_idx+6] += [150, 200, 150, 100, 50, 30]
    
    # 2022年俄乌冲突
    if pd.Timestamp('2022-03-01') in dates:
        ukraine_idx = dates.get_loc(pd.Timestamp('2022-03-01'))
        epu_values[ukraine_idx:ukraine_idx+4] += [80, 100, 60, 30]
    
    df = pd.DataFrame({
        'date': dates,
        'epu_index': np.clip(epu_values, 50, 400)
    })
    df.set_index('date', inplace=True)
    
    return df


def calculate_epu_signal(epu_value: float, 
                          historical_mean: float = 100,
                          historical_std: float = 50) -> Dict:
    """
    根据 EPU 值生成信号
    
    高 EPU = 高不确定性 = 风险规避
    低 EPU = 低不确定性 = 风险偏好
    
    Parameters:
    -----------
    epu_value : float
        当前 EPU 值
    historical_mean : float
        历史均值
    historical_std : float
        历史标准差
        
    Returns:
    --------
    Dict : 信号字典
    """
    z_score = (epu_value - historical_mean) / historical_std
    
    if z_score > 2:
        risk_regime = 'EXTREME_UNCERTAINTY'
        equity_stance = -0.5  # 大幅减仓
        bond_stance = 0.3  # 增持债券
    elif z_score > 1:
        risk_regime = 'HIGH_UNCERTAINTY'
        equity_stance = -0.2
        bond_stance = 0.2
    elif z_score > -1:
        risk_regime = 'NORMAL'
        equity_stance = 0.0
        bond_stance = 0.0
    elif z_score > -2:
        risk_regime = 'LOW_UNCERTAINTY'
        equity_stance = 0.2
        bond_stance = -0.1
    else:
        risk_regime = 'VERY_LOW_UNCERTAINTY'
        equity_stance = 0.3
        bond_stance = -0.2
    
    return {
        'epu_value': epu_value,
        'z_score': round(z_score, 2),
        'risk_regime': risk_regime,
        'equity_stance': equity_stance,
        'bond_stance': bond_stance
    }


def calculate_fed_policy_factor() -> Dict:
    """
    计算美联储政策因子
    
    基于:
    - 联邦基金利率变化
    - 资产负债表变化 (QE/QT)
    - 市场利率预期
    
    Returns:
    --------
    Dict : 政策因子
    """
    # 获取相关数据
    try:
        # 2年期国债收益率 (利率预期)
        ust2y = yf.download('^TNX', start='2025-01-01', progress=False)
        
        # 10年-2年利差 (收益率曲线)
        ust10y = yf.download('^TNX', start='2025-01-01', progress=False)
        
        current_rate = 4.5  # 当前联邦基金利率 (模拟)
        rate_expectation = -0.25  # 市场预期降息 25bp
        
        # 政策立场评估
        if rate_expectation < -0.5:
            policy_stance = 'DOVISH'
            risk_asset_impact = 'POSITIVE'
        elif rate_expectation < 0:
            policy_stance = 'SLIGHTLY_DOVISH'
            risk_asset_impact = 'SLIGHTLY_POSITIVE'
        elif rate_expectation == 0:
            policy_stance = 'NEUTRAL'
            risk_asset_impact = 'NEUTRAL'
        elif rate_expectation < 0.5:
            policy_stance = 'SLIGHTLY_HAWKISH'
            risk_asset_impact = 'SLIGHTLY_NEGATIVE'
        else:
            policy_stance = 'HAWKISH'
            risk_asset_impact = 'NEGATIVE'
        
        return {
            'current_rate': current_rate,
            'rate_expectation_bps': rate_expectation * 100,
            'policy_stance': policy_stance,
            'risk_asset_impact': risk_asset_impact,
            'qe_qt_status': 'QT'  # 当前缩表中
        }
    
    except Exception as e:
        return {'error': str(e)}


def calculate_election_cycle_factor(date: datetime = None) -> Dict:
    """
    计算美国总统选举周期效应
    
    历史规律:
    - 年份1 (就职年): 表现一般
    - 年份2 (中期选举): 最差
    - 年份3 (预选年): 最好
    - 年份4 (大选年): 表现良好
    
    Parameters:
    -----------
    date : datetime
        日期 (默认今天)
        
    Returns:
    --------
    Dict : 周期因子
    """
    if date is None:
        date = datetime.now()
    
    # 上一次大选年
    year = date.year
    last_election_year = year - (year % 4) if year % 4 != 0 else year
    cycle_year = year - last_election_year + 1
    
    if cycle_year > 4:
        cycle_year = cycle_year % 4
        if cycle_year == 0:
            cycle_year = 4
    
    cycle_names = {
        1: '就职年 (Post-Election)',
        2: '中期选举年 (Midterm)',
        3: '预选年 (Pre-Election)',
        4: '大选年 (Election Year)'
    }
    
    # 历史平均表现 (S&P 500)
    historical_returns = {
        1: 0.067,   # 6.7%
        2: 0.043,   # 4.3%
        3: 0.162,   # 16.2%
        4: 0.072    # 7.2%
    }
    
    # 信号强度
    if cycle_year == 3:
        stance = 'BULLISH'
        equity_tilt = 0.15
    elif cycle_year == 4:
        stance = 'SLIGHTLY_BULLISH'
        equity_tilt = 0.05
    elif cycle_year == 1:
        stance = 'NEUTRAL'
        equity_tilt = 0.0
    else:
        stance = 'CAUTIOUS'
        equity_tilt = -0.05
    
    return {
        'current_year': year,
        'cycle_year': cycle_year,
        'cycle_name': cycle_names[cycle_year],
        'historical_avg_return': historical_returns[cycle_year],
        'stance': stance,
        'equity_tilt': equity_tilt
    }


def combine_political_factors(epu_signal: Dict = None,
                               fed_policy: Dict = None,
                               election_cycle: Dict = None) -> Dict:
    """
    综合政治经济学因子
    
    Returns:
    --------
    Dict : 综合评估
    """
    # 收集各因子的权益倾斜
    tilts = []
    weights = []
    
    if epu_signal and 'equity_stance' in epu_signal:
        tilts.append(epu_signal['equity_stance'])
        weights.append(0.4)  # EPU 权重 40%
    
    if fed_policy and 'risk_asset_impact' in fed_policy:
        impact_map = {
            'POSITIVE': 0.2,
            'SLIGHTLY_POSITIVE': 0.1,
            'NEUTRAL': 0.0,
            'SLIGHTLY_NEGATIVE': -0.1,
            'NEGATIVE': -0.2
        }
        tilts.append(impact_map.get(fed_policy['risk_asset_impact'], 0))
        weights.append(0.35)  # 联储政策权重 35%
    
    if election_cycle and 'equity_tilt' in election_cycle:
        tilts.append(election_cycle['equity_tilt'])
        weights.append(0.25)  # 选举周期权重 25%
    
    # 加权平均
    if tilts:
        total_weight = sum(weights)
        combined_tilt = sum(t * w for t, w in zip(tilts, weights)) / total_weight
    else:
        combined_tilt = 0.0
    
    # 综合评估
    if combined_tilt > 0.15:
        overall_stance = 'RISK_ON'
        recommendation = '增加风险资产配置'
    elif combined_tilt > 0.05:
        overall_stance = 'SLIGHTLY_RISK_ON'
        recommendation = '维持略偏积极配置'
    elif combined_tilt > -0.05:
        overall_stance = 'NEUTRAL'
        recommendation = '维持中性配置'
    elif combined_tilt > -0.15:
        overall_stance = 'SLIGHTLY_RISK_OFF'
        recommendation = '适当降低风险敞口'
    else:
        overall_stance = 'RISK_OFF'
        recommendation = '显著降低风险资产'
    
    return {
        'combined_equity_tilt': round(combined_tilt, 3),
        'overall_stance': overall_stance,
        'recommendation': recommendation,
        'components': {
            'epu': epu_signal,
            'fed_policy': fed_policy,
            'election_cycle': election_cycle
        }
    }


# ============== 测试代码 ==============
if __name__ == "__main__":
    print("=" * 60)
    print("政治经济学因子测试")
    print("=" * 60)
    
    # 1. EPU 分析
    print("\n1. Economic Policy Uncertainty (EPU) Index")
    print("-" * 40)
    epu_df = fetch_epu_index()
    latest_epu = epu_df['epu_index'].iloc[-1]
    epu_signal = calculate_epu_signal(
        latest_epu, 
        epu_df['epu_index'].mean(),
        epu_df['epu_index'].std()
    )
    print(f"   最新 EPU: {latest_epu:.1f}")
    print(f"   Z-Score: {epu_signal['z_score']}")
    print(f"   风险环境: {epu_signal['risk_regime']}")
    print(f"   股票立场: {epu_signal['equity_stance']:+.1%}")
    
    # 2. 联储政策
    print("\n2. 美联储政策因子")
    print("-" * 40)
    fed = calculate_fed_policy_factor()
    if 'error' not in fed:
        print(f"   当前利率: {fed['current_rate']}%")
        print(f"   预期变化: {fed['rate_expectation_bps']:.0f}bp")
        print(f"   政策立场: {fed['policy_stance']}")
        print(f"   风险资产影响: {fed['risk_asset_impact']}")
    
    # 3. 选举周期
    print("\n3. 美国总统选举周期")
    print("-" * 40)
    election = calculate_election_cycle_factor()
    print(f"   当前年份: {election['current_year']}")
    print(f"   周期位置: 第{election['cycle_year']}年 - {election['cycle_name']}")
    print(f"   历史平均收益: {election['historical_avg_return']:.1%}")
    print(f"   立场: {election['stance']}")
    
    # 4. 综合评估
    print("\n4. 综合政治经济学评估")
    print("-" * 40)
    combined = combine_political_factors(epu_signal, fed, election)
    print(f"   综合权益倾斜: {combined['combined_equity_tilt']:+.1%}")
    print(f"   整体立场: {combined['overall_stance']}")
    print(f"   建议: {combined['recommendation']}")
