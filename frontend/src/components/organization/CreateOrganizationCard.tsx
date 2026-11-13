import { useRef, useState } from "react";

import * as authApi from "../../api/auth";
import type { Organization } from "../../types/auth";
import { getServerErrorMessage } from "../../utils/error";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const URL_REGEX = /^https?:\/\/(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:\/.*)?$/i;
const ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/svg+xml"];
const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5 MB

interface CreateOrganizationCardProps {
  /**
   * Called after the server confirms creation. The callback may refresh any
   * list the host page owns; a failure there must not turn a successful create
   * into an error message.
   */
  onCreated?: (organization: Organization) => void | Promise<void>;
  onCancel?: () => void;
  className?: string;
}

export function CreateOrganizationCard({
  onCreated,
  onCancel,
  className = "",
}: CreateOrganizationCardProps) {
  const [form, setForm] = useState({
    name: "",
    slug: "",
    industry: "",
    website: "",
    location: "",
    description: "",
    status: "active" as "active" | "inactive",
  });
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string>("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Closes the gap between the first click and React applying the disabled
  // state, so a double-click can never submit twice.
  const createInFlight = useRef(false);

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError("");
    const file = e.target.files?.[0];
    if (!file) {
      setLogoFile(null);
      setLogoPreview("");
      return;
    }

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setError("Invalid image file format. Allowed: PNG, JPG, WebP, SVG.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setError("Logo file size exceeds the 5 MB limit.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setLogoFile(file);
    try {
      setLogoPreview(URL.createObjectURL(file));
    } catch {
      setLogoPreview("");
    }
  };

  const handleRemoveLogo = () => {
    setLogoFile(null);
    setLogoPreview("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (createInFlight.current) return;

    const name = form.name.trim();
    const slug = form.slug.trim();
    const website = form.website.trim();
    setError("");
    setSuccess("");

    if (!name) {
      setError("Organization name is required.");
      return;
    }
    if (name.length > 255) {
      setError("Organization name must be at most 255 characters.");
      return;
    }
    if (!slug) {
      setError("Organization slug is required.");
      return;
    }
    if (slug.length > 100) {
      setError("Organization slug must be at most 100 characters.");
      return;
    }
    if (!SLUG_PATTERN.test(slug)) {
      setError(
        "Slug must use lowercase letters, numbers, and single hyphens (for example, acme-corp)."
      );
      return;
    }
    if (website && !URL_REGEX.test(website)) {
      setError("Invalid website URL format. Must start with http:// or https:// (e.g. https://company.com).");
      return;
    }

    createInFlight.current = true;
    setIsCreating(true);
    try {
      let logoUrl: string | undefined = undefined;
      if (logoFile) {
        try {
          const uploadRes = await authApi.uploadOrganizationLogo(logoFile);
          logoUrl = uploadRes.logo_url;
        } catch (uploadErr) {
          setError(getServerErrorMessage(uploadErr, "Failed to upload organization logo."));
          createInFlight.current = false;
          setIsCreating(false);
          return;
        }
      }

      const created = await authApi.createOrganization({
        name,
        slug,
        industry: form.industry.trim() || undefined,
        website: website || undefined,
        location: form.location.trim() || undefined,
        description: form.description.trim() || undefined,
        status: form.status,
        logo_url: logoUrl,
      });

      setForm({
        name: "",
        slug: "",
        industry: "",
        website: "",
        location: "",
        description: "",
        status: "active",
      });
      handleRemoveLogo();
      setSlugEdited(false);
      setSuccess(`Organization "${created.name}" created successfully.`);

      try {
        await onCreated?.(created);
      } catch {
        // The host owns its refresh error handling.
      }
    } catch (err) {
      setError(getServerErrorMessage(err, "Failed to create organization."));
    } finally {
      createInFlight.current = false;
      setIsCreating(false);
    }
  };

  return (
    <div className={`card p-6 ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 border border-primary-100">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </div>
          <div>
            <h2 className="section-title">Create Organization</h2>
            <p className="text-sm text-gray-500">
              Create an organization record to manage teams, jobs, and access.
            </p>
          </div>
        </div>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Organization Name"
            type="text"
            name="organization-name"
            value={form.name}
            maxLength={255}
            onChange={(event) => {
              const name = event.target.value;
              setError("");
              setSuccess("");
              setForm((previous) => ({
                ...previous,
                name,
                slug: slugEdited
                  ? previous.slug
                  : name
                      .trim()
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-+|-+$/g, ""),
              }));
            }}
            placeholder="e.g. Acme Corp, Amazon, Flipkart, Infosys"
            required
          />
          <Input
            label="Slug (URL-friendly identifier)"
            type="text"
            name="organization-slug"
            value={form.slug}
            maxLength={100}
            onChange={(event) => {
              setSlugEdited(true);
              setError("");
              setSuccess("");
              setForm((previous) => ({
                ...previous,
                slug: event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
              }));
            }}
            placeholder="acme-corp"
            required
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Industry"
            type="text"
            name="organization-industry"
            value={form.industry}
            maxLength={255}
            onChange={(event) => {
              setError("");
              setForm((p) => ({ ...p, industry: event.target.value }));
            }}
            placeholder="e.g. Technology, Finance, Healthcare"
          />
          <Input
            label="Company Website"
            type="url"
            name="organization-website"
            value={form.website}
            maxLength={500}
            onChange={(event) => {
              setError("");
              setForm((p) => ({ ...p, website: event.target.value }));
            }}
            placeholder="https://company.com"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Headquarters / Location"
            type="text"
            name="organization-location"
            value={form.location}
            maxLength={255}
            onChange={(event) => {
              setError("");
              setForm((p) => ({ ...p, location: event.target.value }));
            }}
            placeholder="e.g. Bangalore, India or Seattle, WA"
          />
          <div>
            <label className="field-label" htmlFor="organization-status">
              Organization Status
            </label>
            <select
              id="organization-status"
              name="organization-status"
              value={form.status}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  status: e.target.value as "active" | "inactive",
                }))
              }
              className="field"
              aria-label="Organization Status"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        {/* Logo Upload */}
        <div>
          <label className="field-label" htmlFor="organization-logo">
            Organization Logo (Optional)
          </label>
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-dashed border-gray-200 p-3 bg-gray-50/50">
            {logoPreview && (
              <div className="relative">
                <img
                  src={logoPreview}
                  alt="Logo preview"
                  className="h-12 w-12 rounded-xl object-contain bg-white p-1 ring-1 ring-gray-200"
                />
              </div>
            )}
            <div className="flex-1 min-w-[200px]">
              <input
                id="organization-logo"
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                onChange={handleLogoChange}
                aria-label="Organization Logo"
                className="text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 cursor-pointer"
              />
              <p className="mt-1 text-[11px] text-gray-400">
                PNG, JPG, WebP, or SVG (max 5 MB)
              </p>
            </div>
            {logoFile && (
              <button
                type="button"
                onClick={handleRemoveLogo}
                className="text-xs font-medium text-red-600 hover:text-red-700 hover:underline"
              >
                Remove
              </button>
            )}
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="field-label" htmlFor="organization-description">
            Description (Optional)
          </label>
          <textarea
            id="organization-description"
            name="organization-description"
            value={form.description}
            maxLength={2000}
            rows={3}
            onChange={(e) =>
              setForm((p) => ({ ...p, description: e.target.value }))
            }
            placeholder="Brief overview or mission of the organization..."
            className="field resize-none text-sm"
            aria-label="Description"
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          {onCancel && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onCancel}
              disabled={isCreating}
            >
              Cancel
            </Button>
          )}
          <Button
            type="submit"
            isLoading={isCreating}
            disabled={isCreating}
            size="sm"
          >
            Create Organization
          </Button>
        </div>
      </form>

      {error && (
        <div className="error-banner mt-3" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="success-banner mt-3" role="status">
          {success}
        </div>
      )}
    </div>
  );
}
