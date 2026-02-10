"""
物理金融学因子 - Econophysics Factors
=====================================
1. Hurst 指数 - 长记忆效应检测
2. 市场熵 - 价格信息含量
3. 分形维度 - 自相似性
4. Lyapunov 指数 - 系统不稳定性
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Tuple, Dict
import warnings
warnings.filterwarnings('ignore')


def calculate_hurst_exponent(prices: pd.Series, max_lag: int = 100) -> float:
    """
    计算 Hurst 指数 (R/S 分析法)
    
    H > 0.5: 趋势持续性 (正相关)
    H = 0.5: 随机游走 (无相关)
    H < 0.5: 均值回归 (负相关)
    
    Parameters:
    -----------
    prices : pd.Series
        价格序列
    max_lag : int
        最大滞后期
        
    Returns:
    --------
    float : Hurst 指数
    """
    returns = np.log(prices / prices.shift(1)).dropna().values
    
    lags = range(10, max_lag)
    rs_list = []
    
    for lag in lags:
        rs_values = []
        for start in range(0, len(returns) - lag, lag):
            chunk = returns[start:start + lag]
            if len(chunk) < lag:
                continue
            
            # 计算累积离差
            mean_chunk = np.mean(chunk)
            cumsum = np.cumsum(chunk - mean_chunk)
            
            # R = max - min
            R = np.max(cumsum) - np.min(cumsum)
            
            # S = 标准差
            S = np.std(chunk, ddof=1)
            
            if S > 0:
                rs_values.append(R / S)
        
        if rs_values:
            rs_list.append((lag, np.mean(rs_values)))
    
    if len(rs_list) < 5:
        return 0.5  # 默认随机游走
    
    # 线性回归 log(R/S) vs log(n)
    lags_arr = np.log([x[0] for x in rs_list])
    rs_arr = np.log([x[1] for x in rs_list])
    
    slope, _, _, _, _ = stats.linregress(lags_arr, rs_arr)
    
    return slope


def calculate_market_entropy(returns: pd.Series, bins: int = 50, window: int = 20) -> pd.Series:
    """
    计算市场 Shannon 熵
    
    高熵 = 市场不确定性高，难以预测
    低熵 = 市场有序，可能有趋势
    
    Parameters:
    -----------
    returns : pd.Series
        收益率序列
    bins : int
        直方图分箱数
    window : int
        滚动窗口
        
    Returns:
    --------
    pd.Series : 熵序列
    """
    def shannon_entropy(x):
        hist, _ = np.histogram(x, bins=bins, density=True)
        hist = hist[hist > 0]  # 移除零值
        return -np.sum(hist * np.log2(hist + 1e-10))
    
    return returns.rolling(window=window).apply(shannon_entropy, raw=True)


def calculate_fractal_dimension(prices: pd.Series, window: int = 50) -> pd.Series:
    """
    计算分形维度 (Box-counting 近似)
    
    D ≈ 1: 平滑曲线
    D ≈ 2: 填满空间的曲线
    1.5 < D < 2: 高度不规则/混沌
    
    Parameters:
    -----------
    prices : pd.Series
        价格序列
    window : int
        滚动窗口
        
    Returns:
    --------
    pd.Series : 分形维度序列
    """
    def box_dimension(x):
        if len(x) < 10:
            return 1.5
        
        # 归一化到 [0, 1]
        x_norm = (x - np.min(x)) / (np.max(x) - np.min(x) + 1e-10)
        
        # 计算不同尺度的覆盖数
        scales = [2, 4, 8, 16]
        counts = []
        
        for scale in scales:
            bins = np.linspace(0, 1, scale + 1)
            count = 0
            for i in range(len(x_norm) - 1):
                # 简化：计算跨越的格子数
                y1, y2 = x_norm[i], x_norm[i + 1]
                count += abs(np.digitize(y2, bins) - np.digitize(y1, bins)) + 1
            counts.append(count)
        
        # 线性回归估计维度
        log_scales = np.log(scales)
        log_counts = np.log(np.array(counts) + 1)
        
        slope, _, _, _, _ = stats.linregress(log_scales, log_counts)
        return slope
    
    return prices.rolling(window=window).apply(box_dimension, raw=True)


def calculate_lyapunov_exponent(prices: pd.Series, embedding_dim: int = 3, 
                                  delay: int = 1, window: int = 100) -> float:
    """
    计算 Lyapunov 指数 (简化版)
    
    λ > 0: 混沌系统 (初始条件敏感)
    λ ≈ 0: 周期性/准周期性
    λ < 0: 收敛到稳定点
    
    Parameters:
    -----------
    prices : pd.Series
        价格序列
    embedding_dim : int
        嵌入维度
    delay : int
        时间延迟
    window : int
        计算窗口
        
    Returns:
    --------
    float : Lyapunov 指数
    """
    returns = np.log(prices / prices.shift(1)).dropna().values[-window:]
    
    if len(returns) < embedding_dim * delay:
        return 0.0
    
    # 相空间重构
    n_vectors = len(returns) - (embedding_dim - 1) * delay
    vectors = np.zeros((n_vectors, embedding_dim))
    
    for i in range(n_vectors):
        for j in range(embedding_dim):
            vectors[i, j] = returns[i + j * delay]
    
    # 计算最近邻距离的发散率
    divergences = []
    
    for i in range(len(vectors) - 1):
        # 找最近邻 (排除自己和相邻点)
        distances = np.sqrt(np.sum((vectors - vectors[i])**2, axis=1))
        distances[max(0, i-5):min(len(distances), i+5)] = np.inf
        
        nearest_idx = np.argmin(distances)
        d0 = distances[nearest_idx]
        
        if d0 > 0 and i + 1 < len(vectors) and nearest_idx + 1 < len(vectors):
            d1 = np.sqrt(np.sum((vectors[i+1] - vectors[nearest_idx+1])**2))
            if d1 > 0:
                divergences.append(np.log(d1 / d0))
    
    if divergences:
        return np.mean(divergences)
    return 0.0


def calculate_all_econophysics_factors(prices: pd.Series, 
                                        returns: pd.Series = None) -> Dict[str, float]:
    """
    计算所有物理金融学因子
    
    Parameters:
    -----------
    prices : pd.Series
        价格序列
    returns : pd.Series, optional
        收益率序列
        
    Returns:
    --------
    Dict : 因子字典
    """
    if returns is None:
        returns = np.log(prices / prices.shift(1)).dropna()
    
    factors = {}
    
    # Hurst 指数
    factors['hurst_exponent'] = calculate_hurst_exponent(prices)
    
    # 市场熵 (取最新值)
    entropy_series = calculate_market_entropy(returns)
    factors['market_entropy'] = entropy_series.iloc[-1] if not entropy_series.empty else 0
    
    # 分形维度 (取最新值)
    fractal_series = calculate_fractal_dimension(prices)
    factors['fractal_dimension'] = fractal_series.iloc[-1] if not fractal_series.empty else 1.5
    
    # Lyapunov 指数
    factors['lyapunov_exponent'] = calculate_lyapunov_exponent(prices)
    
    return factors


# ============== 测试代码 ==============
if __name__ == "__main__":
    import yfinance as yf
    
    print("=" * 60)
    print("物理金融学因子测试")
    print("=" * 60)
    
    # 获取 BTC 数据
    btc = yf.download('BTC-USD', start='2023-01-01', progress=False)
    prices = btc['Close'].squeeze()
    returns = np.log(prices / prices.shift(1)).dropna()
    
    print(f"\n数据范围: {prices.index[0]} ~ {prices.index[-1]}")
    print(f"样本数: {len(prices)}")
    
    # 计算因子
    factors = calculate_all_econophysics_factors(prices, returns)
    
    print("\n" + "-" * 40)
    print("计算结果:")
    print("-" * 40)
    
    for name, value in factors.items():
        print(f"{name}: {value:.4f}")
    
    # 解读
    print("\n" + "-" * 40)
    print("因子解读:")
    print("-" * 40)
    
    h = factors['hurst_exponent']
    if h > 0.55:
        print(f"Hurst={h:.3f}: 趋势持续性强，适合趋势跟踪")
    elif h < 0.45:
        print(f"Hurst={h:.3f}: 均值回归特性，适合反转策略")
    else:
        print(f"Hurst={h:.3f}: 接近随机游走")
    
    e = factors['market_entropy']
    print(f"熵={e:.3f}: {'市场混乱' if e > 4 else '市场有序'}")
    
    l = factors['lyapunov_exponent']
    print(f"Lyapunov={l:.4f}: {'混沌/不稳定' if l > 0 else '相对稳定'}")
