import { Sparkles } from "lucide-react";

interface Props {
  prompts: string[];
  onSelect: (prompt: string) => void;
}

export function SuggestedPrompts({ prompts, onSelect }: Props) {
  if (prompts.length === 0) return null;

  return (
    <div className="animate-fade-up px-4 pb-2">
      <div className="section-label mb-2 flex items-center gap-1.5">
        <Sparkles className="h-3 w-3" aria-hidden="true" />
        Suggested
      </div>
      <div className="flex flex-wrap gap-2">
        {prompts.map((p, i) => (
          <button
            key={i}
            onClick={() => onSelect(p)}
            className="chip bg-primary-50/60 text-primary-700 hover:bg-primary-50"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
