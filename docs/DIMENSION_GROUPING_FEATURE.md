# Dimension Grouping Feature

## Overview

The dimension grouping feature allows users to organize custom dimensions into logical categories. The AI analyzer will automatically select the most relevant/primary dimension from each group during content analysis, which helps with:

1. **Simplified Filtering**: Future dashboards can filter by primary dimensions instead of showing all dimensions
2. **Reduced Noise**: Only the most relevant dimension per group is highlighted
3. **Better Insights**: Automatic selection based on evidence and scoring
4. **Organized Analysis**: Dimensions are categorized for better understanding

## How It Works

### 1. Dimension Groups

Each group has:
- **Name & Description**: Clear identification
- **Selection Strategy**: How the primary dimension is chosen
- **Visual Identity**: Color and icon for UI display
- **Max Primary Dimensions**: Usually 1, but can be configured

### 2. Selection Strategies

The AI uses different strategies to select the primary dimension:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `highest_score` | Selects dimension with highest relevance score (0-10) | When you want the most relevant dimension |
| `highest_confidence` | Selects dimension AI is most confident about | When accuracy matters more than relevance |
| `most_evidence` | Selects dimension with most supporting evidence | When you need strong proof |
| `manual` | Uses predefined priority order | When you have specific preferences |

### 3. Default Groups (Examples - Fully Customizable)

The system comes with 4 example dimension groups that can represent ANY content attributes:

1. **Content Style & Tone** (`highest_confidence`)
   - Professional tone, writing style, formality level, voice
   - Primary = style AI is most confident about

2. **Audience Targeting** (`highest_score`)
   - Accessibility, expertise level, persona alignment
   - Primary = most relevant to target audience

3. **Information Quality** (`most_evidence`)
   - Technical depth, data richness, accuracy, completeness
   - Primary = dimension with most supporting evidence

4. **Engagement & Impact** (`highest_score`)
   - Storytelling, emotional appeal, call-to-action strength
   - Primary = most engaging aspect

## Database Schema

### dimension_groups
```sql
- id: UUID
- group_id: Unique identifier
- name: Display name
- description: Purpose of group
- selection_strategy: How to select primary
- max_primary_dimensions: Usually 1
- color_hex: UI color
- icon: UI icon identifier
```

### dimension_group_members
```sql
- group_id: Reference to group
- dimension_id: Reference to dimension
- priority: For manual selection
```

### analysis_primary_dimensions
```sql
- analysis_id: Which content analysis
- group_id: Which dimension group
- dimension_id: Selected primary dimension
- selection_score: Score used for selection
- selection_reason: Why this was selected
```

## More Example Groups and Dimensions

Groups can represent ANY categorization that makes sense for your analysis:

### Content Attributes
- **Writing Quality**: Grammar, clarity, structure, flow
- **Visual Design**: Layout, graphics, whitespace, branding
- **SEO Factors**: Keywords, meta tags, readability, structure

### Communication Traits
- **Persuasion Tactics**: Social proof, urgency, authority, scarcity
- **Cultural Alignment**: Regional tone, local references, cultural sensitivity
- **Brand Voice**: Consistency, personality, differentiation

### Business Attributes  
- **Credibility Signals**: Certifications, awards, testimonials, case studies
- **Value Communication**: ROI focus, benefits clarity, pricing transparency
- **Competitive Positioning**: Differentiation, unique value, market claims

### Technical Attributes
- **Code Quality**: Examples clarity, best practices, error handling
- **Documentation Depth**: API coverage, tutorials, troubleshooting
- **Architecture Maturity**: Scalability, security, performance

## Usage Example

### 1. Create Dimensions with Groups

```javascript
// Example 1: Tone of Voice dimension
{
  name: "Conversational Tone",
  description: "Measures how conversational vs formal the writing is",
  group_id: "content_style",  // Assign to Content Style group
  scoring_levels: [
    { level: 0, label: "Stiff/Robotic", description: "Very formal, no personality" },
    { level: 5, label: "Professional", description: "Business appropriate" },
    { level: 10, label: "Conversational", description: "Friendly and approachable" }
  ],
  evidence_types: ["contractions", "personal pronouns", "questions to reader", "informal phrases"]
}

// Example 2: Trust Signal dimension
{
  name: "Third-Party Validation",
  description: "External proof points and credibility indicators",
  group_id: "information_quality",  // Assign to Information Quality group
  scoring_levels: [...],
  evidence_types: ["customer logos", "testimonials", "analyst mentions", "media coverage", "awards"]
}
```

### 2. Analysis Results

After analyzing content, the system automatically:

```sql
-- For Technical Capabilities group:
-- Dimensions analyzed: Cloud Maturity (8/10), API Quality (9/10), Security (7/10)
-- Primary selected: API Quality (highest score in group)

INSERT INTO analysis_primary_dimensions VALUES (
  analysis_id: 'xxx',
  group_id: 'technical_capabilities',
  dimension_id: 'api_quality',
  selection_score: 9.0,
  selection_reason: 'Highest score (9/10) in Technical Capabilities group'
);
```

### 3. Querying Primary Dimensions

```sql
-- Get primary dimensions for recent content
SELECT * FROM recent_primary_dimensions 
WHERE company_name = 'Acme Corp'
ORDER BY analyzed_at DESC;

-- Get group performance
SELECT * FROM get_dimension_group_performance(project_id);
```

## Benefits for Future Features

### 1. Dashboard Filtering
- Show only primary dimensions by default
- Drill down to see all dimensions in a group
- Compare primary dimensions across content

### 2. Trend Analysis
- Track which dimensions are most often primary
- Identify strengths/weaknesses by group
- Monitor changes over time

### 3. Competitive Analysis
- Compare primary dimensions across competitors
- Identify differentiation opportunities
- Focus on what matters most

### 4. Report Generation
- Cleaner executive summaries
- Focused insights per category
- Reduced information overload

## API Integration

### Creating/Updating Groups

```python
# Backend endpoint (future implementation)
POST /api/v1/dimension-groups
{
  "name": "Customer Experience",
  "description": "All customer-facing aspects",
  "selection_strategy": "highest_score",
  "color": "#EC4899"
}
```

### Assigning Dimensions

```python
# When creating a dimension
POST /api/v1/dimensions
{
  "name": "Onboarding Experience",
  "group_id": "customer_experience",
  ...
}
```

### Retrieving Results

```python
# Get content with primary dimensions
GET /api/v1/analysis/content/{url}/primary-dimensions

Response:
{
  "technical_capabilities": {
    "primary": "api_quality",
    "score": 9.0,
    "reason": "Highest score in group"
  },
  "business_maturity": {
    "primary": "market_presence",
    "score": 8.5,
    "reason": "Highest confidence in group"
  }
}
```

## Best Practices

1. **Group Similar Dimensions**: Keep related dimensions together
2. **Choose Appropriate Strategies**: Match strategy to group purpose
3. **Limit Groups**: 4-6 groups is usually sufficient
4. **Clear Naming**: Use descriptive group and dimension names
5. **Regular Review**: Monitor which dimensions become primary

## Future Enhancements

1. **Custom Selection Logic**: Define complex rules for selection
2. **Multi-Primary Support**: Allow multiple primaries per group
3. **Dynamic Grouping**: AI-suggested groupings based on correlation
4. **Group Weights**: Some groups more important than others
5. **Time-based Selection**: Different primaries for different time periods
