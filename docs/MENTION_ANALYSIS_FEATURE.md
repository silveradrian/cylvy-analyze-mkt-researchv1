# Brand & Competitor Mention Analysis Feature

## Overview

The optimized content analyzer now includes comprehensive brand and competitor mention extraction with AI-powered sentiment analysis. This critical feature identifies when the client's brand or competitors are mentioned in content and analyzes the sentiment of each mention.

## How It Works

### 1. Entity Extraction
The system extracts:
- **Client brand names**: Including company name, legal name, and domain variations
- **Competitor names**: From configured competitors including their domain variations

### 2. AI-Powered Analysis
For each mention found, the AI analyzes:
- **Entity**: The exact name mentioned
- **Type**: Whether it's a "brand" or "competitor" mention
- **Sentiment**: Classified as "positive", "negative", or "neutral"
- **Confidence**: 0-10 score indicating certainty of sentiment classification
- **Context**: 50-100 character snippet surrounding the mention
- **Position**: Character position in the content for reference

### 3. Contextual Sentiment Analysis
Unlike simple keyword matching, the AI considers:
- Full context around the mention
- Overall tone of the passage
- Relationship to other entities mentioned
- Industry-specific language nuances

## Data Storage

Mentions are stored in the `optimized_content_analysis` table in the `mentions` JSONB column with the following structure:

```json
[
  {
    "entity": "Finastra",
    "type": "brand",
    "sentiment": "positive",
    "confidence": 8,
    "context": "...Finastra's innovative platform has transformed how banks...",
    "position": 1234
  },
  {
    "entity": "Stripe",
    "type": "competitor", 
    "sentiment": "neutral",
    "confidence": 7,
    "context": "...compared to solutions like Stripe, the integration offers...",
    "position": 2456
  }
]
```

## Usage in Pipeline

The mention analysis is automatically performed during the content analysis phase (Phase 6) of the pipeline. The system:

1. Loads company and competitor names from the project configuration
2. Includes these in the AI prompt for analysis
3. Extracts and analyzes all mentions found
4. Stores results alongside other content analysis data

## Benefits

- **Competitive Intelligence**: Track how competitors are mentioned across content
- **Brand Monitoring**: Understand sentiment towards your brand
- **Content Strategy**: Identify opportunities based on mention patterns
- **Market Positioning**: See how your brand compares to competitors in discussions

## Example Query

To retrieve content with brand mentions:

```sql
SELECT 
    url,
    mentions,
    overall_insights
FROM optimized_content_analysis
WHERE project_id = 'your-project-id'
AND mentions @> '[{"type": "brand"}]'::jsonb
ORDER BY analyzed_at DESC;
```

## Future Enhancements

- Mention frequency analysis across time periods
- Sentiment trend tracking
- Co-mention analysis (when brand and competitors appear together)
- Industry benchmark comparisons

