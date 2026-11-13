"""Base agent class and agent orchestrator for the multi-agent system."""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.ai_core.llm_client import LLMClient, LLMMessage, LLMResponse, llm_client
from app.ai_core.prompt_safety import PromptSafety
from app.core.logging import get_logger
from app.memory.conversation_memory import conversation_memory
from app.rag.retriever import rag_retriever, RAGRetriever
from app.tools.registry import tool_registry

logger = get_logger(__name__)


@dataclass
class AgentContext:
    user_id: str
    user_roles: list[str]
    conversation_id: str
    user_name: str = ""
    user_email: str = ""


class BaseAgent(ABC):
    agent_type: str = "base"
    description: str = "Base agent"
    capabilities: list[str] = []

    def __init__(
        self,
        llm: LLMClient | None = None,
        retriever: RAGRetriever | None = None,
    ) -> None:
        self._llm = llm or llm_client
        self._retriever = retriever or rag_retriever
        self._safety = PromptSafety()

    @abstractmethod
    def get_system_prompt(self, ctx: AgentContext, rag_context: str = "") -> str:
        ...

    def get_tools(self, ctx: AgentContext) -> list[dict]:
        primary_role = ctx.user_roles[0] if ctx.user_roles else "candidate"
        return tool_registry.get_definitions_for_role(primary_role)

    async def process(
        self,
        message: str,
        ctx: AgentContext,
    ) -> dict:
        start = time.monotonic()

        valid, reason = self._safety.validate(message)
        if not valid:
            return {
                "content": reason,
                "agent_type": self.agent_type,
                "tool_calls": [],
                "tokens_used": 0,
                "latency_ms": 0,
                "citations": [],
            }

        rag_context = await self._retriever.build_context(message, top_k=3)
        citations = await self._retriever.build_citations(message, top_k=3)

        system_prompt = self.get_system_prompt(ctx, rag_context)
        history = conversation_memory.get_history(ctx.conversation_id, limit=20)

        messages = [LLMMessage(role="system", content=system_prompt)]
        for h in history:
            if h["role"] in ("user", "assistant"):
                messages.append(LLMMessage(role=h["role"], content=h["content"]))
        messages.append(LLMMessage(role="user", content=message))

        tools = self.get_tools(ctx)
        response = await self._llm.chat(messages, tools=tools if tools else None)

        tool_results = []
        if response.tool_calls:
            for tc in response.tool_calls:
                result = await tool_registry.execute(
                    tc.name, ctx.user_roles, **tc.arguments
                )
                tool_results.append({
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": result,
                })

            tool_summary = "\n".join(
                f"Tool '{tr['name']}' result: {json.dumps(tr['result'].get('result', tr['result']))}"
                for tr in tool_results
            )
            followup_messages = messages + [
                LLMMessage(role="assistant", content=""),
                LLMMessage(role="tool", content=tool_summary),
                LLMMessage(role="user", content=f"Based on these tool results, please provide a clear summary for the user. Original request: {message}"),
            ]
            final_response = await self._llm.chat(followup_messages)
            content = final_response.content
            tokens = response.tokens_used + final_response.tokens_used
        else:
            content = response.content
            tokens = response.tokens_used

        elapsed = int((time.monotonic() - start) * 1000)

        conversation_memory.add_message(ctx.conversation_id, "user", message)
        conversation_memory.add_message(ctx.conversation_id, "assistant", content, agent_type=self.agent_type)

        return {
            "content": content,
            "agent_type": self.agent_type,
            "tool_calls": tool_results,
            "tokens_used": tokens,
            "latency_ms": elapsed,
            "citations": citations,
        }


class AgentOrchestrator:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.agent_type] = agent

    def get_agent(self, agent_type: str) -> BaseAgent | None:
        return self._agents.get(agent_type)

    def route(self, message: str, user_roles: list[str]) -> str:
        m = message.lower()
        if any(kw in m for kw in ["resume", "cv", "parse"]):
            return "resume"
        if any(kw in m for kw in ["fairness", "bias", "diversity", "adversarial"]):
            return "fairness"
        if any(kw in m for kw in ["interview", "question", "schedule interview"]):
            return "interview"
        if any(kw in m for kw in ["report", "export", "summary report"]):
            return "report"
        if any(kw in m for kw in ["analytics", "metrics", "kpi", "trend"]):
            return "analytics"
        if any(kw in m for kw in ["match", "matching", "best fit"]):
            return "job_matching"
        if "admin" in user_roles or "super_admin" in user_roles:
            if any(kw in m for kw in ["user", "audit", "security", "system", "login", "health"]):
                return "admin"
        if "hr" in user_roles or "hr_manager" in user_roles or "organization_admin" in user_roles:
            if any(kw in m for kw in ["hiring", "pipeline", "headcount", "recruiter performance"]):
                return "hr"
        if "recruiter" in user_roles or "hr" in user_roles or "hr_manager" in user_roles:
            if any(kw in m for kw in ["candidate", "rank", "compare", "shortlist", "search candidate", "job"]):
                return "recruiter"
        if "candidate" in user_roles:
            return "candidate"
        if "recruiter" in user_roles:
            return "recruiter"
        if "hr" in user_roles or "hr_manager" in user_roles or "organization_admin" in user_roles:
            return "hr"
        if "admin" in user_roles or "super_admin" in user_roles:
            return "admin"
        return "candidate"

    async def process(self, message: str, ctx: AgentContext) -> dict:
        agent_type = self.route(message, ctx.user_roles)
        agent = self._agents.get(agent_type)
        if not agent:
            agent = self._agents.get("candidate")
        if not agent:
            return {
                "content": "I'm unable to process your request right now. Please try again.",
                "agent_type": "unknown",
                "tool_calls": [],
                "tokens_used": 0,
                "latency_ms": 0,
                "citations": [],
            }

        return await agent.process(message, ctx)

    def list_agents(self) -> list[dict]:
        return [
            {"type": a.agent_type, "description": a.description, "capabilities": a.capabilities}
            for a in self._agents.values()
        ]


orchestrator = AgentOrchestrator()
