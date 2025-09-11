# SERP Batch Collection Flow Diagram

## Visual Flow of SERP Batch Processing

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PIPELINE EXECUTION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Phase 1: Keyword Metrics                                            │
│     ↓                                                                │
│  Phase 2: SERP Collection ──────────────┐                           │
│                                         │                           │
│                                         ▼                           │
│                            ┌────────────────────────┐               │
│                            │  CREATE SERP BATCH    │               │
│                            │  - Organic batch      │               │
│                            │  - News batch         │               │
│                            │  - Video batch        │               │
│                            └───────────┬────────────┘               │
│                                        │                           │
│                                        ▼                           │
│                            ┌────────────────────────┐               │
│                            │   START BATCH         │               │
│                            │   (Scale SERP API)    │               │
│                            └───────────┬────────────┘               │
│                                        │                           │
│                                        ▼                           │
│                 ┌──────────────────────────────────────────┐        │
│                 │         MONITOR BATCH COMPLETION         │        │
│                 │                                          │        │
│                 │  ┌────────────────────────────────────┐ │        │
│                 │  │  POLLING LOOP (every 30 seconds)  │ │        │
│                 │  │                                    │ │        │
│                 │  │  Check Status:                    │ │        │
│                 │  │  - queued    → WAIT               │ │        │
│                 │  │  - running   → WAIT               │ │        │
│                 │  │  - idle      → DOWNLOAD RESULTS   │ │        │
│                 │  │  - failed    → ERROR              │ │        │
│                 │  └────────────┬───────────────────────┘ │        │
│                 │               │                         │        │
│                 │               ▼                         │        │
│                 │  ┌────────────────────────────────────┐ │        │
│                 │  │  Status = 'idle'?                 │ │        │
│                 │  │  (Batch Complete)                 │ │        │
│                 │  └────────────┬───────────────────────┘ │        │
│                 │               │YES                      │        │
│                 │               ▼                         │        │
│                 │  ┌────────────────────────────────────┐ │        │
│                 │  │  DOWNLOAD ALL RESULT PAGES        │ │        │
│                 │  │  - Page 1: 1-100 results          │ │        │
│                 │  │  - Page 2: 101-200 results        │ │        │
│                 │  │  - Page N: ...                    │ │        │
│                 │  └────────────┬───────────────────────┘ │        │
│                 │               │                         │        │
│                 │               ▼                         │        │
│                 │  ┌────────────────────────────────────┐ │        │
│                 │  │  PROCESS & STORE IN DATABASE      │ │        │
│                 │  │  - Parse JSON results             │ │        │
│                 │  │  - Extract SERP data              │ │        │
│                 │  │  - INSERT into serp_results       │ │        │
│                 │  └────────────┬───────────────────────┘ │        │
│                 │               │                         │        │
│                 └───────────────┼─────────────────────────┘        │
│                                 │                                   │
│                                 ▼                                   │
│                    ┌─────────────────────────────┐                 │
│                    │  RETURN BATCH RESULTS       │                 │
│                    │  {                          │                 │
│                    │    success: true,           │                 │
│                    │    results_stored: 450,     │                 │
│                    │    batch_id: "xyz123"       │                 │
│                    │  }                          │                 │
│                    └──────────────┬──────────────┘                 │
│                                   │                                 │
│     ◄─────────────────────────────┘                                │
│     │                                                               │
│     ▼                                                               │
│  ┌─────────────────────────────────────┐                          │
│  │  QUERY DATABASE FOR RESULTS         │                          │
│  │  - unique_domains = SELECT DISTINCT │                          │
│  │  - video_urls = SELECT WHERE video  │                          │
│  └──────────────┬──────────────────────┘                          │
│                 │                                                   │
│                 ▼                                                   │
│  Phase 3: Company Enrichment                                       │
│     (ONLY starts after SERP data is in DB)                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Blocking Points

### 1. **Batch Monitoring Loop**
```python
# This loop BLOCKS until batch is complete
while batch_status != 'idle':
    await asyncio.sleep(30)  # Wait 30 seconds
    check_status()           # Poll Scale SERP API
```

### 2. **Database Storage**
```python
# All results must be stored before returning
for result in batch_results:
    await store_in_database(result)
return success  # Only after ALL stored
```

### 3. **Phase Transition**
```python
# Phase 2 must complete before Phase 3
serp_result = await phase_2_serp_collection()  # BLOCKS
if serp_result['success']:
    await phase_3_company_enrichment()  # Only runs after SERP done
```

## Timing Example

For a typical batch with 500 searches:
- Batch creation: ~2 seconds
- Batch execution: 2-5 minutes (Scale SERP processing)
- Result download: ~10 seconds
- Database storage: ~5 seconds
- **Total Phase 2 time: 2-6 minutes**

Phase 3 will **NOT** start until all of the above is complete.
