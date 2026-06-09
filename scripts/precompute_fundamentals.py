"""
预计算 Value-Select 6 层基本面评分 — 输出 JSON 注入策略配置。

使用方法:
    python scripts/precompute_fundamentals.py SYMBOLS_FILE [--output OUTPUT_JSON]

    SYMBOLS_FILE: 每行一个 A 股代码 (如 600519 或 000300) 的文本文件
    --output:     输出 JSON 路径 (默认打印到 stdout)

输出格式 (可直接存入 trading_config.fundamentals):
    {
      "CNStock:600519": {
        "passed": 5,
        "score": 55.0,
        "market_cap": 25000000000.0,
        "current_ratio": 2.5,
        "roe": 18.5,
        "free_cash_flow": 1200000000.0,
        "revenue_growth": 15.2,
        "eps": 3.2
      },
      ...
    }

通过 Agent API 注入策略配置:
    curl -X PUT "http://localhost:5000/api/agent/v1/strategy/update" \
      -H "Authorization: Bearer qd_agent_xxxx" \
      -H "Content-Type: application/json" \
      -d '{
        "strategy_id": 1,
        "trading_config": {
          "fundamentals": <paste JSON here>
        }
      }'
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ====================================================================
# 直接从东方财富 API 获取 A 股基本面数据 (无需 akShare/Flask)
# ====================================================================

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

_THRESHOLDS = {
    "market_cap": 10_000_000_000,  # 100亿
    "current_ratio": 1.5,
    "roe": 10.0,  # %
    "free_cash_flow": 0.0,  # > 0
    "revenue_growth": 10.0,  # %
    "eps": 0.5,
}


# ------------------------------------------------------------------
# 数据获取函数
# ------------------------------------------------------------------

def get_stock_code(symbol: str) -> Tuple[str, str]:
    """A股6位代码 → (东财SECUCODE格式, 腾讯代码)"""
    c = symbol.strip().zfill(6)
    suffix = ".SH" if c.startswith("6") else ".SZ"
    tencent = f"sh{c}" if c.startswith("6") else f"sz{c}"
    return f"{c}{suffix}", tencent


def fetch_quote_price(symbol: str) -> Optional[float]:
    """从腾讯获取当前股价 (第4个 ~ 分隔字段)"""
    _, tencent = get_stock_code(symbol)
    url = f"http://qt.gtimg.cn/q={tencent}"
    try:
        r = requests.get(url, timeout=10)
        r.encoding = "gbk"
        # 格式: v_sh600519="1~贵州茅台~600519~1256.00~..."
        # 股价是第4个 ~ 分隔字段 (index 3)
        parts = r.text.split("~")
        if len(parts) > 3:
            price_str = parts[3].strip('"')
            return float(price_str)
    except Exception:
        pass
    return None


def fetch_financial_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    从东方财富数据中心获取财报数据。
    使用 RPT_F10_FINANCE_MAINFINADATA 报表。
    """
    secid, _ = get_stock_code(symbol)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_F10_FINANCE_MAINFINADATA",
        "columns": (
            "SECUCODE,SECURITY_NAME_ABBR,REPORT_DATE,"
            "EPSJB,ROEJQ,TOTALOPERATEREVE,TOTALOPERATEREVETZ,"
            "KCFJCXSYJLR,JYXJLYYSR,LD,TOTAL_SHARE"
        ),
        "filter": f'(SECUCODE="{secid}")',
        "pageNumber": 1,
        "pageSize": 2,
        "sortTypes": -1,
        "sortColumns": "REPORT_DATE",
        "source": "WEB",
        "client": "WEB",
    }
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=15)
        j = r.json()
        if j.get("success") and j.get("result") and j["result"].get("data"):
            return j["result"]["data"]
    except Exception as e:
        logger.warning("[%s] 财报API请求失败: %s", symbol, e)
    return None


def _safe(v) -> Optional[float]:
    if v is None:
        return None
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------
# 评分逻辑 (与原 value_select 模块一致)
# ------------------------------------------------------------------

def six_layer_filter(fund: Dict[str, Any]) -> Tuple[int, List[str]]:
    """6 层过滤。"""
    passed = 0
    details: List[str] = []

    if _safe(fund.get("market_cap")) is not None and _safe(fund["market_cap"]) >= _THRESHOLDS["market_cap"]:
        passed += 1
        details.append("市值")

    cr = _safe(fund.get("current_ratio"))
    if cr is not None and cr >= _THRESHOLDS["current_ratio"]:
        passed += 1
        details.append("流动比率")

    roe = _safe(fund.get("roe"))
    if roe is not None and roe >= _THRESHOLDS["roe"]:
        passed += 1
        details.append("ROE")

    fcf = _safe(fund.get("free_cash_flow"))
    if fcf is not None and fcf > _THRESHOLDS["free_cash_flow"]:
        passed += 1
        details.append("FCF")

    rev = _safe(fund.get("revenue_growth"))
    if rev is not None and rev >= _THRESHOLDS["revenue_growth"]:
        passed += 1
        details.append("营收增长")

    eps = _safe(fund.get("eps"))
    if eps is not None and eps >= _THRESHOLDS["eps"]:
        passed += 1
        details.append("EPS")

    return passed, details


