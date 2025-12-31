# VeriRag Technical & Sales Overview

This document provides a high-level explanation of the VeriRag pipeline, designed for **Extreme Accuracy**, **Enterprise Privacy**, and **Maximum Cost-Efficiency**.

---

## 🚀 The Query Journey

### 1. Speed & Cost-Efficiency Layer (Multi-Tier Caching)
Before any AI "thinking" occurs, the system attempts to resolve the query instantly:
*   **Literal Cache**: An exact character-match lookup in the database. Common greetings ("Hello", "Who are you?") are answered in **< 5ms** with **Zero API cost**.
*   **Semantic Cache**: If the text isn't identical, we check for **meaning**. If a similar question has been answered before for the same client, the system returns that answer instantly, bypassing the entire AI pipeline.

### 2. The "Smart Brain" (Intent & Routing)
If the query is new, the system classifies the user's intent:
*   **Intent Classification**: Distinguishes between document lookups (RAG), human handoffs, or small talk.
*   **Smart Model Routing**: The system calculates a **Complexity Score (1-10)**.
    *   **Simple Queries**: Routes to fast, ultra-cheap "Flash" models.
    *   **Complex Reasoning**: Automatically upgrades to high-power models only when multi-step logic or deep analysis is required. *This saves up to 80% on operational LLM costs.*

### 3. Extreme Retrieval (3-Way Hybrid Search)
We ensure the AI has the best possible context using a unique fusion strategy:
*   **HyDE (Query Expansion)**: The AI generates a "hypothetical answer" to better understand what document chunks it should look for.
*   **Semantic Vector Search**: Finds information based on **conceptual meaning**, overcoming language barriers and differing terminology.
*   **Full-Text Search (Keyword)**: Finds exact matches for **technical terms, part numbers, or specific names**.
*   **RRF (Reciprocal Rank Fusion)**: Mathematically merges these results to present the absolute most relevant facts to the generator.

### 4. Precision Filtering (Reranking)
Retrieved document chunks are cross-referenced against the original query one last time. This "quality check" ensures that only the most truthful and relevant snippets reach the final generation phase.

### 5. Grounded Generation
The final response is generated using a "Closed-Domain" instruction set: **"Only answer based on the provided documents. No guessing. No hallucinations."** The output is delivered in the user's language, backed by proven data.

---

## 💎 Why choose VeriRag?

| Feature | Benefit |
| :--- | :--- |
| **Tenant Isolation** | Data is compartmentalized by `tenant_id`. Client A's data never touches Client B's bot. |
| **Hallucination Prevention** | Responses are strictly grounded in your unique knowledge base. |
| **Auditability** | Every answer can be traced back to its specific source document. |
| **Cost Control** | Tiered caching and smart model routing ensure you never pay for "over-thinking" or repeated questions. |
| **Multi-Modal Ready** | Process text, images, and audio seamlessly in the same pipeline. |
