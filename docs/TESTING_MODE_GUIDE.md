# Pipeline Testing Mode Guide

## Overview

The Testing Mode feature allows you to run full end-to-end pipeline tests with a limited set of keywords for rapid development and testing. This ensures the entire pipeline is working robustly before running full production workloads.

## Features

### 1. **Forced Full Pipeline Execution**
When testing mode is enabled, ALL pipeline phases are forced to run regardless of existing data or cache:
- ✅ Keyword Metrics Enrichment
- ✅ SERP Collection (all content types)
- ✅ Company Enrichment
- ✅ Video Enrichment
- ✅ Content Analysis
- ✅ Historical Tracking
- ✅ Digital Landscape DSI Calculation

### 2. **Batch Size Limiting**
- Default: 5 keywords (configurable)
- Prevents accidentally processing thousands of keywords during testing
- Applies to both keyword metrics and SERP collection phases

### 3. **Testing Mode Indicators**
- Pipeline mode shows as "TESTING" in the UI
- Special 🧪 emoji indicators in logs
- Clear batch size limiting messages

## Usage

### Frontend - Quick Testing Button

The easiest way to start a testing pipeline is using the "🧪 Test Mode" button on the Pipeline page:

1. Navigate to `/pipeline`
2. Click "🧪 Test Mode (5 Keywords)"
3. The pipeline will start with:
   - 5 keywords (first 5 from your project)
   - US region
   - All content types (organic, news, video)
   - All phases enabled

### API - Advanced Testing

For more control, use the `/api/v1/pipeline/test-mode` endpoint:

```bash
curl -X POST http://localhost:3000/api/v1/pipeline/test-mode \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_size": 10,
    "skip_delays": true,
    "regions": ["US", "UK"],
    "content_types": ["organic", "news"]
  }'
```

Parameters:
- `batch_size`: Number of keywords to process (1-100)
- `skip_delays`: Skip rate limiting delays (not implemented yet)
- `regions`: List of regions to test
- `content_types`: List of content types to test

### Manual Configuration

You can also enable testing mode in any pipeline start request:

```json
{
  "testing_mode": true,
  "testing_batch_size": 5,
  "testing_skip_delays": true,
  // ... other pipeline config
}
```

## ScaleSERP Integration

When in testing mode:
- Batches are still created with proper scheduling parameters
- Batch names include content type for easy identification
- The small batch size ensures quick processing
- Webhooks will still fire when batches complete

## Monitoring

Testing pipelines appear in the pipeline list with:
- Mode: "testing"
- Clear indication of batch size used
- All standard pipeline monitoring features

## Best Practices

1. **Start Small**: Use 5-10 keywords for initial tests
2. **Single Region**: Test with one region first
3. **Check Logs**: Testing mode adds special log entries with 🧪 emoji
4. **Verify All Phases**: Check that all phases complete successfully
5. **Monitor Costs**: Even small batches incur API costs

## Troubleshooting

### Pipeline Fails Immediately
- Check that you have at least 5 keywords in your project
- Verify API credentials are configured
- Check backend logs for detailed errors

### SERP Collection Takes Too Long
- Reduce batch size to 3-5 keywords
- Test with single content type first
- Check ScaleSERP API status

### Missing Results
- Ensure force_refresh is enabled (automatic in testing mode)
- Check that all phases are enabled
- Verify database connections

## Implementation Details

### Backend Changes

1. **PipelineMode Enum**: Added `TESTING` mode
2. **PipelineConfig**: Added testing configuration fields
3. **Pipeline Service**: Auto-enables all phases when testing_mode=true
4. **Batch Limiting**: Applied in keyword fetching logic
5. **API Endpoint**: `/pipeline/test-mode` for quick testing

### Frontend Changes

1. **Testing Button**: Added to pipeline page quick actions
2. **Status Display**: Shows testing mode in pipeline list
3. **Alert Messages**: Clear feedback when testing pipeline starts

## Future Enhancements

- [ ] Skip delays implementation for faster testing
- [ ] Testing mode presets (minimal, standard, comprehensive)
- [ ] Dry run mode (validate without API calls)
- [ ] Testing report generation
- [ ] Cost estimation before running
