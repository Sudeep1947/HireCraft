"""Chat service — orchestrates the full chat pipeline.

This is the primary entry point for all chat interactions. It:
1. Validates the request via prompt safety
2. Routes to the correct agent
3. Builds RAG context
4. Calls the LLM via the router
5. Executes tool calls
6. Assembles the final response
7. Manages conversation memory (both in-memory and DB persistence)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.llm_client import LLMClient, LLMMessage, LLMResponse, LLMToolCall
from app.ai_core.llm_router import llm_router
from app.ai_core.prompt_safety import PromptSafety
from app.agents.base import AgentContext, orchestrator
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.agent_models import AgentConversation, AgentMessage, AgentToolExecution, AgentActivityLog
from app.memory.conversation_memory import conversation_memory
from app.rag.retriever import rag_retriever, RAGRetriever
from app.repositories.agent.agent_repo import (
    AgentConversationRepository, AgentMessageRepository,
    AgentToolExecutionRepository, AgentActivityLogRepository,
)
from app.tools import register_all_tools
from app.agents import register_all_agents
from app.tools.executor import tool_executor

logger = get_logger(__name__)
settings = get_settings()

_initialized = False


def _safe_uuid(val: str | None) -> uuid.UUID:
    if not val:
        return uuid.uuid4()
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        import hashlib
        return uuid.UUID(hashlib.md5(str(val).encode("utf-8")).hexdigest())

def _ensure_initialized() -> None:
    global _initialized
    if not _initialized:
        register_all_tools()
        register_all_agents()
        _initialized = True


class ChatService:
    """Full-pipeline chat orchestration with tool calling and RAG."""

    def __init__(self, db: AsyncSession) -> None:
        _ensure_initialized()
        self._db = db
        self._safety = PromptSafety()
        self._conv_repo = AgentConversationRepository(db)
        self._msg_repo = AgentMessageRepository(db)
        self._tool_repo = AgentToolExecutionRepository(db)
        self._log_repo = AgentActivityLogRepository(db)

    async def chat(
        self,
        user_id: str,
        user_roles: list[str],
        message: str,
        conversation_id: str | None = None,
        user_name: str = "",
        user_email: str = "",
    ) -> dict:
        start = time.monotonic()

        valid, reason = self._safety.validate(message)
        if not valid:
            return self._build_error_response(reason, conversation_id, start)

        cid = conversation_memory.get_or_create_conversation(user_id, conversation_id)

        conv = None
        if conversation_id:
            try:
                conv = await self._conv_repo.get_with_messages(uuid.UUID(conversation_id))
            except (ValueError, Exception):
                conv = None

        if conv:
            db_messages = [
                {"role": m.role, "content": m.content, "agent_type": m.agent_type}
                for m in (conv.messages if hasattr(conv, "messages") else [])
            ]
            conversation_memory.load_from_messages(cid, user_id, db_messages)
        else:
            try:
                conv = await self._conv_repo.create(
                    user_id=_safe_uuid(user_id),
                    title=message[:100],
                    agent_type=orchestrator.route(message, user_roles),
                )
                await self._db.commit()
            except Exception as e:
                logger.warning(f"Could not persist conversation: {e}")
                await self._db.rollback()

        agent_type = orchestrator.route(message, user_roles)
        conversation_memory.update_context(cid, agent_type=agent_type, user_id=user_id)

        ctx = AgentContext(
            user_id=user_id,
            user_roles=user_roles,
            conversation_id=cid,
            user_name=user_name,
            user_email=user_email,
        )

        rag_context = await rag_retriever.build_context(message, top_k=3)
        citations = await rag_retriever.build_citations(message, top_k=3)

        agent = orchestrator.get_agent(agent_type) or orchestrator.get_agent("candidate")
        system_prompt = agent.get_system_prompt(ctx, rag_context) if agent else ""

        history = conversation_memory.get_history(cid, limit=20)
        messages = [LLMMessage(role="system", content=system_prompt)]
        for h in history:
            if h["role"] in ("user", "assistant"):
                messages.append(LLMMessage(role=h["role"], content=h["content"]))
        messages.append(LLMMessage(role="user", content=message))

        tools = agent.get_tools(ctx) if agent else []
        tool_calls_data = []

        response = await llm_router.chat(messages, tools=tools if tools else None)

        if response.tool_calls:
            for tc in response.tool_calls:
                result = await tool_executor.execute(tc.name, user_roles, tc.arguments)
                tool_calls_data.append(result)

            tool_summary = tool_executor.format_tool_results_for_llm(tool_calls_data)
            followup_messages = messages + [
                LLMMessage(role="assistant", content=""),
                LLMMessage(role="tool", content=tool_summary),
                LLMMessage(role="user", content=f"Based on these tool results, provide a clear, helpful summary. Original request: {message}"),
            ]
            final_response = await llm_router.chat(followup_messages)
            content = self._safety.filter_response(final_response.content)
            tokens = response.tokens_used + final_response.tokens_used
        else:
            content = self._safety.filter_response(response.content)
            tokens = response.tokens_used

        elapsed_ms = int((time.monotonic() - start) * 1000)

        conversation_memory.add_message(cid, "user", message)
        conversation_memory.add_message(cid, "assistant", content, agent_type=agent_type)

        try:
            await self._persist_messages(conv, message, content, agent_type, tool_calls_data, citations, tokens, user_id, elapsed_ms)
        except Exception as exc:
            logger.warning("Failed to persist chat messages: %s", exc)

        filtered_citations = [
            c for c in citations
            if self._safety.validate(c.get("excerpt", ""))[0]
        ]

        return {
            "conversation_id": str(conv.id if conv else cid),
            "message": {
                "role": "assistant",
                "content": content,
                "agent_type": agent_type,
                "citations": filtered_citations,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "tool_executions": [
                {
                    "id": tc.get("id", str(uuid.uuid4())),
                    "tool_name": tc.get("name", ""),
                    "arguments": tc.get("arguments", {}),
                    "result": tc.get("result"),
                    "status": "completed" if tc.get("success") else "failed",
                    "execution_time_ms": tc.get("execution_time_ms", 0),
                }
                for tc in tool_calls_data
            ],
            "agent_used": agent_type,
            "processing_time_ms": elapsed_ms,
            "provider_used": response.model,
            "tokens_used": tokens,
        }

    async def stream_chat(
        self,
        user_id: str,
        user_roles: list[str],
        message: str,
        conversation_id: str | None = None,
        user_name: str = "",
        user_email: str = "",
    ) -> AsyncIterator[str]:
        valid, reason = self._safety.validate(message)
        if not valid:
            yield json.dumps({"type": "error", "content": reason}) + "\n"
            return

        cid = conversation_memory.get_or_create_conversation(user_id, conversation_id)

        conv = None
        if conversation_id:
            try:
                conv = await self._conv_repo.get_with_messages(uuid.UUID(conversation_id))
            except (ValueError, Exception):
                conv = None

        if conv:
            db_messages = [
                {"role": m.role, "content": m.content, "agent_type": m.agent_type}
                for m in (conv.messages if hasattr(conv, "messages") else [])
            ]
            conversation_memory.load_from_messages(cid, user_id, db_messages)
        else:
            try:
                conv = await self._conv_repo.create(
                    user_id=_safe_uuid(user_id),
                    title=message[:100],
                    agent_type=orchestrator.route(message, user_roles),
                )
                await self._db.commit()
            except Exception as e:
                logger.warning(f"Could not persist conversation: {e}")
                await self._db.rollback()

        agent_type = orchestrator.route(message, user_roles)
        ctx = AgentContext(
            user_id=user_id,
            user_roles=user_roles,
            conversation_id=cid,
            user_name=user_name,
            user_email=user_email,
        )

        rag_context = await rag_retriever.build_context(message, top_k=3)
        citations = await rag_retriever.build_citations(message, top_k=3)

        agent = orchestrator.get_agent(agent_type) or orchestrator.get_agent("candidate")
        system_prompt = agent.get_system_prompt(ctx, rag_context) if agent else ""

        history = conversation_memory.get_history(cid, limit=20)
        messages = [LLMMessage(role="system", content=system_prompt)]
        for h in history:
            if h["role"] in ("user", "assistant"):
                messages.append(LLMMessage(role=h["role"], content=h["content"]))
        messages.append(LLMMessage(role="user", content=message))

        yield json.dumps({"type": "metadata", "conversation_id": str(conv.id if conv else cid), "agent_type": agent_type, "citations": citations}) + "\n"
        yield json.dumps({"type": "start", "content": ""}) + "\n"

        full_content = ""
        try:
            async for chunk in llm_router.stream_chat(messages):
                full_content += chunk
                yield json.dumps({"type": "delta", "content": chunk}) + "\n"
        except Exception as exc:
            logger.error("Streaming failed: %s", exc)
            yield json.dumps({"type": "error", "content": "I encountered an error. Please try again."}) + "\n"
            return

        full_content = self._safety.filter_response(full_content)
        conversation_memory.add_message(cid, "user", message)
        conversation_memory.add_message(cid, "assistant", full_content, agent_type=agent_type)

        try:
            await self._persist_messages(conv, message, full_content, agent_type, [], citations, 0, user_id, 0)
        except Exception as exc:
            logger.warning("Failed to persist streamed messages: %s", exc)

        yield json.dumps({"type": "done", "content": full_content, "agent_type": agent_type, "citations": citations}) + "\n"

    async def _persist_messages(
        self, conv, user_message: str, assistant_content: str,
        agent_type: str, tool_calls_data: list[dict], citations: list[dict],
        tokens: int, user_id: str, elapsed_ms: int,
    ) -> None:
        if conv is None:
            return
        user_msg = AgentMessage(
            conversation_id=conv.id,
            role="user",
            content=user_message,
        )
        self._db.add(user_msg)
        await self._db.flush()

        assistant_msg = AgentMessage(
            conversation_id=conv.id,
            role="assistant",
            content=assistant_content,
            agent_type=agent_type,
            tool_calls=tool_calls_data if tool_calls_data else None,
            citations=citations if citations else None,
            tokens_used=tokens,
        )
        self._db.add(assistant_msg)
        await self._db.flush()

        for tc in tool_calls_data:
            tool_exec = AgentToolExecution(
                conversation_id=conv.id,
                message_id=assistant_msg.id,
                tool_name=tc.get("name", ""),
                arguments=tc.get("arguments"),
                result=tc.get("result"),
                status="completed" if tc.get("success") else "failed",
                execution_time_ms=tc.get("execution_time_ms", 0),
            )
            self._db.add(tool_exec)

        try:
            activity = AgentActivityLog(
                user_id=_safe_uuid(user_id),
                agent_type=agent_type,
                action="chat",
                details={"message_length": len(user_message), "response_length": len(assistant_content)},
                tokens_used=tokens,
                latency_ms=elapsed_ms,
                success=True,
            )
            self._db.add(activity)
            await self._db.commit()
        except Exception as e:
            logger.warning(f"Could not persist activity log: {e}")
            await self._db.rollback()

    def _build_error_response(self, reason: str, conversation_id: str | None, start: float) -> dict:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "conversation_id": conversation_id or str(uuid.uuid4()),
            "message": {
                "role": "assistant",
                "content": reason,
                "agent_type": "base",
                "citations": [],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "tool_executions": [],
            "agent_used": "base",
            "processing_time_ms": elapsed_ms,
            "provider_used": "safety",
            "tokens_used": 0,
        }

    def list_agents(self) -> list[dict]:
        return orchestrator.list_agents()

    def list_tools(self) -> list[str]:
        return tool_executor.get_available_tools()

    def get_providers(self) -> list[dict]:
        return llm_router.list_providers()
