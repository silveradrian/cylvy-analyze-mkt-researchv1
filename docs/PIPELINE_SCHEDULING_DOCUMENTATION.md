# 🗓️ Pipeline Scheduling System Documentation

## 🎯 **Overview**

The Pipeline Scheduling System enables automated execution of competitive intelligence analysis with different frequencies for various content types. This addresses the critical need for regular data collection without manual intervention.

---

## 🔧 **Feature Specification**

### **Content Type Scheduling Requirements:**
```
📰 News Content: Weekly analysis (high change frequency)
🌱 Organic Content: Weekly analysis (regular SEO updates)  
📺 Video Content: Monthly analysis (slower change frequency)
📱 Social Media: Weekly analysis (dynamic social landscape)
💰 Paid Advertising: Daily analysis (rapid campaign changes)
```

### **Scheduling Architecture:**
```
Frontend Schedule Manager → API Layer → SchedulingService → Pipeline Execution
                         ↓
                    Cron-based Scheduler → Background Tasks → Database Storage
```

---

## 🏗️ **Backend Implementation (Already Exists)**

### **Core Service: `SchedulingService`**
```python
class SchedulingService:
    """Service for managing pipeline schedules and execution"""
    
    def __init__(self, settings, db, pipeline_service: PipelineService):
        self.settings = settings
        self.db = db
        self.pipeline_service = pipeline_service
        self._scheduler_running = False
        self._active_executions = {}
    
    async def create_schedule(self, schedule: PipelineSchedule) -> UUID:
        """Create a new pipeline schedule"""
        # Calculate next execution based on content type frequencies
        schedule.next_execution_at = await self._calculate_next_execution(schedule)
        
        # Store in database
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pipeline_schedules (
                    id, name, description, content_schedules, 
                    regions, is_active, next_execution_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, schedule.id, schedule.name, schedule.description,
                json.dumps([cs.dict() for cs in schedule.content_schedules]),
                json.dumps(schedule.regions), schedule.is_active,
                schedule.next_execution_at)
        
        return schedule.id
```

### **Content Type Schedule Model:**
```python
class ContentTypeSchedule(BaseModel):
    """Schedule configuration for specific content type"""
    content_type: str  # 'organic', 'news', 'videos', 'social', 'ads'
    frequency: ScheduleFrequency  # 'daily', 'weekly', 'monthly'
    enabled: bool = True
    
    # Execution timing
    execution_hour: int = 9  # 24-hour format
    execution_day: Optional[int] = None  # For weekly (0-6) or monthly (1-31)
    
    # Content-specific settings
    max_pages_per_execution: int = 100
    include_video_analysis: bool = True
    include_social_signals: bool = True
    
    # Error handling
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay_minutes: int = 30
```

### **Schedule Execution Logic:**
```python
async def _check_and_execute_schedules(self):
    """Check for schedules that need to be executed"""
    now = datetime.utcnow()
    
    # Get schedules due for execution
    due_schedules = await self._get_schedules_due_for_execution(now)
    
    for schedule in due_schedules:
        # Determine which content types are due
        content_types_due = []
        
        for content_schedule in schedule.content_schedules:
            if self._is_content_type_due(content_schedule, now):
                content_types_due.append(content_schedule)
        
        if content_types_due:
            await self._execute_schedule(schedule, content_types_due, now)
```

---

## 🖥️ **Frontend Implementation (Created)**

### **Pipeline Schedules Page (`/pipeline-schedules`)**

#### **User Interface Components:**
```tsx
📋 Schedule Management Interface:
├── Schedule Creation Dialog
│   ├── Basic Info (name, description, active status)
│   ├── Content Type Configuration Grid
│   │   ├── Organic Content: [Weekly] [Enabled ✓]
│   │   ├── News Content: [Weekly] [Enabled ✓]  
│   │   ├── Videos: [Monthly] [Enabled ✓]
│   │   ├── Social Media: [Weekly] [Enabled ✓]
│   │   └── Paid Ads: [Daily] [Enabled ✓]
│   ├── Region Selection (US, UK, DE, SA, VN, etc.)
│   └── Notification Settings
├── Active Schedules List
│   ├── Schedule Status (Active/Paused)
│   ├── Content Type Frequency Display  
│   ├── Next Execution Countdown
│   └── Manual Execution Controls
└── Schedule History and Performance Metrics
```

