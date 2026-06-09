"""
RSRS (Resistance Support Relative Strength) 指标 — 大盘择时。

原理：
  对过去 N 天的最高价(Y)与最低价(X)做 OLS 线性回归 y = α + β·x，
  取标准化后的 β 斜率作为多空判断依据。

  - β > 0.7σ → 多头（支撑强于阻力）
  - β < -0.7σ → 空头（阻力强于支撑）

Reference: 光大证券《基于RSRS的行业配置与择时策略》
"""

from __future__ import annotations

from typing import Optional, Tuple, Union

import numpy as np


def calc_rsrs_slope(
    high: np.ndarray,
    low: np.ndarray,
    n: int = 18,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    计算 RSRS 原始斜率及滚动 z-score 标准化斜率。

    Parameters
    ----------
    high : np.ndarray
        最高价序列，形状 (T,)。
    low : np.ndarray
        最低价序列，形状 (T,)。
    n : int
        回归窗口（默认 18 个交易日）。

    Returns
    -------
    raw_slopes : np.ndarray
        每个时间点的 OLS 回归斜率 β，前 n-1 个为 NaN。
    z_scores : np.ndarray
        标准化斜率 z-score，前 n-1 个为 0。
    """
    T = len(high)
    if T < n:
        raise ValueError(f"数据长度 {T} 小于窗口 {n}")

    raw_slopes = np.full(T, np.nan)

    # OLS: β = Σ((xᵢ - x̄)(yᵢ - ȳ)) / Σ((xᵢ - x̄)²)
    for i in range(n, T):
        x = low[i - n : i]
        y = high[i - n : i]
        xm = x.mean()
        ym = y.mean()
        dx = x - xm
        dy = y - ym
        beta = np.dot(dx, dy) / np.dot(dx, dx)
        raw_slopes[i] = beta

    # 滚动标准化: z = (β - rolling_mean(β)) / rolling_std(β)
    # 用与回归相同的窗口 n 做滚动统计
    valid = ~np.isnan(raw_slopes)
    z_scores = np.zeros(T)

    for i in range(2 * n, T):
        window = raw_slopes[i - n : i]
        if np.all(np.isfinite(window)):
            mu = np.mean(window)
            std = np.std(window, ddof=1)
            if std > 1e-12:
                z_scores[i] = (raw_slopes[i] - mu) / std

    return raw_slopes, z_scores


def calc_rsrs_signal(
    z_scores: np.ndarray,
    threshold: float = 0.7,
) -> np.ndarray:
    """
    将 z-score 转为离散信号。

    Parameters
    ----------
    z_scores : np.ndarray
        标准化斜率序列。
    threshold : float
        信号触发阈值（默认 0.7）。

    Returns
    -------
    signals : np.ndarray
        1 = 多头（z > +threshold）
        0 = 中性
       -1 = 空头（z < -threshold）
    """
    signals = np.zeros_like(z_scores, dtype=int)
    signals[z_scores > threshold] = 1
    signals[z_scores < -threshold] = -1
    return signals


def calc_right_biased_rsrs(
    high: np.ndarray,
    low: np.ndarray,
    n: int = 18,
    m: int = 5,
    threshold: float = 0.7,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    右偏 RSRS 修正版。

    在原始 RSRS 基础上，用未来 m 日的收益对斜率做二次回归，
    得到「修正斜率」，用于排除斜率虽高但未来收益不佳的情况。

    Parameters
    ----------
    high, low : np.ndarray
    n : int
        初始回归窗口。
    m : int
        未来收益窗口（交易日）。
    threshold : float
        信号触发阈值。

    Returns
    -------
    raw_slopes, z_scores, signals : np.ndarray
        与 calc_rsrs_slope/signal 返回值含义一致，
        但 z_scores 已基于修正斜率重新计算。
    """
    T = len(high)
    if T < n + m:
        raise ValueError(f"数据长度 {T} < n + m = {n + m}")

    # 1. 计算原始斜率
    raw_slopes, _ = calc_rsrs_slope(high, low, n)

    # 2. 未来 m 日收益率
    future_ret = np.full(T, np.nan)
    if T > m:
        future_ret[: T - m] = (high[m:] / low[: T - m]) - 1.0

    # 3. 二次回归: 用过去 L 期的 (β, ret) 做修正
    L = 300  # 回溯长度
    corrected_z = np.zeros(T)

    for i in range(n + m, T):
        start = max(n, i - L)
        betas = raw_slopes[start:i]
        rets = future_ret[start:i]
        valid_mask = np.isfinite(betas) & np.isfinite(rets)
        betas_v = betas[valid_mask]
        rets_v = rets[valid_mask]
        if len(betas_v) < 30:
            continue

        # γ = cov(β, ret) / var(β)
        gamma = np.cov(betas_v, rets_v, ddof=1)[0, 1] / np.var(betas_v, ddof=1)
        # 修正斜率 = β - γ * ret 的期望部分
        # 简化: 直接对 beta 做 gamma 缩放
        adjusted_beta = raw_slopes[i] * (1 + gamma) if np.isfinite(gamma) else raw_slopes[i]

        mu = np.mean(betas_v)
        std = np.std(betas_v, ddof=1)
        if std > 1e-12:
            corrected_z[i] = (adjusted_beta - mu) / std

    signals = calc_rsrs_signal(corrected_z, threshold)
    return raw_slopes, corrected_z, signals
