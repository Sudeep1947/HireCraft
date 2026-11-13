import { useEffect, useRef, useState } from "react";
import { simulationApi } from "../../api/simulations";
import type { SimulationScenarioListItem } from "../../types/simulations";
import type {
  ChatMessage,
  NLInterpretResponse,
  ProposalChange,
  SimulationIntent,
} from "../../types/simulationIntent";
import { SUGGESTION_PROMPTS } from "../../types/simulationIntent";

let msgId = 0;
function nextId() {
  return `msg-${++msgId}-${Date.now()}`;
}

export function SimulationAssistant() {
  const [scenarios, setScenarios] = useState<SimulationScenarioListItem[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setListLoading(true);
    simulationApi
      .list()
      .then((res) => {
        const completed = (res.items || []).filter(
          (s: SimulationScenarioListItem) => s.status === "completed" || s.status === "ready" || s.status === "draft",
        );
        setScenarios(completed);
        if (completed.length > 0) {
          setSelectedJobId(completed[0].job_id);
        }
      })
      .catch(console.error)
      .finally(() => setListLoading(false));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const selectedScenario = scenarios.find((s) => s.job_id === selectedJobId);

  const handleSend = async (text?: string) => {
    const message = (text || input).trim();
    if (!message || !selectedJobId || loading) return;

    setInput("");
    const userMsg: ChatMessage = {
      id: nextId(),
      role: "user",
      content: message,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);

    const loadingMsg: ChatMessage = {
      id: nextId(),
      role: "agent",
      content: "Interpreting your request...",
      timestamp: new Date(),
      isLoading: true,
    };
    setMessages((prev) => [...prev, loadingMsg]);
    setLoading(true);

    try {
      const result = await simulationApi.interpretNL({
        job_id: selectedJobId,
        message,
      });

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: result.message || buildInterpretMessage(result),
                proposal: result.proposal,
                intent: result.intent,
                validationErrors: result.validation_errors,
                canExecute: result.can_execute,
                isLoading: false,
              }
            : m,
        ),
      );
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to interpret request. Please try again.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: msg, isLoading: false }
            : m,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (
    intent: SimulationIntent,
    _proposal: ProposalChange[],
    scenarioName?: string,
  ) => {
    if (!selectedJobId) return;

    const loadingMsg: ChatMessage = {
      id: nextId(),
      role: "agent",
      content: "Creating scenario...",
      timestamp: new Date(),
      isLoading: true,
    };
    setMessages((prev) => [...prev, loadingMsg]);
    setLoading(true);

    try {
      const result = await simulationApi.confirmNL({
        job_id: selectedJobId,
        intent,
        scenario_name:
          scenarioName ||
          `NL: ${intent.natural_language_request.slice(0, 80)}`,
        scenario_description: `Created via natural language: ${intent.natural_language_request}`,
      });

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: `${result.message}\n\nScenario ID: ${result.scenario_id}\nStatus: ${result.status}`,
                scenarioId: result.scenario_id,
                isLoading: false,
              }
            : m,
        ),
      );
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to create scenario.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id ? { ...m, content: msg, isLoading: false } : m,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header */}
      <div>
        <h1 className="page-title">
          Simulation Assistant
        </h1>
        <p className="page-subtitle">
          Describe what you want to simulate in natural language. The agent will
          interpret your request, propose changes, and create a simulation
          scenario.
        </p>
      </div>

      {/* What-if banner */}
      <div className="info-banner">
        <p>
          <strong>What-if analysis</strong> — This assistant creates hypothetical
          simulations. No live hiring data or configuration will be modified.
        </p>
      </div>

      {/* Job selector */}
      <div className="card p-4">
        <label className="field-label">
          Select Job
        </label>
        {listLoading ? (
          <div className="skeleton h-10 w-full" />
        ) : (
          <select
            className="field"
            value={selectedJobId || ""}
            onChange={(e) => setSelectedJobId(e.target.value || null)}
          >
            {scenarios.length === 0 ? (
              <option value="">No scenarios available</option>
            ) : (
              <>
                <option value="">Select a job...</option>
                {[...new Map(scenarios.map((s) => [s.job_id, s])).values()].map(
                  (s) => (
                    <option key={s.job_id} value={s.job_id}>
                      {s.job_title || "Untitled Job"}
                      {s.company ? ` — ${s.company}` : ""}
                    </option>
                  ),
                )}
              </>
            )}
          </select>
        )}
        {selectedScenario && (
          <p className="field-hint">
            Based on scenario: {selectedScenario.name}
          </p>
        )}
      </div>

      {/* Suggestion prompts */}
      {messages.length === 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Try asking:
          </h3>
          <div className="flex flex-wrap gap-2">
            {SUGGESTION_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                className="chip"
                onClick={() => handleSend(prompt)}
                disabled={loading || !selectedJobId}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat messages */}
      <div className="space-y-4">
        {messages.map((msg) => (
          <ChatBubble
            key={msg.id}
            message={msg}
            onConfirm={handleConfirm}
            loading={loading}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="card sticky bottom-0 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            className="field flex-1"
            placeholder={
              selectedJobId
                ? "e.g. What if experience becomes 40%?"
                : "Select a job first"
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            disabled={loading || !selectedJobId}
          />
          <button
            className="btn-primary"
            onClick={() => handleSend()}
            disabled={loading || !input.trim() || !selectedJobId}
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Chat Bubble ─────────────────────────────────────────────── */

function ChatBubble({
  message,
  onConfirm,
  loading,
}: {
  message: ChatMessage;
  onConfirm: (
    intent: SimulationIntent,
    proposal: ProposalChange[],
    name?: string,
  ) => Promise<void>;
  loading: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-3xl rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-brand-gradient text-white shadow-glow-sm"
            : "card text-gray-900"
        }`}
      >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600" aria-hidden="true" />
            <span className="text-sm">{message.content}</span>
          </div>
        ) : (
          <>
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>

            {/* Proposal card */}
            {message.proposal && message.proposal.length > 0 && (
              <ProposalCard
                proposal={message.proposal}
                intent={message.intent!}
                canExecute={message.canExecute || false}
                validationErrors={message.validationErrors}
                onConfirm={onConfirm}
                loading={loading}
              />
            )}

            {/* Scenario link */}
            {message.scenarioId && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <a
                  href={`/recruiter/simulations/${message.scenarioId}`}
                  className="text-sm font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
                >
                  View Scenario →
                </a>
                <span className="mx-2 text-gray-300" aria-hidden="true">|</span>
                <a
                  href={`/recruiter/simulations/${message.scenarioId}/results`}
                  className="text-sm font-medium text-primary-600 transition-colors duration-200 hover:text-primary-700"
                >
                  View Results →
                </a>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ─── Proposal Card ──────────────────────────────────────────── */

function ProposalCard({
  proposal,
  intent,
  canExecute,
  validationErrors,
  onConfirm,
  loading,
}: {
  proposal: ProposalChange[];
  intent: SimulationIntent;
  canExecute: boolean;
  validationErrors?: { field: string; message: string }[];
  onConfirm: (
    intent: SimulationIntent,
    proposal: ProposalChange[],
    name?: string,
  ) => Promise<void>;
  loading: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [scenarioName, setScenarioName] = useState("");

  const categoryIcons: Record<string, string> = {
    "Scoring Weight": "⚖️",
    Threshold: "📊",
    Shortlist: "📋",
    "Skill Requirement": "🛠️",
    Experience: "💼",
    Education: "🎓",
    Preset: "⚡",
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-gray-200/80 bg-white/90">
      <div className="border-b border-gray-200/80 bg-gray-50/80 px-3 py-2">
        <h4 className="text-sm font-semibold text-gray-900">
          Simulation Proposal
        </h4>
      </div>
      <div className="p-3 space-y-2">
        {proposal.map((p, i) => (
          <div key={i} className="flex items-center gap-3 text-sm">
            <span className="text-base" aria-hidden="true">{categoryIcons[p.category] || "📝"}</span>
            <div className="flex-1">
              <span className="font-medium text-gray-900">{p.label}</span>
              <span className="text-gray-400 mx-1">·</span>
              <span className="text-gray-500">{p.baseline}</span>
              <span className="text-gray-400 mx-1" aria-hidden="true">→</span>
              <span className="text-gray-900 font-medium">{p.proposed}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Validation errors */}
      {validationErrors && validationErrors.length > 0 && (
        <div className="border-t border-red-200/70 bg-red-50/80 px-3 py-2">
          <p className="mb-1 text-xs font-semibold text-red-700">
            Validation issues:
          </p>
          {validationErrors.map((e, i) => (
            <p key={i} className="text-xs text-red-600">
              • {e.field}: {e.message}
            </p>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 border-t border-gray-200/80 bg-gray-50/60 px-3 py-2">
        {canExecute ? (
          editing ? (
            <div className="flex-1 flex items-center gap-2">
              <input
                type="text"
                className="field flex-1 py-1.5"
                placeholder="Scenario name"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
              />
              <button
                className="btn-primary btn-sm"
                onClick={() =>
                  onConfirm(intent, proposal, scenarioName || undefined)
                }
                disabled={loading}
              >
                Confirm & Create
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>
            </div>
          ) : (
            <>
              <button
                className="btn-primary btn-sm"
                onClick={() => onConfirm(intent, proposal)}
                disabled={loading}
              >
                Run Simulation
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() => setEditing(true)}
              >
                Edit Name
              </button>
            </>
          )
        ) : (
          <p className="text-xs font-medium text-amber-600">
            Cannot execute — fix validation issues above.
          </p>
        )}
      </div>
    </div>
  );
}

/* ─── Helpers ─────────────────────────────────────────────────── */

function buildInterpretMessage(result: NLInterpretResponse): string {
  const { intent, proposal, validation_errors } = result;

  if (intent.clarifications_required.length > 0) {
    return (
      "I need some clarification:\n" +
      intent.clarifications_required.map((c) => `• ${c.question}`).join("\n")
    );
  }

  if (intent.unsupported_requests.length > 0) {
    return (
      "I can't process the following:\n" +
      intent.unsupported_requests.map((u) => `• ${u}`).join("\n") +
      "\n\nThe simulation system supports: scoring weights, thresholds, " +
      "shortlist sizes, skill requirements, experience, and education changes."
    );
  }

  if (validation_errors.length > 0) {
    return (
      "The proposed configuration has issues:\n" +
      validation_errors.map((e) => `• ${e.field}: ${e.message}`).join("\n")
    );
  }

  if (proposal.length > 0) {
    return `I'll simulate ${proposal.length} change(s). Review the proposal below.`;
  }

  return "I interpreted your request but found no specific changes to simulate.";
}
