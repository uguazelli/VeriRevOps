# Feature Specification: RAG Module Organization

**Feature Branch**: `002-rag-module-organization`

**Created**: 2026-05-15

**Status**: Draft

**Input**: User description: "Move and unify RAG-related code into a dedicated RAG module for better organization while preserving existing behavior."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Centralize RAG Behavior (Priority: P1)

As a developer maintaining the engine, I want RAG behavior organized in one dedicated
module so answer generation, document ingestion, retrieval, reranking, and embedding
logic are easier to understand and change.

**Why this priority**: RAG is a core domain of the engine. Keeping it spread across
generic services makes future changes harder and increases the risk of inconsistent
behavior between API, web dashboard, and Chatwoot flows.

**Independent Test**: Review the project structure and verify that RAG-specific workflows
are exposed from a dedicated RAG module while existing RAG behavior still works from each
current caller.

**Acceptance Scenarios**:

1. **Given** a developer needs to change answer generation, **When** they inspect the RAG module, **Then** they can find the high-level answer workflow and its supporting retrieval behavior in clearly named files.
2. **Given** a developer needs to change document ingestion, **When** they inspect the RAG module, **Then** they can find ingestion, parsing, chunking, embedding, and storage behavior in the RAG module.

---

### User Story 2 - Preserve Existing RAG Consumers (Priority: P2)

As an operator, I want the existing RAG API, web dashboard, and Chatwoot responses to keep
working after the refactor so organization changes do not break runtime behavior.

**Why this priority**: This feature is an organization refactor. It should not change the
business behavior users and integrations already rely on.

**Independent Test**: Run the existing RAG API flow, web dashboard query/upload flow, and
Chatwoot retrieval response path against the refactored code and verify equivalent
behavior.

**Acceptance Scenarios**:

1. **Given** an API client calls the existing RAG endpoint, **When** the refactor is complete, **Then** the endpoint still returns an answer using tenant-scoped retrieved context.
2. **Given** the web dashboard uploads a document for ingestion, **When** the refactor is complete, **Then** the document is still parsed, chunked, embedded, and stored.
3. **Given** a Chatwoot message is classified as retrieval, **When** the refactor is complete, **Then** Chatwoot still receives an answer generated through the RAG workflow.

---

### User Story 3 - Make Future RAG Changes Safer (Priority: P3)

As a developer, I want clear boundaries around RAG code so future improvements can be made
without touching unrelated Chatwoot, CRM, tenant, or generic helper code.

**Why this priority**: RAG will likely evolve with better prompts, metadata filters,
retrieval strategies, ingestion formats, and provider behavior. Clear ownership reduces
future blast radius.

**Independent Test**: Identify one future RAG-only change, such as retrieval filter
improvements, and verify it can be planned inside the RAG module without changing
unrelated modules except for explicit call sites.

**Acceptance Scenarios**:

1. **Given** a future retrieval improvement is needed, **When** a developer reviews the RAG module, **Then** the expected files to change are clear and unrelated modules do not own RAG internals.
2. **Given** a future ingestion improvement is needed, **When** a developer reviews the RAG module, **Then** the ingestion workflow has a clear place to evolve.

---

### Edge Cases

- Existing imports from current callers must either be updated or preserved through a compatibility layer.
- RAG prompts must remain discoverable after the move.
- Shared infrastructure such as database sessions, tenant models, logging helpers, and LLM provider selection must remain in shared/core locations.
- Non-RAG services such as transcription, image analysis, media downloading, Chatwoot webhook orchestration, and CRM sync must not be moved into the RAG module.
- The refactor must not change tenant scoping for documents, retrieval, ingestion, or answer generation.
- The refactor must not delete or rename API behavior unless a compatibility plan is included.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated RAG module that owns RAG answer generation, document ingestion, document retrieval, and RAG-specific helper behavior.
- **FR-002**: System MUST preserve existing behavior for the RAG API endpoint.
- **FR-003**: System MUST preserve existing behavior for web dashboard document ingestion and RAG querying.
- **FR-004**: System MUST preserve existing behavior for Chatwoot retrieval responses.
- **FR-005**: System MUST keep tenant-scoped document retrieval and answer generation unchanged.
- **FR-006**: System MUST keep document ingestion behavior equivalent, including parsing, chunking, embedding, metadata handling, and storage.
- **FR-007**: System MUST keep reranking behavior equivalent where reranking is currently enabled.
- **FR-008**: System MUST keep shared infrastructure outside the RAG module when it is used by other domains.
- **FR-009**: System SHOULD keep temporary compatibility imports when needed so existing callers can migrate safely.
- **FR-010**: System MUST remove duplicate or obsolete RAG code paths after all callers use the new module or compatibility layer.
- **FR-011**: System MUST include verification that the refactor did not change public RAG behavior.
- **FR-012**: System MUST keep logs useful for ingestion, retrieval, reranking, and answer-generation failures without logging secrets.

### Integration and Data Scope *(include if feature touches external systems or tenant data)*

- **Tenant Context**: Tenant ID continues to scope document ingestion, document retrieval, and answer generation.
- **External Systems**: LLM provider and embedding provider remain external dependencies used by the RAG workflow.
- **Sensitive Data**: Documents, retrieved content, user questions, generated answers, API keys, and embedding provider credentials.
- **Idempotency Rule**: This refactor does not introduce new external events; existing ingestion and query behavior should remain unchanged.
- **Handoff/Fallback Rule**: If RAG cannot retrieve context or generate an answer, existing fallback behavior should be preserved.

### Key Entities *(include if feature involves data)*

- **RAG Module**: The dedicated domain module that owns RAG workflows and supporting RAG-specific code.
- **Document**: Tenant-scoped stored content used for retrieval and answer generation.
- **Retrieval Result**: A candidate document chunk or parent document used as answer context.
- **Ingestion Job**: A document processing workflow that parses input, creates chunks, embeds content, and stores it.
- **RAG Answer**: The final response generated from retrieved tenant-scoped context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can identify the RAG answer-generation entry point inside the new RAG module in under one minute.
- **SC-002**: A developer can identify the document ingestion workflow inside the new RAG module in under one minute.
- **SC-003**: Existing RAG API behavior remains equivalent for a representative tenant query.
- **SC-004**: Existing web dashboard document upload and query behavior remains equivalent after the refactor.
- **SC-005**: Existing Chatwoot retrieval response behavior remains equivalent after the refactor.
- **SC-006**: No unrelated Chatwoot, CRM, tenant, transcription, image analysis, or media download behavior is changed by the refactor.

## Assumptions

- This feature is an organization refactor, not a functional RAG redesign.
- The first implementation should prefer safe moves and compatibility wrappers over large behavior changes.
- `core` remains the place for shared infrastructure such as database access, models, provider factories, and logging helpers.
- RAG-specific prompts may remain in the shared prompt file during the first refactor if moving them would add unnecessary risk.
- Follow-up features can later improve retrieval quality, ingestion strategy, metadata filtering, or prompt design.
