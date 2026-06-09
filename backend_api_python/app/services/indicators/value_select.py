"""
Value-Select 选股 — 6 层基本面过滤 + 评分。

过滤条件：
  1. 大市值   ≥ 100 亿
  2. 流动比率 ≥ 1.5
  3. ROE      ≥ 10%
  4. FCF      >  0
  5. 营收增长 ≥ 10%
  6. EPS      ≥ 0.5

该模块的量价 proxy 部分可内联至 Cross-Sectional Indicator 代码中；
基本面批量 fetch / 评分部分供外部预计算脚本调用。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------- 阈值常量 ----------
THRESHOLDS: Dict[str, float] = {
    "market_cap": 10_000_000_000,  # 100 亿
    "current_ratio": 1.5,
    "roe": 10.0,  # %
    "free_cash_flow": 0.0,  # > 0
    "revenue_growth": 10.0,  # %
    "eps": 0.5,
}


def six_layer_filter(fundamentals: Dict[str, Any]) -> Tuple[int, List[str]]:
    """
    对单只标的执行 6 层基本面过滤。

    Parameters
    ----------
    fundamentals : dict
        包含市值 / 流动比率 / ROE / FCF / 营收增长 / EPS 等字段的字典。

    Returns
    -------
    passed_count : int
        通过层数（0-6）。
    passed_details : list[str]
        通过的层名称列表。
    """
    passed = 0
    details: List[str] = []

    # 层 1: 大市值
    mcap = _safe_float(fundamentals.get("market_cap"))
    if mcap is not None and mcap >= THRESHOLDS["market_cap"]:
        passed += 1
        details.append("市值")

    # 层 2: 流动比率
    cr = _safe_float(fundamentals.get("current_ratio"))
    if cr is not None and cr >= THRESHOLDS["current_ratio"]:
        passed += 1
        details.append("流动比率")

    # 层 3: ROE
    roe = _safe_float(fundamentals.get("roe"))
    if roe is not None and roe >= THRESHOLDS["roe"]:
        passed += 1
        details.append("ROE")

    # 层 4: FCF > 0
    fcf = _safe_float(fundamentals.get("free_cash_flow"))
    if fcf is not None and fcf > THRESHOLDS["free_cash_flow"]:
        passed += 1
        details.append("FCF")

    # 层 5: 营收增长
    rev_g = _safe_float(fundamentals.get("revenue_growth"))
    if rev_g is not None and rev_g >= THRESHOLDS["revenue_growth"]:
        passed += 1
        details.append("营收增长")

    # 层 6: EPS
    eps = _safe_float(fundamentals.get("eps"))
    if eps is not None and eps >= THRESHOLDS["eps"]:
        passed += 1
        details.append("EPS")

    return passed, details


def composite_score(fundamentals: Dict[str, Any], passed_count: int) -> float:
    """
    基于通过层数 + 因子强度生成综合评分。

    评分公式:   基础分 = passed_count × 10
                加分项 = ROE > 20% 加 5 分
                         营收增长 > 20% 加 5 分
                         同时通过 FCF 且 EPS 加 5 分（质量溢价）
    """
    score = float(passed_count) * 10.0

    roe = _safe_float(fundamentals.get("roe"))
    if roe is not None and roe > 20:
        score += 5

    rev_g = _safe_float(fundamentals.get("revenue_growth"))
    if rev_g is not None and rev_g > 20:
        score += 5

    fcf = _safe_float(fundamentals.get("free_cash_flow"))
    eps = _safe_float(fundamentals.get("eps"))
    if (fcf is not None and fcf > 0) and (eps is not None and eps >= 0.5):
        score += 5  # 质量溢价

    return score


def format_for_config(
    symbol_scores: Dict[str, Tuple[int, float]],
    fundamentals_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    将选股结果格式化为可注入 trading_config.fundamentals 的 JSON。

    Parameters
    ----------
    symbol_scores : (symbol -> (passed_count, composite_score))
    fundamentals_dict : 原始基本面数据字典

    Returns
    -------
    config_fund : dict
        结构: { symbol: { passed, score, market_cap, roe, ... } }
    """
    config: Dict[str, Any] = {}
    for sym, (passed, sc) in symbol_scores.items():
        fd = fundamentals_dict.get(sym, {})
        config[sym] = {
            "passed": passed,
            "score": round(sc, 2),
            "market_cap": _safe_float(fd.get("market_cap")),
            "current_ratio": _safe_float(fd.get("current_ratio")),
            "roe": _safe_float(fd.get("roe")),
            "free_cash_flow": _safe_float(fd.get("free_cash_flow")),
            "revenue_growth": _safe_float(fd.get("revenue_growth")),
            "eps": _safe_float(fd.get("eps")),
        }
    return config


def _safe_float(v: Any) -> Optional[float]:
    """安全转换为 float，None / NaN / inf 均返回 None。"""
    if v is None:
        return None
    try:
        fv = float(v)
        if __import__("math").isnan(fv) or __import__("math").isinf(fv):
            return None
        return fv
    except (TypeError, ValueError):
        return None
