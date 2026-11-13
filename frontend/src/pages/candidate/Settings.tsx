import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { candidateApi } from "../../api/candidate";
import { useAuth } from "../../hooks/useAuth";

export function CandidateSettings() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "" });
  const [emailForm, setEmailForm] = useState({ new_email: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage("");
    setError("");
    try {
      await candidateApi.changePassword(passwordForm);
      setMessage("Password changed successfully");
      setPasswordForm({ current_password: "", new_password: "" });
    } catch {
      setError("Failed to change password");
    }
  };

  const handleEmailUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage("");
    setError("");
    try {
      await candidateApi.updateEmail(emailForm);
      setMessage("Email updated successfully");
      setEmailForm({ new_email: "" });
    } catch {
      setError("Failed to update email");
    }
  };

  const handleDeleteAccount = async () => {
    if (!confirm("Are you sure you want to deactivate your account? This action can be reversed by an admin.")) return;
    try {
      await candidateApi.deleteAccount();
      await logout();
      navigate("/login");
    } catch {
      setError("Failed to deactivate account");
    }
  };

  return (
    <div className="max-w-2xl animate-fade-up space-y-6">
      <div className="page-header">
        <h1 className="page-title">Account Settings</h1>
        <p className="page-subtitle">Manage your account preferences</p>
      </div>

      {message && (
        <div className="success-banner" role="status">{message}</div>
      )}
      {error && (
        <div className="error-banner" role="alert">{error}</div>
      )}

      <form onSubmit={handlePasswordChange} className="card space-y-4">
        <h2 className="section-title">Change Password</h2>
        <Input label="Current Password" type="password" value={passwordForm.current_password}
          onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })} required />
        <Input label="New Password" type="password" value={passwordForm.new_password}
          onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })} required minLength={8} />
        <Button type="submit">Update Password</Button>
      </form>

      <form onSubmit={handleEmailUpdate} className="card space-y-4">
        <h2 className="section-title">Update Email</h2>
        <Input label="New Email" type="email" value={emailForm.new_email}
          onChange={(e) => setEmailForm({ new_email: e.target.value })} required />
        <Button type="submit">Update Email</Button>
      </form>

      <div className="card space-y-4 border-red-200 bg-red-50/40">
        <h2 className="section-title text-red-900">Danger Zone</h2>
        <p className="text-sm text-gray-500">Deactivate your account. This can be reversed by an administrator.</p>
        <Button variant="danger" onClick={handleDeleteAccount}>Deactivate Account</Button>
      </div>
    </div>
  );
}
