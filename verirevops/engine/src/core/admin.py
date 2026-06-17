import logging
import os

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import AuthenticationBackend

from src.core.db import get_engine
from src.core.models import (
    ChatMessage,
    Configuration,
    ContactMapping,
    Document,
    GlobalConfig,
    Invitation,
    Service,
    Subscription,
    Tenant,
    User,
)
from src.core.security import decode_token

logger = logging.getLogger(__name__)


class SuperAdminAuth(AuthenticationBackend):
    """Gate the SQLAdmin panel to superadmin JWT holders only."""

    async def login(self, request: Request) -> bool:
        # We don't handle login here; redirect to our own login page
        return False

    async def logout(self, request: Request) -> bool:
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.cookies.get("access_token")
        if not token:
            return False
        payload = decode_token(token)
        return bool(payload and payload.get("role") == "superadmin")


class DashboardView(BaseView):
    name = "RAG Dashboard"
    icon = "fa-solid fa-house"
    identity = "dashboard"

    @expose("/dashboard", methods=["GET"], identity="dashboard")
    async def index(self, request):
        return RedirectResponse(url="/")


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.full_name, User.role, User.tenant_id, User.is_active, User.created_at]
    column_searchable_list = [User.email, User.full_name]
    form_excluded_columns = [User.hashed_password]
    name_plural = "Users"
    icon = "fa-solid fa-user"


class InvitationAdmin(ModelView, model=Invitation):
    column_list = [Invitation.id, Invitation.email, Invitation.tenant_id, Invitation.role, Invitation.expires_at, Invitation.accepted_at]
    column_searchable_list = [Invitation.email]
    name_plural = "Invitations"
    icon = "fa-solid fa-envelope"


class TenantAdmin(ModelView, model=Tenant):
    column_list = [Tenant.id, Tenant.slug, Tenant.created_at]
    column_searchable_list = [Tenant.slug]
    name_plural = "Tenants"
    icon = "fa-solid fa-users"


class SubscriptionAdmin(ModelView, model=Subscription):
    column_list = [
        Subscription.id,
        Subscription.tenant_id,
        Subscription.is_active,
        Subscription.quota_limit,
        Subscription.usage_count,
        Subscription.end_date,
    ]
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
    column_list = [
        ContactMapping.id,
        ContactMapping.tenant_id,
        ContactMapping.chatwoot_contact_id,
        ContactMapping.service_name,
    ]
    name_plural = "Contact Mappings"
    icon = "fa-solid fa-address-book"


class ChatMessageAdmin(ModelView, model=ChatMessage):
    column_list = [
        ChatMessage.id,
        ChatMessage.tenant_id,
        ChatMessage.chatwoot_conversation_id,
        ChatMessage.message_id,
    ]
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
    secret_key = os.getenv("JWT_SECRET_KEY", "change-me-use-openssl-rand-hex-32")
    admin = Admin(
        app,
        get_engine(),
        base_url="/crud",
        title="VeriRag CRUD",
        logo_url="/static/logo.png",
        favicon_url="/static/favicon.ico",
        templates_dir="src/templates",
        authentication_backend=SuperAdminAuth(secret_key=secret_key),
    )

    admin.add_base_view(DashboardView)
    admin.add_view(UserAdmin)
    admin.add_view(InvitationAdmin)
    admin.add_view(TenantAdmin)
    admin.add_view(SubscriptionAdmin)
    admin.add_view(ConfigurationAdmin)
    admin.add_view(ServiceAdmin)
    admin.add_view(ContactMappingAdmin)
    admin.add_view(ChatMessageAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(GlobalConfigAdmin)
    return admin
