/**
 * API Service - Centralized API communication
 */
// Use relative URLs in browser to leverage Next.js proxy, full URLs for SSR
const API_BASE = typeof window !== 'undefined' 
  ? '/api/v1'  // Browser: use relative URL -> goes through Next.js proxy
  : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'; // SSR: use full URL

// Helper function for API calls
async function apiCall(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE}${endpoint}`;
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  // Add auth token if available
  const token = localStorage.getItem('access_token');
  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || `HTTP ${response.status}`);
  }

  return response.json();
}

// Authentication API
export const authAPI = {
  login: async (email: string, password: string) => {
    return apiCall('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  logout: async () => {
    return apiCall('/auth/logout', { method: 'POST' });
  },

  getCurrentUser: async () => {
    return apiCall('/auth/me');
  },
};

// Configuration API
export const configAPI = {
  getConfig: async () => {
    return apiCall('/config');
  },

  updateConfig: async (updates: any) => {
    return apiCall('/config', {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  },

  getBranding: async () => {
    return apiCall('/config/branding');
  },

  uploadLogo: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE}/config/logo`, {
      method: 'POST',
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP ${response.status}`);
    }

    return response.json();
  },

  deleteLogo: async () => {
    return apiCall('/config/logo', { method: 'DELETE' });
  },

  getSetupStatus: async () => {
    return apiCall('/config/setup-status');
  },
};

// Pipeline API
export const pipelineAPI = {
  startPipeline: async (config: any) => {
    return apiCall('/pipeline/start', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  },

  getPipelineStatus: async (pipelineId: string) => {
    return apiCall(`/pipeline/status/${pipelineId}`);
  },

  cancelPipeline: async (pipelineId: string) => {
    return apiCall(`/pipeline/${pipelineId}`, {
      method: 'DELETE',
    });
  },

  getRecentPipelines: async (limit: number = 10) => {
    return apiCall(`/pipeline/recent?limit=${limit}`);
  },

  // Scheduling
  createSchedule: async (schedule: any) => {
    return apiCall('/pipeline/schedules', {
      method: 'POST',
      body: JSON.stringify(schedule),
    });
  },

  getSchedules: async (activeOnly: boolean = false) => {
    return apiCall(`/pipeline/schedules?active_only=${activeOnly}`);
  },

  updateSchedule: async (scheduleId: string, updates: any) => {
    return apiCall(`/pipeline/schedules/${scheduleId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  },

  deleteSchedule: async (scheduleId: string) => {
    return apiCall(`/pipeline/schedules/${scheduleId}`, {
      method: 'DELETE',
    });
  },

  // Historical Data
  createSnapshot: async (snapshotDate?: string) => {
    return apiCall('/pipeline/snapshot', {
      method: 'POST',
      body: JSON.stringify({ snapshot_date: snapshotDate }),
    });
  },

  getDSITrends: async (limit: number = 50) => {
    return apiCall(`/pipeline/trends/dsi?limit=${limit}`);
  },

  getPageTrends: async (params: {
    months?: number;
    domain?: string;
    content_type?: string;
    limit?: number;
  } = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
    
    return apiCall(`/pipeline/trends/pages?${queryParams.toString()}`);
  },

  getPageLifecycle: async (params: {
    status?: string;
    domain?: string;
  } = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value);
      }
    });
    
    return apiCall(`/pipeline/lifecycle/pages?${queryParams.toString()}`);
  },

  getTrendingContent: async (days: number = 30) => {
    return apiCall(`/pipeline/trending?days=${days}`);
  },
};

