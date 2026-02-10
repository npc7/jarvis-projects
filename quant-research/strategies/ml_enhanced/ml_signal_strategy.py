"""
阶段 2: 机器学习增强策略
========================
时间: 2026-02-09 20:30+ (阶段2开始)

实现内容:
1. XGBoost 分类模型预测价格方向
2. 特征工程：技术指标、波动率、动量
3. 将 ML 信号与传统策略结合
4. 回测 ML 增强版策略
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import warnings
from datetime import datetime
import json
import pickle
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

warnings.filterwarnings('ignore')


@dataclass
class MLBacktestResult:
    """ML回测结果"""
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
    model_accuracy: float
    model_precision: float
    final_capital: float


class FeatureEngineer:
    """特征工程"""
    
    def __init__(self):
        self.feature_names = []
    
    def calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有特征"""
        df = df.copy()
        
        # 基础收益
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # ========== 价格相关特征 ==========
        # 均线
        for period in [5, 10, 20, 30, 50, 100]:
            df[f'sma_{period}'] = df['close'].rolling(period).mean()
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
            df[f'price_vs_sma_{period}'] = (df['close'] - df[f'sma_{period}']) / df[f'sma_{period}']
        
        # 均线斜率
        df['sma_20_slope'] = df['sma_20'].pct_change(5)
        df['sma_50_slope'] = df['sma_50'].pct_change(10)
        
        # ========== 动量特征 ==========
        for period in [5, 10, 14, 20, 30, 60]:
            df[f'momentum_{period}'] = df['close'].pct_change(period)
        
        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            df[f'roc_{period}'] = (df['close'] - df['close'].shift(period)) / df['close'].shift(period)
        
        # ========== RSI ==========
        for period in [7, 14, 21]:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / (loss + 1e-10)
            df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
        
        # ========== MACD ==========
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['macd_hist_diff'] = df['macd_hist'].diff()
        
        # ========== 布林带 ==========
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # ========== ATR 和波动率 ==========
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        
        for period in [7, 14, 20]:
            df[f'atr_{period}'] = df['tr'].rolling(period).mean()
            df[f'atr_{period}_pct'] = df[f'atr_{period}'] / df['close']
        
        # 历史波动率
        for period in [10, 20, 30, 60]:
            df[f'volatility_{period}'] = df['returns'].rolling(period).std() * np.sqrt(252)
        
        # 波动率比率
        df['vol_ratio_10_30'] = df['volatility_10'] / (df['volatility_30'] + 1e-10)
        
        # ========== ADX ==========
        period = 14
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
        
        df['di_plus'] = 100 * df['dm_plus'].rolling(period).mean() / (df['atr_14'] + 1e-10)
        df['di_minus'] = 100 * df['dm_minus'].rolling(period).mean() / (df['atr_14'] + 1e-10)
        df['dx'] = 100 * abs(df['di_plus'] - df['di_minus']) / (df['di_plus'] + df['di_minus'] + 1e-10)
        df['adx'] = df['dx'].rolling(period).mean()
        df['adx_diff'] = df['adx'].diff()
        
        # ========== 成交量特征 ==========
        if 'volume' in df.columns:
            df['volume_sma_10'] = df['volume'].rolling(10).mean()
            df['volume_sma_20'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / (df['volume_sma_20'] + 1e-10)
            df['volume_change'] = df['volume'].pct_change()
            
            # 价量关系
            df['price_volume_trend'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * df['volume']
            df['obv'] = (np.sign(df['returns']) * df['volume']).cumsum()
            df['obv_sma'] = df['obv'].rolling(20).mean()
            df['obv_vs_sma'] = (df['obv'] - df['obv_sma']) / (abs(df['obv_sma']) + 1e-10)
        
        # ========== 高低价特征 ==========
        for period in [10, 20, 50]:
            df[f'high_{period}'] = df['high'].rolling(period).max()
            df[f'low_{period}'] = df['low'].rolling(period).min()
            df[f'donchian_position_{period}'] = (df['close'] - df[f'low_{period}']) / \
                                                 (df[f'high_{period}'] - df[f'low_{period}'] + 1e-10)
        
        # ========== 时间特征 ==========
        df['day_of_week'] = df.index.dayofweek
        df['month'] = df.index.month
        
        # ========== 滞后特征 ==========
        for lag in [1, 2, 3, 5]:
            df[f'returns_lag_{lag}'] = df['returns'].shift(lag)
            df[f'momentum_20_lag_{lag}'] = df['momentum_20'].shift(lag)
        
        # ========== 目标变量 ==========
        # 未来 N 天收益方向
        df['target_1d'] = (df['close'].shift(-1) > df['close']).astype(int)
        df['target_5d'] = (df['close'].shift(-5) > df['close']).astype(int)
        df['target_return_5d'] = df['close'].pct_change(5).shift(-5)
        
        # 收集特征名
        exclude_cols = ['open', 'high', 'low', 'close', 'adj close', 'volume', 
                        'target_1d', 'target_5d', 'target_return_5d',
                        'tr', 'dm_plus', 'dm_minus', 'obv']
        
        self.feature_names = [c for c in df.columns if c not in exclude_cols 
                              and not c.startswith(('sma_', 'ema_', 'high_', 'low_', 'bb_upper', 'bb_lower', 'bb_middle', 'bb_std'))]
        
        return df


class MLSignalModel:
    """机器学习信号模型"""
    
    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.1,
        min_samples_split: int = 10,
        subsample: float = 0.8,
    ):
        self.model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            min_samples_split=min_samples_split,
            subsample=subsample,
            random_state=42,
            verbose=0
        )
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_fitted = False
        
    def prepare_data(self, df: pd.DataFrame, feature_names: List[str], target: str) -> Tuple[np.ndarray, np.ndarray]:
        """准备训练数据"""
        # 选择特征
        valid_features = [f for f in feature_names if f in df.columns]
        
        X = df[valid_features].copy()
        y = df[target].copy()
        
        # 删除缺失值
        mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[mask]
        y = y[mask]
        
        self.feature_names = valid_features
        
        return X.values, y.values
    
    def train(self, X: np.ndarray, y: np.ndarray, train_ratio: float = 0.7) -> Dict:
        """训练模型"""
        split_idx = int(len(X) * train_ratio)
        
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # 标准化
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 训练
        self.model.fit(X_train_scaled, y_train)
        
        self.is_fitted = True
        
        # 评估
        y_pred = self.model.predict(X_test_scaled)
        y_prob = self.model.predict_proba(X_test_scaled)[:, 1]
        
        accuracy = np.mean(y_pred == y_test)
        
        # 计算精确率
        true_positives = np.sum((y_pred == 1) & (y_test == 1))
        predicted_positives = np.sum(y_pred == 1)
        precision = true_positives / predicted_positives if predicted_positives > 0 else 0
        
        # 特征重要性
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'top_features': top_features
        }
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """预测"""
        if not self.is_fitted:
            return np.zeros(len(X)), np.ones(len(X)) * 0.5
            
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)[:, 1]
        
        return predictions, probabilities


