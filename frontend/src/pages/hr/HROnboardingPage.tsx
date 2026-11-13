import React, { useEffect, useState } from "react";
import {
  UserCheck,
  CheckCircle,
  Plus,
  Layers,
  Check,
  ChevronDown,
  ChevronUp,
  Sparkles,
  ShieldCheck,
  Laptop,
  BookOpen,
  Bell,
  Clock,
  UserX,
  BadgeCheck,
  ExternalLink,
} from "lucide-react";

import postHiringApi from "../../api/postHiring";
import type { Employee, OnboardingTask, JoiningConfirmPayload } from "../../types/postHiring";
import { useToast } from "../../contexts/ToastContext";
import { formatDate } from "../../utils/dateTime";

export default function HROnboardingPage() {
  const { addToast } = useToast();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedEmpId, setExpandedEmpId] = useState<string | null>(null);

  // Modals state
  const [selectedEmpForTask, setSelectedEmpForTask] = useState<Employee | null>(null);
  const [taskForm, setTaskForm] = useState({
    title: "",
    description: "",
    instructions: "",
    category: "it_setup",
    assigned_to_role: "candidate",
    deadline: "",
  });
  const [submittingTask, setSubmittingTask] = useState(false);

  // Confirm Joining Modal
  const [confirmJoiningEmp, setConfirmJoiningEmp] = useState<Employee | null>(null);
  const [joiningPayload, setJoiningPayload] = useState<JoiningConfirmPayload>({
    joining_status: "confirmed",
    joining_date: "",
    remarks: "",
  });
  const [confirmingJoining, setConfirmingJoining] = useState(false);

  // Task Review Modal
  const [reviewingTask, setReviewingTask] = useState<{ task: OnboardingTask; empId: string } | null>(null);
  const [reviewRemarks, setReviewRemarks] = useState("");
  const [processingReview, setProcessingReview] = useState(false);

  // Employee Activation State
  const [activatingId, setActivatingId] = useState<string | null>(null);

  const fetchEmployees = async () => {
    setLoading(true);
    try {
      const data = await postHiringApi.getEmployees({ employment_status: "onboarding" });
      setEmployees(data);
      if (data.length > 0 && !expandedEmpId) {
        setExpandedEmpId(data[0].id);
      }
    } catch (err) {
      addToast("Failed to load onboarding employees", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  const handleToggleTask = async (task: OnboardingTask) => {
    try {
      await postHiringApi.updateTask(task.id, { is_completed: !task.is_completed });
      addToast(task.is_completed ? "Task marked incomplete" : "Task completed", "success");
      await fetchEmployees();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to update task", "error");
    }
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEmpForTask) return;
    setSubmittingTask(true);
    try {
      await postHiringApi.addOnboardingTask(selectedEmpForTask.id, {
        ...taskForm,
        deadline: taskForm.deadline ? new Date(taskForm.deadline).toISOString() : undefined,
      });
      addToast("New onboarding task assigned", "success");
      setSelectedEmpForTask(null);
      setTaskForm({
        title: "",
        description: "",
        instructions: "",
        category: "it_setup",
        assigned_to_role: "candidate",
        deadline: "",
      });
      await fetchEmployees();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to assign task", "error");
    } finally {
      setSubmittingTask(false);
    }
  };

  // Open Confirm Joining Dialog
  const handleOpenConfirmJoining = (emp: Employee) => {
    setConfirmJoiningEmp(emp);
    setJoiningPayload({
      joining_status: "confirmed",
      joining_date: emp.joining_date ? emp.joining_date.split("T")[0] : new Date().toISOString().split("T")[0],
      remarks: "Candidate verified and onboarding schedule confirmed.",
    });
  };

  const handleConfirmJoiningSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmJoiningEmp) return;
    setConfirmingJoining(true);
    try {
      await postHiringApi.confirmJoining(confirmJoiningEmp.id, {
        ...joiningPayload,
        joining_date: joiningPayload.joining_date ? new Date(joiningPayload.joining_date).toISOString() : undefined,
      });
      addToast(
        joiningPayload.joining_status === "confirmed"
          ? `Joining confirmed for ${confirmJoiningEmp.user_name}!`
          : `Candidate marked as ${joiningPayload.joining_status}.`,
        "success"
      );
      setConfirmJoiningEmp(null);
      await fetchEmployees();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to confirm joining", "error");
    } finally {
      setConfirmingJoining(false);
    }
  };

  // Handle Employee Activation
  const handleActivateEmployee = async (emp: Employee) => {
    // 1. Mandatory Joining Confirmation Validation
    if (emp.joining_status !== "confirmed") {
      addToast(
        "Mandatory requirement: Candidate joining must be confirmed before activating employee profile.",
        "error"
      );
      handleOpenConfirmJoining(emp);
      return;
    }

    if (!window.confirm(`Activate ${emp.user_name} as an active full-time employee? This will finalize onboarding and promote the profile to active employee status.`)) {
      return;
    }

    setActivatingId(emp.id);
    try {
      await postHiringApi.activateEmployee(emp.id);
      addToast(`🎉 ${emp.user_name} is now an Active Employee! Account activated successfully.`, "success");
      await fetchEmployees();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to activate employee", "error");
    } finally {
      setActivatingId(null);
    }
  };

  // Task Review (Approve / Reject)
  const handleReviewTask = async (status: "completed" | "rejected") => {
    if (!reviewingTask) return;
    setProcessingReview(true);
    try {
      await postHiringApi.reviewTask(reviewingTask.task.id, {
        status,
        hr_remarks: reviewRemarks || (status === "completed" ? "Verified and approved by HR" : "Changes requested"),
      });
      addToast(status === "completed" ? "Task approved!" : "Task revision requested", "success");
      setReviewingTask(null);
      setReviewRemarks("");
      await fetchEmployees();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to review task", "error");
    } finally {
      setProcessingReview(false);
    }
  };

  // Send Task Reminder
  const handleSendReminder = async (task: OnboardingTask) => {
    try {
      await postHiringApi.sendTaskReminder(task.id);
      addToast(`Reminder notification sent for "${task.title}"`, "success");
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to send reminder", "error");
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "it_setup":
        return <Laptop className="w-4 h-4 text-blue-500" />;
      case "documentation":
        return <ShieldCheck className="w-4 h-4 text-purple-500" />;
      case "training":
        return <BookOpen className="w-4 h-4 text-emerald-500" />;
      case "orientation":
        return <Sparkles className="w-4 h-4 text-amber-500" />;
      default:
        return <Layers className="w-4 h-4 text-slate-500" />;
    }
  };

  // Metrics computation (Section 4)
  const totalEmployees = employees.length;
  const notStarted = employees.filter((e) => e.onboarding_status === "not_started").length;
  const inProgress = employees.filter((e) => e.onboarding_status === "in_progress").length;
  const pendingHrApproval = employees.filter((e) =>
    e.tasks?.some((t) => t.status === "pending_approval")
  ).length;
  const overdueTasksCount = employees.reduce((acc, emp) => {
    return (
      acc +
      (emp.tasks?.filter(
        (t) => t.deadline && new Date(t.deadline) < new Date() && !t.is_completed
      ).length || 0)
    );
  }, 0);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <UserCheck className="w-6 h-6 text-blue-600" />
            Employee Onboarding & Activation Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Track onboarding checklists, verify candidate task submissions, confirm joining status, and activate employee profiles.
          </p>
        </div>
      </div>

      {/* Metrics Row (Section 4 Requirements) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Total In Onboarding</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{totalEmployees}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Not Started</p>
          <p className="text-2xl font-bold text-slate-600 mt-1">{notStarted}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-semibold text-blue-600 uppercase tracking-wider">In Progress</p>
          <p className="text-2xl font-bold text-blue-700 mt-1">{inProgress}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-amber-200 bg-amber-50/40 shadow-sm">
          <p className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider">Pending HR Review</p>
          <p className="text-2xl font-bold text-amber-800 mt-1">{pendingHrApproval}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-emerald-200 bg-emerald-50/40 shadow-sm">
          <p className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">Tasks Completed</p>
          <p className="text-2xl font-bold text-emerald-800 mt-1">
            {employees.reduce((acc, e) => acc + (e.completed_tasks || 0), 0)}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-rose-200 bg-rose-50/40 shadow-sm">
          <p className="text-[11px] font-semibold text-rose-700 uppercase tracking-wider">Overdue Tasks</p>
          <p className="text-2xl font-bold text-rose-800 mt-1">{overdueTasksCount}</p>
        </div>
      </div>

      {/* Onboarding Employees List */}
      {loading ? (
        <div className="py-12 text-center text-slate-500 text-sm">Loading onboarding records...</div>
      ) : employees.length === 0 ? (
        <div className="bg-white p-12 rounded-xl border border-slate-200 text-center text-slate-400 text-sm">
          No employees are currently in onboarding. Verify candidate credentials in Document Verification to start onboarding.
        </div>
      ) : (
        <div className="space-y-4">
          {employees.map((emp) => {
            const isExpanded = expandedEmpId === emp.id;
            const hasPendingTasks = emp.tasks?.some((t) => t.status === "pending_approval");
            const isJoiningConfirmed = emp.joining_status === "confirmed";

            return (
              <div
                key={emp.id}
                className={`bg-white rounded-2xl border transition-all shadow-sm overflow-hidden ${
                  isJoiningConfirmed ? "border-emerald-200" : "border-slate-200"
                }`}
              >
                {/* Employee Header Row */}
                <div
                  onClick={() => setExpandedEmpId(isExpanded ? null : emp.id)}
                  className="p-5 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 cursor-pointer hover:bg-slate-50/75 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-700 font-extrabold text-base flex items-center justify-center shrink-0 border border-blue-200">
                      {emp.user_name?.slice(0, 2).toUpperCase() || "EM"}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-bold text-slate-900 text-sm sm:text-base">{emp.user_name}</h3>
                        <span className="text-[11px] font-mono font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                          {emp.employee_id}
                        </span>
                        {emp.checklist_template && (
                          <span className="text-[10px] uppercase font-bold bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded">
                            {emp.checklist_template} checklist
                          </span>
                        )}
                        {/* Joining Status Badge */}
                        {isJoiningConfirmed ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">
                            <BadgeCheck className="w-3.5 h-3.5 text-emerald-600" /> Joining Confirmed
                          </span>
                        ) : emp.joining_status === "no_show" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded-full">
                            <UserX className="w-3.5 h-3.5" /> No Show
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full">
                            <Clock className="w-3.5 h-3.5" /> Joining Pending Confirmation
                          </span>
                        )}
                        {hasPendingTasks && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold bg-blue-600 text-white px-2 py-0.5 rounded-full animate-pulse">
                            Review Required
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        <strong>{emp.designation}</strong> &bull; {emp.department} &bull; Manager: {emp.reporting_manager || "Not assigned"} &bull; Scheduled Joining: <strong>{formatDate(emp.joining_date)}</strong>
                      </p>
                    </div>
                  </div>

                  {/* Progress & Quick Action Buttons */}
                  <div className="flex items-center gap-3 w-full lg:w-auto justify-between lg:justify-end">
                    <div className="w-32 sm:w-40">
                      <div className="flex justify-between text-[11px] font-semibold text-slate-600 mb-1">
                        <span>Progress</span>
                        <span>{emp.onboarding_progress_percent}%</span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${emp.onboarding_progress_percent}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenConfirmJoining(emp);
                        }}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                          isJoiningConfirmed
                            ? "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                            : "bg-amber-500 hover:bg-amber-600 text-white border-transparent shadow-sm"
                        }`}
                      >
                        {isJoiningConfirmed ? "Update Joining" : "Confirm Joining"}
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleActivateEmployee(emp);
                        }}
                        disabled={activatingId === emp.id}
                        className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold shadow-sm transition-all cursor-pointer ${
                          isJoiningConfirmed
                            ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                            : "bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed"
                        }`}
                        title={
                          isJoiningConfirmed
                            ? "Finalize onboarding and activate full-time employee profile"
                            : "Joining must be confirmed first"
                        }
                      >
                        <BadgeCheck className="w-3.5 h-3.5" />
                        {activatingId === emp.id ? "Activating..." : "Activate Employee"}
                      </button>

                      <div className="text-slate-400 pl-1">
                        {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Checklist */}
                {isExpanded && (
                  <div className="p-5 border-t border-slate-100 bg-slate-50/60 space-y-4">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div>
                        <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                          <span>Onboarding Tasks Checklist</span>
                          <span className="bg-slate-200 text-slate-700 text-[11px] px-2 py-0.5 rounded-full font-bold">
                            {emp.completed_tasks}/{emp.total_tasks} Done
                          </span>
                        </h4>
                        {emp.joining_remarks && (
                          <p className="text-[11px] text-slate-500 mt-1 italic">
                            HR Note: {emp.joining_remarks}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEmpForTask(emp);
                          }}
                          className="inline-flex items-center gap-1 bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 px-3 py-1.5 rounded-xl text-xs font-medium shadow-sm transition-colors cursor-pointer"
                        >
                          <Plus className="w-3.5 h-3.5" /> Add Task
                        </button>
                      </div>
                    </div>

                    {/* Tasks List */}
                    <div className="space-y-2">
                      {emp.tasks?.map((task) => {
                        const isPendingApproval = task.status === "pending_approval";
                        const isRejected = task.status === "rejected";

                        return (
                          <div
                            key={task.id}
                            className={`p-4 rounded-xl border transition-all flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
                              task.is_completed
                                ? "bg-white border-slate-200 opacity-80"
                                : isPendingApproval
                                ? "bg-amber-50/60 border-amber-300 shadow-sm"
                                : "bg-white border-slate-200 shadow-sm"
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              <button
                                onClick={() => handleToggleTask(task)}
                                className={`mt-0.5 w-5 h-5 rounded-md border flex items-center justify-center transition-colors cursor-pointer shrink-0 ${
                                  task.is_completed
                                    ? "bg-emerald-500 border-emerald-500 text-white"
                                    : "border-slate-300 hover:border-blue-500"
                                }`}
                              >
                                {task.is_completed && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                              </button>

                              <div>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span
                                    className={
                                      task.is_completed
                                        ? "line-through text-slate-400 font-semibold text-xs"
                                        : "font-semibold text-slate-900 text-xs"
                                    }
                                  >
                                    {task.title}
                                  </span>

                                  <span className="inline-flex items-center gap-1 text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded capitalize">
                                    {getCategoryIcon(task.category)}
                                    {task.category.replace("_", " ")}
                                  </span>

                                  <span className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-medium">
                                    Assigned: {task.assigned_to_role}
                                  </span>

                                  {isPendingApproval && (
                                    <span className="text-[10px] font-bold bg-amber-500 text-white px-2 py-0.5 rounded-full">
                                      Candidate Submitted (Review)
                                    </span>
                                  )}

                                  {isRejected && (
                                    <span className="text-[10px] font-bold bg-rose-100 text-rose-700 px-2 py-0.5 rounded-full">
                                      Revision Requested
                                    </span>
                                  )}
                                </div>

                                {task.description && (
                                  <p className="text-[11px] text-slate-500 mt-1">{task.description}</p>
                                )}

                                {task.instructions && (
                                  <p className="text-[11px] text-blue-700 bg-blue-50/70 border border-blue-200/60 p-1.5 rounded-lg mt-1.5">
                                    <strong>Instructions:</strong> {task.instructions}
                                  </p>
                                )}

                                {/* Candidate Submission Notes */}
                                {task.submission_notes && (
                                  <div className="mt-2 text-[11px] bg-slate-50 border border-slate-200 rounded-lg p-2 text-slate-700">
                                    <span className="font-semibold text-slate-800">Candidate Submission Notes:</span>{" "}
                                    {task.submission_notes}
                                  </div>
                                )}

                                {task.hr_remarks && (
                                  <p className="text-[11px] text-slate-500 mt-1 italic">
                                    HR Remarks: {task.hr_remarks}
                                  </p>
                                )}
                              </div>
                            </div>

                            {/* Task Controls */}
                            <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                              {task.deadline && (
                                <div className="text-[11px] text-slate-400 whitespace-nowrap flex items-center gap-1">
                                  <Clock className="w-3 h-3" />
                                  {formatDate(task.deadline)}
                                </div>
                              )}

                              {isPendingApproval ? (
                                <button
                                  onClick={() => setReviewingTask({ task, empId: emp.id })}
                                  className="inline-flex items-center gap-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg shadow-sm transition-colors cursor-pointer"
                                >
                                  <CheckCircle className="w-3.5 h-3.5" /> Review Submission
                                </button>
                              ) : (
                                !task.is_completed && (
                                  <button
                                    onClick={() => handleSendReminder(task)}
                                    className="inline-flex items-center gap-1 text-slate-500 hover:text-blue-600 bg-white border border-slate-200 hover:bg-slate-50 text-[11px] font-medium px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                                    title="Send task reminder notification"
                                  >
                                    <Bell className="w-3 h-3" /> Remind
                                  </button>
                                )
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* CONFIRM JOINING MODAL (Section 6 Requirements) */}
      {confirmJoiningEmp && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in duration-200">
            <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BadgeCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-base">Confirm Candidate Joining</h3>
              </div>
              <button
                onClick={() => setConfirmJoiningEmp(null)}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleConfirmJoiningSubmit} className="p-6 space-y-4 text-xs">
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-1">
                <p className="text-slate-800 font-bold text-sm">{confirmJoiningEmp.user_name}</p>
                <p className="text-slate-500 text-xs">
                  {confirmJoiningEmp.designation} &bull; {confirmJoiningEmp.department}
                </p>
                <p className="text-slate-500 text-xs">
                  Employee ID: <strong className="font-mono text-slate-700">{confirmJoiningEmp.employee_id}</strong>
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Joining Decision Status *
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: "confirmed", label: "Confirmed", color: "emerald" },
                    { id: "no_show", label: "No Show", color: "rose" },
                    { id: "cancelled", label: "Cancelled", color: "slate" },
                  ].map((st) => (
                    <label
                      key={st.id}
                      className={`p-2.5 rounded-xl border cursor-pointer text-center font-bold text-xs transition-all ${
                        joiningPayload.joining_status === st.id
                          ? st.id === "confirmed"
                            ? "border-emerald-600 bg-emerald-50 text-emerald-800"
                            : "border-rose-600 bg-rose-50 text-rose-800"
                          : "border-slate-200 text-slate-600 hover:border-slate-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="joining_status"
                        checked={joiningPayload.joining_status === st.id}
                        onChange={() => setJoiningPayload({ ...joiningPayload, joining_status: st.id as any })}
                        className="sr-only"
                      />
                      {st.label}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Official Joining Date *
                </label>
                <input
                  type="date"
                  required
                  value={joiningPayload.joining_date}
                  onChange={(e) => setJoiningPayload({ ...joiningPayload, joining_date: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  {joiningPayload.joining_status !== "confirmed" ? "Mandatory Cancellation / No-Show Reason *" : "HR Notes & Remarks"}
                </label>
                <textarea
                  rows={3}
                  required={joiningPayload.joining_status !== "confirmed"}
                  value={joiningPayload.remarks || ""}
                  onChange={(e) => setJoiningPayload({ ...joiningPayload, remarks: e.target.value })}
                  placeholder={
                    joiningPayload.joining_status === "confirmed"
                      ? "e.g. Identity verified, laptop handed over, signed agreement received."
                      : "Provide detailed remarks explaining why the candidate did not join..."
                  }
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setConfirmJoiningEmp(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={confirmingJoining}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer"
                >
                  {confirmingJoining ? "Saving..." : "Confirm & Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TASK REVIEW MODAL (Approve / Reject Candidate Submission) */}
      {reviewingTask && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in duration-150">
            <div className="bg-amber-600 text-white px-6 py-4 flex items-center justify-between">
              <h3 className="font-bold text-base flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-amber-200" />
                Review Candidate Task Submission
              </h3>
              <button
                onClick={() => setReviewingTask(null)}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs">
              <div>
                <p className="text-slate-500 text-[11px] uppercase font-bold">Task Title</p>
                <p className="font-bold text-slate-900 text-sm">{reviewingTask.task.title}</p>
              </div>

              {reviewingTask.task.submission_notes && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                  <p className="text-slate-500 text-[11px] font-semibold mb-1">Candidate Notes:</p>
                  <p className="text-slate-800">{reviewingTask.task.submission_notes}</p>
                </div>
              )}

              {reviewingTask.task.attachment_url && (
                <div>
                  <a
                    href={reviewingTask.task.attachment_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-blue-600 font-semibold hover:underline"
                  >
                    <ExternalLink className="w-3.5 h-3.5" /> View Submission Attachment
                  </a>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  HR Review Feedback / Remarks
                </label>
                <textarea
                  rows={2}
                  value={reviewRemarks}
                  onChange={(e) => setReviewRemarks(e.target.value)}
                  placeholder="Optional notes or feedback for candidate..."
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  disabled={processingReview}
                  onClick={() => handleReviewTask("rejected")}
                  className="px-4 py-2 rounded-xl bg-rose-50 text-rose-700 hover:bg-rose-100 font-bold border border-rose-200 cursor-pointer"
                >
                  Request Revision
                </button>
                <button
                  type="button"
                  disabled={processingReview}
                  onClick={() => handleReviewTask("completed")}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold cursor-pointer"
                >
                  Approve Task
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ADD CUSTOM TASK MODAL */}
      {selectedEmpForTask && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in duration-200">
            <div className="bg-blue-600 text-white px-6 py-4 flex items-center justify-between">
              <h3 className="font-bold text-base flex items-center gap-2">
                <Plus className="w-5 h-5 text-blue-200" />
                Assign Onboarding Task
              </h3>
              <button
                onClick={() => setSelectedEmpForTask(null)}
                className="text-white/80 hover:text-white text-xl font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleAddTask} className="p-6 space-y-4 text-xs">
              <p className="text-slate-600">
                Assigning task to: <strong>{selectedEmpForTask.user_name}</strong> ({selectedEmpForTask.designation})
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Task Title *</label>
                <input
                  type="text"
                  required
                  value={taskForm.title}
                  onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
                  placeholder="e.g. Set up VPN & GitHub SSH keys"
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  value={taskForm.description}
                  onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })}
                  placeholder="Brief summary of the requirement..."
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Instructions for Assignee</label>
                <textarea
                  rows={2}
                  value={taskForm.instructions}
                  onChange={(e) => setTaskForm({ ...taskForm, instructions: e.target.value })}
                  placeholder="Step-by-step guidance..."
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Category</label>
                  <select
                    value={taskForm.category}
                    onChange={(e) => setTaskForm({ ...taskForm, category: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="documentation">Documentation</option>
                    <option value="it_setup">IT Setup</option>
                    <option value="training">Training</option>
                    <option value="orientation">Orientation</option>
                    <option value="compliance">Compliance</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Assigned Role</label>
                  <select
                    value={taskForm.assigned_to_role}
                    onChange={(e) => setTaskForm({ ...taskForm, assigned_to_role: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="candidate">Candidate</option>
                    <option value="hr">HR</option>
                    <option value="it_admin">IT Admin</option>
                    <option value="manager">Manager</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Deadline</label>
                <input
                  type="date"
                  value={taskForm.deadline}
                  onChange={(e) => setTaskForm({ ...taskForm, deadline: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 p-2 text-xs focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedEmpForTask(null)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingTask}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer"
                >
                  {submittingTask ? "Assigning..." : "Assign Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
