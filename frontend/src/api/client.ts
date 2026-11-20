/**
 * client.ts: API client for SETU-NETRA V2.0.0-RC1.
 * Enforces credentials: "include" for session cookies, X-CSRF-Token headers for mutations,
 * and RFC 9457 Problem Details error translation.
 */

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  correlation_id?: string;
  timestamp: string;
  code?: string;
  invalid_params?: Array<{ name: string; reason: string }>;
}

export interface UserRecord {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  created_at: number;
  updated_at: number;
}

export interface SessionInfo {
  authenticated: boolean;
  user: UserRecord | null;
  active_workspace_id: string;
  csrf_token: string | null;
  permissions: string[];
}

export interface WorkspaceRecord {
  workspace_id: string;
  name: string;
  description: string;
  created_at: number;
  updated_at: number;
  is_default: boolean;
  user_role?: string;
}

export interface DocumentRecord {
  doc_id: string;
  file_name: string;
  file_type: string;
  page_count: number;
  created_at: string;
  status: string;
  workspace_id: string;
  metadata: Record<string, any>;
}

export interface DocumentPage {
  page_id: string;
  doc_id: string;
  page_number: number;
  width: number;
  height: number;
  metadata: Record<string, any>;
}

export interface DocumentBlock {
  block_id: number;
  page_number: number;
  block_type: string;
  text: string;
  confidence: number;
  bounding_box: [number, number, number, number];
  source_detection_indices: number[];
}

export interface PageTextResult {
  doc_id: string;
  page_number: number;
  full_text: string;
  raw_transcript: string;
  blocks_count: number;
  ocr_status: string;
  detected_questions: any[];
  warnings: string[];
}

export interface SolveQuestionResult {
  lifecycle_state: string;
  raw_ocr_text: string;
  normalized_question: string;
  domain: string;
  category: string;
  is_mcq: boolean;
  options: Array<{ label: string; text: string }>;
  selected_option: string | null;
  selected_option_text: string | null;
  final_answer: string;
  step_by_step_explanation: string;
  option_analysis: Record<string, string>;
  sql_clauses: Record<string, any> | null;
  epistemic_status: string;
  confidence: number;
  model_id: string;
  uncertain_spans: any[];
  execution_time_ms: number;
  warnings: string[];
}

export interface Citation {
  passage_id?: string;
  doc_id: string;
  document_name?: string;
  page_number: number;
  block_id?: number;
  bounding_box?: [number, number, number, number];
  text: string;
  relevance_score?: number;
}

export interface QueryResult {
  query: string;
  answer_text: string;
  epistemic_status: 'SUPPORTED' | 'CONTRADICTED' | 'UNSUPPORTED' | 'COMPUTATION_VERIFIED' | 'LOGIC_VERIFIED' | 'FORMULA_VERIFIED' | 'GENERAL_KNOWLEDGE' | string;
  citations: Citation[];
  grounding_score: number;
  executing_model_id?: string;
  executing_worker_id?: string;
  execution_time_ms: number;
  explanation?: string;
  thinking?: string;
  correlation_id: string;
  extracted_question?: string;
  ocr_confidence?: number;
  ocr_detections_count?: number;
  pipeline_telemetry?: Record<string, any>;
  domain?: string;
  reconstructed_question?: string;
  verification_method?: string;
  step_by_step_explanation?: string;
  options?: Array<{ label: string; text: string }>;
  selected_option?: string | null;
  selected_option_text?: string | null;
  option_analysis?: Record<string, string>;
}

export interface SystemHealth {
  status: string;
  version: string;
  uptime_seconds: number;
  database: Record<string, any>;
  ollama: Record<string, any>;
  worker_pool: Record<string, any>;
  hardware: Record<string, any>;
}

let storedCsrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  storedCsrfToken = token;
}

export function getCsrfToken(): string | null {
  return storedCsrfToken;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  // Attach CSRF token on mutating requests if present
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes((options.method || 'GET').toUpperCase())) {
    if (storedCsrfToken && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', storedCsrfToken);
    }
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
    credentials: 'include', // Ensure session cookies are always transmitted
  });

  if (!response.ok) {
    let problem: ProblemDetails;
    try {
      const errorJson = await response.json();
      problem = errorJson as ProblemDetails;
      if (!problem.title && errorJson.detail) {
        problem = {
          type: 'about:blank',
          title: 'Request Failed',
          status: response.status,
          detail: typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail),
          timestamp: new Date().toISOString(),
        };
      }
    } catch {
      problem = {
        type: 'about:blank',
        title: response.statusText || 'HTTP Error',
        status: response.status,
        detail: `Server returned status ${response.status}`,
        timestamp: new Date().toISOString(),
      };
    }
    throw problem;
  }

  // If response is empty (e.g. 204 or void)
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return (await response.json()) as T;
  }
  return {} as T;
}

