from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.database import execute_read_query, execute_write_query
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
    rows = execute_read_query(GET_ALL_TENANTS)
    tenants = []
    for row in rows:
        tenants.append(Tenants(id=row[0], name=row[1], slug=row[2], url=row[3], is_active=row[4]))
    return tenants

@router.post("/tenants", response_model=Tenants)
async def create_tenant(tenant: TenantCreate):
    try:
        # execute_write_query returns a tuple (id,) for RETURNING id
        new_id = execute_write_query(
            CREATE_TENANT,
            (tenant.name, tenant.slug, tenant.url, tenant.is_active)
        )[0]
        return Tenants(id=new_id, **tenant.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/tenants/{tenant_id}", response_model=Tenants)
async def update_tenant(tenant_id: int, tenant: TenantCreate):
    try:
        rowcount = execute_write_query(
            UPDATE_TENANT,
            (tenant.name, tenant.slug, tenant.url, tenant.is_active, tenant_id)
        )
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return Tenants(id=tenant_id, **tenant.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: int):
    try:
        rowcount = execute_write_query(DELETE_TENANT, (tenant_id,))
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return {"message": "Tenant deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Subscriptions CRUD ---
@router.get("/subscriptions", response_model=List[Subscriptions])
async def get_subscriptions():
    rows = execute_read_query(GET_ALL_SUBSCRIPTIONS)
    subscriptions = []
    for row in rows:
        subscriptions.append(Subscriptions(
            id=row[0], tenant_id=row[1], quota_limit=row[2], usage_count=row[3],
            start_date=row[4], end_date=row[5], tenant_name=row[6]
        ))
    return subscriptions

@router.post("/subscriptions", response_model=Subscriptions)
async def create_subscription(sub: SubscriptionCreate):
    try:
        # execute_write_query returns (id,)
        new_id = execute_write_query(
            CREATE_SUBSCRIPTION,
            (sub.tenant_id, sub.quota_limit, sub.usage_count, sub.start_date, sub.end_date)
        )[0]
        # Fetch tenant name for response
        tenant_name_row = execute_read_query(GET_TENANT_NAME_BY_ID, (sub.tenant_id,))
        tenant_name = tenant_name_row[0][0] if tenant_name_row else None

        return Subscriptions(id=new_id, tenant_name=tenant_name, **sub.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/subscriptions/{subscription_id}", response_model=Subscriptions)
async def update_subscription(subscription_id: int, sub: SubscriptionCreate):
    try:
        rowcount = execute_write_query(
            UPDATE_SUBSCRIPTION,
            (sub.tenant_id, sub.quota_limit, sub.usage_count, sub.start_date, sub.end_date, subscription_id)
        )
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Fetch tenant name for response
        tenant_name_row = execute_read_query(GET_TENANT_NAME_BY_ID, (sub.tenant_id,))
        tenant_name = tenant_name_row[0][0] if tenant_name_row else None

        return Subscriptions(id=subscription_id, tenant_name=tenant_name, **sub.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: int):
    try:
        rowcount = execute_write_query(DELETE_SUBSCRIPTION, (subscription_id,))
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"message": "Subscription deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Chat Sessions CRUD ---
@router.get("/chat_sessions", response_model=List[ChatSessions])
async def get_chat_sessions():
    rows = execute_read_query(GET_ALL_CHAT_SESSIONS)
    sessions = []
    for row in rows:
        sessions.append(ChatSessions(
            id=row[0], tenant_id=row[1], created_at=row[2], tenant_name=row[3]
        ))
    return sessions

@router.post("/chat_sessions", response_model=ChatSessions)
async def create_chat_session(session: ChatSessionCreate):
    try:
        # execute_write_query returns (id, created_at)
        result = execute_write_query(
            CREATE_CHAT_SESSION,
            (session.tenant_id,)
        )
        new_id, created_at = result

        # Fetch tenant name
        tenant_name_row = execute_read_query(GET_TENANT_NAME_BY_ID, (session.tenant_id,))
        tenant_name = tenant_name_row[0][0] if tenant_name_row else None

        return ChatSessions(id=new_id, tenant_id=session.tenant_id, created_at=created_at, tenant_name=tenant_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/chat_sessions/{session_id}", response_model=ChatSessions)
async def update_chat_session(session_id: int, session: ChatSessionCreate):
    try:
        # execute_write_query returns (created_at,)
        result = execute_write_query(
            UPDATE_CHAT_SESSION,
            (session.tenant_id, session_id)
        )
        if not result:
             raise HTTPException(status_code=404, detail="Chat session not found")
        created_at = result[0]

        # Fetch tenant name
        tenant_name_row = execute_read_query(GET_TENANT_NAME_BY_ID, (session.tenant_id,))
        tenant_name = tenant_name_row[0][0] if tenant_name_row else None

        return ChatSessions(id=session_id, tenant_id=session.tenant_id, created_at=created_at, tenant_name=tenant_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/chat_sessions/{session_id}")
async def delete_chat_session(session_id: int):
    try:
        rowcount = execute_write_query(DELETE_CHAT_SESSION, (session_id,))
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return {"message": "Chat session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Chat Messages CRUD ---
@router.get("/chat_messages", response_model=List[ChatMessages])
async def get_chat_messages(session_id: Optional[int] = None):
    try:
        query = GET_CHAT_MESSAGES_BASE
        params = []
        if session_id:
            query += " WHERE m.session_id = %s"
            params.append(session_id)
        query += " ORDER BY m.created_at"

        rows = execute_read_query(query, tuple(params))
        messages = []
        for row in rows:
            messages.append(ChatMessages(
                id=row[0], session_id=row[1], content=row[2], role=row[3], created_at=row[4], tenant_name=row[5]
            ))
        return messages
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
