import { useState } from "react";
import type { CandidateProfile } from "../../types/candidate";
import { resolveAvatarUrl } from "../../utils/avatar";

interface WelcomeCardProps {
  fullName: string;
  profile: CandidateProfile;
}

export function WelcomeCard({ fullName, profile }: WelcomeCardProps) {
  const [imageError, setImageError] = useState(false);
  const avatarUrl = resolveAvatarUrl(profile?.avatar_url);

  const initials = fullName
    .split(" ")
    .filter(Boolean)
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "C";

  return (
    <div className="panel-dark relative overflow-hidden p-6">
      {/* Decorative glow orbs for depth on the brand panel. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-20 left-10 h-40 w-40 rounded-full bg-white/10 blur-2xl"
      />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          {avatarUrl && !imageError ? (
            <img
              src={avatarUrl}
              alt={fullName}
              onError={() => setImageError(true)}
              className="h-16 w-16 rounded-full border-2 border-white/30 object-cover shadow-soft"
            />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-white/30 bg-white/20 font-display text-xl font-bold">
              {initials}
            </div>
          )}
          <div>
            <h2 className="font-display text-xl font-bold text-white">{fullName}</h2>
            <p className="text-sm text-white/80">
              {profile.current_role || "Candidate"}
            </p>
          </div>
        </div>

        <div className="w-full sm:max-w-xs">
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/25">
              <div
                className="h-full rounded-full bg-white shadow-glow-sm transition-all duration-500"
                style={{ width: `${profile.profile_completion}%` }}
              />
            </div>
            <span className="text-sm font-semibold text-white">{profile.profile_completion}%</span>
          </div>
          <p className="mt-1 text-xs text-white/70">Profile completion</p>
        </div>
      </div>
    </div>
  );
}
