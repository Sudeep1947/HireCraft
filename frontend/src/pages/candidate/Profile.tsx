import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { IdentifierField } from "../../components/ui/IdentifierField";
import { Input } from "../../components/ui/Input";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { candidateApi } from "../../api/candidate";
import { useAuth } from "../../hooks/useAuth";
import type { CandidateProfile } from "../../types/candidate";
import { resolveAvatarUrl } from "../../utils/avatar";
import { validateProfileImage } from "../../utils/validation";

export function CandidateProfile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fetchProfile = useCallback(async () => {
    try {
      const data = await candidateApi.getProfile();
      setProfile(data);
    } catch {
      setError("Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    if (!profile) return;
    setProfile({ ...profile, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await candidateApi.updateProfile({
        phone: profile.phone,
        date_of_birth: profile.date_of_birth,
        gender: profile.gender,
        location: profile.location,
        nationality: profile.nationality,
        linkedin_url: profile.linkedin_url,
        github_url: profile.github_url,
        portfolio_url: profile.portfolio_url,
        website_url: profile.website_url,
        bio: profile.bio,
        current_role: profile.current_role,
      });
      setProfile(updated);
      setSuccess("Profile saved successfully");
    } catch {
      setError("Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [photoVersion, setPhotoVersion] = useState<number>(Date.now());
  const [imageLoadError, setImageLoadError] = useState(false);

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset input so selecting the same file triggers onChange
    e.target.value = "";

    // Image validation (Format & Size limit)
    const validationError = validateProfileImage(file);
    if (validationError) {
      setError(validationError);
      setSuccess("");
      return;
    }

    setUploadingAvatar(true);
    setError("");
    setSuccess("");
    setImageLoadError(false);

    try {
      const updated = await candidateApi.uploadAvatar(file);
      setProfile(updated);
      setPhotoVersion(Date.now());
      setSuccess("Profile photo updated successfully");
    } catch {
      setError("Failed to upload profile photo. Please try again.");
    } finally {
      setUploadingAvatar(false);
    }
  };

  const handleRemoveAvatar = async () => {
    setUploadingAvatar(true);
    setError("");
    setSuccess("");
    try {
      const updated = await candidateApi.removeAvatar();
      setProfile(updated);
      setPhotoVersion(Date.now());
      setImageLoadError(false);
      setSuccess("Profile photo removed successfully");
    } catch {
      setError("Failed to remove profile photo");
    } finally {
      setUploadingAvatar(false);
    }
  };

  if (loading) return <LoadingSpinner size="lg" className="mt-20" />;

  return (
    <div className="max-w-2xl space-y-6 animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">
            Manage your personal information
          </p>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="success-banner" role="status">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <span>{success}</span>
        </div>
      )}

      {/* The candidate's own account identifier, labelled. This is the same
          `users.id` value a recruiter sees as "Candidate ID" on an application,
          so when a hiring team asks for it, the candidate can find it here
          instead of guessing which number in the interface is the right one.
          It is read from the signed-in session, not fetched, and it identifies
          only the candidate reading it -- no other candidate, application,
          organization or recruiter identifier appears on this page. */}
      {user?.id ? (
        <section
          className="card p-5"
          data-testid="candidate-identity"
        >
          <h2 className="section-title">Your identifiers</h2>
          <p className="mt-0.5 text-xs text-gray-500">
            Quote your candidate ID if a hiring team asks for it when following
            up on an application.
          </p>
          <div className="mt-3">
            <IdentifierField
              label="Candidate ID"
              value={user.id}
              hint="Identifies your account, across all your applications."
              copyable
              fullWidth
            />
          </div>
        </section>
      ) : null}

      {(() => {
        const avatarUrl = resolveAvatarUrl(profile?.avatar_url, photoVersion);
        const candidateInitials = (user?.full_name || "Candidate")
          .split(" ")
          .filter(Boolean)
          .map((n) => n[0])
          .join("")
          .toUpperCase()
          .slice(0, 2) || "C";

        return (
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-gray-900">
                  Profile Photo <span className="ml-1 text-xs font-normal text-gray-400">Avatar</span>
                </h2>
                <p className="mt-0.5 text-xs text-gray-500">
                  Upload a photo for your candidate profile. Supported formats: JPG, PNG, WebP (max 5 MB).
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <div className="relative">
                {avatarUrl && !imageLoadError ? (
                  <img
                    src={avatarUrl}
                    alt="Profile Photo"
                    className="h-20 w-20 rounded-full border-2 border-primary-100 object-cover shadow-soft"
                    onError={() => setImageLoadError(true)}
                  />
                ) : (
                  <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-primary-100 bg-gradient-to-br from-primary-100 to-primary-200 font-display text-xl font-bold text-primary-700 shadow-soft">
                    {candidateInitials}
                  </div>
                )}
                {uploadingAvatar && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-full bg-gray-950/40 backdrop-blur-sm">
                    <LoadingSpinner size="sm" className="text-white" />
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-2 text-center sm:text-left">
                <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
                  <label
                    className={`btn-primary btn-md cursor-pointer ${
                      uploadingAvatar ? "cursor-not-allowed opacity-50" : ""
                    }`}
                  >
                    {uploadingAvatar ? (
                      <span className="flex items-center gap-1.5">
                        <LoadingSpinner size="sm" />
                        Uploading...
                      </span>
                    ) : profile?.avatar_url && !imageLoadError ? (
                      <span>Change Photo</span>
                    ) : (
                      <span>Upload Photo</span>
                    )}
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp"
                      className="hidden"
                      disabled={uploadingAvatar}
                      onChange={handleAvatarUpload}
                    />
                  </label>

                  {profile?.avatar_url && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRemoveAvatar}
                      disabled={uploadingAvatar}
                      className="border-gray-300 text-red-600 hover:bg-red-50 hover:text-red-700"
                    >
                      Remove
                    </Button>
                  )}
                </div>
                <p className="text-xs text-gray-500">
                  Recommended size: square image, at least 200x200px
                </p>
              </div>
            </div>
          </div>
        );
      })()}

      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <h2 className="section-title mb-4">
          Personal Information
        </h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Full Name"
            name="full_name"
            value={user?.full_name || ""}
            disabled
          />
          <Input
            label="Email"
            name="email"
            value={user?.email || ""}
            disabled
          />
        </div>

        <Input
          label="Current Role"
          name="current_role"
          value={profile?.current_role || ""}
          onChange={handleChange}
          placeholder="e.g. Senior Software Engineer"
        />

        <Input
          label="Phone"
          name="phone"
          value={profile?.phone || ""}
          onChange={handleChange}
          placeholder="+1 (555) 123-4567"
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Date of Birth"
            name="date_of_birth"
            type="date"
            value={profile?.date_of_birth || ""}
            onChange={handleChange}
          />
          <div className="space-y-1.5">
            <label className="field-label" htmlFor="profile-gender">Gender</label>
            <select
              id="profile-gender"
              name="gender"
              value={profile?.gender || ""}
              onChange={handleChange}
              className="field"
            >
              <option value="">Select</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
              <option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Location"
            name="location"
            value={profile?.location || ""}
            onChange={handleChange}
            placeholder="City, Country"
          />
          <Input
            label="Nationality"
            name="nationality"
            value={profile?.nationality || ""}
            onChange={handleChange}
          />
        </div>

        <div className="space-y-3">
          <h3 className="field-label">Links</h3>
          <Input
            label="LinkedIn URL"
            name="linkedin_url"
            value={profile?.linkedin_url || ""}
            onChange={handleChange}
            placeholder="https://linkedin.com/in/..."
          />
          <Input
            label="GitHub URL"
            name="github_url"
            value={profile?.github_url || ""}
            onChange={handleChange}
            placeholder="https://github.com/..."
          />
          <Input
            label="Portfolio URL"
            name="portfolio_url"
            value={profile?.portfolio_url || ""}
            onChange={handleChange}
          />
          <Input
            label="Website"
            name="website_url"
            value={profile?.website_url || ""}
            onChange={handleChange}
          />
        </div>

        <div className="space-y-1.5">
          <label className="field-label" htmlFor="profile-bio">Bio</label>
          <textarea
            id="profile-bio"
            name="bio"
            value={profile?.bio || ""}
            onChange={handleChange}
            rows={4}
            className="field resize-y"
            placeholder="Tell us about yourself..."
          />
        </div>

        <div className="pt-2">
          <Button type="submit" isLoading={saving}>
            Save Profile
          </Button>
        </div>
      </form>
    </div>
  );
}
