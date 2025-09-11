# 📱 Cylvy Frontend Requirements Specification

## 🎯 **System Overview**

The Cylvy Market Intelligence Agent frontend is a React/Next.js application providing comprehensive digital landscape analysis capabilities. Built with TypeScript, Tailwind CSS, and modern UI components for enterprise-grade competitive intelligence.

---

## 🏗️ **Architecture & Technology Stack**

### **Core Technologies:**
- **Framework:** Next.js 14.0.4 (React-based)
- **Language:** TypeScript
- **Styling:** Tailwind CSS + Custom Cylvy Design System
- **UI Components:** Radix UI primitives with custom styling
- **State Management:** React hooks (useState, useEffect)
- **Authentication:** JWT tokens with localStorage persistence
- **Real-time:** WebSocket connections for live updates
- **API Communication:** Fetch API with centralized service layer

### **Browser Requirements:**
- **Modern browsers** supporting ES2020+
- **WebSocket support** for real-time features
- **Local Storage** for authentication persistence
- **File Upload API** support for CSV imports

---

## 📐 **Design System Requirements**

### **Cylvy Brand Colors:**
```css
Primary: #E51848 (Cylvy Amaranth)
Secondary: #880CBF (Cylvy Grape) 
Midnight: #1A1B2E (Dark text)
Background: White with transparency layers
```

### **Component Standards:**
- **Cards:** `cylvy-card` class with consistent padding and shadows
- **Buttons:** `cylvy-btn-primary`, `cylvy-btn-secondary`, `cylvy-btn-ghost` variants
- **Forms:** White backgrounds with gray borders, Cylvy-colored focus states
- **Typography:** Clear hierarchy with Cylvy brand colors for headers

### **Critical Design Constraints:**
- **❌ ZERO YELLOW BACKGROUNDS:** Comprehensive elimination across all components
- **✅ Consistent White Forms:** All inputs, textareas, and form containers
- **🎨 Brand Alignment:** Professional financial services appearance
- **📱 Responsive Design:** Works across desktop, tablet, mobile viewports

---

## 🖥️ **Screen-by-Screen Requirements**

### **1. Homepage (`/`)**

#### **Functional Requirements:**
- **FR-HOME-001:** Display Cylvy masthead with brand identity and system status
- **FR-HOME-002:** Provide navigation grid to all major system features  
- **FR-HOME-003:** Show admin credentials for testing/demonstration access
- **FR-HOME-004:** Display system readiness indicator with real-time health status

#### **UI Components:**
```
├── Cylvy Gradient Header (brand colors)
├── Navigation Grid (6 primary features)
│   ├── 🏗️ Client Setup Wizard
│   ├── 📊 Pipeline Management  
│   ├── 🌐 Digital Landscapes
│   ├── 🎯 Custom Dimensions
│   ├── ⚙️ Advanced Settings
│   └── 📚 API Documentation
└── Admin Access Card (credentials display)
```

#### **Backend Integration:**
- **Health Check API:** `/api/v1/health` for system status
- **Configuration API:** Check setup completion status

---

### **2. Setup Wizard (`/setup`) - Multi-Step Configuration**

#### **Overall Requirements:**
- **FR-SETUP-001:** 4-step guided configuration process
- **FR-SETUP-002:** Data persistence across browser sessions and container rebuilds  
- **FR-SETUP-003:** Auto-login functionality for seamless testing workflows
- **FR-SETUP-004:** Progress tracking with visual step completion indicators
- **FR-SETUP-005:** Intelligent pre-population of existing configuration data
- **FR-SETUP-006:** Pipeline activity awareness with navigation shortcuts

#### **Authentication Layer:**
```javascript
// Auto-login for testing workflows
if (!localStorage.getItem('access_token')) {
  // Attempt login with admin@cylvy.com/admin123
  // Store token and proceed to configuration loading
}

// Token validation and refresh logic
// Fallback to login form if auto-login fails
```

---

### **2.1 Company Information Step**

#### **Functional Requirements:**
- **FR-COMPANY-001:** Company profile configuration with validation
- **FR-COMPANY-002:** Multi-domain management with country TLD support
- **FR-COMPANY-003:** Logo upload with image processing and preview
- **FR-COMPANY-004:** Form validation with real-time feedback
- **FR-COMPANY-005:** Data persistence and auto-population from existing config

