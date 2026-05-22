import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.modules.chatwoot.service import (
    ChatwootFlowContext,
    build_bot_response,
    build_rag_response,
    run_chatwoot_message_flow,
)


class ChatwootServiceFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_message_flow_runs_connectors_in_order(self):
        ctx = ChatwootFlowContext(slug="demo", payload={})
        calls = []

        def make_step(name):
            async def step(context):
                calls.append(name)

            return step

        with (
            patch(
                "src.modules.chatwoot.service.resolve_current_message",
                new=make_step("resolve"),
            ),
            patch(
                "src.modules.chatwoot.service.fetch_message_history",
                new=make_step("history"),
            ),
            patch(
                "src.modules.chatwoot.service.classify_current_message",
                new=make_step("classify"),
            ),
            patch(
                "src.modules.chatwoot.service.build_bot_response",
                new=make_step("build"),
            ),
            patch(
                "src.modules.chatwoot.service.send_bot_response",
                new=make_step("send"),
            ),
            patch(
                "src.modules.chatwoot.service.run_handoff_flow_if_needed",
                new=make_step("handoff"),
            ),
        ):
            await run_chatwoot_message_flow(ctx)

        self.assertEqual(
            calls,
            ["resolve", "history", "classify", "build", "send", "handoff"],
        )

    async def test_build_bot_response_uses_chitchat_connector(self):
        ctx = ChatwootFlowContext(
            slug="demo",
            payload={},
            category="CHITCHAT",
            current_message="Obrigado",
        )

        with patch(
            "src.modules.chatwoot.service.respond_to_chitchat",
            new=AsyncMock(return_value={"data": "De nada!"}),
        ) as respond_to_chitchat:
            await build_bot_response(ctx)

        respond_to_chitchat.assert_awaited_once_with("Obrigado")
        self.assertEqual(ctx.response, {"data": "De nada!"})
        self.assertFalse(ctx.handoff_required)

    async def test_build_rag_response_switches_to_handoff_when_required(self):
        ctx = ChatwootFlowContext(
            slug="demo",
            payload={},
            tenant_settings=SimpleNamespace(),
            current_message="Quanto custa?",
            message_history=[],
        )

        with (
            patch(
                "src.modules.chatwoot.service.respond_with_rag",
                new=AsyncMock(
                    return_value={
                        "data": "",
                        "handoff_required": True,
                        "reason": "No clear source.",
                    }
                ),
            ),
            patch(
                "src.modules.chatwoot.service.respond_to_handoff",
                new=AsyncMock(return_value={"data": "Vou chamar a equipe."}),
            ),
        ):
            await build_rag_response(ctx)

        self.assertEqual(ctx.category, "HANDOFF")
        self.assertTrue(ctx.handoff_required)
        self.assertEqual(ctx.handoff_reason, "No clear source.")
        self.assertEqual(ctx.response, {"data": "Vou chamar a equipe."})


if __name__ == "__main__":
    unittest.main()