// Keywords API
export const keywordsAPI = {
  getKeywords: async (params: { limit?: number; category?: string } = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
    
    return apiCall(`/keywords?${queryParams.toString()}`);
  },

  uploadKeywords: async (file: File, regions: string[] = ['US', 'UK'], replace: boolean = true) => {
    const formData = new FormData();
    formData.append('file', file);

    const token = localStorage.getItem('access_token');
    const params = new URLSearchParams();
    params.set('regions', regions.join(','));
    if (replace) params.set('replace', 'true');

    const response = await fetch(`${API_BASE}/keywords/upload?${params.toString()}`, {
      method: 'POST',
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP ${response.status}`);
    }

    return response.json();
  },

  deleteKeyword: async (keywordId: string) => {
    return apiCall(`/keywords/${keywordId}`, {
      method: 'DELETE',
    });
  },
};

// Analysis API
export const analysisAPI = {
  getAnalysisConfig: async () => {
    return apiCall('/analysis/config');
  },

  updateAnalysisConfig: async (config: any) => {
    return apiCall('/analysis/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  },

  getPersonas: async () => {
    return apiCall('/analysis/personas');
  },

  updatePersonas: async (personas: any[]) => {
    return apiCall('/analysis/personas', {
      method: 'PUT',
      body: JSON.stringify({ personas }),
    });
  },

  getJTBDPhases: async () => {
    return apiCall('/analysis/jtbd');
  },

  updateJTBDPhases: async (phases: any[]) => {
    return apiCall('/analysis/jtbd', {
      method: 'PUT',
      body: JSON.stringify({ phases }),
    });
  },

  getCompetitors: async () => {
    return apiCall('/analysis/competitors');
  },

  updateCompetitors: async (competitors: string[]) => {
    return apiCall('/analysis/competitors', {
      method: 'PUT',
      body: JSON.stringify({ competitor_domains: competitors }),
    });
  },
};

// Dashboard/Results API
export const resultsAPI = {
  getDSIRankings: async (params: { limit?: number } = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
    
    return apiCall(`/dashboard/dsi?${queryParams.toString()}`);
  },

  getContentAnalysis: async (params: {
    limit?: number;
    domain?: string;
    persona?: string;
    jtbd_phase?: string;
  } = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value);
      }
    });
    
    return apiCall(`/dashboard/content?${queryParams.toString()}`);
  },

  getCompanyDetails: async (domain: string) => {
    return apiCall(`/dashboard/companies/${encodeURIComponent(domain)}`);
  },

  exportResults: async (format: string = 'csv', filters: any = {}) => {
    const queryParams = new URLSearchParams();
    queryParams.append('format', format);
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
    
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_BASE}/dashboard/export?${queryParams.toString()}`, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `HTTP ${response.status}`);
    }

    return response.blob();
  },
};

// Prompt Configuration API
export const promptAPI = {
  getPromptConfig: async () => {
    return apiCall('/prompts/config');
  },

  updatePromptConfig: async (config: any) => {
    return apiCall('/prompts/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  },

  getPromptLibrary: async (category?: string) => {
    const params = category ? `?category=${category}` : '';
    return apiCall(`/prompts/library${params}`);
  },

  savePromptTemplate: async (template: any) => {
    return apiCall('/prompts/library', {
      method: 'POST',
      body: JSON.stringify(template),
    });
  },

  testPrompt: async (prompt: string, content: string) => {
    return apiCall('/prompts/test', {
      method: 'POST',
      body: JSON.stringify({ prompt, content }),
    });
  },
};

// Generic Dimensions API
export const genericDimensionsAPI = {
  getDimensions: async () => {
    return apiCall('/generic-dimensions');
  },

  createDimension: async (dimension: any) => {
    return apiCall('/generic-dimensions', {
      method: 'POST',
      body: JSON.stringify(dimension),
    });
  },

  updateDimension: async (dimensionId: string, updates: any) => {
    return apiCall(`/generic-dimensions/${dimensionId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  },

  deleteDimension: async (dimensionId: string) => {
    return apiCall(`/generic-dimensions/${dimensionId}`, {
      method: 'DELETE',
    });
  },

  getTemplates: async () => {
    return apiCall('/generic-dimensions/templates');
  },

  createFromTemplate: async (templateId: string, customizations: any = {}) => {
    return apiCall('/generic-dimensions/from-template', {
      method: 'POST',
      body: JSON.stringify({ template_id: templateId, customizations }),
    });
  },
};

