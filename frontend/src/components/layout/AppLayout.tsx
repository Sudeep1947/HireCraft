import { Outlet } from "react-router-dom";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { useAuth } from "../../hooks/useAuth";

export function AppLayout() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen flex bg-[#F8FAFC]">
      {isAuthenticated && <Sidebar />}
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 p-6 md:p-8 bg-[#F8FAFC] overflow-y-auto">
          <Outlet />
        </main>
        <footer className="mt-auto px-6 md:px-8 py-4 border-t border-slate-200/60 bg-transparent text-xs text-slate-400 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>AI Hiring Copilot © {new Date().getFullYear()}. All rights reserved.</span>
          <span className="text-slate-400">Smarter Hiring • Better Careers • A Brighter Future</span>
        </footer>
      </div>
    </div>
  );
}
