"""
复杂系统因子 - Complex Systems Factors
======================================
1. 资产相关性网络 - 系统性风险
2. 羊群效应指数 - Ising Model
3. Transfer Entropy - 因果关系
4. 市场状态检测 - 相变信号
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


def calculate_correlation_network(returns: pd.DataFrame, 
                                   threshold: float = 0.5) -> Dict:
    """
    计算资产相关性网络特征
    
    Parameters:
    -----------
    returns : pd.DataFrame
        多资产收益率 (列为资产)
    threshold : float
        相关性阈值
        
    Returns:
    --------
    Dict : 网络特征
    """
    # 相关系数矩阵
    corr_matrix = returns.corr()
    n_assets = len(corr_matrix)
    
    # 网络特征
    # 1. 平均相关性 (系统性风险代理)
    upper_triangle = corr_matrix.values[np.triu_indices(n_assets, k=1)]
    mean_correlation = np.mean(upper_triangle)
    
    # 2. 连接密度 (超过阈值的边比例)
    n_edges = np.sum(np.abs(upper_triangle) > threshold)
    max_edges = n_assets * (n_assets - 1) / 2
    density = n_edges / max_edges if max_edges > 0 else 0
    
    # 3. 最大特征值 (市场因子强度)
    eigenvalues = np.linalg.eigvalsh(corr_matrix)
    max_eigenvalue = np.max(eigenvalues)
    eigenvalue_ratio = max_eigenvalue / np.sum(eigenvalues) * n_assets
    
    # 4. 聚类系数 (局部连接性)
    adj_matrix = (np.abs(corr_matrix.values) > threshold).astype(int)
    np.fill_diagonal(adj_matrix, 0)
    
    clustering_coeffs = []
    for i in range(n_assets):
        neighbors = np.where(adj_matrix[i] == 1)[0]
        k = len(neighbors)
        if k >= 2:
            # 邻居之间的连接数
            neighbor_connections = np.sum(adj_matrix[np.ix_(neighbors, neighbors)]) / 2
            max_connections = k * (k - 1) / 2
            clustering_coeffs.append(neighbor_connections / max_connections)
    
    avg_clustering = np.mean(clustering_coeffs) if clustering_coeffs else 0
    
    # 系统性风险评估
    if mean_correlation > 0.6 or eigenvalue_ratio > 2.5:
        systemic_risk = 'HIGH'
        warning = '资产高度相关，分散化失效风险'
    elif mean_correlation > 0.4 or eigenvalue_ratio > 1.8:
        systemic_risk = 'MEDIUM'
        warning = '适度相关，保持警惕'
    else:
        systemic_risk = 'LOW'
        warning = '相关性较低，分散化有效'
    
    return {
        'mean_correlation': round(mean_correlation, 3),
        'network_density': round(density, 3),
        'max_eigenvalue': round(max_eigenvalue, 3),
        'eigenvalue_ratio': round(eigenvalue_ratio, 3),
        'clustering_coefficient': round(avg_clustering, 3),
        'systemic_risk': systemic_risk,
        'warning': warning
    }


def calculate_herding_index(returns: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    计算羊群效应指数 (基于横截面离散度)
    
    低离散度 = 高羊群效应
    高离散度 = 个体独立决策
    
    Parameters:
    -----------
    returns : pd.DataFrame
        多资产收益率
    window : int
        滚动窗口
        
    Returns:
    --------
    pd.Series : 羊群指数 (0-1, 越高越羊群)
    """
    # 横截面标准差 (Cross-Sectional Standard Deviation)
    cssd = returns.std(axis=1)
    
    # 横截面绝对偏差 (Cross-Sectional Absolute Deviation)
    csad = returns.sub(returns.mean(axis=1), axis=0).abs().mean(axis=1)
    
    # 计算市场收益的绝对值
    market_return = returns.mean(axis=1)
    abs_market_return = market_return.abs()
    
    # 滚动计算羊群效应
    def herding_metric(window_data):
        csad_window = window_data['csad']
        abs_mr_window = window_data['abs_mr']
        
        # 理想情况下 CSAD 与 |Rm| 线性相关
        # 羊群效应导致 CSAD 在极端市场时低于预期
        if len(csad_window) < 10:
            return 0.5
        
        # 简化：用 CSAD 的均值回归程度衡量
        csad_mean = csad_window.mean()
        csad_std = csad_window.std()
        
        if csad_std == 0:
            return 0.5
        
        # 当前 CSAD 相对于均值的位置
        current_csad = csad_window.iloc[-1]
        z_score = (current_csad - csad_mean) / csad_std
        
        # 转换为 0-1 (低 CSAD = 高羊群)
        herding = 1 / (1 + np.exp(z_score))  # sigmoid 转换
        
        return herding
    
    # 创建临时 DataFrame
    temp_df = pd.DataFrame({'csad': csad, 'abs_mr': abs_market_return})
    
    herding_series = []
    for i in range(len(temp_df)):
        if i < window:
            herding_series.append(0.5)
        else:
            window_data = temp_df.iloc[i-window:i]
            herding_series.append(herding_metric(window_data))
    
    return pd.Series(herding_series, index=returns.index, name='herding_index')