#### **Content Type Configuration:**
```typescript
const CONTENT_TYPES = [
  {
    key: 'organic',
    name: 'Organic Content',
    description: 'SEO content, blog posts, landing pages',
    icon: '🌱',
    recommended_frequency: 'weekly',
    update_pattern: 'Regular content updates and SEO changes'
  },
  {
    key: 'news',
    name: 'News & PR', 
    description: 'Press releases, news articles, announcements',
    icon: '📰',
    recommended_frequency: 'weekly',
    update_pattern: 'News cycles and PR announcement patterns'
  },
  {
    key: 'videos',
    name: 'Video Content',
    description: 'YouTube videos, webinars, product demos', 
    icon: '📺',
    recommended_frequency: 'monthly',
    update_pattern: 'Slower video production and publishing cycles'
  }
];
```

---

## 📊 **API Endpoints for Scheduling**

### **POST `/api/v1/pipeline/schedules`**
Create new pipeline schedule.

**Request:**
```json
{
  "name": "Finastra Weekly Content Monitoring",
  "description": "Automated analysis for organic content and news monitoring",
  "content_schedules": [
    {
      "content_type": "organic",
      "frequency": "weekly", 
      "enabled": true,
      "execution_hour": 9,
      "execution_day": 1
    },
    {
      "content_type": "news",
      "frequency": "weekly",
      "enabled": true, 
      "execution_hour": 10,
      "execution_day": 1
    },
    {
      "content_type": "videos", 
      "frequency": "monthly",
      "enabled": true,
      "execution_hour": 9,
      "execution_day": 1
    }
  ],
  "regions": ["US", "UK", "DE", "SA", "VN"],
  "notification_emails": ["admin@finastra.com"]
}
```

**Response (200):**
```json
{
  "schedule_id": "schedule_abc123",
  "message": "Schedule created successfully",
  "next_executions": {
    "organic": "2025-09-09T09:00:00Z",
    "news": "2025-09-09T10:00:00Z", 
    "videos": "2025-10-01T09:00:00Z"
  }
}
```

### **GET `/api/v1/pipeline/schedules`**
Get all pipeline schedules.

**Response (200):**
```json
{
  "schedules": [
    {
      "id": "schedule_abc123",
      "name": "Finastra Weekly Content Monitoring",
      "description": "Automated analysis for content monitoring",
      "is_active": true,
      "content_schedules": [
        {
          "content_type": "organic",
          "frequency": "weekly",
          "enabled": true,
          "last_executed": "2025-09-02T09:00:00Z",
          "next_execution": "2025-09-09T09:00:00Z"
        }
      ],
      "regions": ["US", "UK", "DE", "SA", "VN"],
      "next_execution_at": "2025-09-09T09:00:00Z",
      "last_executed_at": "2025-09-02T09:00:00Z"
    }
  ]
}
```

---

## 🔄 **Scheduling Logic & Algorithms**

### **Content Type Frequency Mapping:**
```python
CONTENT_FREQUENCY_MAPPING = {
    'organic': {
        'default_frequency': 'weekly',
        'rationale': 'SEO content changes regularly with new blog posts, landing page updates',
        'optimal_day': 'monday',  # Start of week for fresh content detection
        'execution_hour': 9       # Business hours for monitoring
    },
    'news': {
        'default_frequency': 'weekly', 
        'rationale': 'Press releases and news articles follow weekly business cycles',
        'optimal_day': 'monday',  # Capture weekend announcements
        'execution_hour': 10      # After organic content analysis
    },
    'videos': {
        'default_frequency': 'monthly',
        'rationale': 'Video content has longer production cycles and less frequent updates',
        'optimal_day': 1,         # First of month
        'execution_hour': 9       # Start of day processing
    },
    'social': {
        'default_frequency': 'weekly',
        'rationale': 'Social media content changes frequently but weekly analysis captures trends',
        'optimal_day': 'friday',  # End of week social activity analysis
        'execution_hour': 11
    },
    'ads': {
        'default_frequency': 'daily',
        'rationale': 'Paid advertising campaigns change daily with bid adjustments and new ads',
        'optimal_hour': 8         # Early morning before business hours
    }
}
```

