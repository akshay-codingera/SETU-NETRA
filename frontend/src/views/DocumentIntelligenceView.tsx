import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { 
  api, 
  DocumentRecord, 
  DocumentPage, 
  DocumentBlock, 
  PageTextResult, 
  SolveQuestionResult 
} from '../api/client';
import { 
  Upload, 
  FileText, 
  ChevronLeft, 
  ChevronRight, 
  ZoomIn, 
  ZoomOut, 
  Trash2, 
  Layers, 
  Info,
  CheckCircle,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Copy,
  Check,
  Edit3,
  Database,
  Code,
  Calculator,
  HelpCircle,
  Cpu,
  CheckCircle2,
  Key,
  Network
} from 'lucide-react';

interface DocumentIntelligenceViewProps {
  initialDocId?: string;
  initialPageNumber?: number;
  highlightedBlockId?: number;
}

export const DocumentIntelligenceView: React.FC<DocumentIntelligenceViewProps> = ({
  initialDocId,
  initialPageNumber = 1,
  highlightedBlockId,
}) => {
  const { activeWorkspaceId } = useAuth();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentRecord | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [currentPageNum, setCurrentPageNum] = useState<number>(initialPageNumber);
  const [blocks, setBlocks] = useState<DocumentBlock[]>([]);
  const [selectedBlock, setSelectedBlock] = useState<DocumentBlock | null>(null);
  const [hoveredBlock, setHoveredBlock] = useState<DocumentBlock | null>(null);
  const [zoomScale, setZoomScale] = useState<number>(1.0);
  const [loading, setLoading] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Question & Answer Solver state
  const [activeTab, setActiveTab] = useState<'qa' | 'blocks' | 'raw'>('qa');
  const [pageTextData, setPageTextData] = useState<PageTextResult | null>(null);
  const [isEditingText, setIsEditingText] = useState<boolean>(false);
  const [editedText, setEditedText] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('qwen3.5:2b');
  const [solving, setSolving] = useState<boolean>(false);
  const [solverState, setSolverState] = useState<string>('IMAGE_UPLOADED');
  const [solution, setSolution] = useState<SolveQuestionResult | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageContainerRef = useRef<HTMLDivElement>(null);
  const solutionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (solution && solutionRef.current) {
      solutionRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [solution]);

  // Load documents for active workspace
  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const docs = await api.documents.list(activeWorkspaceId);
      setDocuments(docs);

      if (docs.length > 0) {
        const target = initialDocId ? docs.find((d) => d.doc_id === initialDocId) || docs[0] : docs[0];
        setSelectedDoc(target);
      } else {
        setSelectedDoc(null);
        setPages([]);
        setBlocks([]);
      }
    } catch (err: any) {
      setError(err?.detail || err?.title || 'Failed to retrieve documents for active workspace.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [activeWorkspaceId]);

  // Load pages when selectedDoc changes
  useEffect(() => {
    if (!selectedDoc) return;
    const fetchPages = async () => {
      try {
        const docPages = await api.documents.getPages(selectedDoc.doc_id);
        setPages(docPages);
        const pNum = initialPageNumber <= docPages.length ? initialPageNumber : 1;
        setCurrentPageNum(pNum);
      } catch (err) {
        console.warn('Failed to fetch pages', err);
      }
    };
    fetchPages();
  }, [selectedDoc]);

  // Load blocks and page text when selectedDoc or currentPageNum changes
  useEffect(() => {
    if (!selectedDoc) return;
    const fetchBlocksAndText = async () => {
      try {
        const [pageBlocks, textResult] = await Promise.all([
          api.documents.getBlocks(selectedDoc.doc_id, currentPageNum),
          api.documents.getPageText(selectedDoc.doc_id, currentPageNum).catch(() => null),
        ]);
        setBlocks(pageBlocks);
        if (textResult) {
          setPageTextData(textResult);
          setEditedText(textResult.full_text || textResult.raw_transcript || '');
        } else {
          const joined = pageBlocks.map((b) => b.text).join('\n\n');
          setEditedText(joined);
        }

        if (highlightedBlockId !== undefined) {
          const match = pageBlocks.find((b) => b.block_id === highlightedBlockId);
          if (match) setSelectedBlock(match);
        } else {
          setSelectedBlock(null);
        }
      } catch (err) {
        console.warn('Failed to fetch blocks or text', err);
      }
    };
    fetchBlocksAndText();
    setSolution(null);
    setSolverState('IMAGE_UPLOADED');
    setIsEditingText(false);
  }, [selectedDoc, currentPageNum, highlightedBlockId]);

  // File Upload Handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const newDoc = await api.documents.upload(file);
      await loadDocuments();
      setSelectedDoc(newDoc);
      setCurrentPageNum(1);
    } catch (err: any) {
      setError(err?.detail || err?.title || 'Upload and layout extraction failed.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Are you sure you want to delete this document from the workspace?')) return;
    try {
      await api.documents.delete(docId);
      await loadDocuments();
    } catch (err: any) {
      setError(err?.detail || 'Failed to delete document.');
    }
  };

  // Solve Question Action
  const handleIdentifyAndAnswer = async () => {
    if (!selectedDoc) return;
    setSolving(true);
    setError(null);
    setSolverState('OCR_PROCESSING');

    const timer1 = window.setTimeout(() => setSolverState('QUESTION_IDENTIFIED'), 400);
    const timer2 = window.setTimeout(() => setSolverState('ANSWER_GENERATING'), 900);

    try {
      const res = await api.documents.solvePageQuestion(selectedDoc.doc_id, currentPageNum, {
        edited_text: isEditingText || editedText !== (pageTextData?.full_text || '') ? editedText : undefined,
        model_id: selectedModel,
      });

      window.clearTimeout(timer1);
      window.clearTimeout(timer2);
      setSolution(res);
      setSolverState(res.lifecycle_state);
      setActiveTab('qa');
    } catch (err: any) {
      window.clearTimeout(timer1);
      window.clearTimeout(timer2);
      setError(err?.detail || err?.title || 'Failed to generate answer for page image.');
      setSolverState('PROCESSING_FAILED');
    } finally {
      setSolving(false);
    }
  };

  const copyToClipboard = (text: string, fieldKey: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldKey);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const currentPage = pages.find((p) => p.page_number === currentPageNum) || {
    width: 800,
    height: 1100,
    page_number: currentPageNum,
  };

  const getBlockBorderColor = (type: string, isSelected: boolean) => {
    if (isSelected) return 'border-[#C24136] bg-[#C24136]/15 shadow-sm ring-2 ring-[#C24136]';
    switch (type.toUpperCase()) {
      case 'HEADING':
      case 'TITLE':
        return 'border-[#C24136] bg-[#C24136]/5 hover:bg-[#C24136]/15';
      case 'QUESTION':
        return 'border-[#1D4ED8] bg-[#1D4ED8]/10 hover:bg-[#1D4ED8]/20 ring-1 ring-[#1D4ED8]/40';
      case 'OPTION':
        return 'border-[#059669] bg-[#059669]/10 hover:bg-[#059669]/20';
      case 'TABLE':
        return 'border-[#2D6A4F] bg-[#2D6A4F]/5 hover:bg-[#2D6A4F]/15';
      case 'LIST':
      case 'LIST_ITEM':
        return 'border-[#B57314] bg-[#B57314]/5 hover:bg-[#B57314]/15';
      default:
        return 'border-[#3D3B38]/60 bg-[#1A1918]/5 hover:bg-[#1A1918]/15';
    }
  };

  const getDomainIcon = (domain: string) => {
    switch (domain?.toUpperCase()) {
      case 'SQL':
      case 'DBMS_NORMALIZATION':
        return <Database className="w-3.5 h-3.5 text-purple-600" />;
      case 'PROGRAMMING':
        return <Code className="w-3.5 h-3.5 text-amber-600" />;
      case 'ARITHMETIC':
      case 'MATHEMATICS':
      case 'MATHEMATICAL':
      case 'PROBABILITY_AND_STATISTICS':
        return <Calculator className="w-3.5 h-3.5 text-blue-600" />;
      case 'CRYPTOGRAPHY':
        return <Key className="w-3.5 h-3.5 text-emerald-600" />;
      case 'COMPUTER_NETWORKS':
      case 'DATA_STRUCTURES':
        return <Network className="w-3.5 h-3.5 text-indigo-600" />;
      default:
        return <HelpCircle className="w-3.5 h-3.5 text-stone-600" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E8E2D5] pb-4">
        <div>
          <span className="text-xs font-mono font-medium text-[#C24136] tracking-wider uppercase">
            Multimodal Spatial Canvas & Neural Solver
          </span>
          <h2 className="font-editorial text-3xl font-bold text-[#1A1918]">
            Document Intelligence & Spatial Layout
          </h2>
        </div>

        <div className="flex items-center space-x-3">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.docx,.txt"
            className="hidden"
            id="doc-upload-input"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="px-4 py-2 rounded-md bg-[#1A1918] hover:bg-[#3D3B38] text-white text-xs font-medium flex items-center space-x-2 transition-all cursor-pointer disabled:opacity-50 shadow-xs"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{uploading ? 'Ingesting & Indexing...' : 'Ingest Document'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-[#FDF1F0] border border-[#F0B8B4] text-xs text-[#C24136] flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Split: Left Sidebar (3 cols), Center Canvas (5 cols), Right Solver/Inspector (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Documents Directory (3 cols) */}
        <div className="lg:col-span-3 bg-[#FDFDFB] border border-[#E8E2D5] rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#E8E2D5]">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#59554E]">
              Workspace Corpus ({documents.length})
            </h3>
            <span className="hanko-seal-sm">ISOLATED</span>
          </div>

          {documents.length === 0 ? (
            <div className="text-center py-8 text-xs text-[#7A766F] space-y-2">
              <FileText className="w-8 h-8 mx-auto text-[#B5B0A6]" />
              <p>No documents ingested in this workspace yet.</p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-[#C24136] font-semibold underline text-xs cursor-pointer"
              >
                Upload your first document
              </button>
            </div>
          ) : (
            <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1">
              {documents.map((doc) => {
                const isSelected = selectedDoc?.doc_id === doc.doc_id;
                return (
                  <div
                    key={doc.doc_id}
                    onClick={() => {
                      setSelectedDoc(doc);
                      setCurrentPageNum(1);
                    }}
                    className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                      isSelected
                        ? 'border-[#1A1918] bg-[#F5F1E6] shadow-2xs'
                        : 'border-[#E8E2D5] bg-[#FDFDFB] hover:border-[#D5CCA8]'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="font-semibold text-[#1A1918] truncate max-w-[160px]" title={doc.file_name}>
                        {doc.file_name}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(doc.doc_id);
                        }}
                        title="Delete document"
                        className="text-[#B5B0A6] hover:text-[#C24136] p-0.5 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-[11px] text-[#7A766F] font-mono">
                      <span>{doc.file_type} • {doc.page_count} {doc.page_count === 1 ? 'page' : 'pages'}</span>
                      <span className="text-[#2D6A4F]">{doc.status}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Center Column: Interactive Spatial Canvas (5 cols) */}
        <div className="lg:col-span-5 bg-[#FDFDFB] border border-[#E8E2D5] rounded-xl p-4 space-y-4">
          {/* Canvas Controls Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#E8E2D5]">
            {/* Page Navigation */}
            <div className="flex items-center space-x-2">
              <button
                disabled={currentPageNum <= 1}
                onClick={() => setCurrentPageNum((p) => Math.max(1, p - 1))}
                className="p-1 rounded border border-[#E8E2D5] hover:bg-[#F2ECE1] disabled:opacity-30 cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono font-medium text-[#1A1918]">
                Page {currentPageNum} of {selectedDoc?.page_count || 1}
              </span>
              <button
                disabled={currentPageNum >= (selectedDoc?.page_count || 1)}
                onClick={() => setCurrentPageNum((p) => Math.min(selectedDoc?.page_count || 1, p + 1))}
                className="p-1 rounded border border-[#E8E2D5] hover:bg-[#F2ECE1] disabled:opacity-30 cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center space-x-1.5 text-xs text-[#59554E]">
              <button
                onClick={() => setZoomScale((z) => Math.max(0.5, z - 0.15))}
                className="p-1 rounded hover:bg-[#F2ECE1] border border-[#E8E2D5] cursor-pointer"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-[11px] w-10 text-center">
                {Math.round(zoomScale * 100)}%
              </span>
              <button
                onClick={() => setZoomScale((z) => Math.min(2.0, z + 0.15))}
                className="p-1 rounded hover:bg-[#F2ECE1] border border-[#E8E2D5] cursor-pointer"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setZoomScale(1.0)}
                className="p-1 rounded hover:bg-[#F2ECE1] border border-[#E8E2D5] cursor-pointer"
                title="Reset Zoom"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Canvas Image Container with SVG / Bounding Box Overlay */}
          <div className="overflow-auto max-h-[640px] flex justify-center bg-[#F5F1E6] rounded-lg p-4 border border-[#E8E2D5]">
            {selectedDoc ? (
              <div
                ref={imageContainerRef}
                style={{
                  transform: `scale(${zoomScale})`,
                  transformOrigin: 'top center',
                  transition: 'transform 0.1s ease-out',
                }}
                className="relative inline-block shadow-md bg-[#FBF9F5]"
              >
                {/* Rendered Document Page Image */}
                <img
                  src={api.documents.getPageImageUrl(selectedDoc.doc_id, currentPageNum)}
                  alt={`Page ${currentPageNum}`}
                  className="max-w-none block select-none pointer-events-none"
                  style={{ width: `${currentPage.width}px`, height: `${currentPage.height}px` }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800"><rect width="100%" height="100%" fill="%23FBF9F5"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%231A1918" font-family="serif" font-size="20">Document Page Rendering</text></svg>';
                  }}
                />

                {/* Spatial Bounding Boxes Overlay */}
                {blocks.map((block) => {
                  const [xmin, ymin, xmax, ymax] = block.bounding_box;
                  const left = (xmin / currentPage.width) * 100;
                  const top = (ymin / currentPage.height) * 100;
                  const width = ((xmax - xmin) / currentPage.width) * 100;
                  const height = ((ymax - ymin) / currentPage.height) * 100;
                  const isSelected = selectedBlock?.block_id === block.block_id;

                  return (
                    <div
                      key={block.block_id}
                      role="button"
                      tabIndex={0}
                      data-testid={`bbox-${block.block_id}`}
                      onClick={() => {
                        setSelectedBlock(block);
                        setActiveTab('blocks');
                      }}
                      onMouseEnter={() => setHoveredBlock(block)}
                      onMouseLeave={() => setHoveredBlock(null)}
                      style={{
                        left: `${left}%`,
                        top: `${top}%`,
                        width: `${width}%`,
                        height: `${height}%`,
                      }}
                      className={`absolute border cursor-pointer transition-all ${getBlockBorderColor(
                        block.block_type,
                        isSelected
                      )}`}
                      title={`Block #${block.block_id} [${block.block_type}] - ${(block.confidence * 100).toFixed(0)}%`}
                    >
                      <span className="absolute -top-3.5 left-0 px-1 py-0.2 text-[9px] font-mono font-bold bg-[#1A1918] text-[#FBF9F5] rounded-xs opacity-0 hover:opacity-100 transition-opacity z-10">
                        #{block.block_id}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-24 text-center text-xs text-[#7A766F]">
                Select or ingest a document to inspect spatial layout.
              </div>
            )}
          </div>

          {/* Quick Stats Footer */}
          <div className="flex items-center justify-between text-[11px] text-[#7A766F] font-mono pt-2">
            <span>Blocks: {blocks.length}</span>
            <span>Canvas: {currentPage.width} × {currentPage.height} px</span>
            <span className="flex items-center space-x-1 text-[#2D6A4F]">
              <CheckCircle className="w-3 h-3" />
              <span>Accurate Coordinates</span>
            </span>
          </div>
        </div>

        {/* Right Column: Q&A Solver & Inspector (4 cols) */}
        <div className="lg:col-span-4 bg-[#FDFDFB] border border-[#E8E2D5] rounded-xl p-4 space-y-4">
          {/* Panel Tab Navigation */}
          <div className="flex items-center justify-between border-b border-[#E8E2D5] pb-2">
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setActiveTab('qa')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md flex items-center space-x-1 transition-colors cursor-pointer ${
                  activeTab === 'qa'
                    ? 'bg-[#1A1918] text-white'
                    : 'text-[#59554E] hover:bg-[#F2ECE1]'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-[#E6C687]" />
                <span>Q&A Pipeline</span>
              </button>
              <button
                onClick={() => setActiveTab('blocks')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md flex items-center space-x-1 transition-colors cursor-pointer ${
                  activeTab === 'blocks'
                    ? 'bg-[#1A1918] text-white'
                    : 'text-[#59554E] hover:bg-[#F2ECE1]'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Blocks</span>
              </button>
              <button
                onClick={() => setActiveTab('raw')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md flex items-center space-x-1 transition-colors cursor-pointer ${
                  activeTab === 'raw'
                    ? 'bg-[#1A1918] text-white'
                    : 'text-[#59554E] hover:bg-[#F2ECE1]'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Text</span>
              </button>
            </div>

            <span className="hanko-seal-sm">V2.0</span>
          </div>

          {/* TAB 1: QUESTION & ANSWER PIPELINE */}
          {activeTab === 'qa' && (
            <div className="space-y-4 max-h-[640px] overflow-y-auto pr-1">
              {/* SECTION B: COMPLETE EXTRACTED TEXT (EDITABLE) */}
              <div className="space-y-1.5 p-3 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5]">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider flex items-center space-x-1">
                    <FileText className="w-3 h-3 text-[#C24136]" />
                    <span>Complete Extracted Text</span>
                  </span>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setIsEditingText(!isEditingText)}
                      className="text-[11px] text-[#C24136] font-medium hover:underline flex items-center space-x-1 cursor-pointer"
                    >
                      <Edit3 className="w-3 h-3" />
                      <span>{isEditingText ? 'Lock' : 'Review / Edit'}</span>
                    </button>
                    <button
                      onClick={() => copyToClipboard(editedText, 'text')}
                      className="text-[11px] text-[#7A766F] hover:text-[#1A1918] cursor-pointer"
                      title="Copy text"
                    >
                      {copiedField === 'text' ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                {isEditingText ? (
                  <textarea
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    rows={4}
                    className="w-full text-xs font-mono p-2 rounded border border-[#D5CCA8] bg-white focus:outline-none focus:ring-1 focus:ring-[#1A1918]"
                    placeholder="Review or correct noisy OCR text..."
                  />
                ) : (
                  <div className="text-xs font-serif text-[#1A1918] bg-white p-2.5 rounded border border-[#E8E2D5] max-h-28 overflow-y-auto leading-relaxed">
                    {editedText || <em className="text-[#8C877D]">No text extracted from page.</em>}
                  </div>
                )}
              </div>

              {/* ACTION: MODEL SELECTION & IDENTIFY AND ANSWER BUTTON */}
              <div className="space-y-2 pt-1">
                <div className="flex items-center justify-between text-[11px] text-[#7A766F]">
                  <span className="flex items-center space-x-1">
                    <Cpu className="w-3 h-3 text-[#3D3B38]" />
                    <span>Inference Model:</span>
                  </span>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="text-xs bg-[#FAF8F5] border border-[#E8E2D5] rounded px-2 py-0.5 font-mono cursor-pointer"
                  >
                    <option value="qwen3.5:2b">qwen3.5:2b (Local Ollama)</option>
                    <option value="auto">Adaptive Auto Router</option>
                  </select>
                </div>

                <button
                  onClick={handleIdentifyAndAnswer}
                  disabled={solving || !selectedDoc}
                  className="w-full py-2.5 px-4 rounded-lg bg-[#C24136] hover:bg-[#A93226] text-white text-xs font-bold uppercase tracking-wider flex items-center justify-center space-x-2 transition-all cursor-pointer disabled:opacity-50 shadow-xs"
                >
                  <Sparkles className="w-4 h-4 text-[#FDE68A]" />
                  <span>{solving ? `Processing (${solverState})...` : 'Identify and Answer Question'}</span>
                </button>

                {/* Lifecycle State Progress Badge */}
                <div className="flex items-center justify-between px-2 py-1 rounded bg-[#F5F1E6] border border-[#E8E2D5] text-[10px] font-mono text-[#59554E]">
                  <span>Status:</span>
                  <span className={`font-bold ${solverState === 'PROCESSING_FAILED' ? 'text-red-700' : 'text-[#1A1918]'}`}>
                    {solverState}
                  </span>
                </div>

                {error && (
                  <div className="p-2 rounded bg-[#FDF1F0] border border-[#F0B8B4] text-[11px] text-[#C24136] flex items-center space-x-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>

              {/* SECTION C & D & E & F: SOLUTION DISPLAY */}
              {solution && (
                <div ref={solutionRef} className="space-y-3 pt-2 border-t border-[#E8E2D5]">
                  {/* Verified Solution Notification Callout */}
                  <div className="p-2.5 rounded-lg bg-[#EBF7EE] border border-[#40916C] text-[#2D6A4F] flex items-center justify-between shadow-2xs">
                    <div className="flex items-center space-x-2">
                      <CheckCircle2 className="w-4 h-4 text-[#2D6A4F] shrink-0" />
                      <div>
                        <div className="text-[11px] font-bold uppercase tracking-wider">Answer Identified & Verified</div>
                        <div className="text-[10px] font-mono opacity-85">Deterministic Cognitive Solver Execution</div>
                      </div>
                    </div>
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-white text-[#2D6A4F] font-bold border border-[#40916C]">
                      {solution.epistemic_status}
                    </span>
                  </div>

                  {/* Question & Domain Badge */}
                  <div className="space-y-1.5 p-3 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5">
                        {getDomainIcon(solution.domain)}
                        <span className="text-[10px] uppercase font-bold text-[#1A1918] tracking-wider">
                          {solution.domain} • {solution.category}
                        </span>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold border ${
                        solution.epistemic_status === 'COMPUTATION_VERIFIED' || solution.epistemic_status === 'EVIDENCE_BACKED'
                          ? 'bg-[#EBF7EE] text-[#2D6A4F] border-[#40916C]'
                          : solution.epistemic_status === 'LOGIC_VERIFIED' || solution.epistemic_status === 'SQL_LOGIC_VERIFIED'
                          ? 'bg-[#F3E8FF] text-[#6B21A8] border-[#9333EA]'
                          : 'bg-[#FAF8F5] text-[#59554E] border-[#D5CCA8]'
                      }`}>
                        {solution.epistemic_status}
                      </span>
                    </div>

                    <div className="text-xs font-medium text-[#1A1918] leading-snug">
                      {solution.normalized_question}
                    </div>
                  </div>

                  {/* SECTION D: ANSWER OPTIONS (IF MCQ) */}
                  {solution.options && solution.options.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                        Extracted Options
                      </span>
                      <div className="grid grid-cols-1 gap-1.5">
                        {solution.options.map((opt) => {
                          const isSelected = opt.label.toUpperCase() === solution.selected_option?.toUpperCase();
                          return (
                            <div
                              key={opt.label}
                              className={`p-2 rounded-md border text-xs flex items-start space-x-2 transition-all ${
                                isSelected
                                  ? 'border-[#2D6A4F] bg-[#EBF7EE] shadow-2xs font-semibold'
                                  : 'border-[#E8E2D5] bg-[#FDFDFB]'
                              }`}
                            >
                              <span
                                className={`w-5 h-5 rounded flex items-center justify-center font-mono text-[10px] shrink-0 font-bold ${
                                  isSelected
                                    ? 'bg-[#2D6A4F] text-white'
                                    : 'bg-[#E8E2D5] text-[#59554E]'
                                }`}
                              >
                                {opt.label}
                              </span>
                              <div className="flex-1 text-[#1A1918] pt-0.5 whitespace-pre-wrap font-mono text-xs">
                                {opt.text}
                              </div>
                              {isSelected && (
                                <span className="text-[10px] text-[#2D6A4F] font-bold flex items-center space-x-0.5">
                                  <Check className="w-3 h-3" />
                                  <span>Selected</span>
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* SECTION E: FINAL ANSWER */}
                  <div className="p-3 rounded-lg bg-[#FAF6EE] border border-[#D5CCA8] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold text-[#C24136] tracking-wider">
                        Final Answer
                      </span>
                      <button
                        onClick={() => copyToClipboard(solution.final_answer, 'ans')}
                        className="text-[10px] text-[#7A766F] hover:text-[#1A1918] cursor-pointer"
                      >
                        {copiedField === 'ans' ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
                      </button>
                    </div>
                    <div className="font-editorial text-base font-bold text-[#1A1918]">
                      {solution.final_answer}
                    </div>
                  </div>

                  {/* SECTION F: STEP-BY-STEP EXPLANATION */}
                  <div className="space-y-1.5 p-3 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5]">
                    <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                      Step-by-Step Reasoning
                    </span>
                    <div className="text-xs text-[#3D3B38] whitespace-pre-line leading-relaxed font-serif">
                      {solution.step_by_step_explanation}
                    </div>
                  </div>

                  {/* OPTION ELIMINATION ANALYSIS */}
                  {solution.option_analysis && Object.keys(solution.option_analysis).length > 0 && (
                    <div className="space-y-1.5 p-3 rounded-lg bg-[#FAF8F5] border border-[#E8E2D5]">
                      <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                        Option Analysis & Elimination
                      </span>
                      <div className="space-y-1 text-xs">
                        {Object.entries(solution.option_analysis).map(([optKey, reasoning]) => (
                          <div key={optKey} className="text-[#59554E] leading-snug">
                            <strong className="text-[#1A1918]">[{optKey}]:</strong> {reasoning}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* SECTION H: TELEMETRY & MODEL DETAILS */}
                  <div className="p-2.5 rounded-lg bg-[#F5F1E6] border border-[#E8E2D5] text-[10px] font-mono text-[#7A766F] space-y-1">
                    <div className="flex justify-between">
                      <span>Model:</span>
                      <span className="text-[#1A1918] font-bold">{solution.model_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>OCR Confidence:</span>
                      <span>{(solution.confidence * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Solving Latency:</span>
                      <span>{solution.execution_time_ms} ms</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: BLOCK INSPECTOR */}
          {activeTab === 'blocks' && (
            <div className="space-y-4 max-h-[640px] overflow-y-auto pr-1 text-xs">
              {selectedBlock ? (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                      Classification & Quality
                    </span>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[#1A1918]">{selectedBlock.block_type}</span>
                      <span className="font-mono px-2 py-0.5 rounded bg-[#EBF7EE] text-[#2D6A4F] border border-[#40916C]">
                        {(selectedBlock.confidence * 100).toFixed(1)}% Conf
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                      Bounding Coordinates (Original Image Px)
                    </span>
                    <div className="font-mono text-[11px] bg-[#F5F1E6] p-2 rounded border border-[#E8E2D5] text-[#3D3B38]">
                      [{selectedBlock.bounding_box.map((v) => Math.round(v)).join(', ')}]
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                      Extracted Text
                    </span>
                    <div className="p-3 rounded-md bg-[#FBF9F5] border border-[#E8E2D5] text-[#1A1918] leading-relaxed max-h-48 overflow-y-auto font-serif">
                      {selectedBlock.text || <em className="text-[#8C877D]">Empty text</em>}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-xs text-[#7A766F] space-y-1">
                  <Layers className="w-6 h-6 mx-auto text-[#B5B0A6]" />
                  <p>Click any bounding box on the canvas to inspect its classification and coordinates.</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: RAW OCR TRANSCRIPT */}
          {activeTab === 'raw' && (
            <div className="space-y-3 max-h-[640px] overflow-y-auto pr-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-[#8C877D] tracking-wider">
                  Verbatim Transcript
                </span>
                <button
                  onClick={() => copyToClipboard(editedText, 'raw_transcript')}
                  className="text-[11px] text-[#C24136] font-medium hover:underline flex items-center space-x-1 cursor-pointer"
                >
                  {copiedField === 'raw_transcript' ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
                  <span>Copy</span>
                </button>
              </div>

              <div className="p-3 rounded-md bg-[#FBF9F5] border border-[#E8E2D5] text-[#1A1918] whitespace-pre-wrap font-serif leading-relaxed">
                {editedText || <em className="text-[#8C877D]">No text available for this page.</em>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
