import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Users,
  Plus,
  Search,
  CheckCircle,
  Clock,
  Eye,
} from "lucide-react";

import postHiringApi from "../../api/postHiring";
import type {
  ApprovedCandidateSummary,
  Employee,
  EmployeeCreatePayload,
  EmploymentStatus,
} from "../../types/postHiring";
import { useToast } from "../../contexts/ToastContext";
import { formatDate } from "../../utils/dateTime";

export default function HREmployeesPage() {
  const [searchParams] = useSearchParams();
  const prefillCandId = searchParams.get("candidate_id");
  const prefillAppId = searchParams.get("app_id");
  const { addToast } = useToast();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [approvedCandidates, setApprovedCandidates] = useState<ApprovedCandidateSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDept, setSelectedDept] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState("all");

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Form State
  const [formData, setFormData] = useState<EmployeeCreatePayload>({
    candidate_id: "",
    application_id: "",
    designation: "",
    department: "Engineering",
    employment_type: "full_time",
    work_location: "Hybrid - Headquarters",
    reporting_manager: "",
    joining_date: new Date().toISOString().split("T")[0],
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [empList, candsList] = await Promise.all([
        postHiringApi.getEmployees(),
        postHiringApi.getApprovedCandidates(),
      ]);
      setEmployees(empList);
      setApprovedCandidates(candsList);

      if (prefillCandId) {
        const found = candsList.find((c) => c.candidate_id === prefillCandId);
        if (found) {
          setFormData({
            candidate_id: found.candidate_id,
            application_id: found.application_id,
            designation: found.job_title,
            department: found.department,
            employment_type: "full_time",
            work_location: "Hybrid - Headquarters",
            reporting_manager: "",
            joining_date: new Date().toISOString().split("T")[0],
          });
          setShowCreateModal(true);
        }
      }
    } catch (err) {
      addToast("Failed to load employee directory", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [prefillCandId, prefillAppId]);

  const handleSelectCandidate = (candId: string) => {
    const cand = approvedCandidates.find((c) => c.candidate_id === candId);
    if (cand) {
      setFormData((prev) => ({
        ...prev,
        candidate_id: cand.candidate_id,
        application_id: cand.application_id,
        designation: cand.job_title,
        department: cand.department || "Engineering",
      }));
    }
  };

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.candidate_id) {
      addToast("Please select a candidate", "error");
      return;
    }
    setSubmitting(true);
    try {
      await postHiringApi.createEmployee({
        ...formData,
        joining_date: new Date(formData.joining_date).toISOString(),
      });
      addToast("Official employee profile created & onboarding initialized", "success");
      setShowCreateModal(false);
      await fetchData();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to create employee profile", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const filteredEmployees = employees.filter((emp) => {
    const matchesSearch =
      emp.employee_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (emp.user_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (emp.user_email || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.designation.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesDept = selectedDept === "all" || emp.department === selectedDept;
    const matchesStatus = selectedStatus === "all" || emp.employment_status === selectedStatus;

    return matchesSearch && matchesDept && matchesStatus;
  });

  const departments = Array.from(new Set(employees.map((e) => e.department).filter(Boolean)));

  const getStatusBadge = (status: EmploymentStatus) => {
    switch (status) {
      case "active":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"><CheckCircle className="w-3.5 h-3.5" /> Active</span>;
      case "onboarding":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200"><Clock className="w-3.5 h-3.5" /> Onboarding</span>;
      case "on_leave":
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">On Leave</span>;
      case "terminated":
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">{status}</span>;
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Users className="w-6 h-6 text-blue-600" />
            Employee Directory & Profiles
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Maintain active team records, official employee IDs, and monitor onboarding completion.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          Create Employee Profile
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Headcount</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{employees.length}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-emerald-600 uppercase tracking-wider">Active Employees</p>
          <p className="text-2xl font-bold text-emerald-700 mt-1">
            {employees.filter((e) => e.employment_status === "active").length}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-blue-600 uppercase tracking-wider">In Onboarding</p>
          <p className="text-2xl font-bold text-blue-700 mt-1">
            {employees.filter((e) => e.employment_status === "onboarding").length}
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-purple-600 uppercase tracking-wider">Departments</p>
          <p className="text-2xl font-bold text-purple-700 mt-1">{departments.length || 1}</p>
        </div>
      </div>

      {/* Directory Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            {/* Search */}
            <div className="relative w-full sm:w-64">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search by ID, name, title..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Dept Filter */}
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="text-xs rounded-lg border border-slate-200 p-1.5 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Departments</option>
              {departments.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="text-xs rounded-lg border border-slate-200 p-1.5 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="onboarding">Onboarding</option>
              <option value="on_leave">On Leave</option>
            </select>
          </div>
        </div>

        {/* Directory Table */}
        {loading ? (
          <div className="py-12 text-center text-slate-500 text-sm">Loading employee records...</div>
        ) : filteredEmployees.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">
            No employees found matching the current criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Employee</th>
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">Department & Role</th>
                  <th className="py-3 px-4">Location</th>
                  <th className="py-3 px-4">Joining Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Onboarding Progress</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {filteredEmployees.map((emp) => (
                  <tr key={emp.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center">
                          {emp.user_name?.slice(0, 2).toUpperCase() || "EM"}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{emp.user_name || "Employee"}</div>
                          <div className="text-slate-400 text-[11px]">{emp.user_email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs font-semibold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                        {emp.employee_id}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">{emp.designation}</div>
                      <div className="text-slate-500 text-[11px]">{emp.department}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-600">{emp.work_location}</td>
                    <td className="py-3 px-4 text-slate-600">{formatDate(emp.joining_date)}</td>
                    <td className="py-3 px-4">{getStatusBadge(emp.employment_status)}</td>
                    <td className="py-3 px-4">
                      <div className="w-28">
                        <div className="flex justify-between text-[10px] text-slate-500 mb-0.5 font-medium">
                          <span>{emp.completed_tasks}/{emp.total_tasks} Tasks</span>
                          <span>{emp.onboarding_progress_percent}%</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-1.5 rounded-full ${emp.employment_status === "active" ? "bg-emerald-500" : "bg-blue-600"}`}
                            style={{ width: `${emp.onboarding_progress_percent}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedEmployee(emp)}
                        className="inline-flex items-center gap-1 text-slate-600 hover:text-blue-600 font-medium"
                      >
                        <Eye className="w-3.5 h-3.5" /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE EMPLOYEE MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
            <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-base">Create Official Employee Profile</h3>
                <p className="text-xs text-slate-400 mt-0.5">Generate Employee ID and initialize onboarding workflow.</p>
              </div>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white text-xl font-bold">×</button>
            </div>
            <form onSubmit={handleCreateEmployee} className="p-6 space-y-4 text-xs">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Candidate *</label>
                <select
                  required
                  value={formData.candidate_id}
                  onChange={(e) => handleSelectCandidate(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 p-2.5 bg-white focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">-- Choose Candidate --</option>
                  {approvedCandidates.map((c) => (
                    <option key={c.candidate_id} value={c.candidate_id}>
                      {c.candidate_name} ({c.job_title}) [{c.application_status.toUpperCase()}]
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Designation *</label>
                  <input
                    type="text"
                    required
                    value={formData.designation}
                    onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Department *</label>
                  <input
                    type="text"
                    required
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Work Location *</label>
                  <input
                    type="text"
                    required
                    value={formData.work_location}
                    onChange={(e) => setFormData({ ...formData, work_location: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Joining Date *</label>
                  <input
                    type="date"
                    required
                    value={formData.joining_date}
                    onChange={(e) => setFormData({ ...formData, joining_date: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Reporting Manager</label>
                <input
                  type="text"
                  value={formData.reporting_manager || ""}
                  onChange={(e) => setFormData({ ...formData, reporting_manager: e.target.value })}
                  placeholder="e.g. VP of Engineering"
                  className="w-full rounded-lg border border-slate-300 p-2 focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium"
                >
                  {submitting ? "Creating..." : "Confirm & Create Profile"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* VIEW EMPLOYEE DETAILS MODAL */}
      {selectedEmployee && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
            <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-500 text-white font-bold flex items-center justify-center text-sm">
                  {selectedEmployee.user_name?.slice(0, 2).toUpperCase() || "EM"}
                </div>
                <div>
                  <h3 className="font-semibold text-base">{selectedEmployee.user_name}</h3>
                  <p className="text-xs text-slate-400">{selectedEmployee.employee_id} • {selectedEmployee.designation}</p>
                </div>
              </div>
              <button onClick={() => setSelectedEmployee(null)} className="text-slate-400 hover:text-white text-xl font-bold">×</button>
            </div>
            <div className="p-6 space-y-4 text-xs max-h-[70vh] overflow-y-auto">
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Email:</span>
                  <span className="font-medium text-slate-900">{selectedEmployee.user_email}</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Department:</span>
                  <span className="font-medium text-slate-900">{selectedEmployee.department}</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Location:</span>
                  <span className="font-medium text-slate-900">{selectedEmployee.work_location}</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Joining Date:</span>
                  <span className="font-medium text-slate-900">{formatDate(selectedEmployee.joining_date)}</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-200 pb-2">
                  <span className="text-slate-500">Status:</span>
                  <span>{getStatusBadge(selectedEmployee.employment_status)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Onboarding Status:</span>
                  <span className="capitalize font-semibold text-slate-800">{selectedEmployee.onboarding_status.replace("_", " ")}</span>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] mb-2">
                  Tasks History ({selectedEmployee.completed_tasks}/{selectedEmployee.total_tasks})
                </h4>
                <div className="space-y-1.5">
                  {selectedEmployee.tasks.map((t) => (
                    <div key={t.id} className="p-2.5 rounded-lg border border-slate-200 bg-white flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        {t.is_completed ? (
                          <CheckCircle className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <Clock className="w-4 h-4 text-slate-300" />
                        )}
                        <span className={t.is_completed ? "line-through text-slate-400" : "text-slate-800 font-medium"}>
                          {t.title}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 capitalize">{t.category}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end pt-2 border-t border-slate-100">
                <button
                  onClick={() => setSelectedEmployee(null)}
                  className="px-4 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