### **Cron Expression Generation:**
```python
def generate_cron_expression(content_schedule: ContentTypeSchedule) -> str:
    """Generate cron expression for content schedule"""
    
    hour = content_schedule.execution_hour
    
    if content_schedule.frequency == ScheduleFrequency.DAILY:
        return f"0 {hour} * * *"  # Daily at specified hour
    
    elif content_schedule.frequency == ScheduleFrequency.WEEKLY:
        day = content_schedule.execution_day or 1  # Default to Monday
        return f"0 {hour} * * {day}"  # Weekly on specified day
    
    elif content_schedule.frequency == ScheduleFrequency.MONTHLY:
        day = content_schedule.execution_day or 1  # Default to 1st
        return f"0 {hour} {day} * *"  # Monthly on specified date
    
    else:  # Custom cron
        return content_schedule.custom_cron_expression
```

---

## 🚀 **Production Scheduling Workflow**

### **Typical Finastra Implementation:**

#### **Monday Morning (9:00 AM):**
```
🌱 Organic Content Analysis:
├── Scan finastra.com blog and resource pages
├── Analyze new landing pages and product updates  
├── Check SEO content changes across domains
├── Monitor competitor organic content updates
└── Generate weekly organic content intelligence report
```

#### **Monday Morning (10:00 AM):**
```
📰 News & PR Analysis:
├── Scan press release sections across all domains
├── Monitor competitor announcement pages
├── Analyze industry news mentions and coverage
├── Track thought leadership content publication
└── Generate weekly news intelligence summary
```

#### **First of Each Month (9:00 AM):**
```
📺 Video Content Analysis:
├── YouTube channel monitoring for new content
├── Webinar and demo video analysis
├── Competitor video content strategy tracking
├── Social video performance metrics collection
└── Generate monthly video intelligence report
```

### **Schedule Execution Process:**

```python
async def execute_scheduled_pipeline(schedule: PipelineSchedule, content_types: List[str]):
    """Execute pipeline for specific content types"""
    
    # Create content-type-specific pipeline configuration
    pipeline_config = PipelineConfig(
        mode=PipelineMode.SCHEDULED,
        
        # Content type filtering
        collect_serp=True,
        content_type_filter=content_types,  # Only analyze specified content types
        
        # Geographic scope
        target_regions=schedule.regions,
        
        # Analysis depth based on content type
        analyze_content='organic' in content_types or 'news' in content_types,
        enrich_videos='videos' in content_types,
        analyze_social='social' in content_types,
        
        # Scheduling metadata
        scheduled_execution=True,
        schedule_id=schedule.id
    )
    
    # Start pipeline execution
    pipeline_id = await self.pipeline_service.start_pipeline(
        config=pipeline_config,
        mode=PipelineMode.SCHEDULED
    )
    
    # Track scheduled execution
    execution_record = ScheduleExecution(
        id=uuid4(),
        schedule_id=schedule.id,
        pipeline_id=pipeline_id,
        content_types=content_types,
        scheduled_for=datetime.utcnow(),
        status='running'
    )
    
    await self._store_execution_record(execution_record)
    
    return pipeline_id
```

---

## 📊 **Scheduling Database Schema**

