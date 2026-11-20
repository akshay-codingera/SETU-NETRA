import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  FileText, 
  Search, 
  FileCheck, 
  Layers, 
  LogOut, 
  ChevronDown, 
  Shield, 
  Cpu,
  Activity
} from 'lucide-react';

interface NavbarProps {
  currentTab: 'documents' | 'qa' | 'report' | 'desk';
  onSelectTab: (tab: 'documents' | 'qa' | 'report' | 'desk') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onSelectTab }) => {
  const { user, activeWorkspaceId, workspaces, switchWorkspace, logout } = useAuth();
  const [wsDropdownOpen, setWsDropdownOpen] = useState(false);

  const activeWs = workspaces.find((w) => w.workspace_id === activeWorkspaceId);

  return (
    <header className="sticky top-0 z-50 bg-[#FBF9F5]/90 backdrop-blur-md border-b border-[#E8E2D5] px-6 py-3 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brandmark and Seal */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2.5 cursor-pointer" onClick={() => onSelectTab('documents')}>
            <span className="font-editorial text-2xl font-bold tracking-tight text-[#1A1918]">
              SETU-NETRA
            </span>
            <span className="hanko-seal" title="Grounded Institutional Intelligence">
              सेतु-नेत्र
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-[#F0ECE1] text-[#7A766F] font-mono font-medium">
              v2.0-rc1
            </span>
          </div>

          <div className="h-5 w-px bg-[#E8E2D5]" />

          {/* Navigation Tabs */}
          <nav className="flex items-center space-x-1" role="tablist">
            <button
              role="tab"
              aria-selected={currentTab === 'documents'}
              onClick={() => onSelectTab('documents')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'documents'
                  ? 'bg-[#1A1918] text-[#FBF9F5] shadow-xs'
                  : 'text-[#59554E] hover:text-[#1A1918] hover:bg-[#F2ECE1]'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Documents & Spatial</span>
            </button>

            <button
              role="tab"
              aria-selected={currentTab === 'qa'}
              onClick={() => onSelectTab('qa')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'qa'
                  ? 'bg-[#1A1918] text-[#FBF9F5] shadow-xs'
                  : 'text-[#59554E] hover:text-[#1A1918] hover:bg-[#F2ECE1]'
              }`}
            >
              <Search className="w-3.5 h-3.5" />
              <span>Intelligence QA</span>
            </button>

            <button
              role="tab"
              aria-selected={currentTab === 'report'}
              onClick={() => onSelectTab('report')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'report'
                  ? 'bg-[#1A1918] text-[#FBF9F5] shadow-xs'
                  : 'text-[#59554E] hover:text-[#1A1918] hover:bg-[#F2ECE1]'
              }`}
            >
              <FileCheck className="w-3.5 h-3.5" />
              <span>Report Studio</span>
            </button>

            <button
              role="tab"
              aria-selected={currentTab === 'desk'}
              onClick={() => onSelectTab('desk')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentTab === 'desk'
                  ? 'bg-[#1A1918] text-[#FBF9F5] shadow-xs'
                  : 'text-[#59554E] hover:text-[#1A1918] hover:bg-[#F2ECE1]'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Desk</span>
            </button>
          </nav>
        </div>

        {/* Workspace, Mode Badge & User Profile */}
        <div className="flex items-center space-x-3">
          {/* Local CPU Guard Pill */}
          <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded bg-[#F2ECE1] border border-[#E8E2D5] text-[11px] text-[#59554E]">
            <Cpu className="w-3 h-3 text-[#2D6A4F]" />
            <span className="font-medium">Local-Only CPU</span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#2D6A4F] animate-pulse" />
          </div>

          {/* Active Workspace Selector */}
          <div className="relative">
            <button
              onClick={() => setWsDropdownOpen(!wsDropdownOpen)}
              className="flex items-center space-x-2 px-3 py-1.5 rounded-md border border-[#E8E2D5] bg-[#FDFDFB] hover:bg-[#F5F1E6] text-xs font-medium text-[#1A1918] shadow-2xs transition-all"
            >
              <span className="text-[#8C877D] font-normal">Desk:</span>
              <span className="font-semibold truncate max-w-[120px]">
                {activeWs ? activeWs.name : activeWorkspaceId}
              </span>
              <ChevronDown className="w-3 h-3 text-[#8C877D]" />
            </button>

            {wsDropdownOpen && (
              <div 
                className="absolute right-0 mt-1 w-56 bg-[#FDFDFB] border border-[#E8E2D5] rounded-md shadow-lg py-1 z-50 animate-in fade-in zoom-in-95 duration-100"
                onMouseLeave={() => setWsDropdownOpen(false)}
              >
                <div className="px-3 py-1.5 text-[10px] uppercase font-bold tracking-wider text-[#8C877D] border-b border-[#E8E2D5]">
                  Select Active Workspace
                </div>
                {workspaces.map((w) => (
                  <button
                    key={w.workspace_id}
                    onClick={() => {
                      switchWorkspace(w.workspace_id);
                      setWsDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-[#F2ECE1] transition-colors ${
                      w.workspace_id === activeWorkspaceId ? 'font-bold text-[#1A1918] bg-[#F9F5EB]' : 'text-[#59554E]'
                    }`}
                  >
                    <span className="truncate">{w.name}</span>
                    {w.is_default && (
                      <span className="text-[10px] text-[#8C877D] font-mono px-1 rounded bg-[#E8E2D5]">default</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* User Badge */}
          {user && (
            <div className="flex items-center space-x-2 pl-2 border-l border-[#E8E2D5]">
              <div className="flex flex-col items-end">
                <span className="text-xs font-semibold text-[#1A1918]">{user.display_name}</span>
                <span className="text-[10px] font-mono font-medium text-[#C24136]">
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                className="p-1.5 rounded-md hover:bg-[#FDF1F0] text-[#7A766F] hover:text-[#C24136] transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
