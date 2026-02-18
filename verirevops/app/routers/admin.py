from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_postgres_connection
from app.models import Tenants, TenantCreate, Subscriptions, SubscriptionCreate, ChatSessions, ChatSessionCreate, ChatMessages
from app.core.queries import (
    GET_ALL_TENANTS, CREATE_TENANT, UPDATE_TENANT, DELETE_TENANT, GET_TENANT_NAME_BY_ID,
    GET_ALL_SUBSCRIPTIONS, CREATE_SUBSCRIPTION, UPDATE_SUBSCRIPTION, DELETE_SUBSCRIPTION,
    GET_ALL_CHAT_SESSIONS, CREATE_CHAT_SESSION, UPDATE_CHAT_SESSION, DELETE_CHAT_SESSION,
    GET_CHAT_MESSAGES_BASE
)

router = APIRouter(
    prefix="/api",
    tags=["admin"]
)

# --- Tenants CRUD ---
@router.get("/tenants", response_model=List[Tenants])
async def get_tenants():
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(GET_ALL_TENANTS)
        rows = cur.fetchall()
        tenants = []
        for row in rows:
            tenants.append(Tenants(id=row[0], name=row[1], slug=row[2], url=row[3], is_active=row[4]))
        return tenants
    finally:
        cur.close()
        conn.close()

@router.post("/tenants", response_model=Tenants)
async def create_tenant(tenant: TenantCreate):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            CREATE_TENANT,
            (tenant.name, tenant.slug, tenant.url, tenant.is_active)
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return Tenants(id=new_id, **tenant.model_dump())
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.put("/tenants/{tenant_id}", response_model=Tenants)
async def update_tenant(tenant_id: int, tenant: TenantCreate):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            UPDATE_TENANT,
            (tenant.name, tenant.slug, tenant.url, tenant.is_active, tenant_id)
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return Tenants(id=tenant_id, **tenant.model_dump())
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: int):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(DELETE_TENANT, (tenant_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return {"message": "Tenant deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- Subscriptions CRUD ---
@router.get("/subscriptions", response_model=List[Subscriptions])
async def get_subscriptions():
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(GET_ALL_SUBSCRIPTIONS)
        rows = cur.fetchall()
        subscriptions = []
        for row in rows:
            subscriptions.append(Subscriptions(
                id=row[0], tenant_id=row[1], quota_limit=row[2], usage_count=row[3],
                start_date=row[4], end_date=row[5], tenant_name=row[6]
            ))
        return subscriptions
    finally:
        cur.close()
        conn.close()

@router.post("/subscriptions", response_model=Subscriptions)
async def create_subscription(sub: SubscriptionCreate):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            CREATE_SUBSCRIPTION,
            (sub.tenant_id, sub.quota_limit, sub.usage_count, sub.start_date, sub.end_date)
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        # Fetch tenant name for response
        cur.execute(GET_TENANT_NAME_BY_ID, (sub.tenant_id,))
        tenant_name = cur.fetchone()[0]

        return Subscriptions(id=new_id, tenant_name=tenant_name, **sub.model_dump())
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.put("/subscriptions/{subscription_id}", response_model=Subscriptions)
async def update_subscription(subscription_id: int, sub: SubscriptionCreate):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            UPDATE_SUBSCRIPTION,
            (sub.tenant_id, sub.quota_limit, sub.usage_count, sub.start_date, sub.end_date, subscription_id)
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Fetch tenant name for response
        cur.execute(GET_TENANT_NAME_BY_ID, (sub.tenant_id,))
        tenant_name = cur.fetchone()[0]

        return Subscriptions(id=subscription_id, tenant_name=tenant_name, **sub.model_dump())
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: int):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(DELETE_SUBSCRIPTION, (subscription_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"message": "Subscription deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- Chat Sessions CRUD ---
@router.get("/chat_sessions", response_model=List[ChatSessions])
async def get_chat_sessions():
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(GET_ALL_CHAT_SESSIONS)
        rows = cur.fetchall()
        sessions = []
        for row in rows:
            sessions.append(ChatSessions(
                id=row[0], tenant_id=row[1], created_at=row[2], tenant_name=row[3]
            ))
        return sessions
    finally:
        cur.close()
        conn.close()

@router.post("/chat_sessions", response_model=ChatSessions)
async def create_chat_session(session: ChatSessionCreate):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            CREATE_CHAT_SESSION,
            (session.tenant_id,)
        )
        new_id, created_at = cur.fetchone()
        conn.commit()

        # Fetch tenant name
        cur.execute(GET_TENANT_NAME_BY_ID, (session.tenant_id,))
        tenant_name = cur.fetchone()[0]

        return ChatSessions(id=new_id, tenant_id=session.tenant_id, created_at=created_at, tenant_name=tenant_name)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.put("/chat_sessions/{session_id}", response_model=ChatSessions)
async def update_chat_session(session_id: int, session: ChatSessionCreate):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        # Note: created_at is usually not updated, preserving original value or handling via different logic if needed.
        # For simplicity, we only update tenant_id here as it's the only editable field in Create model.
        # We need to fetch created_at to return full object.
        cur.execute(
            UPDATE_CHAT_SESSION,
            (session.tenant_id, session_id)
        )
        result = cur.fetchone()
        if not result:
             raise HTTPException(status_code=404, detail="Chat session not found")
        created_at = result[0]
        conn.commit()

        # Fetch tenant name
        cur.execute(GET_TENANT_NAME_BY_ID, (session.tenant_id,))
        tenant_name = cur.fetchone()[0]

        return ChatSessions(id=session_id, tenant_id=session.tenant_id, created_at=created_at, tenant_name=tenant_name)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/chat_sessions/{session_id}")
async def delete_chat_session(session_id: int):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        cur.execute(DELETE_CHAT_SESSION, (session_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return {"message": "Chat session deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- Chat Messages CRUD ---
@router.get("/chat_messages", response_model=List[ChatMessages])
async def get_chat_messages(session_id: Optional[int] = None):
    conn = get_postgres_connection()
    cur = conn.cursor()
    try:
        query = GET_CHAT_MESSAGES_BASE
        params = []
        if session_id:
            query += " WHERE m.session_id = %s"
            params.append(session_id)
        query += " ORDER BY m.created_at"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        messages = []
        for row in rows:
            messages.append(ChatMessages(
                id=row[0], session_id=row[1], content=row[2], role=row[3], created_at=row[4], tenant_name=row[5]
            ))
        return messages
    finally:
        cur.close()
        conn.close()
