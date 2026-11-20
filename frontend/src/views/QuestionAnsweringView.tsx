import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, DocumentRecord, QueryResult } from '../api/client';
import { 
  Search, 
  Upload, 
  Sparkles, 
  BrainCircuit, 
  CheckCircle2, 
  XCircle, 
  HelpCircle, 
  FileText, 
  ExternalLink, 
  Clock, 
  ChevronDown, 
  ChevronUp,
  Image as ImageIcon,
  Cpu,
  ShieldCheck,
  AlertCircle,
  Calculator,
  Code,
  BookOpen,
  Copy,
  Check,
  Loader2
} from 'lucide-react';

interface QuestionAnsweringViewProps {
  onNavigateToDocument: (docId: string, pageNumber: number, blockId?: number) => void;
}

export const QuestionAnsweringView: React.FC<QuestionAnsweringViewProps> = ({
  onNavigateToDocument,
}) => {
  const { activeWorkspaceId } = useAuth();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [queryText, setQueryText] = useState<string>('');
  const [queryMode, setQueryMode] = useState<'text' | 'image'>('text');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [modelId, setModelId] = useState<string>('auto');
  const [thinkMode, setThinkMode] = useState<boolean>(true);
  const [topK, setTopK] = useState<number>(3);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showThinking, setShowThinking] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if ((result || error) && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [result, error]);

  useEffect(() => {
    if (isSubmitting && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [isSubmitting]);

  // Fetch documents for the active workspace
  useEffect(() => {
    api.documents.list(activeWorkspaceId).then(setDocuments).catch(() => {});
  }, [activeWorkspaceId]);

  const handleFileProcess = (file: File) => {
    setImageFile(file);
    setQueryMode('image');
    setError(null);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    handleFileProcess(file);
  };

  const handleExecuteQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    setResult(null);

    try {
      if (queryMode === 'text') {
        if (!queryText.trim()) return;
        const res = await api.query.executeText({
          query: queryText.trim(),
          doc_id: selectedDocId || undefined,
          model_id: modelId === 'auto' ? undefined : modelId,
          think: thinkMode ? 'keep' : 'strip',
          top_k: topK,
        });
        setResult(res);
      } else {
        if (!imageFile) {
          setError('Please select or drag-and-drop a question image first.');
          setIsSubmitting(false);
          return;
        }
        const res = await api.query.executeImage({
          file: imageFile,
          doc_id: selectedDocId || undefined,
          model_id: modelId === 'auto' ? undefined : modelId,
          think: thinkMode ? 'keep' : 'strip',
          top_k: topK,
        });
        setResult(res);
      }
    } catch (err: any) {
      setError(err?.detail || err?.title || 'Execution failed. Check Ollama daemon or model availability.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderEpistemicBadge = (status: string, score: number) => {
    const s = (status || '').toUpperCase();
    if (s === 'COMPUTATION_VERIFIED') {
      return (
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#EBF7EE] border border-[#40916C] text-[#2D6A4F]">
          <Calculator className="w-4 h-4 text-[#2D6A4F]" />
          <span className="font-bold text-xs tracking-wide">COMPUTATION VERIFIED</span>
          <span className="text-[11px] font-mono font-medium">(Deterministic AST Proof)</span>
        </div>
      );
    }
    if (s === 'LOGIC_VERIFIED' || s === 'FORMULA_VERIFIED' || s === 'SQL_LOGIC_VERIFIED') {
      return (
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#F3E8FF] border border-[#9333EA] text-[#6B21A8]">
          <Code className="w-4 h-4 text-[#6B21A8]" />
          <span className="font-bold text-xs tracking-wide">{s.replace(/_/g, ' ')}</span>
          <span className="text-[11px] font-mono font-medium">(Formal Proof)</span>
        </div>
      );
    }
    if (s === 'CODE_EXECUTION_VERIFIED') {
      return (
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#EFF6FF] border border-[#3B82F6] text-[#1D4ED8]">
          <Cpu className="w-4 h-4 text-[#1D4ED8]" />
          <span className="font-bold text-xs tracking-wide">CODE EXECUTION VERIFIED</span>
          <span className="text-[11px] font-mono font-medium">(Deterministic Execution)</span>
        </div>
      );
    }
    if (s === 'SUPPORTED' || s === 'EVIDENCE_BACKED') {
      return (
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#EBF7EE] border border-[#40916C] text-[#2D6A4F]">
          <CheckCircle2 className="w-4 h-4 text-[#2D6A4F]" />
          <span className="font-bold text-xs tracking-wide">EVIDENCE BACKED</span>
          <span className="text-[11px] font-mono font-medium">({(score * 100).toFixed(0)}% grounded)</span>
        </div>
      );
    }
    if (s === 'GENERAL_KNOWLEDGE') {
      return (
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#FFFBEB] border border-[#F59E0B] text-[#B45309]">
          <HelpCircle className="w-4 h-4 text-[#B45309]" />
          <span className="font-bold text-xs tracking-wide">GENERAL KNOWLEDGE</span>
          <span className="text-[11px] font-mono font-medium">(External Model Synthesis)</span>
        </div>
      );
    }
    if (s === 'CONTRADICTED') {
      return (
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#FFF9EB] border border-[#D48B28] text-[#B57314]">
          <XCircle className="w-4 h-4 text-[#B57314]" />
          <span className="font-bold text-xs tracking-wide">CONTRADICTED</span>
          <span className="text-[11px] font-mono font-medium">({(score * 100).toFixed(0)}% conflict)</span>
        </div>
      );
    }
    return (
      <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#F3F1EC] border border-[#9E9A92] text-[#6E6A64]">
        <HelpCircle className="w-4 h-4 text-[#6E6A64]" />
        <span className="font-bold text-xs tracking-wide">UNSUPPORTED</span>
        <span className="text-[11px] font-mono font-medium">(Insufficient evidence)</span>
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-150">
      {/* Header */}
      <div className="border-b border-[#E8E2D5] pb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs font-mono font-medium text-[#C24136] tracking-wider uppercase">
            Epistemic Inquiry Engine
          </span>
          <h2 className="font-editorial text-3xl font-bold text-[#1A1918]">
            Evidence-Grounded Intelligence QA
          </h2>
        </div>

        <div className="flex items-center space-x-2">
          <span className="hanko-seal">TRIPARTITE PROVENANCE</span>
        </div>
      </div>

      {/* Query Formulation Workbench Card */}
      <div className="bg-[#FDFDFB] border border-[#D5CCA8] rounded-xl p-6 shadow-xs space-y-5">
        {/* Mode Selector Tabs (Typed Query vs Image-Based OCR-to-Query) */}
        <div className="flex items-center justify-between border-b border-[#E8E2D5] pb-3">
          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => setQueryMode('text')}
              className={`flex items-center space-x-1.5 text-xs font-semibold pb-1 border-b-2 cursor-pointer transition-colors ${
                queryMode === 'text'
                  ? 'border-[#C24136] text-[#1A1918]'
                  : 'border-transparent text-[#7A766F] hover:text-[#1A1918]'
              }`}
            >
              <Search className="w-3.5 h-3.5" />
              <span>Typed Inquiry</span>
            </button>

            <button
              type="button"
              onClick={() => setQueryMode('image')}
              className={`flex items-center space-x-1.5 text-xs font-semibold pb-1 border-b-2 cursor-pointer transition-colors ${
                queryMode === 'image'
                  ? 'border-[#C24136] text-[#1A1918]'
                  : 'border-transparent text-[#7A766F] hover:text-[#1A1918]'
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Handwritten / Image Question Ingestion</span>
            </button>
          </div>

          <div className="flex items-center space-x-4 text-xs">
            {/* Thinking Mode Toggle */}
            <label className="flex items-center space-x-1.5 cursor-pointer text-[#59554E]">
              <BrainCircuit className="w-3.5 h-3.5 text-[#C24136]" />
              <span className="text-[11px] font-medium">Qwen Think Trace</span>
              <input
                type="checkbox"
                checked={thinkMode}
                onChange={(e) => setThinkMode(e.target.checked)}
                className="rounded border-[#E8E2D5] text-[#C24136] focus:ring-[#C24136]"
              />
            </label>
          </div>
        </div>

        {/* Query Input Form */}
        <form onSubmit={handleExecuteQuery} className="space-y-4">
          {queryMode === 'text' ? (
            <div>
              <label className="block text-xs font-medium text-[#3D3B38] mb-1.5">
                Research Inquiry or Verification Hypothesis
              </label>
              <div className="relative">
                <textarea
                  rows={3}
                  required
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder="e.g. What are the key architectural principles governing evidence grounding in SETU-NETRA?"
                  className="w-full px-4 py-3 rounded-lg border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136] leading-relaxed resize-none"
                />
              </div>

              {/* Sample Quick Questions */}
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <span className="text-[10px] text-[#7A766F] font-semibold uppercase">Prompts:</span>
                {[
                  'What is the primary function of the reconstructor?',
                  'Explain the Tripartite epistemic status classification.',
                  'How does the Ollama concurrency guard prevent memory spikes?',
                ].map((sample) => (
                  <button
                    key={sample}
                    type="button"
                    onClick={() => setQueryText(sample)}
                    className="text-[11px] px-2.5 py-1 rounded-md bg-[#F5F1E6] hover:bg-[#E8E2D5] text-[#3D3B38] transition-colors cursor-pointer"
                  >
                    {sample}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-[#3D3B38] mb-1.5 flex items-center justify-between">
                <span>Upload Question Image (Handwriting, Exam Snippet, or Screenshot)</span>
                {imageFile && (
                  <span className="text-[11px] font-mono text-[#2D6A4F] font-bold">
                    ✓ Image Loaded ({(imageFile.size / 1024).toFixed(0)} KB)
                  </span>
                )}
              </label>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImageSelect}
                accept=".png,.jpg,.jpeg,.bmp,.webp"
                className="hidden"
                id="question-image-upload"
              />
              <div
                onClick={() => !isSubmitting && !imagePreview && fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleFileProcess(file);
                }}
                className={`border-2 border-dashed rounded-lg p-5 text-center transition-all space-y-3 relative overflow-hidden ${
                  isDragging
                    ? 'border-[#C24136] bg-[#FDF1F0]'
                    : imagePreview
                    ? 'border-[#A39E93] bg-[#FAF8F5]'
                    : 'border-[#D5CCA8] bg-[#FBF9F5] hover:bg-[#F5F1E6] cursor-pointer'
                }`}
              >
                {isSubmitting && (
                  <div className="absolute inset-0 bg-[#FBF9F5]/95 backdrop-blur-xs flex flex-col items-center justify-center rounded-lg z-20 space-y-3">
                    <Loader2 className="w-8 h-8 text-[#C24136] animate-spin" />
                    <p className="text-sm font-bold text-[#1A1918]">Extracting OCR & Synthesizing Proof...</p>
                    <p className="text-xs text-[#7A766F] font-mono">Executing layout segmentation & deterministic domain solvers</p>
                  </div>
                )}

                {imagePreview ? (
                  <div className="space-y-3">
                    <div className="relative inline-block mx-auto max-w-full">
                      <img
                        src={imagePreview}
                        alt="Question preview"
                        className="max-h-52 max-w-full mx-auto rounded shadow-sm border border-[#E8E2D5] object-contain"
                      />
                    </div>
                    
                    <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
                      <span className="text-xs font-semibold text-[#1A1918] bg-white px-2.5 py-1 rounded border border-[#E8E2D5]">
                        {imageFile?.name}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                        className="text-xs px-3 py-1 rounded bg-[#FAF8F5] hover:bg-[#E8E2D5] border border-[#D5CCA8] text-[#59554E] cursor-pointer font-medium transition-colors"
                      >
                        Change Image
                      </button>
                    </div>

                    {/* Instant Direct Solve Action Button */}
                    <div className="pt-2 flex justify-center">
                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExecuteQuery(e as any);
                        }}
                        className="w-full sm:w-auto px-8 py-3 rounded-lg bg-[#C24136] hover:bg-[#A93226] text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center space-x-2 transition-all cursor-pointer disabled:opacity-50 shadow-md hover:shadow-lg active:scale-98"
                      >
                        <Sparkles className="w-4 h-4 text-[#FDE68A]" />
                        <span>{isSubmitting ? 'Analyzing & Solving...' : '⚡ Solve & Verify Question Now'}</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="py-4 space-y-2">
                    <Upload className="w-10 h-10 mx-auto text-[#B5B0A6]" />
                    <p className="text-xs font-semibold text-[#1A1918]">
                      Drag and drop handwritten question image here, or click to browse
                    </p>
                    <p className="text-[11px] text-[#7A766F] max-w-md mx-auto">
                      Supports PNG, JPG, JPEG. Automatically extracts logical structure, options, formulas, and evaluates proofs.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Model & Scope Controls Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div>
              <label className="block text-[11px] font-medium text-[#7A766F] mb-1">
                Document Scope
              </label>
              <select
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="w-full px-3 py-1.5 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136]"
              >
                <option value="">Entire Workspace Corpus</option>
                {documents.map((d) => (
                  <option key={d.doc_id} value={d.doc_id}>
                    {d.file_name} ({d.page_count}p)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#7A766F] mb-1">
                Orchestrated Model
              </label>
              <select
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                className="w-full px-3 py-1.5 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136]"
              >
                <option value="auto">Auto Adaptive Router (Local First)</option>
                <option value="ollama/qwen3.5:2b">Ollama Qwen 3.5 2B (Local CPU)</option>
                <option value="local/smollm2:135m">SmolLM2 135M (Fast Fallback)</option>
                <option value="gemini/gemini-2.5-flash">Gemini 2.5 Flash (Cloud)</option>
                <option value="groq/llama-3.3-70b-versatile">Groq Llama 3.3 70B (Cloud)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#7A766F] mb-1">
                Top-K Citations
              </label>
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-md border border-[#E8E2D5] bg-[#FBF9F5] text-xs text-[#1A1918] focus:outline-none focus:border-[#C24136]"
              >
                <option value={2}>Top 2 Passages</option>
                <option value={3}>Top 3 Passages (Default)</option>
                <option value={5}>Top 5 Passages</option>
              </select>
            </div>
          </div>

          <div className="pt-3 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-[#E8E2D5]">
            <div className="text-[11px] text-[#7A766F] font-mono">
              {queryMode === 'image' && imageFile ? (
                <span className="text-[#2D6A4F] font-semibold">
                  Ready to solve: {imageFile.name} (Click button to execute)
                </span>
              ) : (
                'Configure parameters and click to execute grounded verification.'
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting || (queryMode === 'image' && !imageFile)}
              className={`w-full sm:w-auto py-2.5 px-6 rounded-md text-white text-xs font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer disabled:opacity-50 shadow-xs ${
                queryMode === 'image'
                  ? 'bg-[#C24136] hover:bg-[#A93226]'
                  : 'bg-[#1A1918] hover:bg-[#3D3B38]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-[#E5DFC9]" />
              <span>
                {isSubmitting
                  ? 'Synthesizing Verified Proof...'
                  : queryMode === 'image'
                  ? '⚡ Solve Handwritten Question'
                  : 'Execute Grounded Inquiry'}
              </span>
            </button>
          </div>
        </form>
      </div>

      <div ref={resultRef} className="space-y-6">
        {error && (
          <div className="p-4 rounded-lg bg-[#FDF1F0] border border-[#F0B8B4] text-xs text-[#C24136] flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Synthesis Result Display */}
        {result && (
          <div className="bg-[#FDFDFB] border border-[#D5CCA8] rounded-xl p-8 shadow-xs space-y-6 animate-in fade-in duration-200">
          {/* Header with Epistemic Status & Grounding Metric */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[#E8E2D5]">
            <div className="space-y-1">
              <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                Epistemic Outcome
              </span>
              <div>{renderEpistemicBadge(result.epistemic_status, result.grounding_score)}</div>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-[#7A766F]">
              <span className="px-2 py-0.5 rounded bg-[#E8E2D5] font-bold text-[#1A1918]">
                {result.domain || 'DOCUMENT_QA'}
              </span>
              <span className="flex items-center space-x-1">
                <Cpu className="w-3.5 h-3.5 text-[#1A1918]" />
                <span>{result.executing_model_id || 'qwen3.5:2b'}</span>
              </span>
              <span className="flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5 text-[#1A1918]" />
                <span>{Math.round(result.execution_time_ms)}ms</span>
              </span>
            </div>
          </div>

          {/* Reconstructed Question Card */}
          <div className="p-4 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5] space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider flex items-center space-x-1">
                <FileText className="w-3 h-3 text-[#C24136]" />
                <span>Reconstructed Question</span>
              </span>
              {result.ocr_confidence !== undefined && (
                <span className="text-[10px] font-mono text-[#59554E]">
                  OCR Conf: {(result.ocr_confidence * 100).toFixed(1)}%
                </span>
              )}
            </div>
            <p className="text-sm font-serif text-[#1A1918] leading-relaxed whitespace-pre-line font-medium">
              {result.reconstructed_question || result.extracted_question || result.query}
            </p>
          </div>

          {/* Options Card if multiple choice */}
          {result.options && result.options.length > 0 && (
            <div className="space-y-2 p-4 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5]">
              <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                Candidate Options
              </span>
              <div className="grid grid-cols-1 gap-2 pt-1">
                {result.options.map((opt: any) => {
                  const isSelected = opt.label?.toUpperCase() === result.selected_option?.toUpperCase();
                  return (
                    <div
                      key={opt.label}
                      className={`p-3 rounded-lg border text-xs transition-all ${
                        isSelected
                          ? 'border-[#2D6A4F] bg-[#EBF7EE] shadow-2xs font-semibold'
                          : 'border-[#E8E2D5] bg-[#FDFDFB]'
                      }`}
                    >
                      <div className="flex items-center justify-between pb-1">
                        <span className={`w-5 h-5 rounded flex items-center justify-center font-mono text-[10px] font-bold ${
                          isSelected ? 'bg-[#2D6A4F] text-white' : 'bg-[#E8E2D5] text-[#59554E]'
                        }`}>
                          {opt.label}
                        </span>
                        {isSelected && (
                          <span className="text-[11px] text-[#2D6A4F] font-bold flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Correct Choice</span>
                          </span>
                        )}
                      </div>
                      <pre className="font-mono text-xs text-[#1A1918] whitespace-pre-wrap leading-relaxed">
                        {opt.text}
                      </pre>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Answer Card */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-[#C24136] tracking-wider">
                Verified Answer
              </span>
              <span className="text-[10px] font-mono text-[#7A766F]">
                Verification: {result.verification_method || 'DETERMINISTIC_PROOF'}
              </span>
            </div>
            <div className="font-editorial text-2xl font-bold text-[#1A1918] bg-[#FAF6EE] p-5 rounded-lg border border-[#D5CCA8] shadow-2xs whitespace-pre-line">
              {result.answer_text}
            </div>
          </div>

          {/* Step-by-Step Explanation / Derivation */}
          {(result.step_by_step_explanation || result.explanation) && (
            <div className="space-y-2 p-4 rounded-lg bg-[#FDFDFB] border border-[#E8E2D5]">
              <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider flex items-center space-x-1.5">
                <BookOpen className="w-3.5 h-3.5 text-[#3D3B38]" />
                <span>Calculation Steps & Logical Derivation</span>
              </span>
              <div className="text-xs text-[#3D3B38] whitespace-pre-line leading-relaxed font-serif">
                {result.step_by_step_explanation || result.explanation}
              </div>
            </div>
          )}

          {/* Reasoning / Thinking Accordion */}
          {result.thinking && (
            <div className="border border-[#E8E2D5] rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setShowThinking(!showThinking)}
                className="w-full px-4 py-2.5 bg-[#F5F1E6] hover:bg-[#EFECE3] flex items-center justify-between text-xs font-medium text-[#3D3B38] transition-colors cursor-pointer"
              >
                <div className="flex items-center space-x-2">
                  <BrainCircuit className="w-3.5 h-3.5 text-[#C24136]" />
                  <span>Model Deliberation & Reasoning Trace ({result.thinking.length} chars)</span>
                </div>
                {showThinking ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showThinking && (
                <div className="p-4 bg-[#FDFDFB] text-[11px] font-mono text-[#59554E] leading-relaxed max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-[#E8E2D5]">
                  {result.thinking}
                </div>
              )}
            </div>
          )}

          {/* Grounded Citation Cards (Filtered to non-empty only) */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[#59554E] flex items-center space-x-1.5">
                <ShieldCheck className="w-4 h-4 text-[#2D6A4F]" />
                <span>
                  Grounded Evidence Citations ({(result.citations || []).filter((c) => c && c.text && c.text.trim()).length})
                </span>
              </span>
              <span className="text-[10px] font-mono text-[#7A766F]">
                Trace ID: {result.correlation_id}
              </span>
            </div>

            {(() => {
              const validCites = (result.citations || []).filter((c) => c && c.text && c.text.trim());
              if (validCites.length === 0) {
                if (result.domain === 'ARITHMETIC') {
                  return (
                    <div className="p-3.5 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5] text-xs text-[#59554E] font-mono">
                      Deterministic Mathematical Proof: Derived from formal arithmetic axioms and operator precedence. No document citations required.
                    </div>
                  );
                }
                if (result.domain === 'SQL' || result.domain === 'LOGICAL_REASONING' || result.domain === 'FORMAL_LOGIC') {
                  return (
                    <div className="p-3.5 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5] text-xs text-[#59554E] font-mono">
                      Formal Logical Verification: Evaluated through {result.verification_method || 'formal deductive proofs and countermodels'}. No document citations required.
                    </div>
                  );
                }
                if (result.domain === 'DBMS_NORMALIZATION') {
                  return (
                    <div className="p-3.5 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5] text-xs text-[#59554E] font-mono">
                      Relational Algebra & Normal Form Closure Proof: Verified through attribute closures X+ and dependency normal forms. No document citations required.
                    </div>
                  );
                }
                if (result.domain === 'CRYPTOGRAPHY') {
                  return (
                    <div className="p-3.5 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5] text-xs text-[#59554E] font-mono">
                      Cryptographic Deterministic Proof: Evaluated through modular number theory and parameter synthesis. No document citations required.
                    </div>
                  );
                }
                if (result.domain === 'MATHEMATICS') {
                  return (
                    <div className="p-3.5 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5] text-xs text-[#59554E] font-mono">
                      Mathematical Closed-Form Derivation: Evaluated via deterministic algebraic formula proofs. No document citations required.
                    </div>
                  );
                }
                return (
                  <p className="text-xs text-[#7A766F] italic">
                    No external document citations required or retrieved for this inquiry.
                  </p>
                );
              }

              return (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {validCites.map((cite, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-lg bg-[#FBF9F5] border border-[#E8E2D5] space-y-2 hover:border-[#D5CCA8] transition-all"
                    >
                      <div className="flex items-center justify-between text-[11px] font-mono text-[#7A766F]">
                        <span className="font-semibold text-[#1A1918] truncate max-w-[160px]">
                          {cite.document_name || cite.doc_id}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-[#F0ECE1]">
                          Page {cite.page_number} {cite.block_id !== undefined ? `• Block #${cite.block_id}` : ''}
                        </span>
                      </div>

                      <p className="text-xs text-[#3D3B38] font-serif leading-relaxed line-clamp-3">
                        "{cite.text}"
                      </p>

                      <div className="pt-2 border-t border-[#E8E2D5] flex items-center justify-between">
                        <span className="text-[10px] font-mono text-[#2D6A4F]">
                          Score: {cite.relevance_score ? cite.relevance_score.toFixed(3) : 'Verified'}
                        </span>
                        <button
                          type="button"
                          onClick={() => onNavigateToDocument(cite.doc_id, cite.page_number, cite.block_id)}
                          className="text-xs font-medium text-[#C24136] hover:underline flex items-center space-x-1 cursor-pointer"
                        >
                          <span>Locate on Canvas</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>
      )}
      </div>
    </div>
  );
};
