import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { 
  Layers, 
  Plus, 
  ShieldCheck, 
  CheckCircle2, 
  ArrowRight, 
  FolderLock, 
  Clock,
  UserCheck
} from 'lucide-react';

export const WorkspaceDeskView: React.FC = () => {
  const { user, activeWorkspaceId, workspaces, switchWorkspace, refreshWorkspaces } = useAuth();
  const [newWsName, setNewWsName] = useState('');
  const [newWsDesc, setNewWsDesc] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const activeWs = workspaces.find((w) => w.workspace_id === activeWorkspaceId);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setError(null);
    setSuccess(null);
    setIsCreating(true);
    try {
      const created = await api.workspaces.create(newWsName.trim(), newWsDesc.trim());
      setSuccess(`Workspace "${created.name}" created and registered.`);
      setNewWsName('');
      setNewWsDesc('');
      await refreshWorkspaces();
      await switchWorkspace(created.workspace_id);
    } catch (err: any) {
      setError(err?.detail || err?.title || 'Could not create workspace.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in duration-150">
      {/* Workspace Header */}
      <div className="border-b border-[#E8E2D5] pb-5">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs font-mono font-medium text-[#C24136] tracking-wider uppercase">
              Institutional Multi-Tenancy
            </span>
            <h2 className="font-editorial text-3xl font-bold text-[#1A1918] mt-1">
              Workspace Desk
            </h2>
            <p className="text-xs text-[#7A766F] mt-1 font-light">
              Isolated cryptographic and retrieval boundaries. Documents, citations, and conversation history remain strictly partitioned.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <span className="hanko-seal">TENANT ISOLATED</span>
          </div>
        </div>
      </div>

      {/* Grid: Active Workspace & Switcher */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Workspaces List */}
        <div className="lg:col-span-7 space-y-4">
          <h3 className="text-sm font-semibold text-[#1A1918] flex items-center space-x-2">
            <Layers className="w-4 h-4 text-[#C24136]" />
            <span>Accessible Workspaces ({workspaces.length})</span>
          </h3>

          <div className="space-y-3">
            {workspaces.map((ws) => {
              const isActive = ws.workspace_id === activeWorkspaceId;
              return (
                <div
                  key={ws.workspace_id}
                  className={`p-5 rounded-lg border transition-all ${
                    isActive
                      ? 'bg-[#FDFDFB] border-[#1A1918] shadow-xs'
                      : 'bg-[#FDFDFB] border-[#E8E2D5] hover:border-[#D5CCA8]'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="font-editorial text-lg font-bold text-[#1A1918]">
                          {ws.name}
                        </h4>
                        {ws.is_default && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#F2ECE1] text-[#7A766F]">
                            V1.1 Default
                          </span>
                        )}
                        {isActive && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#EBF7EE] text-[#2D6A4F] border border-[#40916C]">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[#7A766F] mt-1">
                        {ws.description || 'Institutional research workspace'}
                      </p>
                    </div>

                    {!isActive && (
                      <button
                        onClick={() => switchWorkspace(ws.workspace_id)}
                        className="px-3 py-1.5 rounded-md border border-[#D5CCA8] bg-[#F5F1E6] hover:bg-[#1A1918] hover:text-white text-xs font-medium text-[#1A1918] transition-all flex items-center space-x-1 cursor-pointer"
                      >
                        <span>Switch</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>

                  <div className="mt-4 pt-3 border-t border-[#F0ECE1] flex items-center justify-between text-[11px] text-[#7A766F] font-mono">
                    <span className="truncate max-w-[200px]">ID: {ws.workspace_id}</span>
                    <span className="flex items-center space-x-1 text-[#2D6A4F]">
                      <FolderLock className="w-3 h-3" />
                      <span>Boundary Enforced</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Create Workspace Card */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-[#FDFDFB] border border-[#D5CCA8] rounded-xl p-6 shadow-2xs">
            <h3 className="text-sm font-semibold text-[#1A1918] mb-1 flex items-center space-x-2">
              <Plus className="w-4 h-4 text-[#C24136]" />
              <span>Create New Workspace</span>
            </h3>
            <p className="text-xs text-[#7A766F] mb-4">
              Provision an isolated partition with dedicated embeddings, audit logs, and document stores.
            </p>

            {error && (
              <div className="mb-3 p-2.5 rounded bg-[#FDF1F0] border border-[#F0B8B4] text-xs text-[#C24136]">
                {error}
              </div>
            )}
            {success && (
              <div className="mb-3 p-2.5 rounded bg-[#EBF7EE] border border-[#40916C] text-xs text-[#2D6A4F]">
                {success}
              </div>
            )}

            <form onSubmit={handleCreateWorkspace} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[#3D3B38] mb-1">
                  Workspace Name
                </label>
                <input
                  type="text"
                  required
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  placeholder="e.g. Legal Intelligence Docket #4"
                  className="w-full px-3 py-2 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#3D3B38] mb-1">
                  Scope & Purpose Description
                </label>
                <textarea
                  rows={3}
                  value={newWsDesc}
                  onChange={(e) => setNewWsDesc(e.target.value)}
                  placeholder="e.g. Ingestion of multi-page patent portfolios and claims analysis."
                  className="w-full px-3 py-2 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136]"
                />
              </div>

              <button
                type="submit"
                disabled={isCreating || !newWsName.trim()}
                className="w-full py-2 px-4 rounded-md bg-[#1A1918] hover:bg-[#3D3B38] text-white text-xs font-medium transition-all cursor-pointer disabled:opacity-50"
              >
                {isCreating ? 'Provisioning Desk...' : 'Create Isolated Desk'}
              </button>
            </form>
          </div>

          {/* Security Guarantee Box */}
          <div className="p-4 rounded-lg bg-[#F5F1E6] border border-[#E8E2D5] space-y-2 text-xs text-[#59554E]">
            <div className="font-semibold text-[#1A1918] flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-[#2D6A4F]" />
              <span>Multi-Tenant Guarantees</span>
            </div>
            <ul className="space-y-1 text-[11px] list-disc list-inside">
              <li>Documents uploaded are tagged strictly by workspace_id</li>
              <li>Semantic embedding search filters only active workspace vectors</li>
              <li>Cross-tenant document access triggers HTTP 403 Forbidden</li>
              <li>Conversations and reasoning traces remain segregated</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
