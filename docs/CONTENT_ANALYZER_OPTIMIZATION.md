# Content Analyzer Optimization Recommendations

## Current Issues

### 1. Excessive Rationale Requirements
The current analyzer requests extensive rationale for each dimension:
- `detailed_reasoning`: Full text explanation
- `scoring_breakdown`: Base score, adjustments, and `scoring_rationale` 
- `evidence_analysis`: Word counts, specificity scores, quality indicators
- `matched_criteria`: Full list of matched signals

### 2. Content Truncation
- Content is truncated to 4000 characters in the prompt
- This leaves ~28K tokens available for output with GPT-4.1's 32K limit

### 3. Token Usage
With 10-20 dimensions, each requiring detailed rationale, the output can be excessive:
- ~200-400 tokens per dimension for detailed reasoning
- Total: 2,000-8,000 tokens just for reasoning

## Recommended Optimizations

### 1. Simplify Output Schema
Replace verbose fields with concise ones:

```python
# Current (verbose)
{
    "final_score": 8,
    "evidence_summary": "Long paragraph...",
    "evidence_analysis": {
        "total_relevant_words": 156,
        "evidence_threshold_met": true,
        "specificity_score": 7,
        "quality_indicators": {...}
    },
    "scoring_breakdown": {
        "base_score": 6,
        "evidence_adjustments": {...},
        "contextual_adjustments": {...},
        "scoring_rationale": "Long explanation..."
    },
    "confidence_score": 9,
    "detailed_reasoning": "Very long multi-paragraph explanation...",
    "matched_criteria": ["signal1", "signal2", "signal3"]
}

# Recommended (concise)
{
    "score": 8,
    "confidence": 9,
    "key_evidence": "Brief 1-2 sentence summary of strongest evidence",
    "primary_signals": ["top 3 matched signals"],
    "score_factors": {
        "positive": ["brief factor 1", "brief factor 2"],
        "negative": ["brief limitation"]
    }
}
```

### 2. Optimize Prompt Instructions
Instead of:
```
Provide structured analysis with:
1. final_score (0-10)
2. evidence_summary
3. evidence_analysis (word count, specificity, quality indicators)
4. scoring_breakdown (base score, adjustments, rationale)
5. confidence_score (0-10)
6. detailed_reasoning
7. matched_criteria (list of matched positive signals)
```

Use:
```
For each dimension, provide concise analysis:
- score: 0-10 rating
- confidence: 0-10 certainty level
- key_evidence: 1-2 sentences highlighting strongest evidence
- primary_signals: Top 3 matched criteria (brief labels only)
- score_factors: Brief positive/negative factors (3-5 words each)
```

### 3. Increase Content Window
Since we're reducing output verbosity, we can analyze more content:
- Current: 4000 characters
- Recommended: 8000-10000 characters
- This provides better context for analysis

### 4. Batch Processing
For dimensions that don't require deep reasoning:
- Group similar dimensions
- Use simpler scoring for low-complexity dimensions
- Reserve detailed analysis for critical dimensions

## Expected Benefits

1. **Token Efficiency**
   - Reduce output by 60-70%
   - Analyze more content with same token budget
   - Lower API costs

2. **Faster Processing**
   - Less data to generate and parse
   - Quicker response times
   - Better user experience

3. **Clearer Insights**
   - Focused on actionable information
   - Easier to understand scores
   - Less noise in the analysis

4. **Scalability**
   - Can handle more dimensions
   - More suitable for real-time analysis
   - Better for dashboard displays

## Implementation Priority

1. **Phase 1**: Simplify output schema (High Impact)
2. **Phase 2**: Optimize prompts (Medium Impact)
3. **Phase 3**: Increase content window (Low Risk)
4. **Phase 4**: Implement dimension batching (Future Enhancement)
