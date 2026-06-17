import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.db import get_session
from src.core.models import Configuration, Invitation, Subscription, Tenant, User
from src.core.security import generate_token, hash_password, verify_password

logger = logging.getLogger(__name__)

TRIAL_QUOTA = 1000
TRIAL_DAYS = 30


async def get_user_by_id(user_id: int) -> User | None:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def get_user_by_email(email: str) -> User | None:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()


async def authenticate_user(email: str, password: str) -> User | None:
    user = await get_user_by_email(email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_tenant_with_admin(email: str, password: str, tenant_slug: str, full_name: str | None) -> User:
    """Register a new tenant and its first admin user atomically."""
    email = email.lower()
    existing = await get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    now = datetime.now(timezone.utc)
    webhook_token = generate_token()

    async with get_session() as session:
        # Check slug uniqueness
        slug_check = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        if slug_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name already taken")

        tenant = Tenant(slug=tenant_slug)
        session.add(tenant)
        await session.flush()  # get tenant.id

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role="tenant_admin",
            tenant_id=tenant.id,
            is_active=True,
        )
        session.add(user)

        # Trial subscription
        subscription = Subscription(
            tenant_id=tenant.id,
            is_active=True,
            quota_limit=TRIAL_QUOTA,
            usage_count=0,
            start_dat=now,
            end_date=now + timedelta(days=TRIAL_DAYS),
        )
        session.add(subscription)

        # Configuration with webhook token
        configuration = Configuration(
            tenant_id=tenant.id,
            settings={"webhook_token": webhook_token},
        )
        session.add(configuration)

        await session.commit()
        await session.refresh(user)
        return user


async def get_tenant_users(tenant_id: int) -> list[User]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
        )
        return list(result.scalars().all())


async def create_invitation(tenant_id: int, email: str, role: str, created_by_id: int) -> Invitation:
    email = email.lower()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    token = generate_token()

    async with get_session() as session:
        invitation = Invitation(
            tenant_id=tenant_id,
            email=email,
            token=token,
            role=role,
            expires_at=expires_at,
            created_by_id=created_by_id,
        )
        session.add(invitation)
        await session.commit()
        await session.refresh(invitation)
        return invitation


async def get_invitation_by_token(token: str) -> Invitation | None:
    async with get_session() as session:
        result = await session.execute(
            select(Invitation)
            .where(Invitation.token == token)
            .options(selectinload(Invitation.tenant))
        )
        return result.scalar_one_or_none()


async def accept_invitation(token: str, password: str, full_name: str | None) -> User:
    invitation = await get_invitation_by_token(token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    now = datetime.now(timezone.utc)
    if invitation.accepted_at:
        raise HTTPException(status_code=400, detail="Invitation already accepted")
    if invitation.expires_at < now:
        raise HTTPException(status_code=400, detail="Invitation has expired")

    existing = await get_user_by_email(invitation.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    async with get_session() as session:
        user = User(
            email=invitation.email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=invitation.role,
            tenant_id=invitation.tenant_id,
            is_active=True,
        )
        session.add(user)

        result = await session.execute(select(Invitation).where(Invitation.token == token))
        inv = result.scalar_one()
        inv.accepted_at = now

        await session.commit()
        await session.refresh(user)
        return user


async def get_tenant_webhook_token(tenant_id: int) -> str | None:
    """Return the webhook_token stored in the tenant's configuration, if any."""
    async with get_session() as session:
        result = await session.execute(
            select(Configuration).where(Configuration.tenant_id == tenant_id)
        )
        config = result.scalars().first()
        if config and config.settings:
            return config.settings.get("webhook_token")
        return None


async def get_tenant_by_slug_simple(slug: str) -> Tenant | None:
    async with get_session() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()
