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
    resolved: bool     # 是否给出有效答案（非转人工兜底）
    qc_score: float    # 0-100 质检分（有来源=高，转人工/无来源=低）
    missing_evidence: list[str]


@dataclass
class RunResult:
    metrics: RunMetrics
    cases: list[CaseResult] = field(default_factory=list)


async def run_testset(
    testset: TestSet,
    kb_dir: str,
    knowledge_version: str,
    llm: object | None = None,
    top_k: int = 5,
) -> RunResult:
    """跑完整测试集，返回聚合指标 + 逐题结果。

    qc_score 规则（确定性，不赌 LLM）：
    - 有来源且非转人工 → 90（答对基线，质检分高）
    - 转为人工兜底（无来源）→ 40（未解决）
    resolved = 有来源（非转人工兜底）。
    缺口题：v1 知识未同步 → 无来源 → resolved=False → 计入 gap_detected。
    """
    graph = RagAgentGraph(kb_dir=kb_dir, llm=llm or _LlmAdapter())
    cases: list[CaseResult] = []
    resolved_count = 0
    escalated_count = 0
    gap_detected = 0
    qc_sum = 0.0

    for q in testset.questions:
        result = await graph.query(q.question, top_k=top_k)
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        missing = result.get("missing_evidence", [])
        # resolved = 有来源 且 非转人工/确证兜底 且 非生成失败
        resolved = (
            bool(sources)
            and "转人工" not in answer
            and "确证" not in answer
            and "失败" not in answer
        )
        qc_score = 90.0 if resolved else 40.0
        if resolved:
            resolved_count += 1
        else:
            escalated_count += 1
        if q.gap and not resolved:
            gap_detected += 1
        qc_sum += qc_score
        cases.append(CaseResult(
            question_id=q.id, category=q.category, gap=q.gap,
            answer=answer, sources=sources, resolved=resolved,
            qc_score=qc_score, missing_evidence=missing,
        ))

    total = len(testset.questions)
    metrics = RunMetrics(
        knowledge_version=knowledge_version,
        resolution_rate=resolved_count / total if total else 0.0,
        escalation_rate=escalated_count / total if total else 0.0,
        qc_avg_score=round(qc_sum / total, 2) if total else 0.0,
        regression_pass_rate=resolved_count / total if total else 0.0,
        gap_detected=gap_detected,
    )
    return RunResult(metrics=metrics, cases=cases)


class _LlmAdapter:
    """惰性 LLM 适配：无 key 时检索汇报模式（跑纯检索侧）。"""

    async def get_chat_client(self):
        if is_configured():
            return create_chat_client()
        return None