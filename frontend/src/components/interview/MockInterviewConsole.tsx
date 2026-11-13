import { useState } from "react";
import { QuestionCard } from "./QuestionCard";
import { AnswerPanel } from "./AnswerPanel";
import { FeedbackCard } from "./FeedbackCard";
import type { InterviewQuestion, InterviewEvaluation } from "../../types/interview";

export function MockInterviewConsole({
  questions,
  onSubmitAnswer,
  onComplete,
}: {
  questions: InterviewQuestion[];
  onSubmitAnswer: (questionId: string, answer: string, timeSeconds: number) => Promise<InterviewEvaluation>;
  onComplete: () => void;
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [_answers, setAnswers] = useState<
    { questionId: string; evaluation: InterviewEvaluation }[]
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [latestEvaluation, setLatestEvaluation] = useState<InterviewEvaluation | null>(null);

  const currentQuestion = questions[currentIndex];
  const isLast = currentIndex >= questions.length - 1;

  const handleSubmit = async (answer: string, timeSeconds: number) => {
    if (!currentQuestion || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const evaluation = await onSubmitAnswer(currentQuestion.id, answer, timeSeconds);
      setLatestEvaluation(evaluation);
      setShowFeedback(true);
      setAnswers((prev) => [...prev, { questionId: currentQuestion.id, evaluation }]);
    } catch {
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNext = () => {
    setShowFeedback(false);
    setLatestEvaluation(null);
    if (isLast) {
      onComplete();
    } else {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  if (!currentQuestion) {
    return (
      <div className="text-center py-12">
        <p className="text-ink-muted">No questions available.</p>
        <button onClick={onComplete} className="mt-4 rounded-lg bg-primary-600 px-4 py-2 text-sm text-white">
          Complete Interview
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-ink">Mock Interview</h3>
          <p className="text-sm text-ink-muted">Question {currentIndex + 1} of {questions.length}</p>
        </div>
        <div className="flex items-center gap-2">
          {questions.map((_, idx) => (
            <div
              key={idx}
              className={`h-2 w-2 rounded-full ${
                idx < currentIndex
                  ? "bg-emerald-500"
                  : idx === currentIndex
                    ? "bg-primary-500"
                    : "bg-surface-muted"
              }`}
            />
          ))}
        </div>
      </div>

      <QuestionCard question={currentQuestion} index={currentIndex} />

      {showFeedback && latestEvaluation ? (
        <div className="space-y-4">
          <FeedbackCard evaluation={latestEvaluation} />
          <div className="flex justify-end">
            <button
              onClick={handleNext}
              className="rounded-lg bg-primary-600 px-5 py-2 text-sm font-medium text-white hover:bg-primary-700"
            >
              {isLast ? "Complete Interview" : "Next Question"}
            </button>
          </div>
        </div>
      ) : (
        <AnswerPanel onSubmit={handleSubmit} disabled={isSubmitting} />
      )}
    </div>
  );
}
