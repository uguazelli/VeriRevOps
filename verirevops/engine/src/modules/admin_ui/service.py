from uuid import UUID

from sqlalchemy import delete, select, update

from src.core.db import get_session
from src.core.models import Document, Tenant


async def get_tenants():
    async with get_session() as session:
        tenants = (
            await session.execute(
                select(Tenant).order_by(Tenant.created_at.desc())
            )
        ).scalars().all()
        return [(tenant.id, tenant.slug) for tenant in tenants]


async def get_tenant_documents(tenant_id: int):
    async with get_session() as session:
        documents = (
            await session.execute(
                select(Document)
                .where(Document.tenant_id == tenant_id)
                .where(Document.parent_id.is_(None))
                .order_by(Document.created_at.desc())
            )
        ).scalars().all()
        return [
            (document.id, document.filename, document.created_at)
            for document in documents
        ]


async def create_tenant(slug: str):
    async with get_session() as session:
        session.add(Tenant(slug=slug))
        await session.commit()


async def rename_tenant(tenant_id: int, slug: str):
    async with get_session() as session:
        await session.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(slug=slug)
        )
        await session.commit()


async def delete_tenant(tenant_id: int):
    async with get_session() as session:
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await session.commit()


async def delete_document(doc_id: UUID):
    async with get_session() as session:
        await session.execute(delete(Document).where(Document.id == doc_id))
        await session.commit()