#### **Form Fields:**
```typescript
interface CompanyForm {
  company_name: string;        // Required
  company_domain: string;      // Required, validated
  admin_email: string;         // Required, email format
  description?: string;        // Critical for pipeline analysis context
  industry?: string;          // Company categorization
  logo_file?: File;           // PNG, JPG, SVG up to 5MB
  additional_domains: Array<{
    domain: string;
    type: 'subsidiary' | 'country_tld' | 'brand';
    country_code?: string;
    notes?: string;
  }>;
}
```

#### **UI Components:**
- **Primary Form:** Company details with validation indicators
- **Logo Upload Zone:** Drag-and-drop with preview area
- **Domain Manager:** Dynamic list with country TLD suggestions
- **Success Badge:** "Already Configured" indicator for existing data

#### **Backend Integration:**
- **Config API:** `PUT /api/v1/config` for updates
- **Logo Upload:** `POST /api/v1/config/logo` with multipart form data
- **Domain Management:** Future API endpoints for multi-domain storage

---

### **2.2 Countries & Keywords Step**

#### **Functional Requirements:**
- **FR-KEYWORDS-001:** Multi-country selection with regional quick-select groups
- **FR-KEYWORDS-002:** CSV keyword upload with validation and processing
- **FR-KEYWORDS-003:** Existing keywords display with success state indication
- **FR-KEYWORDS-004:** Template download for proper CSV formatting
- **FR-KEYWORDS-005:** Upload status tracking with detailed progress feedback

#### **Country Selection:**
```typescript
interface CountrySelection {
  available_countries: Country[];     // 20+ countries across regions
  regional_groups: {
    client_primary: ['US', 'UK', 'DE', 'SA', 'VN'];
    emea: [...];
    americas: [...]; 
    apac: [...];
  };
  selected_countries: string[];       // User selection
}
```

#### **CSV Upload Process:**
```typescript
interface KeywordUpload {
  file: File;                        // CSV file validation
  processing_status: 'idle' | 'uploading' | 'success' | 'error';
  upload_result: {
    keywords_processed: number;
    total_keywords: number;
    errors: string[];
  };
}
```

#### **Existing Keywords Display:**
- **Success State:** "Keywords Successfully Uploaded" with green checkmark
- **Keyword Grid:** Visual badges showing first 12 keywords + count
- **Re-upload Option:** Button to update existing keyword set
- **Status Message:** Clear indication of configuration readiness

#### **Backend Integration:**
- **Keywords API:** `GET /api/v1/keywords` for existing data
- **Upload API:** `POST /api/v1/keywords/upload` with CSV processing
- **Validation:** Server-side CSV parsing with detailed error reporting

---

### **2.3 Analysis Configuration Step**

#### **Functional Requirements:**
- **FR-ANALYSIS-001:** Target personas definition with detailed descriptions
- **FR-ANALYSIS-002:** JTBD (Jobs-to-be-Done) phases configuration
- **FR-ANALYSIS-003:** Competitor domains management  
- **FR-ANALYSIS-004:** Tabbed interface with form validation
- **FR-ANALYSIS-005:** Data persistence and pre-population from existing config

#### **Personas Management:**
```typescript
interface Persona {
  name: string;                      // e.g., "The Payments Innovator"
  description: string;               // Detailed role and context
  title?: string;                    // Job titles
  goals?: string[];                  // Business objectives
  pain_points?: string[];           // Key challenges
  decision_criteria?: string[];     // Selection factors
  content_preferences?: string[];   // Content consumption patterns
}
```

#### **JTBD Phases:**
```typescript
interface JTBDPhase {
  name: string;                     // e.g., "Awareness", "Consideration"
  description: string;              // Phase characteristics
  buyer_mindset?: string;           // Customer psychology
  key_questions?: string[];         // Phase-specific inquiries
  content_types?: string[];         // Optimal content formats
}
```

#### **UI Requirements:**
- **Tabbed Interface:** Personas | Journey Phases | Competitors
- **Dynamic Forms:** Add/remove personas and phases
- **Validation:** Required field checking with visual feedback
- **Pre-population:** Load existing configuration data
- **Clean Styling:** White form containers, no yellow backgrounds

#### **Backend Integration:**
- **Personas API:** `GET/PUT /api/v1/analysis/personas`
- **JTBD API:** `GET/PUT /api/v1/analysis/jtbd`  
- **Competitors API:** `GET/PUT /api/v1/analysis/competitors`

