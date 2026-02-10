"""
生成回测可视化图表
==================
使用 matplotlib 生成专业的回测报告图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import json

# 设置中文字体 (如果可用)
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['figure.dpi'] = 100


def load_data():
    """加载回测数据"""
    equity = pd.read_csv('../final_strategy_equity.csv', index_col=0, parse_dates=True)
    
    with open('../final_strategy_result.json', 'r') as f:
        result = json.load(f)
    
    return equity, result


def plot_equity_curve(equity: pd.DataFrame, result: dict):
    """绘制资金曲线"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), height_ratios=[2, 1, 1])
    
    # 1. 资金曲线
    ax1 = axes[0]
    ax1.fill_between(equity.index, 100000, equity['equity'], alpha=0.3, color='blue')
    ax1.plot(equity.index, equity['equity'], 'b-', linewidth=1.5, label='Portfolio Value')
    ax1.axhline(y=100000, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    
    ax1.set_title('Portfolio Equity Curve (2019-2026)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($)', fontsize=11)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(equity.index[0], equity.index[-1])
    
    # 添加年度标签
    final_value = equity['equity'].iloc[-1]
    ax1.annotate(f'Final: ${final_value:,.0f}\n(+{(final_value/100000-1)*100:.1f}%)', 
                 xy=(equity.index[-1], final_value),
                 xytext=(-100, 20), textcoords='offset points',
                 fontsize=10, color='blue',
                 arrowprops=dict(arrowstyle='->', color='blue', alpha=0.5))
    
    # 2. 回撤曲线
    ax2 = axes[1]
    rolling_max = equity['equity'].expanding().max()
    drawdown = (equity['equity'] - rolling_max) / rolling_max * 100
    
    ax2.fill_between(equity.index, 0, drawdown, alpha=0.3, color='red')
    ax2.plot(equity.index, drawdown, 'r-', linewidth=1, label='Drawdown')
    ax2.axhline(y=-15, color='orange', linestyle='--', alpha=0.7, label='15% Target')
    
    max_dd = drawdown.min()
    max_dd_date = drawdown.idxmin()
    ax2.annotate(f'Max: {max_dd:.1f}%', 
                 xy=(max_dd_date, max_dd),
                 xytext=(20, -20), textcoords='offset points',
                 fontsize=10, color='red')
    
    ax2.set_ylabel('Drawdown (%)', fontsize=11)
    ax2.legend(loc='lower left')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(equity.index[0], equity.index[-1])
    
    # 3. 仓位
    ax3 = axes[2]
    ax3.fill_between(equity.index, 0, equity['position'] * 100, alpha=0.3, color='green')
    ax3.plot(equity.index, equity['position'] * 100, 'g-', linewidth=1, label='Position')
    ax3.axhline(y=100, color='gray', linestyle='--', alpha=0.5)
    
    ax3.set_ylabel('Position (%)', fontsize=11)
    ax3.set_xlabel('Date', fontsize=11)
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(equity.index[0], equity.index[-1])
    
    plt.tight_layout()
    plt.savefig('equity_curve.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ 资金曲线图已保存: equity_curve.png")


def plot_monthly_returns(equity: pd.DataFrame):
    """绘制月度收益热力图"""
    # 计算月度收益
    monthly = equity['equity'].resample('M').last()
    monthly_returns = monthly.pct_change() * 100
    
    # 创建年-月矩阵
    years = monthly_returns.index.year.unique()
    months = range(1, 13)
    
    data = np.zeros((len(years), 12))
    data[:] = np.nan
    
    for i, year in enumerate(years):
        year_data = monthly_returns[monthly_returns.index.year == year]
        for date, val in year_data.items():
            month_idx = date.month - 1
            data[i, month_idx] = val
    
    # 绘图
    fig, ax = plt.subplots(figsize=(14, 6))
    
    im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=-10, vmax=10)
    
    # 设置标签
    ax.set_xticks(range(12))
    ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels(years)
    
    # 添加数值标签
    for i in range(len(years)):
        for j in range(12):
            if not np.isnan(data[i, j]):
                color = 'white' if abs(data[i, j]) > 5 else 'black'
                ax.text(j, i, f'{data[i, j]:.1f}', ha='center', va='center', 
                        color=color, fontsize=9)
    
    ax.set_title('Monthly Returns Heatmap (%)', fontsize=14, fontweight='bold')
    
    # 添加颜色条
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Return (%)', fontsize=11)
    
    plt.tight_layout()
    plt.savefig('monthly_returns.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ 月度收益热力图已保存: monthly_returns.png")


def plot_risk_metrics(result: dict):
    """绘制风险指标仪表盘"""
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    
    # 指标数据
    metrics = [
        ('Annual Return', result['annual_return'], '%', 10, 20, 'green'),
        ('Max Drawdown', abs(result['max_drawdown']), '%', 0, 15, 'red'),
        ('Sharpe Ratio', result['sharpe_ratio'], '', 0, 2, 'blue'),
        ('Sortino Ratio', result['sortino_ratio'], '', 0, 3, 'purple'),
        ('Calmar Ratio', result['calmar_ratio'], '', 0, 2, 'orange'),
        ('Volatility', result['volatility'], '%', 0, 20, 'gray')
    ]
    
    for idx, (name, value, unit, min_val, max_val, color) in enumerate(metrics):
        ax = axes[idx // 3, idx % 3]
        
        # 绘制半圆仪表
        theta = np.linspace(0, np.pi, 100)
        r = 1
        
        # 背景弧
        ax.fill_between(np.cos(theta), np.sin(theta) * 0.8, np.sin(theta), 
                        alpha=0.1, color='gray')
        
        # 值对应的角度
        pct = min(1, max(0, (value - min_val) / (max_val - min_val)))
        value_theta = np.pi * (1 - pct)
        
        # 指针
        ax.plot([0, np.cos(value_theta) * 0.9], [0, np.sin(value_theta) * 0.9], 
                color=color, linewidth=3)
        ax.scatter([np.cos(value_theta) * 0.9], [np.sin(value_theta) * 0.9], 
                   color=color, s=100, zorder=5)
        
        # 刻度
        for i in range(5):
            t = np.pi * (1 - i/4)
            ax.plot([np.cos(t) * 0.85, np.cos(t)], [np.sin(t) * 0.85, np.sin(t)], 
                    color='gray', linewidth=1)
            label_val = min_val + (max_val - min_val) * i / 4
            ax.text(np.cos(t) * 1.1, np.sin(t) * 1.1, f'{label_val:.0f}', 
                    ha='center', va='center', fontsize=8, color='gray')
        
        # 标题和值
        ax.text(0, -0.3, f'{value:.2f}{unit}', ha='center', va='center', 
                fontsize=16, fontweight='bold', color=color)
        ax.text(0, -0.5, name, ha='center', va='center', fontsize=11)
        
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.6, 1.3)
        ax.set_aspect('equal')
        ax.axis('off')
    
    fig.suptitle('Risk Metrics Dashboard', fontsize=16, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    plt.savefig('risk_metrics.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ 风险指标仪表盘已保存: risk_metrics.png")


def plot_asset_allocation(result: dict):
    """绘制资产配置饼图"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # 1. 资产权重饼图
    weights = result['weights']
    labels = list(weights.keys())
    sizes = list(weights.values())
    colors = ['#FF9500', '#007AFF', '#FFD700', '#4CD964']
    explode = [0.05, 0, 0, 0]
    
    ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
            shadow=True, startangle=90, textprops={'fontsize': 12})
    ax1.set_title('Asset Allocation', fontsize=14, fontweight='bold')
    
    # 2. 资产类别权重
    categories = {
        'Crypto': weights.get('BTC', 0),
        'Equities': weights.get('SPY', 0),
        'Commodities': weights.get('GLD', 0),
        'Fixed Income': weights.get('TLT', 0)
    }
    
    bars = ax2.barh(list(categories.keys()), list(categories.values()), 
                    color=['#FF9500', '#007AFF', '#FFD700', '#4CD964'])
    ax2.set_xlim(0, 0.6)
    ax2.set_xlabel('Weight', fontsize=11)
    ax2.set_title('Asset Categories', fontsize=14, fontweight='bold')
    
    for bar, val in zip(bars, categories.values()):
        ax2.text(val + 0.02, bar.get_y() + bar.get_height()/2, 
                 f'{val*100:.1f}%', va='center', fontsize=11)
    
    plt.tight_layout()
    plt.savefig('asset_allocation.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✅ 资产配置图已保存: asset_allocation.png")


def main():
    print("=" * 50)
    print("📊 生成回测可视化图表")
    print("=" * 50)
    
    equity, result = load_data()
    
    plot_equity_curve(equity, result)
    plot_monthly_returns(equity)
    plot_risk_metrics(result)
    plot_asset_allocation(result)
    
    print("\n✅ 所有图表生成完成!")


if __name__ == '__main__':
    main()
