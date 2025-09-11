# Simplified AI Analysis Flow

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONFIGURATION PHASE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Company Profile  →  2. Personas  →  3. Keywords             │
│         ↓                    ↓                ↓                  │
│  ┌──────────────┐    ┌─────────────┐   ┌──────────┐           │
│  │ Company Name │    │ Tech DM     │   │ Keywords │           │
│  │ Domain       │    │ Business DM │   │ Regions  │           │
│  │ Value Prop   │    │ End User    │   │          │           │
│  └──────────────┘    └─────────────┘   └──────────┘           │
│                                                                  │
│  4. JTBD Phases (Pre-configured)    5. Custom Dimensions (Opt)  │
│  ┌────────────────────────────┐    ┌─────────────────────┐    │
│  │ 1. Problem Identification  │    │ • Cloud Maturity    │    │
│  │ 2. Solution Exploration    │    │ • Security Trust    │    │
│  │ 3. Requirements Building   │    │ • Innovation        │    │
│  │ 4. Vendor Selection        │    └─────────────────────┘    │
│  │ 5. Validation & Consensus  │                                │
│  │ 6. Negotiation & Purchase  │                                │
│  └────────────────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ANALYSIS PHASE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Content URL → Scraper → Raw Content                            │
│                              ↓                                   │
│                 ┌────────────────────────┐                      │
│                 │  Unified AI Context    │                      │
│                 ├────────────────────────┤                      │
│                 │ • All Personas         │                      │
│                 │ • All JTBD Phases      │                      │
│                 │ • All Dimensions       │                      │
│                 │ • Scoring Criteria     │                      │
│                 └──────────┬─────────────┘                      │
│                            ↓                                     │
│              ┌──────────────────────────┐                       │
│              │   Single AI API Call     │                       │
│              │   (GPT-4 with JSON mode) │                       │
│              └──────────┬───────────────┘                       │
│                         ↓                                        │
│         ┌───────────────────────────────────┐                  │
│         │      Structured Response          │                  │
│         ├───────────────────────────────────┤                  │
│         │ {                                 │                  │
│         │   "primary_persona": "Tech DM",   │                  │
│         │   "persona_scores": {...},        │                  │
│         │   "primary_jtbd_phase": 3,        │                  │
│         │   "dimension_scores": {...},      │                  │
│         │   "mentions": [...],              │                  │
│         │   "summary": "..."                │                  │
│         │ }                                 │                  │
│         └───────────────┬───────────────────┘                  │
│                         ↓                                        │
│              ┌───────────────────────┐                         │
│              │  Single Table Store   │                         │
│              │  content_analysis     │                         │
│              └───────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      INSIGHTS PHASE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────────┐│
│  │  Persona Alignment  │  │  Journey Stage  │  │  Dimension  ││
│  │  ┌───┬───┬───┐     │  │  Distribution   │  │   Scores    ││
│  │  │TDM│BDM│EU │     │  │  ████░░░░░░     │  │  Cloud: 8/10││
│  │  │ 8 │ 3 │ 5 │     │  │  Phase 3: 45%   │  │  Sec: 10/10 ││
│  │  └───┴───┴───┘     │  │                 │  │  Innov: 5/10││
│  └─────────────────────┘  └─────────────────┘  └─────────────┘│
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │                    Actionable Insights                      ││
│  ├────────────────────────────────────────────────────────────┤│
│  │ • Technical Decision Makers are primary audience (80%)      ││
│  │ • Content focuses on Requirements Building phase (45%)      ││
│  │ • Strong security positioning, weak on innovation           ││
│  │ • Competitor X mentioned 3x positively                      ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Key Simplifications

### 1. Configuration → Context (One Time)
- Load all config once into `UnifiedAnalysisContext`
- No multiple database queries during analysis
- Clear data structure the AI understands

### 2. Analysis → Single AI Call
- One comprehensive prompt with ALL context
- AI sees relationships between personas, phases, dimensions
- Structured JSON response format

### 3. Storage → Single Table
- One `content_analysis` table
- All scores in JSONB fields
- Easy to query and aggregate

### 4. Scoring → Consistent Framework
- **Personas**: 0-10 alignment score
- **JTBD Phase**: 1-6 phase, 0-10 alignment
- **Dimensions**: 0/5/10 evidence-based levels
- **Mentions**: Positive/Neutral/Negative sentiment

## Example Analysis Output

```json
{
  "primary_persona": "Technical Decision Maker",
  "persona_scores": {
    "Technical Decision Maker": 8,
    "Business Decision Maker": 3,
    "End User Champion": 5
  },
  "persona_reasoning": "Content focuses on API architecture, security certifications, and technical integration - directly addressing Technical DM concerns",
  
  "primary_jtbd_phase": 3,
  "phase_alignment_score": 9,
  "phase_reasoning": "Heavy focus on specific requirements, feature comparisons, and technical specifications indicates Requirements Building phase",
  
  "dimension_scores": {
    "Cloud Maturity": 10,
    "Security & Trust": 10,
    "Innovation & Partnerships": 5
  },
  "dimension_evidence": {
    "Cloud Maturity": "Multi-cloud support, AWS/Azure/GCP certifications, auto-scaling mentioned",
    "Security & Trust": "SOC2, ISO27001, GDPR compliance, zero-trust architecture detailed",
    "Innovation & Partnerships": "Some API ecosystem mentions but no concrete partnership examples"
  },
  
  "mentions": [
    {
      "entity": "Competitor X",
      "sentiment": "positive",
      "context": "integrates seamlessly with Competitor X's API"
    }
  ],
  
  "summary": "Technical deep-dive content targeting architects evaluating cloud security solutions. Strong on compliance and technical requirements, positioned for mid-funnel evaluation.",
  
  "buyer_intent_signals": [
    "comparing our requirements",
    "need to ensure compatibility",
    "evaluating vendors"
  ]
}
```

## Benefits of Simplification

1. **Faster Analysis**: Single AI call vs multiple
2. **Better Context**: AI sees full picture, not fragments
3. **Consistent Scoring**: Same scale across all dimensions
4. **Easier Debugging**: One prompt, one response, one table
5. **Clear Insights**: Direct mapping from config to scores

## Implementation Priority

1. **Phase 1**: Create simplified analyzer (done)
2. **Phase 2**: Create database schema (done)
3. **Phase 3**: Update pipeline to use new analyzer
4. **Phase 4**: Create insights dashboard
5. **Phase 5**: Migrate existing data