---

### **2.4 Verify & Launch Step**

#### **Functional Requirements:**
- **FR-VERIFY-001:** System readiness validation with health checks
- **FR-VERIFY-002:** Configuration summary display with completion status
- **FR-VERIFY-003:** Launch process with visual feedback and redirect
- **FR-VERIFY-004:** Error handling with graceful degradation

#### **System Checks:**
```typescript
interface SystemChecks {
  database: { status: 'success' | 'error', message: string };
  services: { status: 'success' | 'error', message: string };
  analysis: { status: 'success' | 'error', message: string };
}
```

#### **Launch Process:**
- **Loading State:** "Launching..." with spinner (2 seconds)
- **Success State:** "Setup Complete!" with green checkmark
- **Redirect:** Navigate to homepage dashboard (`/`)
- **Error Handling:** Reset state and show error message if launch fails

---

### **3. Pipeline Management (`/pipeline`)**

#### **Functional Requirements:**
- **FR-PIPELINE-001:** Real-time pipeline execution monitoring
- **FR-PIPELINE-002:** Pipeline start/stop/pause controls
- **FR-PIPELINE-003:** Historical pipeline execution history
- **FR-PIPELINE-004:** WebSocket integration for live updates
- **FR-PIPELINE-005:** Auto-login authentication for seamless access
- **FR-PIPELINE-006:** Tabbed interface for active and historical pipelines

#### **Pipeline Execution Display:**
```typescript
interface PipelineStatus {
  pipeline_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  mode: 'batch_optimized' | 'scheduled' | 'manual';
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  current_phase?: string;
  phases_completed: string[];
  phases_remaining: string[];
  
  // Progress Metrics
  keywords_processed: number;
  serp_results_collected: number;
  companies_enriched: number;
  content_analyzed: number;
  landscapes_calculated: number;
  
  // Error Tracking  
  errors: string[];
  warnings: string[];
}
```

#### **Pipeline Phases Display:**
```
Phase 1: 🔢 Keyword Metrics Enrichment
Phase 2: 🌐 SERP Data Collection  
Phase 3: 🏢 Company Enrichment
Phase 4: 📺 Video Content Enrichment
Phase 5: 📄 Web Content Scraping
Phase 6: 🤖 AI Content Analysis
Phase 7: 📊 DSI Calculation
Phase 8: 🌍 Digital Landscape DSI
Phase 9: 📈 Historical Data Storage
```

#### **WebSocket Integration:**
```typescript
// Real-time updates for pipeline progress
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8001/ws/pipeline');
  
  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    updatePipelineStatus(update);
  };
});
```

#### **Backend Integration:**
- **Start API:** `POST /api/v1/pipeline/start`
- **Status API:** `GET /api/v1/pipeline/status/{pipeline_id}`
- **History API:** `GET /api/v1/pipeline/recent?limit=10`
- **WebSocket:** `ws://localhost:8001/ws/pipeline`

---

### **4. Digital Landscapes (`/landscapes`)**

#### **Functional Requirements:**
- **FR-LANDSCAPE-001:** Digital landscape creation and management interface
- **FR-LANDSCAPE-002:** Keyword assignment to landscapes with search/filter
- **FR-LANDSCAPE-003:** DSI calculation triggers and progress monitoring
- **FR-LANDSCAPE-004:** Landscape summary with key metrics display
- **FR-LANDSCAPE-005:** Historical trend visualization and data export

#### **Landscape Creation Process:**
```typescript
interface LandscapeForm {
  name: string;                    // e.g., "UK Banking Technology"
  description: string;             // Market context and scope
  target_countries: string[];      // Geographic focus
  assigned_keywords: string[];     // Keyword IDs for analysis
}
```

#### **DSI Metrics Display:**
```typescript
interface LandscapeDSIDisplay {
  calculation_date: string;
  total_companies: number;
  total_keywords: number;
  avg_dsi_score: number;
  
  company_rankings: Array<{
    entity_name: string;
    dsi_score: number;
    rank: number;
    market_position: string;
    traffic_share: number;
    keyword_coverage: number;
  }>;
  
  trend_data: Array<{
    date: string;
    dsi_score: number;
    rank: number;
  }>;
}
```

