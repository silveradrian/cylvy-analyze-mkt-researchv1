# Company Enrichment - Exact Domain Match

## Overview

The company enrichment service now uses exact domain matching to ensure precise company identification when searching via the Cognism API.

## Configuration

The `match_exact_domain` parameter is set in the `accountSearchOptions` when making API calls to Cognism:

```python
"accountSearchOptions": {
    "match_exact_domain": 1,  # Boolean - exact domain match
    "filter_domain": "exists",
    "exclude_dataTypes": ["companyHiring", "locations", "officePhoneNumbers", "hqPhoneNumbers", "technologies"]
}
```

## What This Does

1. **Exact Matching**: When set to `1` (true), the API will only return companies whose domain exactly matches the search query
2. **No Partial Matches**: Prevents returning companies with similar but not exact domains
3. **Better Accuracy**: Reduces false positives and ensures we enrich the correct company

## Examples

- Searching for `acme.com`:
  - ✅ Will match: `acme.com`
  - ❌ Won't match: `acme-corp.com`, `acmetech.com`, `subdomain.acme.com`

## Files Updated

1. `backend/app/services/enrichment/company_enricher.py` - Line 112
2. `backend/app/services/enrichment/enhanced_company_enricher.py` - Line 168

## API Reference

According to Cognism API documentation, the `match_exact_domain` parameter should be passed as a numeric boolean (0 or 1) rather than Python's True/False.

## Benefits

- **Accuracy**: Ensures we're enriching the exact company, not a similar one
- **Reliability**: Reduces errors from mismatched company data
- **Performance**: Fewer false matches mean less data to process
