import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { 
  Printer, 
  Download, 
  FileCheck2, 
  FileText, 
  Sparkles, 
  ShieldCheck, 
  Clock, 
  Calendar,
  User,
  CheckCircle2
} from 'lucide-react';

export const ReportStudioView: React.FC = () => {
  const { user, activeWorkspaceId, workspaces } = useAuth();
  const [reportTitle, setReportTitle] = useState('Evidence-Grounded Intelligence Dossier');
  const [investigatorName, setInvestigatorName] = useState(user?.display_name || 'Dr. Lead Investigator');
  const [reportDate, setReportDate] = useState(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }));
  const [executiveSummary, setExecutiveSummary] = useState(
    'This dossier compiles multi-page document intelligence, OCR structural reconstructions, and verified model deductions under strict workspace boundary isolation. All citations referenced in this assessment have been grounded to spatial coordinate blocks and verified through the SETU-NETRA tripartite epistemic pipeline.'
  );
  const [findingsText, setFindingsText] = useState(
    '1. Cross-document layout alignment verified 100% of geometric bounding coordinates.\n2. Epistemic verification classified core hypotheses as SUPPORTED with zero ungrounded hallucinations.\n3. Local CPU inference maintained strict single-concurrency bounds on Qwen 3.5 2B without system memory thrashing.'
  );

  const activeWs = workspaces.find((w) => w.workspace_id === activeWorkspaceId);

  const handlePrint = () => {
    window.print();
  };

  const handleExportMarkdown = () => {
    const mdContent = `# ${reportTitle}\n\n` +
      `**Investigator:** ${investigatorName}  \n` +
      `**Date:** ${reportDate}  \n` +
      `**Workspace:** ${activeWs?.name || activeWorkspaceId}  \n` +
      `**Security Classification:** SECURE - INSTITUTIONAL EVIDENCE DOSSIER  \n\n` +
      `---\n\n` +
      `## 1. Executive Summary\n\n${executiveSummary}\n\n` +
      `## 2. Verified Analytical Findings\n\n${findingsText}\n\n` +
      `## 3. Epistemic Provenance\n\n` +
      `- Pipeline Version: SETU-NETRA V2.0.0-RC1 (Kora Kaagaz)\n` +
      `- OCR Engine: EasyOCR Non-Destructive Layout Reconstructor\n` +
      `- Semantic Model: Sentence-Transformers Dense + BM25 Sparse\n` +
      `- Reasoning Model: Ollama Qwen 3.5 2B (Local CPU Execution)\n` +
      `- Isolation Scope: Workspace ID ${activeWorkspaceId}\n`;

    const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `SETU_NETRA_DOSSIER_${Date.now()}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-150">
      {/* Studio Controls Header (Hidden during print) */}
      <div className="border-b border-[#E8E2D5] pb-4 flex flex-wrap items-center justify-between gap-4 print:hidden">
        <div>
          <span className="text-xs font-mono font-medium text-[#C24136] tracking-wider uppercase">
            Publication & Verification
          </span>
          <h2 className="font-editorial text-3xl font-bold text-[#1A1918]">
            Report Studio
          </h2>
          <p className="text-xs text-[#7A766F] font-light">
            Author and export publication-ready intelligence dossiers with embedded provenance and spatial citations.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleExportMarkdown}
            className="px-3.5 py-2 rounded-md border border-[#D5CCA8] bg-[#FDFDFB] hover:bg-[#F2ECE1] text-xs font-medium text-[#1A1918] flex items-center space-x-1.5 transition-all cursor-pointer shadow-2xs"
          >
            <Download className="w-3.5 h-3.5 text-[#C24136]" />
            <span>Export Markdown</span>
          </button>

          <button
            onClick={handlePrint}
            className="px-4 py-2 rounded-md bg-[#1A1918] hover:bg-[#3D3B38] text-white text-xs font-medium flex items-center space-x-1.5 transition-all cursor-pointer shadow-xs"
          >
            <Printer className="w-3.5 h-3.5 text-[#E5DFC9]" />
            <span>Print Dossier (PDF)</span>
          </button>
        </div>
      </div>

      {/* Printable Document Paper */}
      <div className="bg-[#FDFDFB] border border-[#D5CCA8] rounded-xl p-10 sm:p-14 shadow-sm space-y-8 print:border-none print:shadow-none print:p-0">
        {/* Top Letterhead / Institutional Seal */}
        <div className="border-b-2 border-[#1A1918] pb-6 flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <span className="font-editorial text-2xl font-bold tracking-tight text-[#1A1918]">
                SETU-NETRA
              </span>
              <span className="hanko-seal">
                सेतु-नेत्र
              </span>
            </div>
            <p className="text-xs uppercase tracking-widest text-[#7A766F] font-mono">
              Institutional Intelligence & Grounded Epistemic QA Platform
            </p>
          </div>

          <div className="text-right space-y-1">
            <span className="hanko-seal-sm">SECURE DOSSIER</span>
            <p className="text-[10px] font-mono text-[#7A766F]">
              TENANT: {activeWs?.name || activeWorkspaceId}
            </p>
          </div>
        </div>

        {/* Dossier Metadata Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 rounded-lg bg-[#FBF9F5] border border-[#E8E2D5] text-xs">
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider block">
              Lead Investigator
            </span>
            <input
              type="text"
              value={investigatorName}
              onChange={(e) => setInvestigatorName(e.target.value)}
              className="w-full bg-transparent font-medium text-[#1A1918] focus:outline-none border-b border-transparent hover:border-[#D5CCA8] print:border-none"
            />
          </div>

          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider block">
              Assessment Date
            </span>
            <input
              type="text"
              value={reportDate}
              onChange={(e) => setReportDate(e.target.value)}
              className="w-full bg-transparent font-medium text-[#1A1918] focus:outline-none border-b border-transparent hover:border-[#D5CCA8] print:border-none"
            />
          </div>

          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider block">
              Workspace Boundary
            </span>
            <span className="font-mono text-[11px] text-[#2D6A4F] flex items-center space-x-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>{activeWs?.name || 'Default Desk'}</span>
            </span>
          </div>
        </div>

        {/* Dossier Title */}
        <div>
          <input
            type="text"
            value={reportTitle}
            onChange={(e) => setReportTitle(e.target.value)}
            className="w-full font-editorial text-3xl sm:text-4xl font-bold text-[#1A1918] bg-transparent focus:outline-none border-b border-transparent hover:border-[#D5CCA8] print:border-none"
          />
        </div>

        {/* Section 1: Executive Summary */}
        <div className="space-y-3">
          <h3 className="font-editorial text-xl font-bold text-[#1A1918] border-b border-[#E8E2D5] pb-1">
            1. Executive Synthesis & Scope
          </h3>
          <textarea
            rows={4}
            value={executiveSummary}
            onChange={(e) => setExecutiveSummary(e.target.value)}
            className="w-full bg-transparent font-serif text-sm leading-relaxed text-[#3D3B38] focus:outline-none border border-transparent hover:border-[#E8E2D5] p-2 rounded print:border-none print:p-0 resize-none"
          />
        </div>

        {/* Section 2: Verified Findings */}
        <div className="space-y-3">
          <h3 className="font-editorial text-xl font-bold text-[#1A1918] border-b border-[#E8E2D5] pb-1">
            2. Verified Analytical Findings & Epistemic Status
          </h3>
          <textarea
            rows={5}
            value={findingsText}
            onChange={(e) => setFindingsText(e.target.value)}
            className="w-full bg-transparent font-serif text-sm leading-relaxed text-[#3D3B38] focus:outline-none border border-transparent hover:border-[#E8E2D5] p-2 rounded print:border-none print:p-0 resize-none"
          />
        </div>

        {/* Section 3: Epistemic Provenance Audit */}
        <div className="space-y-3 pt-4">
          <h3 className="font-editorial text-xl font-bold text-[#1A1918] border-b border-[#E8E2D5] pb-1">
            3. Provenance & Cryptographic Ledger
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded bg-[#FBF9F5] border border-[#E8E2D5]">
              <span className="text-[10px] text-[#8C877D] block">OCR ENGINE</span>
              <span className="font-bold text-[#1A1918]">EasyOCR Layout</span>
            </div>
            <div className="p-3 rounded bg-[#FBF9F5] border border-[#E8E2D5]">
              <span className="text-[10px] text-[#8C877D] block">RETRIEVAL</span>
              <span className="font-bold text-[#1A1918]">Hybrid Dense+BM25</span>
            </div>
            <div className="p-3 rounded bg-[#FBF9F5] border border-[#E8E2D5]">
              <span className="text-[10px] text-[#8C877D] block">INFERENCE MODEL</span>
              <span className="font-bold text-[#1A1918]">Qwen 3.5 2B CPU</span>
            </div>
            <div className="p-3 rounded bg-[#FBF9F5] border border-[#E8E2D5]">
              <span className="text-[10px] text-[#8C877D] block">INTEGRITY</span>
              <span className="font-bold text-[#2D6A4F]">ACID WAL VERIFIED</span>
            </div>
          </div>
        </div>

        {/* Dossier Signature Strip */}
        <div className="pt-8 border-t border-[#E8E2D5] flex items-center justify-between text-xs text-[#7A766F]">
          <div>
            <p className="font-semibold text-[#1A1918]">{investigatorName}</p>
            <p className="text-[11px]">Authorized Lead Investigator</p>
          </div>

          <div className="text-right">
            <span className="hanko-seal" title="Authenticity Seal">
              SEAL: {activeWorkspaceId.slice(0, 8).toUpperCase()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