#### **Backend Integration:**
- **Landscapes API:** `GET/POST/PUT/DELETE /api/v1/landscapes`
- **Keywords API:** `GET /api/v1/landscapes/keywords/available`
- **Assignment API:** `POST /api/v1/landscapes/{id}/keywords`
- **Calculation API:** `POST /api/v1/landscapes/{id}/calculate`
- **Metrics API:** `GET /api/v1/landscapes/{id}/metrics`

---

### **5. Custom Dimensions (`/dimensions`)**

#### **Functional Requirements:**
- **FR-DIMENSIONS-001:** Custom scoring dimension creation and management
- **FR-DIMENSIONS-002:** Multi-level scoring system configuration (1-10 scale)
- **FR-DIMENSIONS-003:** Strategic pillar templates for financial services
- **FR-DIMENSIONS-004:** Dimension editing and deletion capabilities

#### **Dimension Configuration:**
```typescript
interface CustomDimension {
  name: string;                    // e.g., "Technology Innovation"
  description: string;             // Dimension purpose and scope
  scoring_levels: Array<{
    level: number;                 // 1-10 scale
    label: string;                 // e.g., "Innovative"
    description: string;           // Level characteristics
  }>;
  is_active: boolean;
  category?: string;               // Grouping for related dimensions
}
```

#### **Template System:**
- **Finastra Strategic Pillars:** Pre-configured dimensions
- **Industry Templates:** Financial services focus
- **Custom Creation:** User-defined dimensions

#### **Backend Integration:**
- **Dimensions API:** `GET/POST/PUT/DELETE /api/v1/generic-dimensions`
- **Templates API:** `GET /api/v1/generic-dimensions/templates`

---

### **6. Settings (`/settings`)**

#### **Functional Requirements:**
- **FR-SETTINGS-001:** System configuration management interface
- **FR-SETTINGS-002:** API key status display (read-only, environment-managed)
- **FR-SETTINGS-003:** User profile and preferences management
- **FR-SETTINGS-004:** Advanced pipeline and analysis settings

#### **Configuration Categories:**
```
├── User Profile Settings
├── Analysis Configuration  
├── Pipeline Default Settings
├── API Integration Status (read-only)
└── System Preferences
```

---

## 🔐 **Authentication Requirements**

### **Authentication Flow:**
1. **Token Check:** Verify existing `access_token` in localStorage
2. **Auto-Login:** Attempt login with `admin@cylvy.com/admin123` for testing
3. **Token Storage:** Persist successful authentication tokens
4. **Token Validation:** Check token validity with `/api/v1/auth/me`
5. **Refresh Logic:** Handle token expiration with graceful re-authentication

### **Protected Routes:**
- **All admin pages** require valid authentication
- **API calls** include `Authorization: Bearer {token}` headers
- **WebSocket connections** authenticated for real-time updates

---

## 📊 **Data Flow Architecture**

### **Client-Side State Management:**
```typescript
// Setup Wizard State
const [setupData, setSetupData] = useState({});
const [completedSteps, setCompletedSteps] = useState(new Set());
const [currentStep, setCurrentStep] = useState(0);

// Authentication State  
const [isAuthenticated, setIsAuthenticated] = useState(false);
const [isCheckingAuth, setIsCheckingAuth] = useState(true);

// Feature-Specific State (per page)
const [pipelines, setPipelines] = useState([]);
const [landscapes, setLandscapes] = useState([]);
const [dimensions, setDimensions] = useState([]);
```

### **API Service Layer:**
```typescript
// Centralized API communication
const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    ...options.headers
  };
  
  const response = await fetch(`/api/v1${endpoint}`, {
    ...options,
    headers
  });
  
  return await response.json();
};
```

---

## 🔄 **Real-Time Features**

### **WebSocket Integration:**
- **Pipeline Updates:** Live progress during execution
- **Landscape Calculations:** Real-time DSI computation progress  
- **System Health:** Connection status indicators
- **Multi-Channel:** Separate channels for different data types