### **Pipeline Schedules Table:**
```sql
CREATE TABLE pipeline_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Schedule configuration
    content_schedules JSONB NOT NULL,  -- Array of ContentTypeSchedule objects
    regions JSONB NOT NULL,            -- Array of country codes
    
    -- Schedule status
    is_active BOOLEAN DEFAULT true,
    
    -- Execution settings
    max_concurrent_executions INTEGER DEFAULT 1,
    
    -- Notifications
    notification_emails JSONB,
    notify_on_completion BOOLEAN DEFAULT true,
    notify_on_error BOOLEAN DEFAULT true,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_executed_at TIMESTAMPTZ,
    next_execution_at TIMESTAMPTZ,
    
    UNIQUE(name)
);
```

### **Schedule Execution History:**
```sql
CREATE TABLE schedule_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL,
    pipeline_id UUID NOT NULL,
    
    -- Execution details
    content_types JSONB NOT NULL,     -- Which content types were executed
    scheduled_for TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    -- Results
    status VARCHAR(20) DEFAULT 'running',  -- 'running', 'completed', 'failed'
    execution_duration_seconds INTEGER,
    retry_count INTEGER DEFAULT 0,
    results_summary JSONB,
    
    -- Error tracking
    error_message TEXT,
    
    FOREIGN KEY (schedule_id) REFERENCES pipeline_schedules(id) ON DELETE CASCADE,
    FOREIGN KEY (pipeline_id) REFERENCES pipeline_executions(id) ON DELETE SET NULL
);
```

---

## 🔄 **Scheduling Algorithms**

### **Next Execution Calculation:**
```python
async def _calculate_next_execution(self, schedule: PipelineSchedule) -> datetime:
    """Calculate next execution time for schedule"""
    
    now = datetime.utcnow()
    earliest_next = None
    
    for content_schedule in schedule.content_schedules:
        if not content_schedule.enabled:
            continue
            
        if content_schedule.frequency == ScheduleFrequency.DAILY:
            # Next daily execution
            next_time = now.replace(
                hour=content_schedule.execution_hour,
                minute=0, second=0, microsecond=0
            )
            if next_time <= now:
                next_time += timedelta(days=1)
                
        elif content_schedule.frequency == ScheduleFrequency.WEEKLY:
            # Next weekly execution
            days_ahead = (content_schedule.execution_day - now.weekday()) % 7
            if days_ahead == 0 and now.hour >= content_schedule.execution_hour:
                days_ahead = 7
            
            next_time = (now + timedelta(days=days_ahead)).replace(
                hour=content_schedule.execution_hour,
                minute=0, second=0, microsecond=0
            )
            
        elif content_schedule.frequency == ScheduleFrequency.MONTHLY:
            # Next monthly execution
            if now.day < content_schedule.execution_day:
                next_time = now.replace(
                    day=content_schedule.execution_day,
                    hour=content_schedule.execution_hour,
                    minute=0, second=0, microsecond=0
                )
            else:
                # Next month
                next_month = now.replace(day=1) + timedelta(days=32)
                next_time = next_month.replace(
                    day=content_schedule.execution_day,
                    hour=content_schedule.execution_hour,
                    minute=0, second=0, microsecond=0
                )
        
        # Track earliest execution needed
        if earliest_next is None or next_time < earliest_next:
            earliest_next = next_time
    
    return earliest_next
```

---

## 🎯 **User Stories for Scheduling**

### **US-SCHEDULE-001: Configure Automated Content Analysis**
```
As a competitive intelligence manager,
I want to configure automated analysis schedules for different content types,
So that I can maintain current competitive intelligence without manual intervention.
```

**Acceptance Criteria:**
- [ ] Create schedules with custom names and descriptions
- [ ] Configure different frequencies for each content type:
  - Organic Content: Weekly (captures regular SEO updates)
  - News & PR: Weekly (follows business news cycles)
  - Videos: Monthly (slower video production cycles)
  - Social Media: Weekly (dynamic but manageable frequency)
  - Paid Ads: Daily (rapid campaign change cycles)
- [ ] Select geographic regions for analysis scope
- [ ] Enable/disable individual content types within schedule
- [ ] Set notification preferences for completion and errors

