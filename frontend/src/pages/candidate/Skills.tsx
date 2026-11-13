import { useCallback, useEffect, useState } from "react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import type { CandidateSkill, Skill } from "../../types/candidate";

const proficiencyOptions = ["beginner", "intermediate", "advanced", "expert"];

export function CandidateSkills() {
  const [skills, setSkills] = useState<CandidateSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Skill[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [proficiency, setProficiency] = useState("intermediate");
  const [years, setYears] = useState("");

  const fetch = useCallback(async () => {
    try { setSkills(await candidateApi.listSkills()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const handleSearch = async (q: string) => {
    setSearchQuery(q);
    if (q.length < 2) { setSearchResults([]); return; }
    try { setSearchResults(await candidateApi.searchSkills(q)); }
    catch { setSearchResults([]); }
  };

  const handleAdd = async () => {
    if (!selectedSkill) return;
    await candidateApi.addSkill({
      skill_id: selectedSkill.id,
      proficiency,
      years_of_experience: years ? parseFloat(years) : null,
    });
    setSelectedSkill(null);
    setSearchQuery("");
    setSearchResults([]);
    setProficiency("intermediate");
    setYears("");
    await fetch();
  };

  const handleRemove = async (skillId: number) => {
    await candidateApi.removeSkill(skillId);
    await fetch();
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl animate-fade-up space-y-6">
      <div className="page-header">
        <h1 className="page-title">Skills</h1>
        <p className="page-subtitle">Add and manage your skills</p>
      </div>

      <section className="card space-y-4">
        <h2 className="section-title">Add Skill</h2>
        <div className="relative">
          <Input
            label="Search Skills"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Type to search..."
          />
          {searchResults.length > 0 && (
            <div className="absolute z-10 mt-1 w-full overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg max-h-40">
              {searchResults.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`w-full px-3 py-2 text-left text-sm transition-colors hover:bg-gray-50 focus:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                    selectedSkill?.id === s.id ? "bg-indigo-50 text-indigo-700" : "text-gray-700"
                  }`}
                  onClick={() => { setSelectedSkill(s); setSearchResults([]); setSearchQuery(s.name); }}
                >
                  {s.name}
                  <span className="ml-2 text-xs text-gray-400">({s.category})</span>
                </button>
              ))}
            </div>
          )}
        </div>
        {selectedSkill && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg bg-indigo-50/60 p-3">
            <span className="chip text-indigo-700">
              {selectedSkill.name}
            </span>
            <select
              value={proficiency}
              onChange={(e) => setProficiency(e.target.value)}
              className="field w-auto text-sm"
              aria-label="Proficiency"
            >
              {proficiencyOptions.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <Input
              placeholder="Years"
              type="number"
              step="0.5"
              value={years}
              onChange={(e) => setYears(e.target.value)}
              className="w-20"
            />
            <Button size="sm" onClick={handleAdd}>Add</Button>
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="section-title mb-4">Your Skills ({skills.length})</h2>
        {skills.length === 0 ? (
          <div className="empty-state">
            <p className="text-sm text-gray-400">No skills added yet.</p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {skills.map((cs) => (
              <div
                key={cs.skill_id}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm transition-colors hover:border-indigo-200 hover:bg-indigo-50/50"
              >
                <span className="font-medium text-gray-900">{cs.skill?.name || `Skill #${cs.skill_id}`}</span>
                <span className="text-xs text-gray-400">({cs.proficiency})</span>
                <button
                  onClick={() => handleRemove(cs.skill_id)}
                  aria-label={`Remove ${cs.skill?.name || `Skill #${cs.skill_id}`}`}
                  className="ml-1 rounded p-0.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
