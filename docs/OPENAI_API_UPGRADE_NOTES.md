# OpenAI API Upgrade Notes

## Overview
This document tracks the OpenAI API upgrade efforts based on the new API documentation.

## Current Status (September 2025)

### What Was Requested
The user requested upgrading all AI services to use the new OpenAI API format:
- New `responses.create()` method
- Model: `gpt-4.1`
- New input/output format

### What Was Discovered
After attempting to implement the new API format, we found that:

1. **The Python OpenAI SDK (v1.x) doesn't yet support the `responses.create()` method**
   - The documentation shows this new API, but the Python SDK still uses `chat.completions.create()`
   - Attempting to use `client.responses.create()` results in AttributeError

2. **Model Availability**
   - `gpt-4.1` model is not yet available in the API
   - We're using `gpt-4o-mini` for cost-effective operations
   - For more complex tasks, `gpt-4-turbo-preview` is available

### What Was Done
We upgraded all AI services to use the best practices with the current OpenAI SDK:

1. **Video Enricher** (`video_enricher.py`)
   - Uses `client.chat.completions.create()` with tool calling
   - Model: `gpt-4o-mini`
   - Proper error handling for domain extraction

2. **Company Enricher** (`company_enricher.py`)
   - Updated to use tools format instead of functions
   - Model: `gpt-4o-mini`
   - Async HTTP client for API calls

3. **Optimized Unified Analyzer** (`optimized_unified_analyzer.py`)
   - Kept using direct API calls for flexibility
   - Model: `gpt-4.1` (will fallback to available model)
   - Tool-based function calling

4. **AI Service** (`ai_service.py`)
   - Uses AsyncOpenAI client
   - Model: `gpt-4.1` (will fallback to available model)
   - Simple completion-based analysis

### Configuration Updates
- Updated default models in config files
- Maintained backward compatibility
- Added error handling for model availability

### Future Considerations
When the new `responses.create()` API becomes available in the Python SDK:

1. Update all `chat.completions.create()` calls to `responses.create()`
2. Change message format from `messages` to `input`
3. Update response parsing from `choices[0].message` to `output[0]`
4. Update tool calling format as per new API

### Current Best Practices
Until the new API is available:
1. Use `chat.completions.create()` with the OpenAI client
2. Use tool calling for structured outputs
3. Handle errors gracefully
4. Use appropriate models based on task complexity and cost