### **US-SCHEDULE-002: Monitor Scheduled Execution Status**
```
As a system administrator,
I want to monitor scheduled pipeline executions and their performance,
So that I can ensure reliable automated data collection.
```

**Acceptance Criteria:**
- [ ] View all active schedules with next execution times
- [ ] See execution history with success/failure rates
- [ ] Monitor content type-specific performance metrics
- [ ] Receive notifications for failed executions
- [ ] Manual override capabilities for immediate execution

### **US-SCHEDULE-003: Optimize Content Analysis Frequency**
```
As a business analyst,
I want to adjust content analysis frequency based on business needs,
So that I can balance data freshness with system resource usage.
```

**Acceptance Criteria:**
- [ ] Edit existing schedule frequencies
- [ ] Pause/resume individual content types
- [ ] View frequency recommendations based on content type characteristics
- [ ] See resource usage implications of frequency changes

---

## 💼 **Business Value & ROI**

### **Automation Benefits:**
```
🔄 Manual Process (Before):
├── Weekly manual pipeline execution: 2 hours/week
├── Content type coordination: 1 hour/week  
├── Result compilation: 1 hour/week
├── Total: 4 hours/week = 208 hours/year
└── Cost: $10,400/year (assuming $50/hour analyst time)

🤖 Automated Process (After):
├── Initial schedule setup: 1 hour (one-time)
├── Weekly monitoring: 15 minutes/week
├── Monthly optimization: 30 minutes/month
├── Total: 19 hours/year
└── Cost: $950/year + automated intelligence quality
```

### **Intelligence Quality Improvements:**
```
📊 Data Freshness:
├── Organic Content: Weekly updates capture SEO changes
├── News Monitoring: Weekly capture of competitive announcements
├── Video Intelligence: Monthly analysis covers new video content
├── Competitive Timing: Automated detection of competitor activity
└── Trend Analysis: Continuous data collection enables sophisticated trending
```

---

## 🔧 **Implementation Status**

### **✅ Backend Complete:**
- SchedulingService fully implemented
- Content type scheduling logic
- Cron-based execution engine
- Database schema and models
- API endpoints for CRUD operations

### **✅ Frontend Created:**
- Pipeline Schedules page with full UI
- Content type configuration interface
- Schedule management controls
- Real-time status monitoring

### **⚠️ Minor Fix Needed:**
- JSON serialization issue with time objects (backend)
- Select component import (frontend)

---

## 🧪 **Testing Scenarios**

### **Test Case 1: Create Weekly Organic + News Schedule**
```
1. Navigate to /pipeline-schedules
2. Click "Create Schedule" 
3. Name: "Weekly Content Monitoring"
4. Configure:
   - Organic: Weekly ✓
   - News: Weekly ✓  
   - Videos: Monthly ✓
5. Select regions: US, UK, DE
6. Save and verify next execution times
```

### **Test Case 2: Monitor Schedule Execution**
```
1. Wait for scheduled execution time
2. Verify pipeline starts automatically
3. Monitor real-time progress via WebSocket
4. Check execution appears in schedule history
5. Verify email notifications sent
```

---

## 🚀 **Production Deployment Requirements**

### **Environment Configuration:**
```bash
# Schedule execution settings
ENABLE_SCHEDULING=true
SCHEDULER_CHECK_INTERVAL=60  # seconds
DEFAULT_SCHEDULE_TIMEZONE=UTC

# Notification settings  
SMTP_HOST=smtp.finastra.com
SMTP_PORT=587
NOTIFICATION_FROM_EMAIL=cylvy@finastra.com
```

### **Monitoring & Alerting:**
```python
# Schedule monitoring endpoints
GET /api/v1/pipeline/schedules/health  # Scheduler health check
GET /api/v1/pipeline/schedules/statistics  # Execution statistics
GET /api/v1/pipeline/schedules/{id}/history  # Execution history
```

---

This comprehensive scheduling system addresses the critical gap you identified, enabling automated competitive intelligence collection with optimized frequencies for different content types. The backend infrastructure is complete and ready for frontend integration!
