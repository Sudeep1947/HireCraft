import { useState, useEffect, useRef } from "react";

export function AnswerPanel({
  onSubmit,
  disabled = false,
}: {
  onSubmit: (answer: string, timeSeconds: number) => void;
  disabled?: boolean;
}) {
  const [answer, setAnswer] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const handleSubmit = () => {
    if (!answer.trim()) return;
    if (timerRef.current) clearInterval(timerRef.current);
    onSubmit(answer.trim(), elapsed);
    setAnswer("");
    setElapsed(0);
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-ink-muted">Your Answer</span>
        <span className={`text-sm font-mono ${elapsed > 120 ? "text-rose-500" : "text-ink-muted"}`}>
          {formatTime(elapsed)}
        </span>
      </div>
      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        disabled={disabled}
        placeholder="Type your answer here..."
        rows={6}
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm text-ink placeholder-ink-subtle focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-surface-muted"
      />
      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={disabled || !answer.trim()}
          className="rounded-lg bg-primary-600 px-5 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Submit Answer
        </button>
      </div>
    </div>
  );
}
