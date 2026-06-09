"""
预计算 Value-Select 6 层基本面评分 — 输出 JSON 注入策略配置。

使用方法:
    python scripts/precompute_fundamentals.py SYMBOLS_FILE [--output OUTPUT_JSON]

    SYMBOLS_FILE: 每行一个 A 股代码 (如 600519 或 000300) 的文本文件
    --output:     输出 JSON 路径 (默认打印到 stdout)

输出格式 (可直接存入 trading_config.fundamentals):
    {
      "symbol": {
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
import os
import sys
from typing import Any, Dict, List

# 确保能找到 backend_api_python 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_api_python"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def load_symbol_list(path: str) -> List[str]:
    """从文本文件加载 A 股代码列表 (每行一个代码)。"""
    symbols = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            code = line.strip()
            if code and code.isdigit():
                symbols.append(code)
    logger.info("从 %s 加载了 %d 个标的", path, len(symbols))
    return symbols


def to_tencent_code(code: str) -> str:
    """将 6 位A股代码转为腾讯格式 (SH600519 / SZ000001)。"""
    c = code.strip().zfill(6)
    return f"SH{c}" if c.startswith("6") else f"SZ{c}"


def fetch_and_score(symbols: List[str]) -> Dict[str, Any]:
    """
    批量获取基本面数据并执行 6 层过滤 + 评分。

    使用 AkShare (东方财富) 和 Twelve Data 两种数据源,
    优先 Twelve Data (境外服务器友好), fallback 到 AkShare Eastmoney。
    """
    from app.data_sources.cn_hk_fundamentals import (
        fetch_cn_fundamental_akshare,
        fetch_cn_financial_indicators,
        fetch_twelvedata_fundamental,
    )
    from app.services.indicators.value_select import (
        six_layer_filter,
        composite_score,
        format_for_config,
    )

    fundamentals_dict: Dict[str, Dict] = {}
    symbol_scores: Dict[str, tuple] = {}

    for code in symbols:
        tc = to_tencent_code(code)
        symbol_key = f"CNStock:{code}"

        # --- 获取基本面数据 ---
        fund: Dict[str, Any] = {}

        # Tier 1: Twelve Data (境外稳定, 需要 API Key)
        td = fetch_twelvedata_fundamental(tc, is_hk=False)
        if td.get("source") == "twelvedata":
            fund.update(td)
            logger.debug("[%s] 使用 Twelve Data 数据", code)

        # Tier 2: AkShare Eastmoney (国内稳定, 境外可能失败)
        ak = fetch_cn_fundamental_akshare(tc)
        if ak.get("source") == "akshare_em":
            # 补充 TD 可能缺失的字段
            for key in ("pe_ratio", "pb_ratio", "ps_ratio", "peg"):
                if key not in fund and key in ak and ak[key] is not None:
                    fund[key] = ak[key]
            logger.debug("[%s] 补充 AkShare 数据", code)

        # Tier 3: 详细财务指标 (流动比率 / FCF / 营收增长 / EPS)
        fin = fetch_cn_financial_indicators(tc)
        fund.update(fin)

        if len(fund) < 3:
            logger.warning("[%s] 基本面数据不足 (%d 字段), 跳过", code, len(fund))
            continue

        # --- 6 层过滤 ---
        passed, details = six_layer_filter(fund)
        if passed >= 4:
            score = composite_score(fund, passed)
            symbol_scores[symbol_key] = (passed, score)
            logger.info("[%s] ✅ 通过 %d/6 层 (%s), 评分 %.1f",
                        code, passed, " | ".join(details), score)
        else:
            logger.info("[%s] ❌ 仅通过 %d/6 层 (%s), 未达标",
                        code, passed, " | ".join(details) or "无")

        fundamentals_dict[symbol_key] = fund

    # --- 格式化为配置 JSON ---
    config_fund = format_for_config(symbol_scores, fundamentals_dict)
    logger.info("总计 %d 个标的中 %d 个通过筛选", len(symbols), len(symbol_scores))
    return config_fund


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="预计算 Value-Select 基本面评分",
    )
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
