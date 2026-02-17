from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from bot.core.config import settings


class AdminAuth(AuthenticationBackend):
    """Authentication backend for the Admin panel."""

    async def login(self, request: Request) -> bool:
        """Handle login request."""
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        # Basic env-based auth
        if username == settings.admin_user and password == settings.admin_password:
            request.session.update({"token": "admin-token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        """Handle logout request."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Check if request is authenticated."""
        token = request.session.get("token")
        return bool(token)


authentication_backend = AdminAuth(secret_key=settings.secret_key)