def calculate_transfer_entropy(source: pd.Series, 
                                target: pd.Series,
                                lag: int = 1,
                                bins: int = 10) -> float:
    """
    计算 Transfer Entropy (信息流向)
    
    TE(X→Y) > TE(Y→X): X 领先 Y
    
    Parameters:
    -----------
    source : pd.Series
        源序列 (潜在因)
    target : pd.Series
        目标序列 (潜在果)
    lag : int
        滞后期
    bins : int
        离散化分箱数
        
    Returns:
    --------
    float : Transfer Entropy
    """
    # 对齐数据
    source = source.dropna()
    target = target.dropna()
    common_idx = source.index.intersection(target.index)
    source = source.loc[common_idx]
    target = target.loc[common_idx]
    
    if len(source) < lag + 10:
        return 0.0
    
    # 离散化
    source_binned = pd.cut(source, bins=bins, labels=False).values
    target_binned = pd.cut(target, bins=bins, labels=False).values
    
    # 创建滞后序列
    y_t = target_binned[lag:]
    y_t1 = target_binned[:-lag]
    x_t1 = source_binned[:-lag]
    
    # 计算概率分布
    def entropy(x):
        _, counts = np.unique(x, return_counts=True)
        probs = counts / len(x)
        return -np.sum(probs * np.log2(probs + 1e-10))
    
    def joint_entropy(*arrays):
        combined = np.column_stack(arrays)
        _, counts = np.unique(combined, axis=0, return_counts=True)
        probs = counts / len(combined)
        return -np.sum(probs * np.log2(probs + 1e-10))
    
    # Transfer Entropy = H(Y_t | Y_t-1) - H(Y_t | Y_t-1, X_t-1)
    # = H(Y_t, Y_t-1) - H(Y_t-1) - H(Y_t, Y_t-1, X_t-1) + H(Y_t-1, X_t-1)
    
    h_y_yt1 = joint_entropy(y_t, y_t1)
    h_yt1 = entropy(y_t1)
    h_y_yt1_xt1 = joint_entropy(y_t, y_t1, x_t1)
    h_yt1_xt1 = joint_entropy(y_t1, x_t1)
    
    te = h_y_yt1 - h_yt1 - h_y_yt1_xt1 + h_yt1_xt1
    
    return max(0, te)  # TE 应该非负


def detect_market_regime(returns: pd.Series, 
                          window: int = 60) -> Dict:
    """
    检测市场状态 (相变信号)
    
    基于:
    - 波动率聚类
    - 收益率分布变化
    - 自相关结构
    
    Parameters:
    -----------
    returns : pd.Series
        收益率序列
    window : int
        检测窗口
        
    Returns:
    --------
    Dict : 市场状态
    """
    if len(returns) < window:
        return {'regime': 'UNKNOWN', 'confidence': 0}
    
    recent = returns.iloc[-window:]
    
    # 1. 波动率状态
    volatility = recent.std() * np.sqrt(252)
    vol_percentile = stats.percentileofscore(
        returns.rolling(window).std().dropna() * np.sqrt(252),
        volatility
    )
    
    # 2. 偏度 (负偏度 = 崩盘风险)
    skewness = stats.skew(recent)
    
    # 3. 峰度 (高峰度 = 厚尾风险)
    kurtosis = stats.kurtosis(recent)
    
    # 4. 自相关 (高自相关 = 趋势)
    autocorr = recent.autocorr(lag=1)
    
    # 综合判断
    if vol_percentile > 80 and skewness < -0.5:
        regime = 'CRISIS'
        description = '危机模式：高波动 + 负偏度'
        risk_level = 0.9
    elif vol_percentile > 70:
        regime = 'HIGH_VOLATILITY'
        description = '高波动模式'
        risk_level = 0.7
    elif vol_percentile < 20 and kurtosis > 3:
        regime = 'CALM_BEFORE_STORM'
        description = '暴风雨前的平静：低波动但厚尾'
        risk_level = 0.6
    elif autocorr > 0.1:
        regime = 'TRENDING'
        description = '趋势模式'
        risk_level = 0.4
    elif autocorr < -0.1:
        regime = 'MEAN_REVERTING'
        description = '均值回归模式'
        risk_level = 0.3
    else:
        regime = 'NORMAL'
        description = '正常市场状态'
        risk_level = 0.3
    
    return {
        'regime': regime,
        'description': description,
        'risk_level': round(risk_level, 2),
        'metrics': {
            'volatility': round(volatility, 4),
            'vol_percentile': round(vol_percentile, 1),
            'skewness': round(skewness, 3),
            'kurtosis': round(kurtosis, 3),
            'autocorrelation': round(autocorr, 3)
        }
    }


