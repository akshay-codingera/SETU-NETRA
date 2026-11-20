import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { LandingView } from './views/LandingView';
import { WorkspaceDeskView } from './views/WorkspaceDeskView';
import { DocumentIntelligenceView } from './views/DocumentIntelligenceView';
import { QuestionAnsweringView } from './views/QuestionAnsweringView';
import { ReportStudioView } from './views/ReportStudioView';

const AuthenticatedApp: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();
  const [currentTab, setCurrentTab] = useState<'documents' | 'qa' | 'report' | 'desk'>('documents');
  const [navTarget, setNavTarget] = useState<{
    docId?: string;
    pageNumber?: number;
    blockId?: number;
  }>({});

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FBF9F5] flex flex-col items-center justify-center space-y-4">
        <div className="font-editorial text-3xl font-bold tracking-tight text-[#1A1918]">
          SETU-NETRA
        </div>
        <div className="hanko-seal animate-pulse">
          सेतु-नेत्र
        </div>
        <p className="text-xs font-mono text-[#7A766F]">Verifying session and workspace isolation...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LandingView />;
  }

  const handleNavigateToDocument = (docId: string, pageNumber: number, blockId?: number) => {
    setNavTarget({ docId, pageNumber, blockId });
    setCurrentTab('documents');
  };

  return (
    <div className="min-h-screen bg-[#FBF9F5] text-[#1A1918] flex flex-col selection:bg-[#C24136] selection:text-white">
      <Navbar currentTab={currentTab} onSelectTab={setCurrentTab} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        {currentTab === 'documents' && (
          <DocumentIntelligenceView
            initialDocId={navTarget.docId}
            initialPageNumber={navTarget.pageNumber || 1}
            highlightedBlockId={navTarget.blockId}
          />
        )}
        {currentTab === 'qa' && (
          <QuestionAnsweringView onNavigateToDocument={handleNavigateToDocument} />
        )}
        {currentTab === 'report' && <ReportStudioView />}
        {currentTab === 'desk' && <WorkspaceDeskView />}
      </main>

      <footer className="border-t border-[#E8E2D5] bg-[#F5F1E6] px-6 py-3 text-center text-[11px] text-[#7A766F] font-mono print:hidden">
        SETU-NETRA V2.0.0-RC1 (Kora Kaagaz) • Bound to 127.0.0.1 • Tripartite Epistemic Provenance
      </footer>
    </div>
  );
};

export function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}

export default App;
