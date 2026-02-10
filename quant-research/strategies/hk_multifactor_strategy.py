"""
港股多因子选股策略
==================
使用价值、动量、质量因子 + LightGBM 信号确认

目标：
- 年化收益 8-15%
- 最大回撤 < 15%
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class StockSelection:
    """股票选择结果"""
    symbols: List[str]
    weights: List[float]
    scores: List[float]
    factors: pd.DataFrame


class HKMultiFactorStrategy:
    """
    港股多因子选股策略
    
    因子类别:
    1. 价值因子: PE, PB, 股息率
    2. 动量因子: 1M/3M/6M/12M 收益率
    3. 质量因子: ROE (如有数据)
    4. 技术因子: RSI, 波动率
    """
    
    def __init__(
        self,
        n_stocks: int = 10,  # 选股数量
        rebalance_freq: str = 'M',  # 再平衡频率
        factor_weights: Optional[Dict[str, float]] = None
    ):
        self.n_stocks = n_stocks
        self.rebalance_freq = rebalance_freq
        self.factor_weights = factor_weights or {
            'momentum_3m': 0.25,
            'momentum_6m': 0.20,
            'momentum_12m': 0.15,
            'volatility': 0.15,  # 低波动优先
            'rsi_score': 0.15,
            'volume_trend': 0.10
        }
        
    def calculate_factors(self, prices: pd.DataFrame, volumes: pd.DataFrame = None) -> pd.DataFrame:
        """
        计算各种因子
        
        Args:
            prices: 股票价格 DataFrame (columns=股票代码, index=日期)
            volumes: 成交量 DataFrame (可选)
            
        Returns:
            因子得分 DataFrame
        """
        factors = pd.DataFrame(index=prices.columns)
        
        # 动量因子
        if len(prices) > 21:
            factors['momentum_1m'] = (prices.iloc[-1] / prices.iloc[-21] - 1).rank(pct=True)
        if len(prices) > 63:
            factors['momentum_3m'] = (prices.iloc[-1] / prices.iloc[-63] - 1).rank(pct=True)
        if len(prices) > 126:
            factors['momentum_6m'] = (prices.iloc[-1] / prices.iloc[-126] - 1).rank(pct=True)
        if len(prices) > 252:
            factors['momentum_12m'] = (prices.iloc[-1] / prices.iloc[-252] - 1).rank(pct=True)
            
        # 波动率因子 (低波动优先)
        if len(prices) > 60:
            returns = prices.pct_change()
            volatility = returns.iloc[-60:].std()
            factors['volatility'] = 1 - volatility.rank(pct=True)  # 低波动得分高
            
        # RSI 因子 (中性偏多)
        if len(prices) > 14:
            rsi = self._calculate_rsi(prices, 14)
            # RSI 40-60 得分最高
            factors['rsi_score'] = 1 - abs(rsi - 50) / 50
            factors['rsi_score'] = factors['rsi_score'].rank(pct=True)
            
        # 成交量趋势因子
        if volumes is not None and len(volumes) > 20:
            vol_ma5 = volumes.iloc[-5:].mean()
            vol_ma20 = volumes.iloc[-20:].mean()
            factors['volume_trend'] = (vol_ma5 / vol_ma20).rank(pct=True)
        else:
            factors['volume_trend'] = 0.5  # 无数据时中性
            
        # 填充缺失值
        factors = factors.fillna(0.5)
        
        return factors
    
    def _calculate_rsi(self, prices: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 RSI"""
        latest_prices = prices.iloc[-period-1:]
        delta = latest_prices.diff()
        
        gain = delta.where(delta > 0, 0).iloc[-period:].mean()
        loss = (-delta.where(delta < 0, 0)).iloc[-period:].mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if isinstance(rsi, pd.DataFrame) else rsi
    
    def calculate_composite_score(self, factors: pd.DataFrame) -> pd.Series:
        """计算综合得分"""
        score = pd.Series(0, index=factors.index, dtype=float)
        
        for factor, weight in self.factor_weights.items():
            if factor in factors.columns:
                score += factors[factor] * weight
                
        return score
    
    def select_stocks(self, prices: pd.DataFrame, volumes: pd.DataFrame = None) -> StockSelection:
        """选股"""
        # 计算因子
        factors = self.calculate_factors(prices, volumes)
        
        # 综合得分
        scores = self.calculate_composite_score(factors)
        
        # 选择得分最高的 n 只股票
        top_stocks = scores.nlargest(self.n_stocks)
        
        # 等权配置
        weights = [1.0 / len(top_stocks)] * len(top_stocks)
        
        return StockSelection(
            symbols=top_stocks.index.tolist(),
            weights=weights,
            scores=top_stocks.values.tolist(),
            factors=factors.loc[top_stocks.index]
        )


