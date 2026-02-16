from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from app.core.config import settings
from app.core.db import get_session
from app.models import BotSession, Client, GlobalConfig, ServiceConfig, Subscription, SyncConfig
from app.rag.models.sql import Document, ChatSession

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        # Basic env-based auth
        if username == settings.admin_user and password == settings.admin_password:
            request.session.update({"token": "admin-token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        return bool(token)


authentication_backend = AdminAuth(secret_key=settings.secret_key)


class ClientAdmin(ModelView, model=Client):
    name = "Client / Tenant"
    name_plural = "Clients / Tenants"
    column_list = [Client.id, Client.name, Client.slug, Client.is_active]
    form_columns = [Client.name, Client.slug, Client.is_active]
    can_create = True
    can_edit = True
    can_delete = True
    icon = "fa-solid fa-users"


class SyncConfigAdmin(ModelView, model=SyncConfig):
    name = "Job Schedule"
    name_plural = "Job Schedules"
    column_list = [
        SyncConfig.id,
        SyncConfig.client_id,
        SyncConfig.platform,
        SyncConfig.is_active,
        SyncConfig.frequency_minutes,
        SyncConfig.inactivity_threshold_minutes,
        SyncConfig.last_run_at,
    ]
    form_columns = [
        SyncConfig.client,
        SyncConfig.platform,
        SyncConfig.config_json,
        SyncConfig.is_active,
        SyncConfig.frequency_minutes,
        SyncConfig.inactivity_threshold_minutes,
        SyncConfig.last_run_at,
    ]
    icon = "fa-solid fa-clock"


class ClientConfigAdmin(ModelView, model=ServiceConfig):
    name = "Client Configuration"
    name_plural = "Client Configurations"
    column_list = [ServiceConfig.id, ServiceConfig.client_id]
    form_columns = [ServiceConfig.client, ServiceConfig.config]
    icon = "fa-solid fa-robot"


class SubscriptionAdmin(ModelView, model=Subscription):
    name = "Usage Quota"
    name_plural = "Usage Quotas"
    column_list = [
        Subscription.id,
        Subscription.client_id,
        Subscription.quota_limit,
        Subscription.usage_count,
        Subscription.start_date,
        Subscription.end_date,
    ]
    form_columns = [
        Subscription.client,
        Subscription.quota_limit,
        Subscription.usage_count,
        Subscription.start_date,
        Subscription.end_date,
    ]
    icon = "fa-solid fa-file-invoice"


class BotSessionAdmin(ModelView, model=BotSession):
    can_create = False
    name = "Live Session"
    name_plural = "Live Sessions"
    column_list = [BotSession.id, BotSession.client_id, BotSession.external_session_id, BotSession.rag_session_id]
    icon = "fa-solid fa-comments"


class GlobalConfigAdmin(ModelView, model=GlobalConfig):
    name = "Global Setting"
    name_plural = "Global Settings"
    column_list = [GlobalConfig.id, GlobalConfig.updated_at]
    form_columns = [GlobalConfig.config]
    icon = "fa-solid fa-gears"

class DocumentAdmin(ModelView, model=Document):
    name = "RAG Document"
    name_plural = "RAG Documents"
    column_list = [Document.id, Document.client_id, Document.filename, Document.created_at]
    can_create = False
    can_edit = False # Managed via RAG Ingestion
    can_delete = True
    icon = "fa-solid fa-file-pdf"
