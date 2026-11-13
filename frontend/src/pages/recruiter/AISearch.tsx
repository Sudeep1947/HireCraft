import { useState } from "react";

import { useToast } from "../../contexts/ToastContext";
import { aiSearch } from "../../api/screening";
import type { AISearchResultItem, AISearchResponse } from "../../types/screening";

const SUGGESTION_QUERIES = [
  "Python developers with AWS",
  "React developers with 3 years experience",
  "Java Backend candidates",
  "Machine Learning Engineers",
  "Full stack developers with TypeScript",
  "DevOps engineers with Kubernetes",
  "Senior frontend developers remote",
  "Data scientists with Python and TensorFlow",
];

export function AISearchPage() {
  const { addToast } = useToast();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AISearchResponse | null>(null);
  const [searched, setSearched] = useState(false);

  async function handleSearch(q?: string) {
    const searchQuery = q || query;
    if (!searchQuery.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const data = await aiSearch({ query: searchQuery, limit: 20 });
      setResults(data);
    } catch {
      addToast("Search failed. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSearch();
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="page-title">AI Candidate Search</h1>
        <p className="page-subtitle">Search candidates using natural language</p>
      </div>

      <div className="card p-6">
        <div className="flex gap-3">
          <label className="sr-only" htmlFor="ai-search-input">Search candidates</label>
          <input
            id="ai-search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='e.g. "Python developers with AWS experience"'
            className="field flex-1"
          />
          <button
            onClick={() => handleSearch()}
            disabled={loading || !query.trim()}
            className="btn-primary btn-md px-6"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>

        {!searched && (
          <div className="mt-4">
            <p className="section-label mb-2">Try these queries</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTION_QUERIES.map((sq) => (
                <button
                  key={sq}
                  onClick={() => { setQuery(sq); handleSearch(sq); }}
                  className="chip"
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {loading && (
        <div className="space-y-3" aria-busy="true" aria-label="Searching candidates">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-5 w-48" />
              <div className="skeleton mt-2 h-4 w-64" />
              <div className="skeleton mt-3 h-4 w-full" />
            </div>
          ))}
        </div>
      )}

      {results && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Found <span className="font-bold text-gray-900">{results.total}</span> candidates
              {results.query_skills.length > 0 && (
                <span className="ml-2">
                  matching <span className="font-medium text-primary-600">{results.query_skills.join(", ")}</span>
                </span>
              )}
            </p>
          </div>

          {results.results.length === 0 ? (
            <div className="empty-state">
              <svg className="mb-3 h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607z" />
              </svg>
              <h3 className="text-base font-semibold text-gray-900">No candidates found</h3>
              <p className="mt-1 text-sm text-gray-500">No candidates found matching your query. Try broadening your search.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {results.results.map((r) => (
                <SearchResultCard key={r.candidate_id} result={r} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SearchResultCard({ result }: { result: AISearchResultItem }) {
  const relevanceColor =
    result.relevance_score >= 80 ? "badge-success" :
    result.relevance_score >= 60 ? "badge-info" :
    result.relevance_score >= 40 ? "badge-warning" :
    "badge-danger";

  const recLabel = result.recommendation.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const recColor =
    result.recommendation === "strongly_recommend" ? "badge-success" :
    result.recommendation === "recommend" ? "badge-info" :
    result.recommendation === "consider" ? "badge-warning" :
    result.recommendation === "not_recommended" ? "badge-danger" :
    "badge-neutral";

  return (
    <div className="card card-hover p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-gray-900">{result.candidate_name}</h3>
            <span className={`badge ${relevanceColor}`}>
              {result.relevance_score}% match
            </span>
            {result.overall_score > 0 && (
              <span className={`badge ${
                result.overall_score >= 80 ? "badge-success" :
                result.overall_score >= 60 ? "badge-info" :
                "badge-warning"
              }`}>
                Score: {result.overall_score}%
              </span>
            )}
          </div>
          <p className="mt-0.5 text-sm text-gray-500">{result.candidate_email}</p>
          <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
            {result.experience_years > 0 && <span>{result.experience_years} years exp</span>}
            {result.location && <span>{result.location}</span>}
          </div>
        </div>
        <span className={`badge ${recColor}`}>
          {recLabel}
        </span>
      </div>

      {result.matched_skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {result.matched_skills.slice(0, 8).map((s) => (
            <span key={s} className="badge badge-success">{s}</span>
          ))}
        </div>
      )}
      {result.missing_skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {result.missing_skills.slice(0, 5).map((s) => (
            <span key={s} className="badge badge-danger">{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}