# ============== 测试代码 ==============
if __name__ == "__main__":
    import yfinance as yf
    
    print("=" * 60)
    print("复杂系统因子测试")
    print("=" * 60)
    
    # 获取多资产数据
    tickers = ['BTC-USD', 'ETH-USD', 'SPY', 'GLD', 'TLT']
    print(f"\n获取数据: {tickers}")
    
    prices = {}
    for ticker in tickers:
        data = yf.download(ticker, start='2024-01-01', progress=False)
        prices[ticker] = data['Close'].squeeze()
    
    prices_df = pd.DataFrame(prices).dropna()
    returns_df = np.log(prices_df / prices_df.shift(1)).dropna()
    
    print(f"数据范围: {returns_df.index[0]} ~ {returns_df.index[-1]}")
    print(f"样本数: {len(returns_df)}")
    
    # 1. 相关性网络
    print("\n1. 资产相关性网络")
    print("-" * 40)
    network = calculate_correlation_network(returns_df)
    print(f"   平均相关性: {network['mean_correlation']}")
    print(f"   网络密度: {network['network_density']}")
    print(f"   最大特征值比: {network['eigenvalue_ratio']}")
    print(f"   系统性风险: {network['systemic_risk']}")
    print(f"   警告: {network['warning']}")
    
    # 2. 羊群效应
    print("\n2. 羊群效应指数")
    print("-" * 40)
    herding = calculate_herding_index(returns_df)
    print(f"   当前羊群指数: {herding.iloc[-1]:.3f}")
    print(f"   30日均值: {herding.tail(30).mean():.3f}")
    print(f"   解读: {'高羊群效应' if herding.iloc[-1] > 0.6 else '正常' if herding.iloc[-1] > 0.4 else '独立决策'}")
    
    # 3. Transfer Entropy
    print("\n3. Transfer Entropy (信息流向)")
    print("-" * 40)
    btc_returns = returns_df['BTC-USD']
    eth_returns = returns_df['ETH-USD']
    spy_returns = returns_df['SPY']
    
    te_btc_eth = calculate_transfer_entropy(btc_returns, eth_returns)
    te_eth_btc = calculate_transfer_entropy(eth_returns, btc_returns)
    te_spy_btc = calculate_transfer_entropy(spy_returns, btc_returns)
    te_btc_spy = calculate_transfer_entropy(btc_returns, spy_returns)
    
    print(f"   BTC → ETH: {te_btc_eth:.4f}")
    print(f"   ETH → BTC: {te_eth_btc:.4f}")
    print(f"   领先关系: {'BTC 领先 ETH' if te_btc_eth > te_eth_btc else 'ETH 领先 BTC'}")
    print()
    print(f"   SPY → BTC: {te_spy_btc:.4f}")
    print(f"   BTC → SPY: {te_btc_spy:.4f}")
    print(f"   领先关系: {'SPY 领先 BTC' if te_spy_btc > te_btc_spy else 'BTC 领先 SPY'}")
    
    # 4. 市场状态
    print("\n4. 市场状态检测")
    print("-" * 40)
    regime = detect_market_regime(btc_returns)
    print(f"   当前状态: {regime['regime']}")
    print(f"   描述: {regime['description']}")
    print(f"   风险水平: {regime['risk_level']:.0%}")
    print(f"   年化波动率: {regime['metrics']['volatility']:.1%}")
    print(f"   波动率百分位: {regime['metrics']['vol_percentile']:.0f}%")
