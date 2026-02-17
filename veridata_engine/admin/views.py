from sqladmin import ModelView

from bot.models import BotSession, Client, GlobalConfig, ServiceConfig, Subscription, SyncConfig
from rag.models.sql import Document


class ClientAdmin(ModelView, model=Client):
    """Admin view for Clients/Tenants."""
    name = "Client / Tenant"
    name_plural = "Clients / Tenants"
    column_list = [Client.id, Client.name, Client.slug, Client.is_active]
    form_columns = [Client.name, Client.slug, Client.is_active]
    can_create = True
    can_edit = True
    can_delete = True
    icon = "fa-solid fa-users"


class SyncConfigAdmin(ModelView, model=SyncConfig):
    """Admin view for Sync Configurations (Job Schedules)."""
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
    """Admin view for Client Service Configurations."""
    name = "Client Configuration"
    name_plural = "Client Configurations"
    column_list = [ServiceConfig.id, ServiceConfig.client_id]
    form_columns = [ServiceConfig.client, ServiceConfig.config]
    icon = "fa-solid fa-robot"


class SubscriptionAdmin(ModelView, model=Subscription):
    """Admin view for Usage Quotas/Subscriptions."""
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
    """Admin view for live Bot Sessions."""
    can_create = False
    name = "Live Session"
    name_plural = "Live Sessions"
    column_list = [BotSession.id, BotSession.client_id, BotSession.external_session_id, BotSession.rag_session_id]
    icon = "fa-solid fa-comments"


class GlobalConfigAdmin(ModelView, model=GlobalConfig):
    """Admin view for Global System Settings."""
    name = "Global Setting"
    name_plural = "Global Settings"
    column_list = [GlobalConfig.id, GlobalConfig.updated_at]
    form_columns = [GlobalConfig.config]
    icon = "fa-solid fa-gears"


class DocumentAdmin(ModelView, model=Document):
    """Admin view for RAG Documents."""
    name = "RAG Document"
    name_plural = "RAG Documents"
    column_list = [Document.id, Document.client_id, Document.filename, Document.created_at]
    can_create = False
    can_edit = False # Managed via RAG Ingestion
    can_delete = True
    icon = "fa-solid fa-file-pdf"
