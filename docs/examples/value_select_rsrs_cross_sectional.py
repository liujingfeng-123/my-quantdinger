# ============================================================
# Value-Select 选股 + RSRS 择时 — 全自动截面策略
# ============================================================
#
# 使用方法:
# 1. 在 QuantDinger 中创建截面策略
# 2. symbol_list 第一个标的填写大盘指数 (如 CNStock:000300)
#    后续标的填写候选股票池
# 3. 将此代码粘贴到 Indicator 代码编辑器中
#
# 策略逻辑:
#   Step 1 — RSRS 判断大盘多空
#     ✓ z_score > +0.7 → 多头 (执行选股)
#     ✓ z_score < -0.7 → 空头 (全仓观望)
#     ✓ 之间 → 中性 (维持现有持仓, 不新开仓)
#
#   Step 2 — 多头时用量价代理因子选股 (全自动, 无需外部数据)
#     因子: 动量 40% + 波动稳定性 30% + 流动性 30%
#
#   Step 3 — 截面引擎每月调仓
#     ✓ 排序 → 选 Top N → 生成买卖信号
#
# ============================================================

import numpy as np
# 注: pd 和 np 已在沙箱环境中预加载, 无需额外 import

# ============================================================
# 配置参数 (可在 QuantDinger UI 中通过 params 覆盖)
# ============================================================
RSRS_WINDOW = 18          # RSRS 回归窗口
RSRS_THRESHOLD = 0.7      # 信号触发阈值
RSRS_LOOKBACK = 120       # z-score 标准化回溯期 (至少 60)
MIN_PASSED_LAYERS = 4     # 基本面至少通过几层才入选

# ============================================================
# 辅助函数: RSRS 计算
# ============================================================
def calc_rsrs(high, low, n=18, lookback=120):
    """
    计算 RSRS 标准化斜率和信号。

    参数:
        high, low: np.ndarray, 最高价/最低价序列
        n: int, 回归窗口
        lookback: int, 滚动标准化回溯期

    返回:
        z_score: float, 最新标准化斜率
        signal: int, 1=多头, -1=空头, 0=中性
    """
    T = len(high)
    if T < n + 1:
        return 0.0, 0

    # --- 计算最新斜率 ---
    x = low[-n:]
    y = high[-n:]
    xm = x.mean()
    ym = y.mean()
    beta = np.sum((x - xm) * (y - ym)) / max(np.sum((x - xm)**2), 1e-12)

    # --- 计算历史斜率序列用于标准化 ---
    all_betas = []
    for i in range(max(n, T - lookback), T):
        xx = low[i-n:i]
        yy = high[i-n:i]
        if len(xx) == n:
            bx = xx - xx.mean()
            by = yy - yy.mean()
            b = np.sum(bx * by) / max(np.sum(bx**2), 1e-12)
            all_betas.append(b)

    if len(all_betas) < n:
        return 0.0, 0

    mean_beta = np.mean(all_betas)
    std_beta = np.std(all_betas, ddof=1)
    if std_beta < 1e-12:
        return 0.0, 0

    z_score = (beta - mean_beta) / std_beta

    # 信号判断
    if z_score > RSRS_THRESHOLD:
        signal = 1
    elif z_score < -RSRS_THRESHOLD:
        signal = -1
    else:
        signal = 0

    return z_score, signal


# ============================================================
# 辅助函数: 量价代理评分 (Phase 1 — 无需基本面数据)
# ============================================================
def kline_quality_score(df):
    """
    使用 K 线数据计算"质量代理评分"。

    思路: 低波动 + 趋势向上 + 流动性充足 = 基本面良好 proxy
    当无法获取真实基本面数据时使用。

    因子:
      - 动量: 最近 20 日收益率 (越高越好)
      - 波动稳定性: 60日收益率标准差倒数 (越低波动越好)
      - 流动性: 20日均量 × 均价 (越高越好)
    """
    if df is None or len(df) < 60:
        return 0.0

    close = df['close'].values
    volume = df['volume'].values if 'volume' in df.columns else None

    # 动量因子 (20日)
    momentum = (close[-1] / close[-20] - 1) * 100

    # 波动因子 (60日收益率标准差, 取负值)
    returns = np.diff(close[-61:]) / close[-61:-1]
    volatility = np.std(returns) * 100
    # 取倒数并 capped, 波动越小分越高
    vol_score = min(10.0 / max(volatility, 0.1), 10.0)

    # 流动性因子
    liq_score = 0.0
    if volume is not None and len(volume) >= 20:
        avg_vol = np.mean(volume[-20:])
        avg_price = np.mean(close[-20:])
        turnover = avg_vol * avg_price
        # 归一化: 假设 1 亿以上为满分
        liq_score = min(turnover / 1e8, 5.0)

    # 综合评分
    score = momentum * 0.4 + vol_score * 0.3 + liq_score * 0.3
    return max(score, 0.0)

# ============================================================
# 主逻辑: 遍历标的, 填充 scores
# ============================================================

# --- Step 0: 识别指数与股票 ---
# 约定: symbol_list 第一个为大盘指数 (用于 RSRS)
index_symbol = symbols[0] if symbols else None
stock_symbols = symbols[1:] if len(symbols) > 1 else []

# --- Step 1: RSRS 择时 ---
market_regime = 0  # 默认中性
index_z_score = 0.0

if index_symbol and index_symbol in data:
    idx_df = data[index_symbol]
    if idx_df is not None and len(idx_df) > RSRS_WINDOW + 10:
        idx_high = idx_df['high'].values
        idx_low = idx_df['low'].values
        index_z_score, market_regime = calc_rsrs(
            idx_high, idx_low,
            n=RSRS_WINDOW,
            lookback=RSRS_LOOKBACK,
        )

# 可选: 将指数也传入 scores 以便在 UI 中查看
# (截面引擎不会买入, 因为指数通常不在 stock_symbols 中)
scores[index_symbol] = 0.0

# --- Step 2: 根据多空信号决定选股 ---
if market_regime == -1:
    # ====== 空头: 全仓观望, 所有标的分 = 0 ======
    for sym in stock_symbols:
        scores[sym] = 0.0

elif market_regime == 0:
    # ====== 中性: 维持现状, 不新开仓 ======
    # 分数设为负值, 截面引擎会平仓但不开新仓
    for sym in stock_symbols:
        scores[sym] = -1.0

else:
    # ====== 多头: 全自动量价代理选股 ======
    # 无需外部基本面数据, 完全基于 K 线计算
    for sym in stock_symbols:
        df = data.get(sym)
        if df is None or len(df) < RSRS_WINDOW:
            scores[sym] = 0.0
            continue

        proxy_score = kline_quality_score(df)
        scores[sym] = proxy_score


# ============================================================
# 可选: 输出诊断信息 (仅在实盘日志中可见)
# ============================================================
# logger 在沙箱中不可用, 使用 print 仅用于 IDE 测试
# print(f"[RSRS] z_score={index_z_score:.2f}, regime={market_regime}")
# print(f"[选股] 多头标的: {sum(1 for v in scores.values() if v > 0)} 只")