class MLEnhancedStrategy:
    """机器学习增强策略"""
    
    def __init__(
        self,
        # ML 参数
        ml_threshold: float = 0.55,  # ML 信号阈值
        use_ml_signal: bool = True,
        
        # 传统策略参数
        momentum_period: int = 30,
        target_volatility: float = 0.12,
        stop_loss_pct: float = 0.05,
        trailing_stop_pct: float = 0.08,
        
        # 仓位
        min_position: float = 0.2,
        max_position: float = 1.0,
    ):
        self.ml_threshold = ml_threshold
        self.use_ml_signal = use_ml_signal
        self.momentum_period = momentum_period
        self.target_volatility = target_volatility
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.min_position = min_position
        self.max_position = max_position


def backtest_ml_strategy(
    df: pd.DataFrame,
    strategy: MLEnhancedStrategy,
    feature_engineer: FeatureEngineer,
    ml_model: MLSignalModel,
    initial_capital: float = 100000
) -> Tuple[pd.DataFrame, MLBacktestResult]:
    """运行 ML 增强策略回测"""
    
    # 计算特征
    df = feature_engineer.calculate_features(df)
    
    # 准备 ML 数据
    X, y = ml_model.prepare_data(df.dropna(), feature_engineer.feature_names, 'target_5d')
    
    # 初始化
    capital = initial_capital
    position = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    trailing_stop = 0.0
    
    equity_curve = []
    trades = []
    
    # 滚动训练
    train_size = 500  # 至少 500 天数据训练
    retrain_interval = 60  # 每 60 天重新训练
    
    start_idx = max(100, strategy.momentum_period) + 10
    
    # 确保有足够数据
    valid_indices = df.dropna().index
    df_clean = df.loc[valid_indices]
    
    if len(df_clean) < train_size + 100:
        print("数据不足，无法训练模型")
        return pd.DataFrame(), None
    
    # 初始训练
    train_end_idx = train_size
    X_train = X[:train_end_idx]
    y_train = y[:train_end_idx]
    train_metrics = ml_model.train(X_train, y_train)
    
    print(f"\n📊 初始模型训练完成:")
    print(f"   准确率: {train_metrics['accuracy']*100:.1f}%")
    print(f"   精确率: {train_metrics['precision']*100:.1f}%")
    print(f"   Top 5 特征: {[f[0] for f in train_metrics['top_features'][:5]]}")
    
    last_train_idx = train_end_idx
    
    for i in range(train_end_idx, len(X)):
        # 获取对应的日期
        date_idx = valid_indices[i]
        row = df.loc[date_idx]
        current_price = row['close']
        
        # 定期重训练
        if i - last_train_idx >= retrain_interval:
            X_train = X[:i]
            y_train = y[:i]
            ml_model.train(X_train, y_train)
            last_train_idx = i
        
        # 计算当前权益
        if position != 0:
            if position > 0:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = -(current_price - entry_price) / entry_price
            current_equity = capital * (1 + abs(position) * pnl_pct)
        else:
            current_equity = capital
        
        # 更新移动止损
        if position > 0 and current_price > highest_since_entry:
            highest_since_entry = current_price
            trailing_stop = highest_since_entry * (1 - strategy.trailing_stop_pct)
        
        # 检查止损
        if position != 0:
            trigger_stop = False
            stop_price = 0
            
            if position > 0:
                initial_stop = entry_price * (1 - strategy.stop_loss_pct)
                effective_stop = max(initial_stop, trailing_stop)
                
                if current_price < effective_stop:
                    trigger_stop = True
                    stop_price = effective_stop
                    pnl_pct = (stop_price - entry_price) / entry_price
            else:
                initial_stop = entry_price * (1 + strategy.stop_loss_pct)
                if current_price > initial_stop:
                    trigger_stop = True
                    stop_price = initial_stop
                    pnl_pct = -(stop_price - entry_price) / entry_price
            
            if trigger_stop:
                realized_pnl = capital * abs(position) * pnl_pct
                capital += realized_pnl
                
                trades.append({
                    'date': date_idx,
                    'action': 'stop_loss',
                    'price': stop_price,
                    'position': position,
                    'pnl': realized_pnl,
                    'pnl_pct': pnl_pct * 100
                })
                
                position = 0
                entry_price = 0
                highest_since_entry = 0
                trailing_stop = 0
        
        # 获取 ML 信号
        X_current = X[i:i+1]
        ml_pred, ml_prob = ml_model.predict(X_current)
        
        # 传统动量信号
        momentum = row.get('momentum_30', 0)
        if pd.isna(momentum):
            momentum = 0
            
        volatility = row.get('volatility_20', 0.3)
        if pd.isna(volatility) or volatility <= 0:
            volatility = 0.3
        
        # 综合信号
        signal = 0
        
        if strategy.use_ml_signal:
            # ML 信号为主
            if ml_prob[0] > strategy.ml_threshold and momentum > 0:
                signal = 1
            elif ml_prob[0] < (1 - strategy.ml_threshold) and momentum < 0:
                signal = -1
        else:
            # 纯动量信号
            if momentum > 0:
                signal = 1
            elif momentum < 0:
                signal = -1
        
        # 执行交易
        if position == 0 and signal != 0:
            # 计算仓位
            raw_position = strategy.target_volatility / volatility
            target_position = np.clip(raw_position, strategy.min_position, strategy.max_position)
            
            position = target_position * signal
            entry_price = current_price
            highest_since_entry = current_price
            trailing_stop = current_price * (1 - strategy.trailing_stop_pct) if position > 0 else 0
            
            trades.append({
                'date': date_idx,
                'action': 'open',
                'price': current_price,
                'position': position,
                'ml_prob': float(ml_prob[0]),
                'pnl': 0,
                'pnl_pct': 0
            })
        
        # 反向信号时平仓换向
        elif position != 0 and signal != 0 and np.sign(signal) != np.sign(position):
            # 平仓
            if position > 0:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = -(current_price - entry_price) / entry_price
            
            realized_pnl = capital * abs(position) * pnl_pct
            capital += realized_pnl
            
            trades.append({
                'date': date_idx,
                'action': 'close',
                'price': current_price,
                'position': position,
                'pnl': realized_pnl,
                'pnl_pct': pnl_pct * 100
            })
            
            # 开新仓
            raw_position = strategy.target_volatility / volatility
            target_position = np.clip(raw_position, strategy.min_position, strategy.max_position)
            
            position = target_position * signal
            entry_price = current_price
            highest_since_entry = current_price
            trailing_stop = current_price * (1 - strategy.trailing_stop_pct) if position > 0 else 0
            
            trades.append({
                'date': date_idx,
                'action': 'open',
                'price': current_price,
                'position': position,
                'ml_prob': float(ml_prob[0]),
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
        
        equity_curve.append({
            'date': date_idx,
            'equity': current_equity,
            'position': position,
            'close': current_price,
            'ml_prob': float(ml_prob[0])
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
    
    result = MLBacktestResult(
        strategy_name='ML_Enhanced',
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
        model_accuracy=round(train_metrics['accuracy'] * 100, 2),
        model_precision=round(train_metrics['precision'] * 100, 2),
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


def main():
    """主函数"""
    print("=" * 70)
    print("🤖 机器学习增强策略回测")
    print("=" * 70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取数据
    print("\n📥 获取 BTC 历史数据...")
    df = fetch_btc_data('2018-01-01', '2026-02-01')  # 更长的历史数据
    
    if len(df) == 0:
        print("❌ 无法获取数据")
        return
        
    print(f"✅ 获取到 {len(df)} 条数据 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")
    
    # 初始化
    feature_engineer = FeatureEngineer()
    ml_model = MLSignalModel()
    
    # 1. ML 增强策略
    print("\n" + "-" * 70)
    print("🧪 测试 1: ML 增强策略")
    print("-" * 70)
    
    strategy = MLEnhancedStrategy(
        ml_threshold=0.55,
        use_ml_signal=True,
        momentum_period=30,
        target_volatility=0.12,
        stop_loss_pct=0.05,
        trailing_stop_pct=0.08
    )
    
    equity, result = backtest_ml_strategy(df, strategy, feature_engineer, ml_model)
    
    if result:
        print(f"\n📊 ML 增强策略结果:")
        print("-" * 50)
        print(f"年化收益率:   {result.annual_return:.2f}%")
        print(f"最大回撤:     {result.max_drawdown:.2f}%")
        print(f"夏普比率:     {result.sharpe_ratio:.3f}")
        print(f"Sortino比率:  {result.sortino_ratio:.3f}")
        print(f"Calmar比率:   {result.calmar_ratio:.3f}")
        print(f"胜率:         {result.win_rate:.1f}%")
        print(f"盈亏比:       {result.profit_factor:.2f}")
        print(f"交易次数:     {result.total_trades}")
        print(f"模型准确率:   {result.model_accuracy:.1f}%")
        print(f"模型精确率:   {result.model_precision:.1f}%")
        print("-" * 50)
        
        # 保存结果
        equity.to_csv('backtest_results/ml_results/ml_enhanced_equity.csv')
    
    # 2. 纯动量策略 (对照)
    print("\n" + "-" * 70)
    print("🧪 测试 2: 纯动量策略 (对照组)")
    print("-" * 70)
    
    # 重新初始化模型
    ml_model_baseline = MLSignalModel()
    
    strategy_baseline = MLEnhancedStrategy(
        use_ml_signal=False,  # 不使用 ML
        momentum_period=30,
        target_volatility=0.12,
        stop_loss_pct=0.05,
        trailing_stop_pct=0.08
    )
    
    equity_baseline, result_baseline = backtest_ml_strategy(
        df, strategy_baseline, feature_engineer, ml_model_baseline
    )
    
    if result_baseline:
        print(f"\n📊 纯动量策略结果:")
        print("-" * 50)
        print(f"年化收益率:   {result_baseline.annual_return:.2f}%")
        print(f"最大回撤:     {result_baseline.max_drawdown:.2f}%")
        print(f"夏普比率:     {result_baseline.sharpe_ratio:.3f}")
        print(f"交易次数:     {result_baseline.total_trades}")
        print("-" * 50)
        
        equity_baseline.to_csv('backtest_results/ml_results/baseline_equity.csv')
    
    # 3. 对比
    if result and result_baseline:
        print("\n" + "=" * 70)
        print("📈 ML vs 基线对比:")
        print("=" * 70)
        print(f"年化收益: ML {result.annual_return:.1f}% vs 基线 {result_baseline.annual_return:.1f}% (差异 {result.annual_return - result_baseline.annual_return:+.1f}%)")
        print(f"最大回撤: ML {result.max_drawdown:.1f}% vs 基线 {result_baseline.max_drawdown:.1f}%")
        print(f"夏普比率: ML {result.sharpe_ratio:.2f} vs 基线 {result_baseline.sharpe_ratio:.2f}")
        
        ml_improved = result.sharpe_ratio > result_baseline.sharpe_ratio
        print(f"\n结论: ML {'提升' if ml_improved else '未能提升'}策略表现")
    
    # 保存对比结果
    comparison = {
        'ml_enhanced': asdict(result) if result else None,
        'baseline': asdict(result_baseline) if result_baseline else None,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('backtest_results/ml_results/comparison.json', 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"\n💾 结果已保存到 backtest_results/ml_results/")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
