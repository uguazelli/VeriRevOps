<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template placeholder I -> I. Tenant-Isolated Automation
- Template placeholder II -> II. Immediate Webhook Acknowledgement
- Template placeholder III -> III. Provider Boundaries and Module Ownership
- Template placeholder IV -> IV. Grounded AI and Human Handoff
- Template placeholder V -> V. Privacy, Secrets, and Observability
Added sections:
- Operational Constraints
- Development Workflow and Quality Gates
Removed sections:
- Placeholder template sections
Templates requiring updates:
- .specify/templates/plan-template.md: updated
- .specify/templates/spec-template.md: updated
- .specify/templates/tasks-template.md: updated
Follow-up TODOs:
- Update README.md to describe the broader automation engine scope, not only RAG.
-->

# VeriRevOps Engine Constitution

## Core Principles

### I. Tenant-Isolated Automation
Every feature MUST operate inside an explicit tenant context. Tenant identity, service
configuration, credentials, quotas, contact mappings, chat message tracking, document
retrieval, and automation state MUST NOT leak across tenants.

Tenant service settings MUST come from the tenant configuration layer or database-backed
service records. Code MUST NOT hard-code tenant IDs, Chatwoot account IDs, API keys, CRM
URLs, or provider credentials except in local throwaway tests that are never committed.

Rationale: the engine is a multi-tenant automation system. A correct answer for one tenant
can be a data leak or destructive action for another.

### II. Immediate Webhook Acknowledgement
Inbound Chatwoot webhooks MUST be acknowledged quickly before long-running work starts.
LLM calls, RAG retrieval, media download, transcription, image analysis, CRM sync, and
conversation summarization MUST run after the acknowledgement path.

Webhook processing MUST be idempotent where duplicate delivery is possible. Features that
send Chatwoot messages, update conversation status, summarize conversations, or sync CRM
records MUST define how duplicate events are detected or tolerated.

Rationale: Chatwoot treats slow webhook responses as bot failures. The engine protects
the user conversation even when external systems are slow.

### III. Provider Boundaries and Module Ownership
Domain behavior MUST live in feature modules. Routers MUST stay thin, services MUST
orchestrate clear steps, and external systems MUST be accessed through named clients or
providers.

Internal code MUST call Python functions directly instead of calling this application's own
HTTP endpoints. HTTP calls are reserved for external systems such as Chatwoot, CRMs, and
LLM or media providers.

Provider-specific logic MUST be isolated behind interfaces or provider modules. Adding a
new CRM, chat channel, or LLM provider MUST NOT require rewriting unrelated workflows.

Rationale: the engine integrates multiple external systems. Clear boundaries keep each
automation understandable, testable, and replaceable.

### IV. Grounded AI and Human Handoff
AI behavior MUST be constrained by explicit prompts, parsed outputs, and deterministic
branching. Classifier outputs MUST be validated before choosing actions such as RAG,
chitchat, CRM automation, summarization, or human handoff.

RAG responses MUST use tenant-scoped retrieval context and MUST answer in the user's
language. When retrieved context is insufficient for a factual answer, the assistant MUST
avoid inventing facts and route to an honest fallback or handoff path.

Requests for a human, strong frustration, urgent complaints, or uncertain automation paths
MUST support a handoff behavior. Handoff responses SHOULD include a concise conversation
summary when relevant context exists.

Rationale: the engine acts in live conversations. AI output needs guardrails before it
affects customers, operators, CRM records, or support workflows.

### V. Privacy, Secrets, and Observability
Secrets MUST NOT be committed, logged, or returned in API responses. Logs MUST avoid full
webhook payload dumps when they contain personal data, access tokens, message content,
phone numbers, emails, or CRM records. Prefer concise structured logs with tenant slug or
ID, conversation ID, contact ID, provider name, action, and result.

Failures MUST be logged with enough context to debug the workflow without exposing
sensitive content. External API failures MUST preserve the failing provider and action in
logs. Background or queued jobs MUST be observable through durable logs and retry-safe
status where practical.

Rationale: this engine handles customer conversations, contact data, tenant credentials,
and CRM identifiers. Debuggability cannot come at the cost of privacy or secret exposure.

## Operational Constraints

The engine is a FastAPI application using asynchronous workflows where practical. Long
network-bound work SHOULD use async clients and MUST NOT block the webhook acknowledgement
path.

PostgreSQL is the durable store for tenants, service configuration, contact mappings, chat
message tracking, documents, and vector-backed RAG data. Contact sync MUST use
`contact_mappings` as the durable relationship between Chatwoot contact IDs and external
CRM contact IDs.

LLM access MUST go through shared provider selection infrastructure. RAG, direct LLM,
classification, chitchat, handoff, transcription, and image analysis MUST keep provider
selection explicit and configurable.

External integrations MUST be represented by focused clients or providers. Chatwoot API
details belong in the Chatwoot module. CRM-specific details belong in CRM provider modules.
Cross-system decisions, such as contact synchronization, belong in their own domain module.

## Development Workflow and Quality Gates

Feature plans MUST identify affected tenants, external systems, data entities, idempotency
rules, privacy-sensitive fields, and failure behavior before implementation.

Tests SHOULD scale with risk. Pure payload parsing, classification parsing, mapping
selection, and provider payload construction SHOULD have unit tests. Database mapping
behavior SHOULD have service or integration tests. Live Chatwoot, CRM, and LLM behavior MAY
be verified with manual or mocked integration checks when real credentials are unavailable.

Before a feature is considered complete, the implementation MUST pass syntax/import checks
for touched modules and MUST include a clear verification note. Any untested external API
behavior MUST be called out explicitly.

Refactors MUST preserve existing behavior unless a specification says otherwise. Moving a
feature into modules MUST keep imports compatible or update all callers in the same change.

## Governance

This constitution is the primary engineering standard for the VeriRevOps engine. When a
feature specification, implementation plan, task list, or local convention conflicts with
this constitution, the constitution wins.

Amendments MUST update this file, include a Sync Impact Report, and review dependent
templates or runtime guidance for consistency. Material principle changes require a MINOR
or MAJOR version bump. Clarifications and wording-only improvements require a PATCH bump.

Versioning follows semantic versioning:
- MAJOR: governance or principle changes that invalidate existing compliant designs.
- MINOR: new principles, new required sections, or materially expanded obligations.
- PATCH: clarifications, examples, typo fixes, and non-semantic wording changes.

Every feature plan MUST include a Constitution Check. Every implementation review MUST
verify tenant isolation, webhook acknowledgement behavior, provider boundaries, grounded AI
behavior, privacy, and observability for the changed surface.

**Version**: 1.0.0 | **Ratified**: 2026-05-14 | **Last Amended**: 2026-05-14
