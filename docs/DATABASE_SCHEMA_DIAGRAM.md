# Database Schema Relationship Diagram

## Core Data Flow

```mermaid
graph TD
    subgraph "Data Collection Layer"
        KW[keywords<br/>✓ Has data]
        SERP[serp_results<br/>✓ 1.3MB data]
        KW -->|keyword_id FK| SERP
    end

    subgraph "Content Layer - REDUNDANT"
        SC[scraped_content<br/>❌ Empty]
        VC[video_content<br/>❌ Empty]
        YV[youtube_videos<br/>✓ Some data]
        YC[youtube_channels<br/>❌ Empty]
        VS[video_snapshots<br/>✓ Some data]
        
        YV -->|No FK| YC
        VS -->|video_id| YV
    end

    subgraph "Company Data - TRIPLICATION"
        CP[company_profiles<br/>❌ Empty]
        CPC[company_profiles_cache<br/>❌ Empty]
        CC[client_config.company_profile<br/>JSONB field]
        CD[company_domains<br/>✓ Some data]
        
        CD -->|company_id FK| CP
        style CP fill:#ff9999
        style CPC fill:#ff9999
        style CC fill:#ffcc99
    end

    subgraph "Analysis Layer - QUADRUPLICATION"
        CA[content_analysis<br/>❌ Empty]
        GDA[generic_dimension_analysis<br/>❌ Empty]
        OCA[optimized_content_analysis<br/>❌ Empty]
        ADA[advanced_dimension_analysis<br/>❓ Doesn't exist]
        
        GDA -->|content_analysis_id FK| CA
        OCA -->|project_id FK| CC
        
        style CA fill:#ff9999
        style GDA fill:#ff9999
        style OCA fill:#ff9999
        style ADA fill:#ffcccc,stroke:#ff0000,stroke-dasharray: 5 5
    end

    subgraph "Configuration - FRAGMENTED"
        AC[analysis_config<br/>✓ Has data]
        GCD[generic_custom_dimensions<br/>✓ Has data]
        PC[prompt_configurations<br/>❌ Empty]
        
        style AC fill:#99ff99
        style GCD fill:#99ff99
        style PC fill:#ff9999
    end

    subgraph "Pipeline State - REDUNDANT"
        PE[pipeline_executions<br/>✓ Has data]
        PS[pipeline_state<br/>✓ Has data]
        PPS[pipeline_phase_status<br/>❌ Empty]
        PCH[pipeline_checkpoints<br/>✓ Has data]
        
        PS -->|pipeline_execution_id FK| PE
        PCH -->|pipeline_execution_id FK| PE
        
        style PE fill:#99ff99
        style PS fill:#ffcc99
        style PPS fill:#ff9999
        style PCH fill:#ffcc99
    end

    subgraph "Historical Data - ALL EMPTY"
        HCM[historical_content_metrics<br/>❌ Empty]
        HDS[historical_dsi_snapshots<br/>❌ Empty]
        HKM[historical_keyword_metrics<br/>✓ TimescaleDB]
        HPCC[historical_page_content_changes<br/>❌ Empty]
        HPDS[historical_page_dsi_snapshots<br/>❌ Empty]
        HPL[historical_page_lifecycle<br/>❌ Empty]
        
        style HCM fill:#ff9999
        style HDS fill:#ff9999
        style HKM fill:#ccffcc
        style HPCC fill:#ff9999
        style HPDS fill:#ff9999
        style HPL fill:#ff9999
    end

    subgraph "Orphaned Tables"
        EC[error_categories<br/>❌ Empty]
        JQ[job_queue<br/>❌ Empty]
        RH[retry_history<br/>❌ Empty]
        SHM[service_health_metrics<br/>❌ Empty]
        DSI[dsi_calculations<br/>❌ Empty]
        
        style EC fill:#ff9999
        style JQ fill:#ff9999
        style RH fill:#ff9999
        style SHM fill:#ff9999
        style DSI fill:#ff9999
    end

    SERP -.->|No FK!| SC
    SC -.->|No FK!| CA
    SERP -.->|Should link| OCA
```

## Legend
- 🟢 **Green**: Tables with data and proper usage
- 🟡 **Yellow**: Tables with some issues
- 🔴 **Red**: Empty or problematic tables
- ⚪ **Dashed**: Missing relationships or non-existent tables

## Major Issues Visualized

### 1. **Broken Data Flow**
```
SERP Results → ❌ → Scraped Content → ❌ → Content Analysis
```
The main data pipeline is broken with no foreign keys connecting the flow.

### 2. **Company Data Redundancy**
```
company_profiles ←→ company_profiles_cache
       ↕
client_config.company_profile (JSONB)
```
Three different places storing the same company information.

### 3. **Analysis Paralysis**
Four different content analysis approaches:
- `content_analysis` (original)
- `generic_dimension_analysis` (generic)
- `optimized_content_analysis` (new)
- `advanced_dimension_analysis` (referenced but doesn't exist!)

### 4. **Historical Data Overengineering**
Six historical tables, all empty, representing different granularities of the same data.

### 5. **Pipeline State Confusion**
```
pipeline_executions
    ├── pipeline_state (current state)
    ├── pipeline_checkpoints (checkpoints)
    └── pipeline_phase_status (empty)
```

## Recommended Simplified Schema

```mermaid
graph TD
    subgraph "Simplified Core Flow"
        K[keywords] -->|FK| S[serp_results]
        S -->|FK| C[content]
        C -->|FK| A[analysis]
        
        CO[companies] -->|FK| C
        
        P[projects] -->|FK| A
        P -->|FK| K
    end
    
    subgraph "Single State Table"
        PE2[pipeline_runs] -->|FK| P
        PH[pipeline_history] -->|FK| PE2
    end
    
    subgraph "One Historical Table"
        H[historical_snapshots] -->|polymorphic| A
        H -->|polymorphic| S
    end
```

This would reduce 42 tables to ~10-12 core tables with clear relationships and no redundancy.
