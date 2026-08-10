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


def _match_key_points(answer: str, key_points: list[str]) -> bool:
    """确定性要点匹配：任一预期要点出现在答案中即视为命中该点。

    全部要点命中（或要点为空时视为通过）→ 回归通过。不赌 LLM，可复现。
    """
    if not key_points:
        return bool(answer)
    return all(kp in answer for kp in key_points)


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