### **Implementation Requirements:**
```typescript
// WebSocket connection management
const initWebSocket = (channel: string) => {
  const ws = new WebSocket(`ws://localhost:8001/ws/${channel}`);
  
  ws.onopen = () => setWsConnected(true);
  ws.onclose = () => {
    setWsConnected(false);
    // Auto-reconnection with exponential backoff
    setTimeout(() => initWebSocket(channel), 5000);
  };
  ws.onmessage = (event) => handleRealtimeUpdate(JSON.parse(event.data));
};
```

---

## 📱 **Responsive Design Requirements**

### **Breakpoint Strategy:**
```css
/* Mobile First Approach */
sm: 640px   /* Small tablets */
md: 768px   /* Tablets */
lg: 1024px  /* Desktop */
xl: 1280px  /* Large desktop */
```

### **Component Responsiveness:**
- **Navigation:** Collapses to mobile menu on small screens
- **Forms:** Single column on mobile, multi-column on desktop
- **Tables:** Horizontal scroll with priority column ordering
- **Charts:** Responsive scaling with touch-friendly controls

---

## 🎨 **UI Component Requirements**

### **Form Components:**
- **Consistent Styling:** White backgrounds, gray borders
- **Focus States:** Cylvy-colored focus indicators
- **Validation:** Real-time feedback with error messaging
- **Accessibility:** Proper labels, ARIA attributes, keyboard navigation

### **Data Display Components:**
- **Cards:** Consistent shadow and padding system
- **Tables:** Sortable headers, pagination, responsive design
- **Badges:** Status indicators with brand color variants
- **Progress Bars:** Visual progress tracking for long operations

### **Interactive Components:**
- **Buttons:** Primary, secondary, ghost, and outline variants
- **Modals:** Confirmation dialogs and form overlays
- **Dropdowns:** Search-enabled selection components
- **File Upload:** Drag-and-drop zones with preview

---

## 📊 **Performance Requirements**

### **Page Load Performance:**
- **Initial Load:** < 3 seconds for any page
- **Navigation:** < 500ms between pages  
- **API Calls:** < 2 seconds for complex operations
- **Real-time Updates:** < 100ms latency for WebSocket messages

### **Data Handling:**
- **Large Datasets:** Pagination for 1000+ records
- **CSV Processing:** Client-side validation before server upload
- **Memory Management:** Efficient state updates, no memory leaks

---

## 🔧 **Error Handling Requirements**

### **Error Scenarios:**
```typescript
// Network errors
if (!response.ok) {
  throw new APIError(response.status, await response.text());
}

// Authentication errors  
if (response.status === 401) {
  localStorage.removeItem('access_token');
  redirectToLogin();
}

// Validation errors
if (response.status === 422) {
  displayFieldErrors(response.data.details);
}
```

### **User Experience:**
- **Graceful Degradation:** Features work without optional APIs
- **Error Messages:** Clear, actionable feedback to users
- **Retry Logic:** Automatic retry for transient failures
- **Offline Handling:** Indication when backend is unavailable

---

## 📚 **Browser Storage Requirements**

### **localStorage Usage:**
```javascript
// Authentication
'access_token': 'JWT token string'

// User Preferences (future)
'cylvy_preferences': JSON.stringify({
  dashboard_layout: 'default',
  notification_settings: {...}
})
```

### **Session Storage:**
- **Form Drafts:** Temporary storage for incomplete forms
- **Navigation State:** Preserve scroll position and tab selection

---

## 🧪 **Testing Requirements**

### **Frontend Testing Strategy:**
- **Unit Tests:** Component rendering and behavior
- **Integration Tests:** API communication and error handling
- **E2E Tests:** Complete user workflows across all screens
- **Visual Regression:** UI consistency across browser/device matrix

### **Browser Compatibility:**
```
✅ Chrome 90+ (Primary)
✅ Firefox 88+
✅ Safari 14+  
✅ Edge 90+
❌ Internet Explorer (Not supported)
```

### **Device Testing:**
```
📱 Mobile: iPhone, Android (375px-428px width)
📟 Tablet: iPad, Android tablets (768px-1024px width)  
💻 Desktop: 1280px+ width with multiple resolutions
🖥️ Large Desktop: 1920px+ width
```

---

## 🚀 **Deployment Requirements**

### **Docker Container:**
```dockerfile
# Next.js application in Node.js Alpine container
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN mkdir -p .next && chown -R node:node .next
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

### **Environment Variables:**
```bash
NEXT_PUBLIC_API_URL=http://backend:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://backend:8000/ws
```

### **Production Optimizations:**
- **Next.js Proxy:** `/api/*` routes to backend for CORS handling
- **Static Asset Optimization:** Image optimization and caching
- **Bundle Optimization:** Code splitting and lazy loading

---

This specification provides the foundation for understanding the complete frontend architecture and requirements. The companion user stories document will detail specific user interactions and workflows.
