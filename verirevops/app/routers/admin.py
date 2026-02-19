from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.models import Tenant, Subscription, ChatSession, ChatMessage, IntegrationConfig
from app.schemas import (
    Tenants, TenantCreate,
    Subscriptions, SubscriptionCreate,
    ChatSessions, ChatSessionCreate,
    ChatMessages,
    IntegrationConfigs, IntegrationConfigCreate
)

router = APIRouter(prefix="/api", tags=["admin"])

# --- Tenants CRUD ---

@router.get("/tenants", response_model=List[Tenants])
async def get_tenants(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Tenant))
    tenants = result.scalars().all()
    return tenants


@router.post("/tenants", response_model=Tenants)
async def create_tenant(tenant: TenantCreate, session: AsyncSession = Depends(get_db)):
    db_tenant = Tenant(**tenant.model_dump())
    session.add(db_tenant)
    try:
        await session.commit()
        await session.refresh(db_tenant)
        return db_tenant
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/tenants/{tenant_id}", response_model=Tenants)
async def update_tenant(tenant_id: int, tenant: TenantCreate, session: AsyncSession = Depends(get_db)):
    db_tenant = await session.get(Tenant, tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_data = tenant.model_dump(exclude_unset=True)
    for key, value in tenant_data.items():
        setattr(db_tenant, key, value)

    try:
        await session.commit()
        await session.refresh(db_tenant)
        return db_tenant
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: int, session: AsyncSession = Depends(get_db)):
    db_tenant = await session.get(Tenant, tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    try:
        await session.delete(db_tenant)
        await session.commit()
        return {"message": "Tenant deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# --- Subscriptions CRUD ---

@router.get("/subscriptions", response_model=List[Subscriptions])
async def get_subscriptions(session: AsyncSession = Depends(get_db)):
    # Join with Tenant to get tenant_name
    stmt = select(Subscription).options(selectinload(Subscription.tenant))
    result = await session.execute(stmt)
    subscriptions = result.scalars().all()

    # Map ORM objects to Pydantic models (including computed/joined fields)
    response = []
    for sub in subscriptions:
        response.append(Subscriptions(
            id=sub.id,
            tenant_id=sub.tenant_id,
            quota_limit=sub.quota_limit,
            usage_count=sub.usage_count,
            start_date=sub.start_date,
            end_date=sub.end_date,
            tenant_name=sub.tenant.name if sub.tenant else None
        ))
    return response


@router.post("/subscriptions", response_model=Subscriptions)
async def create_subscription(sub: SubscriptionCreate, session: AsyncSession = Depends(get_db)):
    db_sub = Subscription(**sub.model_dump())
    session.add(db_sub)
    try:
        await session.commit()
        await session.refresh(db_sub)

        # Load tenant relationship for response
        # Using a separate query or refresh with options if needed, but explicit get is safe
        # db_sub.tenant is likely not loaded yet unless we eagerly loaded it, but we just inserted it.
        # We can just fetch the name.
        tenant = await session.get(Tenant, sub.tenant_id)

        return Subscriptions(
            id=db_sub.id,
            tenant_id=db_sub.tenant_id,
            quota_limit=db_sub.quota_limit,
            usage_count=db_sub.usage_count,
            start_date=db_sub.start_date,
            end_date=db_sub.end_date,
            tenant_name=tenant.name if tenant else None
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/subscriptions/{subscription_id}", response_model=Subscriptions)
async def update_subscription(subscription_id: int, sub: SubscriptionCreate, session: AsyncSession = Depends(get_db)):
    db_sub = await session.get(Subscription, subscription_id)
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub_data = sub.model_dump(exclude_unset=True)
    for key, value in sub_data.items():
        setattr(db_sub, key, value)

    try:
        await session.commit()
        await session.refresh(db_sub)

        tenant = await session.get(Tenant, db_sub.tenant_id)

        return Subscriptions(
            id=db_sub.id,
            tenant_id=db_sub.tenant_id,
            quota_limit=db_sub.quota_limit,
            usage_count=db_sub.usage_count,
            start_date=db_sub.start_date,
            end_date=db_sub.end_date,
            tenant_name=tenant.name if tenant else None
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: int, session: AsyncSession = Depends(get_db)):
    db_sub = await session.get(Subscription, subscription_id)
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        await session.delete(db_sub)
        await session.commit()
        return {"message": "Subscription deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# --- Chat Sessions CRUD ---

@router.get("/chat_sessions", response_model=List[ChatSessions])
async def get_chat_sessions(session: AsyncSession = Depends(get_db)):
    stmt = select(ChatSession).options(selectinload(ChatSession.tenant))
    result = await session.execute(stmt)
    sessions = result.scalars().all()

    response = []
    for s in sessions:
        response.append(ChatSessions(
            id=s.id,
            tenant_id=s.tenant_id,
            created_at=s.created_at,
            tenant_name=s.tenant.name if s.tenant else None
        ))
    return response


@router.post("/chat_sessions", response_model=ChatSessions)
async def create_chat_session(session_in: ChatSessionCreate, session: AsyncSession = Depends(get_db)):
    db_session = ChatSession(tenant_id=session_in.tenant_id)
    session.add(db_session)
    try:
        await session.commit()
        await session.refresh(db_session)

        tenant = await session.get(Tenant, db_session.tenant_id)

        return ChatSessions(
            id=db_session.id,
            tenant_id=db_session.tenant_id,
            created_at=db_session.created_at,
            tenant_name=tenant.name if tenant else None
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/chat_sessions/{session_id}", response_model=ChatSessions)
async def update_chat_session(session_id: int, session_in: ChatSessionCreate, session: AsyncSession = Depends(get_db)):
    # Note: Logic usually implies updating something, but here it might be just tenant_id?
    # Keeping consistency with original logic which allowed updating tenant_id
    db_session = await session.get(ChatSession, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    db_session.tenant_id = session_in.tenant_id

    try:
        await session.commit()
        await session.refresh(db_session)

        tenant = await session.get(Tenant, db_session.tenant_id)

        return ChatSessions(
            id=db_session.id,
            tenant_id=db_session.tenant_id,
            created_at=db_session.created_at,
            tenant_name=tenant.name if tenant else None
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/chat_sessions/{session_id}")
async def delete_chat_session(session_id: int, session: AsyncSession = Depends(get_db)):
    db_session = await session.get(ChatSession, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    try:
        await session.delete(db_session)
        await session.commit()
        return {"message": "Chat session deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# --- Chat Messages CRUD ---

@router.get("/chat_messages", response_model=List[ChatMessages])
async def get_chat_messages(session_id: Optional[int] = None, session: AsyncSession = Depends(get_db)):
    stmt = select(ChatMessage).order_by(ChatMessage.created_at)
    if session_id:
        stmt = stmt.where(ChatMessage.session_id == session_id)

    stmt = stmt.options(selectinload(ChatMessage.session).selectinload(ChatSession.tenant))

    result = await session.execute(stmt)
    messages = result.scalars().all()

    response = []
    for m in messages:
         tenant_name = None
         tenant_id = None
         if m.session:
             tenant_id = m.session.tenant_id
             if m.session.tenant:
                 tenant_name = m.session.tenant.name

         response.append(ChatMessages(
            id=m.id,
            session_id=m.session_id,
            tenant_id=tenant_id,
            content=m.content,
            role=m.role,
            created_at=m.created_at,
            tenant_name=tenant_name
         ))
    return response

# --- Integration Config CRUD ---

@router.get("/integrations", response_model=List[IntegrationConfigs])
async def get_integrations(session: AsyncSession = Depends(get_db)):
    stmt = select(IntegrationConfig).options(selectinload(IntegrationConfig.tenant))
    result = await session.execute(stmt)
    configs = result.scalars().all()
    return configs

@router.post("/integrations", response_model=IntegrationConfigs)
async def create_integration(config_in: IntegrationConfigCreate, session: AsyncSession = Depends(get_db)):
    db_config = IntegrationConfig(**config_in.model_dump())
    session.add(db_config)
    try:
        await session.commit()
        await session.refresh(db_config)
        return db_config
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/integrations/{config_id}", response_model=IntegrationConfigs)
async def update_integration(config_id: int, config_in: IntegrationConfigCreate, session: AsyncSession = Depends(get_db)):
    db_config = await session.get(IntegrationConfig, config_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    config_data = config_in.model_dump(exclude_unset=True)
    for key, value in config_data.items():
        setattr(db_config, key, value)

    try:
        await session.commit()
        await session.refresh(db_config)
        return db_config
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/integrations/{config_id}")
async def delete_integration(config_id: int, session: AsyncSession = Depends(get_db)):
    db_config = await session.get(IntegrationConfig, config_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    try:
        await session.delete(db_config)
        await session.commit()
        return {"message": "Configuration deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
