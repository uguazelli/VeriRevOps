import logging
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme
from rich.panel import Panel
from typing import Any

# Custom theme for VeriRevOps
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "critical": "bold white on red",
    "success": "bold green",
    "orchestrator": "bold magenta",
    "rag": "bold blue",
    "webhook": "bold cyan",
    "tenant": "bold yellow",
})

console = Console(theme=custom_theme)

class Log:
    @staticmethod
    def info(message: str):
        console.print(f"ℹ️ [info]{message}[/info]")

    @staticmethod
    def success(message: str):
        console.print(f"✅ [success]{message}[/success]")

    @staticmethod
    def warning(message: str):
        console.print(f"⚠️ [warning]{message}[/warning]")

    @staticmethod
    def error(message: str):
        console.print(f"🚨 [error]{message}[/error]")

    @staticmethod
    def critical(message: str):
        console.print(Panel(f"🔥 [critical]{message}[/critical]", border_style="red"))

    @staticmethod
    def orchestrator(message: str):
        console.print(f"🧠 [orchestrator]ORCHESTRATOR:[/orchestrator] {message}")

    @staticmethod
    def rag(message: str, step: str = None):
        prefix = f"🔍 [rag]RAG[/rag]"
        if step:
            prefix += f" [bold white]({step})[/bold white]"
        console.print(f"{prefix}: {message}")

    @staticmethod
    def webhook(message: str, direction: str = "IN"):
        icon = "📥" if direction == "IN" else "📤"
        console.print(f"{icon} [webhook]WEBHOOK {direction}:[/webhook] {message}")

    @staticmethod
    def tenant(tenant_id: Any, message: str):
        console.print(f"🆔 [tenant]TENANT {tenant_id}:[/tenant] {message}")

    @staticmethod
    def divider(title: str = ""):
        console.rule(f"[bold white]{title}[/bold white]")

# Setup standard logging to use RichHandler for library logs
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("verirevops")