def composite_score(fund: Dict[str, Any], passed: int) -> float:
    """综合评分。"""
    score = float(passed) * 10.0
    roe = _safe(fund.get("roe"))
    if roe is not None and roe > 20:
        score += 5
    rev = _safe(fund.get("revenue_growth"))
    if rev is not None and rev > 20:
        score += 5
    fcf = _safe(fund.get("free_cash_flow"))
    eps = _safe(fund.get("eps"))
    if (fcf is not None and fcf > 0) and (eps is not None and eps >= 0.5):
        score += 5
    return score


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def load_symbol_list(path: str) -> List[str]:
    """从文本文件加载 A 股代码列表。"""
    symbols = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            code = line.strip()
            if code and code.isdigit():
                symbols.append(code)
    logger.info("从 %s 加载了 %d 个标的", path, len(symbols))
    return symbols


def fetch_and_score(symbols: List[str]) -> Dict[str, Any]:
    """批量获取基本面数据并执行 6 层过滤 + 评分。"""
    config_fund: Dict[str, Dict] = {}
    total_passed = 0

    for code in symbols:
        symbol_key = f"CNStock:{code}"

        # --- 获取财报数据 ---
        rows = fetch_financial_data(code)
        if not rows:
            logger.warning("[%s] 财报数据为空, 跳过", code)
            continue

        latest = rows[0]
        fund: Dict[str, Any] = {}

        # EPS
        eps = _safe(latest.get("EPSJB"))
        if eps is not None:
            fund["eps"] = eps

        # ROE (%)
        roe = _safe(latest.get("ROEJQ"))
        if roe is not None:
            fund["roe"] = roe

        # 营收增长 (%)
        rev_g = _safe(latest.get("TOTALOPERATEREVETZ"))
        if rev_g is not None:
            fund["revenue_growth"] = rev_g

        # 流动比率
        ld = _safe(latest.get("LD"))
        if ld is not None:
            fund["current_ratio"] = ld

        # 总股本 (用于计算市值)
        total_shares = _safe(latest.get("TOTAL_SHARE"))

        # 经营现金流: JYXJLYYSR 是每股经营现金流, * 总股本 = 总经营现金流
        cf_per_share = _safe(latest.get("JYXJLYYSR"))
        if cf_per_share is not None and total_shares is not None:
            fund["free_cash_flow"] = cf_per_share * total_shares

        # 市值: 股价 × 总股本
        price = fetch_quote_price(code)
        if price is not None and total_shares is not None:
            fund["market_cap"] = price * total_shares

        if len(fund) < 3:
            logger.warning("[%s] 数据不足 (%d 字段), 跳过", code, len(fund))
            continue

        # --- 6 层过滤 ---
        passed, details = six_layer_filter(fund)

        entry = {
            "passed": passed,
            "score": round(composite_score(fund, passed), 2) if passed >= 4 else 0,
            "market_cap": _safe(fund.get("market_cap")),
            "current_ratio": _safe(fund.get("current_ratio")),
            "roe": _safe(fund.get("roe")),
            "free_cash_flow": _safe(fund.get("free_cash_flow")),
            "revenue_growth": _safe(fund.get("revenue_growth")),
            "eps": _safe(fund.get("eps")),
        }

        if passed >= 4:
            total_passed += 1
            logger.info("[%s] ✅ 通过 %d/6 层 (%s), 评分 %.1f",
                        code, passed, " | ".join(details), entry["score"])
        else:
            logger.info("[%s] ❌ 仅通过 %d/6 层 (%s), 未达标",
                        code, passed, " | ".join(details) or "无")

        config_fund[symbol_key] = entry

        # 避免请求过快被限
        time.sleep(0.3)

    logger.info("总计 %d 个标的中 %d 个通过筛选", len(symbols), total_passed)
    return config_fund


def main():
    import argparse

    parser = argparse.ArgumentParser(description="预计算 Value-Select 基本面评分")
    parser.add_argument("symbols_file", help="股票代码文件 (每行一个代码)")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径 (默认 stdout)")
    args = parser.parse_args()

    symbols = load_symbol_list(args.symbols_file)
    if not symbols:
        logger.error("未加载到任何标的, 退出")
        sys.exit(1)

    result = fetch_and_score(symbols)
    output = json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        logger.info("结果已写入 %s", args.output)
    else:
        print(output)


if __name__ == "__main__":
    main()
