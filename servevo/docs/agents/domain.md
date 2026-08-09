# Domain Docs

How the engineering skills should consume the servevo domain documentation when exploring the codebase.

## Before exploring, read these

- **`AgentTeams/servevo/CONTEXT.md`** — servevo is a single-context increment; its glossary lives here.
- **`AgentTeams/servevo/docs/adr/`** — read ADRs that touch the area you're about to work in. Existing ADRs: ADR-001 (知识消费=R 方案), ADR-002 (copaw 原生接入).

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context increment (servevo):

```
AgentTeams/servevo/
├── CONTEXT.md                     ← glossary
├── docs/
│   └── adr/                       ← ADR-001, ADR-002, ... (编号 ADR-NNN-kebab-case)
└── servevo_eval/  servevo_rag/  ...   ← increment code
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-001 (知识消费方式) — but worth reopening because…_