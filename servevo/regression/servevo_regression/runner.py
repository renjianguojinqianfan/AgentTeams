"""回归执行器：用 RAG 主岗跑 50 题测试集，产出聚合指标。

确定性：同一知识包版本 + 固定测试集 → 可复现；dua 缺口题（知识未同步）应转人工/低分。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from servevo_eval.llm import create_chat_client, is_configured
from servevo_rag.graph import RagAgentGraph

from .compare import RunMetrics
from .testset import TestSet


@dataclass
class CaseResult:
    question_id: str
    category: str
    gap: bool
    answer: str
    sources: list[dict]
    resolved: bool      # 服务闭环：是否给出有效答案（有来源 + 非转人工兜底）
    qc_score: float     # 0-100 质检分（有来源=高，转人工=低）
    passed: bool        # 回归通过：答案命中预期要点（知识对错，独立于 resolved）
    missing_evidence: list[str]


@dataclass
class RunResult:
    metrics: RunMetrics
    cases: list[CaseResult] = field(default_factory=list)


# 同义词归一表（确定性：等价表述 -> 规范词），避免子串匹配因同义词漏判
_SYNONYMS = {
    "质保": "保修",
    "质保期": "保修期",
}

# 中文数字 -> 阿拉伯数字（用于"一年" vs "1年" 归一）
_CN_DIGITS = {
    "零": "0", "一": "1", "两": "2", "二": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
}

# 货币符号与 markdown 强调：真实 LLM 应答常带（"价格为 ¥1999" / "**¥1999**"），
# 测试集 kp 为纯文本要点不含这些，剥离后要点匹配更贴近真实措辞
_CURRENCY_CHARS = "¥￥$€元"
# 中文标点：真实应答常以"未使用、包装完好"等措辞给出，kp 为纯文本无标点
_CH_PUNCT = "、，。！？；：·「」『』（）【】"


def _normalize(text: str) -> str:
    """归一化文本以提升同义词/数字/空白匹配鲁棒性（确定性，可复现）。

    - 去空白（"1 年" -> "1年"）
    - 剥离货币符号与 markdown 强调（"¥1999" / "**¥1999**" -> "1999"）
    - 剥离中文标点（"未使用、包装完好" -> "未使用包装完好"）
    - 中文数字 -> 阿拉伯（"一年" -> "1年"）
    - 等价同义词 -> 规范词（"质保" -> "保修"）
    """
    t = text.replace(" ", "").replace("\u3000", "")
    for ch in _CURRENCY_CHARS:
        t = t.replace(ch, "")
    t = t.replace("**", "").replace("*", "")
    for ch in _CH_PUNCT:
        t = t.replace(ch, "")
    # 中文数字（仅单字）归一
    for cn, digit in _CN_DIGITS.items():
        t = t.replace(cn, digit)
    for src, dst in _SYNONYMS.items():
        t = t.replace(src, dst)
    return t


def _match_key_points(answer: str, key_points: list[str]) -> bool:
    """确定性要点匹配：kp 按空白拆 token，逐 token 在答案中命中即视为命中该点。

    真实 LLM 应答常以「价格为 ¥1999」「免费维修，运费由星辰承担」等自然措辞给出；
    多要点 kp（如「价格 1999」）若要求整串连续子串，会被 为/¥/** 等隔断而漏判。
    改为按空白拆 token 后逐 token 归一匹配（"价格"与"1999"都出现即命中），
    对真实措辞更鲁棒，仍确定性可复现。全部 token 命中（或要点为空时视为通过）→ 回归通过。
    """
    if not key_points:
        return bool(answer)
    norm_answer = _normalize(answer)
    return all(
        all(_normalize(tok) in norm_answer for tok in kp.split())
        for kp in key_points
    )


async def run_testset(
    testset: TestSet,
    kb_dir: str,
    knowledge_version: str,
    llm: object | None = None,
    top_k: int = 5,
) -> RunResult:
    """跑完整测试集，返回聚合指标 + 逐题结果。

    三个独立信号（确定性，不赌 LLM）：
    - resolved（解决）：有来源且非转人工兜底 → 服务闭环是否应答
    - passed（回归通过）：答案命中预期 key_points → 知识对错
    - qc_score：有来源=90，转人工=40（服务闭环质量）
    escalation_rate = 转人工兜底占比（独立于 resolved）。
    """
    graph = RagAgentGraph(kb_dir=kb_dir, llm=llm or _LlmAdapter())
    cases: list[CaseResult] = []
    resolved_count = 0
    escalated_count = 0
    passed_count = 0
    gap_detected = 0
    qc_sum = 0.0

    for q in testset.questions:
        result = await graph.query(q.question, top_k=top_k)
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        missing = result.get("missing_evidence", [])
        # resolved = 服务闭环：有来源 且 非转人工/确证兜底 且 非生成失败
        resolved = (
            bool(sources)
            and "转人工" not in answer
            and "确证" not in answer
            and "失败" not in answer
        )
        # passed = 知识对错：答案命中预期要点（独立信号）
        passed = _match_key_points(answer, q.key_points) if resolved else False
        qc_score = 90.0 if resolved else 40.0
        if resolved:
            resolved_count += 1
        else:
            escalated_count += 1
        if passed:
            passed_count += 1
        if q.gap and not resolved:
            gap_detected += 1
        qc_sum += qc_score
        cases.append(CaseResult(
            question_id=q.id, category=q.category, gap=q.gap,
            answer=answer, sources=sources, resolved=resolved,
            qc_score=qc_score, passed=passed, missing_evidence=missing,
        ))

    total = len(testset.questions)
    metrics = RunMetrics(
        knowledge_version=knowledge_version,
        resolution_rate=resolved_count / total if total else 0.0,
        escalation_rate=escalated_count / total if total else 0.0,
        qc_avg_score=round(qc_sum / total, 2) if total else 0.0,
        regression_pass_rate=passed_count / total if total else 0.0,
        gap_detected=gap_detected,
    )
    return RunResult(metrics=metrics, cases=cases)


class _LlmAdapter:
    """惰性 LLM 适配：无 key 时检索汇报模式（跑纯检索侧）。"""

    async def get_chat_client(self):
        if is_configured():
            return create_chat_client()
        return None