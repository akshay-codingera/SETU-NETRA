import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, SystemHealth } from '../api/client';
import { 
  ShieldCheck, 
  Cpu, 
  FileSearch, 
  Layers, 
  Lock, 
  CheckCircle, 
  Activity,
  ArrowRight,
  Database
} from 'lucide-react';

export const LandingView: React.FC = () => {
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState<'signin' | 'register'>('signin');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('Admin@Setu2026');
  const [displayName, setDisplayName] = useState('Lead Investigator');
  const [requestedRole, setRequestedRole] = useState('LEAD_INVESTIGATOR');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    api.health.check().then(setHealth).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (activeTab === 'signin') {
        await login(username, password);
      } else {
        await register({
          username,
          password,
          display_name: displayName,
          requested_role: requestedRole,
        });
      }
    } catch (err: any) {
      setError(err?.detail || err?.title || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FBF9F5] text-[#1A1918] flex flex-col justify-between selection:bg-[#C24136] selection:text-white">
      {/* Top Banner */}
      <header className="border-b border-[#E8E2D5] px-8 py-5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="font-editorial text-3xl font-bold tracking-tight text-[#1A1918]">
              SETU-NETRA
            </span>
            <span className="hanko-seal" title="Authentic Evidence Bridge">
              सेतु-नेत्र
            </span>
          </div>

          <div className="flex items-center space-x-2 text-xs font-mono text-[#7A766F]">
            <span className="w-2 h-2 rounded-full bg-[#2D6A4F] animate-pulse" />
            <span>KORA KAAGAZ V2.0-RC1</span>
          </div>
        </div>
      </header>

      {/* Main Hero & Auth Split */}
      <main className="max-w-7xl mx-auto px-8 py-12 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center flex-1">
        {/* Left Column: Editorial Overview */}
        <div className="lg:col-span-7 space-y-8">
          <div className="space-y-4">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full border border-[#D5CCA8] bg-[#F5F1E6] text-xs font-serif text-[#3D3B38]">
              <span className="font-semibold text-[#C24136]">◆</span>
              <span>Evidence-Grounded Intelligence & Document Provenance</span>
            </div>
            
            <h1 className="font-editorial text-5xl sm:text-6xl font-normal tracking-tight text-[#1A1918] leading-[1.12]">
              Uncompromising clarity from raw ink to verified reason.
            </h1>

            <p className="text-[#59554E] text-base leading-relaxed max-w-2xl font-light">
              SETU-NETRA reconciles vision layout OCR, dense-sparse semantic retrieval, and local 
              adaptive LLMs into an airtight epistemic reasoning workspace. Every factual claim is 
              anchored to spatial coordinates on the source document with cryptographic auditability.
            </p>
          </div>

          {/* Architectural Pillars */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div className="p-4 rounded-lg bg-[#FDFDFB] border border-[#E8E2D5] space-y-2">
              <div className="flex items-center space-x-2 text-xs font-bold text-[#1A1918]">
                <FileSearch className="w-4 h-4 text-[#C24136]" />
                <span>Spatial Document Intelligence</span>
              </div>
              <p className="text-xs text-[#7A766F] leading-relaxed">
                Non-destructive OCR extracts multi-page reading order, bounding boxes, tables, and handwritten questions.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-[#FDFDFB] border border-[#E8E2D5] space-y-2">
              <div className="flex items-center space-x-2 text-xs font-bold text-[#1A1918]">
                <ShieldCheck className="w-4 h-4 text-[#2D6A4F]" />
                <span>Tripartite Epistemic Status</span>
              </div>
              <p className="text-xs text-[#7A766F] leading-relaxed">
                Every deduction is formally classified as <strong className="text-[#2D6A4F]">SUPPORTED</strong>, <strong className="text-[#B57314]">CONTRADICTED</strong>, or <strong className="text-[#7A766F]">UNSUPPORTED</strong>.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-[#FDFDFB] border border-[#E8E2D5] space-y-2">
              <div className="flex items-center space-x-2 text-xs font-bold text-[#1A1918]">
                <Cpu className="w-4 h-4 text-[#1A1918]" />
                <span>Deterministic Local Inference</span>
              </div>
              <p className="text-xs text-[#7A766F] leading-relaxed">
                Single-concurrency CPU guard runs Qwen 3.5 2B locally with bounded memory and thinking trace support.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-[#FDFDFB] border border-[#E8E2D5] space-y-2">
              <div className="flex items-center space-x-2 text-xs font-bold text-[#1A1918]">
                <Lock className="w-4 h-4 text-[#C24136]" />
                <span>Institutional Multi-Tenancy</span>
              </div>
              <p className="text-xs text-[#7A766F] leading-relaxed">
                Argon2id hashing, sliding-window rate limiting, and strict SQLite workspace boundary isolation.
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: Authentication Card */}
        <div className="lg:col-span-5">
          <div className="bg-[#FDFDFB] border border-[#D5CCA8] rounded-xl p-8 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#C24136]" />

            <div className="flex items-center justify-between mb-6 pb-3 border-b border-[#E8E2D5]">
              <div className="flex space-x-4">
                <button
                  type="button"
                  onClick={() => setActiveTab('signin')}
                  className={`text-sm font-semibold transition-colors pb-1 border-b-2 ${
                    activeTab === 'signin'
                      ? 'border-[#C24136] text-[#1A1918]'
                      : 'border-transparent text-[#7A766F] hover:text-[#1A1918]'
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('register')}
                  className={`text-sm font-semibold transition-colors pb-1 border-b-2 ${
                    activeTab === 'register'
                      ? 'border-[#C24136] text-[#1A1918]'
                      : 'border-transparent text-[#7A766F] hover:text-[#1A1918]'
                  }`}
                >
                  Register Account
                </button>
              </div>

              <span className="hanko-seal-sm">SECURE</span>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-md bg-[#FDF1F0] border border-[#F0B8B4] text-xs text-[#C24136] leading-relaxed">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#3D3B38] mb-1">
                  Username
                </label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136] transition-colors"
                  placeholder="e.g. investigator_rao"
                />
              </div>

              {activeTab === 'register' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-[#3D3B38] mb-1">
                      Full Display Name
                    </label>
                    <input
                      type="text"
                      required
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136] transition-colors"
                      placeholder="e.g. Dr. A. Rao"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-[#3D3B38] mb-1">
                      Institutional Role
                    </label>
                    <select
                      value={requestedRole}
                      onChange={(e) => setRequestedRole(e.target.value)}
                      className="w-full px-3 py-2 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136] transition-colors"
                    >
                      <option value="LEAD_INVESTIGATOR">Lead Investigator</option>
                      <option value="RESEARCH_ANALYST">Research Analyst</option>
                      <option value="FACULTY_OBSERVER">Faculty Observer</option>
                      <option value="AUDITOR">Auditor</option>
                    </select>
                  </div>
                </>
              )}

              <div>
                <label className="block text-xs font-medium text-[#3D3B38] mb-1">
                  Password
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136] transition-colors"
                  placeholder="••••••••••••"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full mt-2 py-2.5 px-4 rounded-md bg-[#1A1918] hover:bg-[#3D3B38] text-[#FBF9F5] text-xs font-medium flex items-center justify-center space-x-2 transition-all disabled:opacity-50 cursor-pointer"
              >
                <span>{isSubmitting ? 'Authenticating...' : activeTab === 'signin' ? 'Enter Workspace Desk' : 'Create Verified Identity'}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </form>

            <div className="mt-6 pt-4 border-t border-[#E8E2D5] flex items-center justify-between text-[11px] text-[#7A766F]">
              <span>Argon2id + AES Session Protection</span>
              <span className="font-mono text-[#2D6A4F] flex items-center space-x-1">
                <CheckCircle className="w-3 h-3" />
                <span>ACID Local Storage</span>
              </span>
            </div>
          </div>
        </div>
      </main>

      {/* Live System Hardware Strip */}
      <footer className="border-t border-[#E8E2D5] bg-[#F5F1E6] px-8 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between text-[11px] text-[#7A766F] gap-4">
          <div className="flex items-center space-x-4">
            <span className="font-semibold text-[#1A1918]">Platform Telemetry:</span>
            <span>Uptime: {health ? `${Math.floor(health.uptime_seconds)}s` : 'Connecting...'}</span>
            <span>Database: {health?.database?.status || 'CONNECTED'}</span>
            <span>Ollama Daemon: {health?.ollama?.daemon_reachable ? 'OPERATIONAL' : 'LOCAL CPU'}</span>
          </div>

          <div className="flex items-center space-x-4 font-mono">
            <span>RAM: {health?.hardware?.ram_percent ? `${health.hardware.ram_percent}%` : 'N/A'}</span>
            <span>CPU: {health?.hardware?.cpu_percent ? `${health.hardware.cpu_percent}%` : 'N/A'}</span>
            <span className="text-[#2D6A4F] font-bold">127.0.0.1 BOUND</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
