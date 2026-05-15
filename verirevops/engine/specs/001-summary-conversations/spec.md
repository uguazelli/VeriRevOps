# Feature Specification: Conversation Summary on Chatwoot Resolve

**Feature Branch**: `001-summary-conversations`

**Created**: 2026-05-14

**Status**: Draft

**Input**: User description: "Expose an endpoint called by Chatwoot when conversation status changes to resolved. Retrieve the last summarized message marker from chat_messages, load tenant settings, fetch Chatwoot messages after that marker, summarize the conversation with the LLM, send the summary to EspoCRM as a stream note on Contact if one exists or Lead otherwise, then update chat_messages with the latest summarized message id."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Summarize a Resolved Conversation (Priority: P1)

When a Chatwoot conversation is resolved, the engine summarizes the new conversation
messages since the last summary and sends that summary to the CRM so the sales or support
team has the conversation context in the customer record.

**Why this priority**: This is the primary business value. Resolved conversations should
leave useful context in the CRM without a human manually copying chat history.

**Independent Test**: Send a resolved-conversation notification for a tenant with a known
Chatwoot conversation and a known CRM target. Verify that one CRM stream note is created
with a summary of only the messages after the stored marker.

**Acceptance Scenarios**:

1. **Given** a tenant has Chatwoot and EspoCRM configured and `chat_messages` stores a previous `message_id`, **When** Chatwoot notifies the engine that the conversation is resolved, **Then** the engine fetches only messages after that `message_id`, summarizes them, and sends one summary note to the CRM.
2. **Given** the resolved notification is for a conversation with no new messages after the stored marker, **When** the engine processes the notification, **Then** no CRM summary note is created and the stored marker is not changed.

---

### User Story 2 - Attach the Summary to the Right CRM Record (Priority: P2)

As an operator, I want the summary attached to the most relevant CRM record so the next
person opening the customer or lead record can continue with the right context.

**Why this priority**: A useful summary in the wrong CRM record creates confusion and can
be worse than no summary.

**Independent Test**: Process one resolved conversation where the Chatwoot contact maps to
an existing CRM Contact, and one where only a CRM Lead is available. Verify the first
summary is attached to the Contact stream and the second is attached to the Lead stream.

**Acceptance Scenarios**:

1. **Given** the Chatwoot contact is associated with an existing CRM Contact, **When** the conversation summary is sent to the CRM, **Then** the stream note is attached to the Contact.
2. **Given** the Chatwoot contact is not associated with a CRM Contact but a CRM Lead is available, **When** the conversation summary is sent to the CRM, **Then** the stream note is attached to the Lead.

---

### User Story 3 - Prevent Duplicate Summaries (Priority: P3)

As an operator, I want repeated resolved notifications to be safe so the CRM does not get
duplicate notes for the same conversation range.

**Why this priority**: Webhooks can be retried or sent more than once. The engine must be
safe under duplicate delivery.

**Independent Test**: Send the same resolved notification twice. Verify the second run
does not create another CRM note when no newer Chatwoot messages exist.

**Acceptance Scenarios**:

1. **Given** a resolved conversation has already been summarized through message `N`, **When** the same resolved notification is processed again, **Then** no duplicate CRM note is created for messages up to `N`.
2. **Given** a CRM write fails during summary processing, **When** the same notification is retried, **Then** the system can retry the same message range because the marker was not advanced.

---

### Edge Cases