class HKBacktester:
    """港股策略回测器"""
    
    def __init__(
        self, 
        strategy: HKMultiFactorStrategy, 
        initial_capital: float = 100000,
        transaction_cost: float = 0.001  # 0.1% 交易成本
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        
    def run(self, prices: pd.DataFrame, volumes: pd.DataFrame = None) -> pd.DataFrame:
        """
        运行回测
        
        Args:
            prices: 价格数据 (columns=股票代码, index=日期)
            volumes: 成交量数据
        """
        # 生成再平衡日期
        rebalance_dates = prices.resample(self.strategy.rebalance_freq).last().index
        
        # 初始化
        cash = self.initial_capital
        holdings = {}  # {symbol: quantity}
        
        equity_curve = []
        trades = []
        
        # 确保有足够的历史数据
        min_history = 252 + 30  # 至少一年数据 + 缓冲
        
        for i, date in enumerate(prices.index):
            current_prices = prices.loc[date]
            
            # 计算当前持仓价值
            portfolio_value = 0
            for sym, qty in holdings.items():
                if sym in current_prices.index and not pd.isna(current_prices[sym]):
                    portfolio_value += qty * current_prices[sym]
            
            total_equity = cash + portfolio_value
            
            # 检查是否是再平衡日
            if date in rebalance_dates and i >= min_history:
                # 使用到当前日期的历史数据
                historical_prices = prices.iloc[:i+1]
                historical_volumes = volumes.iloc[:i+1] if volumes is not None else None
                
                # 选股
                selection = self.strategy.select_stocks(historical_prices, historical_volumes)
                
                # 清算所有持仓
                for sym, qty in list(holdings.items()):
                    if sym in current_prices.index and not pd.isna(current_prices[sym]) and current_prices[sym] > 0:
                        sell_value = qty * current_prices[sym]
                        cost = sell_value * self.transaction_cost
                        cash += sell_value - cost
                        trades.append({
                            'date': date,
                            'symbol': sym,
                            'action': 'sell',
                            'price': current_prices[sym],
                            'quantity': qty,
                            'cost': cost
                        })
                holdings = {}
                
                # 买入新持仓
                available_capital = cash * 0.95  # 保留 5% 现金
                
                for sym, weight in zip(selection.symbols, selection.weights):
                    if sym in current_prices.index and not pd.isna(current_prices[sym]) and current_prices[sym] > 0:
                        target_value = available_capital * weight
                        quantity = target_value / current_prices[sym]
                        cost = target_value * self.transaction_cost
                        
                        holdings[sym] = quantity
                        cash -= (target_value + cost)
                        
                        trades.append({
                            'date': date,
                            'symbol': sym,
                            'action': 'buy',
                            'price': current_prices[sym],
                            'quantity': quantity,
                            'cost': cost
                        })
                
                # 重新计算持仓价值
                portfolio_value = 0
                for sym, qty in holdings.items():
                    if sym in current_prices.index and not pd.isna(current_prices[sym]):
                        portfolio_value += qty * current_prices[sym]
                total_equity = cash + portfolio_value
            
            equity_curve.append({
                'date': date,
                'equity': total_equity,
                'n_holdings': len(holdings),
                'cash': cash
            })
        
        self.trades = pd.DataFrame(trades)
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
        
        # 夏普比率
        daily_returns = equity.pct_change().dropna()
        sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
        
        # 交易统计
        total_trades = len(self.trades) // 2 if len(self.trades) > 0 else 0
        
        return {
            'total_return': round(total_return, 2),
            'annual_return': round(annual_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe, 2),
            'total_trades': total_trades,
            'final_capital': round(equity.iloc[-1], 2)
        }


def fetch_hk_stocks(symbols: List[str], start_date: str, end_date: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    获取港股数据
    
    Args:
        symbols: 股票代码列表 (如 ['0700.HK', '9988.HK'])
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        prices: 收盘价 DataFrame
        volumes: 成交量 DataFrame
    """
    try:
        import yfinance as yf
        
        prices_dict = {}
        volumes_dict = {}
        
        for symbol in symbols:
            try:
                data = yf.download(symbol, start=start_date, end=end_date, progress=False)
                if len(data) > 0:
                    if isinstance(data.columns, pd.MultiIndex):
                        prices_dict[symbol] = data['Close'][symbol] if symbol in data['Close'].columns else data['Close'].iloc[:, 0]
                        volumes_dict[symbol] = data['Volume'][symbol] if symbol in data['Volume'].columns else data['Volume'].iloc[:, 0]
                    else:
                        prices_dict[symbol] = data['Close']
                        volumes_dict[symbol] = data['Volume']
            except Exception as e:
                print(f"  ⚠️ 无法获取 {symbol}: {e}")
                
        prices = pd.DataFrame(prices_dict)
        volumes = pd.DataFrame(volumes_dict)
        
        return prices, volumes
        
    except ImportError:
        print("❌ 请安装 yfinance: pip install yfinance")
        return pd.DataFrame(), pd.DataFrame()


# 恒生指数成分股示例
HSI_COMPONENTS = [
    '0001.HK',  # 长江和记
    '0002.HK',  # 中电控股
    '0003.HK',  # 中华煤气
    '0005.HK',  # 汇丰控股
    '0011.HK',  # 恒生银行
    '0012.HK',  # 恒基地产
    '0016.HK',  # 新鸿基地产
    '0017.HK',  # 新世界发展
    '0027.HK',  # 银河娱乐
    '0066.HK',  # 港铁公司
    '0101.HK',  # 恒隆地产
    '0175.HK',  # 吉利汽车
    '0241.HK',  # 阿里健康
    '0267.HK',  # 中信股份
    '0288.HK',  # 万洲国际
    '0388.HK',  # 香港交易所
    '0669.HK',  # 创科实业
    '0700.HK',  # 腾讯控股
    '0762.HK',  # 中国联通
    '0823.HK',  # 领展房产
    '0857.HK',  # 中国石油
    '0883.HK',  # 中国海洋石油
    '0939.HK',  # 建设银行
    '0941.HK',  # 中国移动
    '0960.HK',  # 龙湖集团
    '0968.HK',  # 信义光能
    '0981.HK',  # 中芯国际
    '1038.HK',  # 长江基建
    '1044.HK',  # 恒安国际
    '1093.HK',  # 石药集团
    '1109.HK',  # 华润置地
    '1113.HK',  # 长实集团
    '1177.HK',  # 中国生物制药
    '1211.HK',  # 比亚迪
    '1299.HK',  # 友邦保险
    '1398.HK',  # 工商银行
    '1810.HK',  # 小米集团
    '1876.HK',  # 百威亚太
    '1928.HK',  # 金沙中国
    '1997.HK',  # 九龙仓置业
    '2007.HK',  # 碧桂园
    '2018.HK',  # 瑞声科技
    '2269.HK',  # 药明生物
    '2313.HK',  # 申洲国际
    '2318.HK',  # 中国平安
    '2319.HK',  # 蒙牛乳业
    '2331.HK',  # 李宁
    '2382.HK',  # 舜宇光学
    '2388.HK',  # 中银香港
    '2628.HK',  # 中国人寿
    '3690.HK',  # 美团
    '3968.HK',  # 招商银行
    '3988.HK',  # 中国银行
    '6098.HK',  # 碧桂园服务
    '6862.HK',  # 海底捞
    '9618.HK',  # 京东
    '9633.HK',  # 农夫山泉
    '9888.HK',  # 百度
    '9988.HK',  # 阿里巴巴
    '9999.HK',  # 网易
]


if __name__ == '__main__':
    print("=" * 60)
    print("港股多因子选股策略回测")
    print("=" * 60)
    
    # 选择一部分流动性好的股票测试
    test_symbols = [
        '0700.HK',  # 腾讯
        '9988.HK',  # 阿里巴巴
        '1810.HK',  # 小米
        '3690.HK',  # 美团
        '9618.HK',  # 京东
        '1211.HK',  # 比亚迪
        '2318.HK',  # 中国平安
        '0388.HK',  # 港交所
        '0005.HK',  # 汇丰
        '1299.HK',  # 友邦保险
        '2382.HK',  # 舜宇光学
        '0175.HK',  # 吉利汽车
        '0941.HK',  # 中国移动
        '0883.HK',  # 中海油
        '1398.HK',  # 工商银行
        '3988.HK',  # 中国银行
        '0939.HK',  # 建设银行
        '2628.HK',  # 中国人寿
        '0857.HK',  # 中石油
        '0066.HK',  # 港铁
    ]
    
    # 获取数据
    print("\n📥 获取港股历史数据...")
    prices, volumes = fetch_hk_stocks(test_symbols, '2020-01-01', '2026-02-01')
    
    if len(prices) == 0:
        print("❌ 无法获取数据")
        exit(1)
        
    print(f"✅ 获取到 {len(prices.columns)} 只股票数据")
    print(f"   时间范围: {prices.index[0]} 至 {prices.index[-1]}")
    print(f"   股票: {list(prices.columns)}")
    
    # 创建策略
    strategy = HKMultiFactorStrategy(
        n_stocks=5,  # 选择前 5 只
        rebalance_freq='M',  # 每月再平衡
        factor_weights={
            'momentum_3m': 0.25,
            'momentum_6m': 0.20,
            'momentum_12m': 0.15,
            'volatility': 0.15,
            'rsi_score': 0.15,
            'volume_trend': 0.10
        }
    )
    
    # 运行回测
    print("\n🔄 运行回测...")
    backtester = HKBacktester(strategy, initial_capital=100000, transaction_cost=0.001)
    equity = backtester.run(prices, volumes)
    
    # 统计结果
    stats = backtester.get_stats()
    
    print("\n📊 回测结果:")
    print("-" * 40)
    print(f"总收益率:     {stats['total_return']:.2f}%")
    print(f"年化收益率:   {stats['annual_return']:.2f}%")
    print(f"最大回撤:     {stats['max_drawdown']:.2f}%")
    print(f"夏普比率:     {stats['sharpe_ratio']:.2f}")
    print(f"交易次数:     {stats['total_trades']}")
    print(f"最终资金:     ${stats['final_capital']:,.2f}")
    print("-" * 40)
    
    # 保存结果
    equity.to_csv('backtest_results/hk_equity_curve.csv')
    backtester.trades.to_csv('backtest_results/hk_trades.csv', index=False)
    print("\n💾 结果已保存到 backtest_results/")
