from fastapi.responses import RedirectResponse, HTMLResponse
from sqladmin import Admin, ModelView, BaseView, expose
from src.core.models import Tenant, Subscription, Configuration, Service, ContactMapping, ChatMessage, Document, GlobalConfig
from src.core.db import get_engine
import logging

logger = logging.getLogger(__name__)

class DashboardView(BaseView):
    name = "RAG Dashboard"
    icon = "fa-solid fa-house"
    identity = "dashboard"

    @expose("/", methods=["GET"])
    async def index(self, request):
        # Using JS redirect to ensure we break out of SQLAdmin's AJAX content area
        return HTMLResponse("<script>window.location.href='/';</script>")

class TenantAdmin(ModelView, model=Tenant):
    column_list = [Tenant.id, Tenant.slug, Tenant.created_at]
    column_searchable_list = [Tenant.slug]
    name_plural = "Tenants"
    icon = "fa-solid fa-users"

class SubscriptionAdmin(ModelView, model=Subscription):
    column_list = [Subscription.id, Subscription.tenant_id, Subscription.is_active, Subscription.quota_limit, Subscription.usage_count, Subscription.end_date]
    name_plural = "Subscriptions"
    icon = "fa-solid fa-credit-card"

class ConfigurationAdmin(ModelView, model=Configuration):
    column_list = [Configuration.id, Configuration.tenant_id]
    name_plural = "Configurations"
    icon = "fa-solid fa-gear"

class ServiceAdmin(ModelView, model=Service):
    column_list = [Service.id, Service.tenant_id, Service.name, Service.url]
    column_searchable_list = [Service.name]
    name_plural = "Services"
    icon = "fa-solid fa-server"

class ContactMappingAdmin(ModelView, model=ContactMapping):
    column_list = [ContactMapping.id, ContactMapping.tenant_id, ContactMapping.chatwoot_contact_id, ContactMapping.service_name]
    name_plural = "Contact Mappings"
    icon = "fa-solid fa-address-book"

class ChatMessageAdmin(ModelView, model=ChatMessage):
    column_list = [ChatMessage.id, ChatMessage.tenant_id, ChatMessage.chatwoot_conversation_id, ChatMessage.is_summarized]
    name_plural = "Chat Messages"
    icon = "fa-solid fa-comments"

class DocumentAdmin(ModelView, model=Document):
    column_list = [Document.id, Document.tenant_id, Document.filename, Document.created_at]
    column_searchable_list = [Document.filename]
    name_plural = "Documents"
    icon = "fa-solid fa-file-lines"

class GlobalConfigAdmin(ModelView, model=GlobalConfig):
    column_list = [GlobalConfig.id]
    name_plural = "Global Configs"
    icon = "fa-solid fa-globe"

def setup_admin(app):
    admin = Admin(
        app,
        get_engine(),
        base_url="/crud",
        title="VeriRag CRUD",
        logo_url="/static/logo.png"
    )

    # Dashboard Link at the top - MUST use add_base_view for BaseView
    admin.add_base_view(DashboardView)

    admin.add_view(TenantAdmin)
    admin.add_view(SubscriptionAdmin)
    admin.add_view(ConfigurationAdmin)
    admin.add_view(ServiceAdmin)
    admin.add_view(ContactMappingAdmin)
    admin.add_view(ChatMessageAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(GlobalConfigAdmin)
    return admin