export const api = {
  auth: {
    async getSession(): Promise<SessionInfo> {
      const data = await request<SessionInfo>('/api/v1/auth/session');
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      return data;
    },
    async login(username: string, password: string): Promise<SessionInfo> {
      const data = await request<SessionInfo>('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      return data;
    },
    async register(payload: {
      username: string;
      password: string;
      display_name: string;
      requested_role?: string;
    }): Promise<SessionInfo> {
      const data = await request<SessionInfo>('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (data.csrf_token) {
        setCsrfToken(data.csrf_token);
      }
      return data;
    },
    async logout(): Promise<void> {
      await request('/api/v1/auth/logout', { method: 'POST' });
      setCsrfToken(null);
    },
  },

  workspaces: {
    async list(): Promise<WorkspaceRecord[]> {
      return request<WorkspaceRecord[]>('/api/v1/workspaces');
    },
    async create(name: string, description: string = ''): Promise<WorkspaceRecord> {
      return request<WorkspaceRecord>('/api/v1/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description }),
      });
    },
    async switchActive(workspaceId: string): Promise<{ status: string; active_workspace_id: string }> {
      return request<{ status: string; active_workspace_id: string }>(`/api/v1/workspaces/${workspaceId}/switch`, {
        method: 'POST',
      });
    },
  },

  documents: {
    async list(workspaceId?: string): Promise<DocumentRecord[]> {
      const q = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
      return request<DocumentRecord[]>(`/api/v1/documents${q}`);
    },
    async upload(file: File): Promise<DocumentRecord> {
      const formData = new FormData();
      formData.append('file', file);
      return request<DocumentRecord>('/api/v1/documents/upload', {
        method: 'POST',
        body: formData,
      });
    },
    async get(docId: string): Promise<DocumentRecord> {
      return request<DocumentRecord>(`/api/v1/documents/${docId}`);
    },
    async delete(docId: string): Promise<{ status: string }> {
      return request<{ status: string }>(`/api/v1/documents/${docId}`, {
        method: 'DELETE',
      });
    },
    async getPages(docId: string): Promise<DocumentPage[]> {
      return request<DocumentPage[]>(`/api/v1/documents/${docId}/pages`);
    },
    async getBlocks(docId: string, pageNumber: number): Promise<DocumentBlock[]> {
      return request<DocumentBlock[]>(`/api/v1/documents/${docId}/pages/${pageNumber}/blocks`);
    },
    getPageImageUrl(docId: string, pageNumber: number): string {
      return `/api/v1/documents/${docId}/pages/${pageNumber}/image?t=${Date.now()}`;
    },
    async getPageText(docId: string, pageNumber: number): Promise<PageTextResult> {
      return request<PageTextResult>(`/api/v1/documents/${docId}/pages/${pageNumber}/text`);
    },
    async solvePageQuestion(
      docId: string,
      pageNumber: number,
      payload: { edited_text?: string; model_id?: string; think?: boolean } = {}
    ): Promise<SolveQuestionResult> {
      return request<SolveQuestionResult>(`/api/v1/documents/${docId}/pages/${pageNumber}/solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    },
  },

  query: {
    async executeText(payload: {
      query: string;
      doc_id?: string;
      model_id?: string;
      think?: string;
      top_k?: number;
      threshold?: number;
    }): Promise<QueryResult> {
      return request<QueryResult>('/api/v1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    },
    async executeImage(payload: {
      file: File;
      doc_id?: string;
      model_id?: string;
      think?: string;
      top_k?: number;
      threshold?: number;
    }): Promise<QueryResult> {
      const formData = new FormData();
      formData.append('file', payload.file);
      if (payload.doc_id) formData.append('doc_id', payload.doc_id);
      if (payload.model_id) formData.append('model_id', payload.model_id);
      if (payload.think) formData.append('think', payload.think);
      if (payload.top_k) formData.append('top_k', payload.top_k.toString());
      if (payload.threshold !== undefined) formData.append('threshold', payload.threshold.toString());

      return request<QueryResult>('/api/v1/query/image', {
        method: 'POST',
        body: formData,
      });
    },
  },

  health: {
    async check(): Promise<SystemHealth> {
      return request<SystemHealth>('/api/v1/health');
    },
  },
};