- If the tenant slug is unknown, the summary process is rejected and no external systems are called.
- If the tenant has no Chatwoot or EspoCRM service configuration, the process fails safely and does not update the summary marker.
- If there is no existing `chat_messages` marker for the conversation, the system treats the last summarized message as `0` and summarizes available conversation messages.
- If Chatwoot returns no messages after the marker, no CRM note is created.
- If the LLM summary is empty or invalid, no CRM note is created and the marker is not advanced.
- If no CRM Contact or Lead can be confidently identified, no CRM note is created and the marker is not advanced.
- If the CRM note creation fails, the marker is not advanced.
- If the resolved webhook is duplicated, the stored marker prevents duplicate notes for the same message range.
- If non-resolved conversation status notifications call this endpoint, the system ignores them without creating a summary.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a tenant-scoped integration endpoint that accepts Chatwoot conversation status notifications.
- **FR-002**: System MUST process summary generation only for notifications indicating the conversation is resolved.
- **FR-003**: System MUST load tenant settings using the tenant slug before calling Chatwoot, the LLM, or the CRM.
- **FR-004**: System MUST retrieve the last summarized `message_id` for the tenant, Chatwoot account, and Chatwoot conversation from `chat_messages`.
- **FR-005**: System MUST fetch Chatwoot conversation messages after the last summarized `message_id`.
- **FR-006**: System MUST summarize only the newly fetched messages, not the entire conversation history already summarized.
- **FR-007**: System MUST create a concise summary containing the customer's request, relevant context, actions or answers provided, outcome, and any follow-up items.
- **FR-008**: System MUST attach the summary as an EspoCRM stream note to a Contact when a Contact exists for the Chatwoot contact.
- **FR-009**: System MUST attach the summary as an EspoCRM stream note to a Lead when no Contact exists but a Lead is available.
- **FR-010**: System MUST NOT create a CRM note when there are no new Chatwoot messages after the stored marker.
- **FR-011**: System MUST update `chat_messages.message_id` to the latest summarized Chatwoot message id only after the CRM note is successfully created.
- **FR-012**: System MUST NOT update the stored marker when Chatwoot fetch, LLM summary generation, CRM target resolution, or CRM note creation fails.
- **FR-013**: System MUST tolerate duplicate resolved notifications without creating duplicate CRM notes for the same message range.
- **FR-014**: System MUST log summary attempts, skips, and failures with tenant, conversation, provider, and action identifiers without logging secrets or full raw payloads.
- **FR-015**: System MUST support EspoCRM as the first CRM target while keeping the behavior compatible with additional CRM providers later.

### Integration and Data Scope *(include if feature touches external systems or tenant data)*

- **Tenant Context**: The tenant slug from the request scopes all service settings, account IDs, credentials, message markers, and CRM writes.
- **External Systems**: Chatwoot for resolved notifications and message retrieval; LLM provider for summary generation; EspoCRM for stream note creation.
- **Sensitive Data**: Chat message content, contact names, emails, phone numbers, Chatwoot account IDs, CRM record IDs, API keys, and generated summaries.
- **Idempotency Rule**: The stored `chat_messages.message_id` is advanced only after successful CRM note creation. Repeated notifications with no newer messages become no-ops.
- **Handoff/Fallback Rule**: If a safe CRM target cannot be found or the summary cannot be produced, the feature records the failure and does not create a note or advance the marker.

### Key Entities *(include if feature involves data)*

- **Chat Message Marker**: Tracks the last Chatwoot message id summarized for a tenant, Chatwoot account, and Chatwoot conversation.
- **Resolved Conversation Notification**: The Chatwoot event that indicates a conversation has moved to resolved status and should be considered for summarization.
- **Conversation Summary**: A generated summary of newly fetched conversation messages, intended for CRM stream context.
- **CRM Target Record**: The EspoCRM Contact or Lead that should receive the conversation summary stream note.
- **CRM Stream Note**: The record created in EspoCRM containing the conversation summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For conversations with new messages and a valid CRM target, one and only one CRM stream note is created per summarized message range.
- **SC-002**: Reprocessing the same resolved notification after a successful summary creates zero duplicate CRM notes.
- **SC-003**: The summary marker is advanced only after a CRM note is successfully created in 100% of tested success and failure cases.
- **SC-004**: Generated summaries include the customer request, context, outcome, and follow-up items when those details are present in the conversation.
- **SC-005**: Failed or skipped summary attempts are traceable through logs without exposing API keys, full raw webhook payloads, or unnecessary personal data.

## Assumptions

- Chatwoot will call this feature when a conversation status changes to resolved.
- The request includes enough information to identify the tenant, Chatwoot account, Chatwoot conversation, status, and Chatwoot contact.
- If no `chat_messages` row exists for the conversation, summarizing from message id `0` is acceptable for the first run.
- EspoCRM is the only CRM required for the first version.
- The CRM has enough contact or lead information to attach the summary to exactly one target record.
- Additional CRM providers will follow the same high-level behavior but may use different provider-specific APIs.
