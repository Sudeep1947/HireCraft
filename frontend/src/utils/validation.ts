export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidPassword(password: string): boolean {
  return password.length >= 8;
}

export function hasMinLength(value: string, min: number): boolean {
  return value.length >= min;
}

export interface ValidationErrors {
  [key: string]: string;
}

export function getPasswordStrengthIssues(password: string): string[] {
  const issues: string[] = [];
  if (password.length < 8) issues.push("at least 8 characters");
  if (!/[A-Z]/.test(password)) issues.push("an uppercase letter");
  if (!/[a-z]/.test(password)) issues.push("a lowercase letter");
  if (!/[0-9]/.test(password)) issues.push("a digit");
  return issues;
}

export function getPasswordStrengthLevel(password: string): "weak" | "fair" | "strong" {
  const issues = getPasswordStrengthIssues(password);
  if (issues.length >= 3) return "weak";
  if (issues.length >= 1) return "fair";
  return "strong";
}

export function validateRegisterForm(data: {
  full_name: string;
  email: string;
  password: string;
  confirm_password?: string;
}): ValidationErrors {
  const errors: ValidationErrors = {};
  if (!hasMinLength(data.full_name, 1)) {
    errors.full_name = "Full name is required";
  }
  if (!isValidEmail(data.email)) {
    errors.email = "Invalid email address";
  }
  const issues = getPasswordStrengthIssues(data.password);
  if (issues.length > 0) {
    errors.password = `Password must contain ${issues.join(", ")}`;
  }
  if (data.confirm_password !== undefined && data.password !== data.confirm_password) {
    errors.confirm_password = "Passwords do not match";
  }
  return errors;
}

export function validateLoginForm(data: {
  email: string;
  password: string;
}): ValidationErrors {
  const errors: ValidationErrors = {};
  if (!isValidEmail(data.email)) {
    errors.email = "Invalid email address";
  }
  if (!hasMinLength(data.password, 1)) {
    errors.password = "Password is required";
  }
  return errors;
}

export const ALLOWED_PROFILE_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
export const MAX_PROFILE_IMAGE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

export function validateProfileImage(file: File): string | null {
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  const validMime = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
  ].includes(file.type);
  const validExt = ALLOWED_PROFILE_IMAGE_EXTENSIONS.includes(ext);

  if (!validMime && !validExt) {
    return "Invalid file format. Please upload a JPG, JPEG, PNG, or WebP image.";
  }
  if (file.size > MAX_PROFILE_IMAGE_SIZE_BYTES) {
    return "Image file size exceeds 5 MB limit. Please choose a smaller image.";
  }
  return null;
}

