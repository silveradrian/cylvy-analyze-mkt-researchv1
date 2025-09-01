# Cylvy Digital Landscape Analyzer

A client-agnostic, AI-powered competitive intelligence platform for B2B content analysis with configurable branding, personas, and analysis parameters.

## 🌟 Features

- **🏢 Single-Instance Deployment**: Each client gets their own dedicated instance
- **🎨 Complete Customization**: Logo upload, brand colors, company configuration  
- **🤖 Configurable AI Analysis**: Custom prompts, personas, and JTBD phases
- **📊 Batch-Optimized Pipeline**: Efficient 7-phase processing workflow
- **⏰ Advanced Scheduling**: Daily/weekly/monthly/custom cron scheduling
- **📈 Historical Tracking**: Month-over-month trend analysis and insights
- **🔄 Real-time Monitoring**: WebSocket-powered progress tracking
- **📱 Modern Admin Interface**: React-based configuration and management

## 🏗️ Architecture

### Tech Stack
- **Backend**: FastAPI, PostgreSQL (TimescaleDB), Redis, Python 3.11+
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **AI**: OpenAI GPT-4, configurable prompt engineering
- **Infrastructure**: Docker, production-ready containerization

### Service Architecture
```
📱 Frontend (Next.js)
    ↓
🔄 API Gateway (FastAPI)
    ↓
┌─────────────────────────────────────────┐
│ 🧠 Analysis    📊 Metrics    🗄️  Storage │
│ 🌐 Scraping    💼 Enrichment  ⏱️ Scheduling │
│ 🔍 SERP        📈 Historical  🔌 WebSocket │
└─────────────────────────────────────────┘
    ↓
🗃️ Database (TimescaleDB) + 📦 Redis
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 4GB+ RAM, 2+ CPU cores  
- 50GB+ storage space

### 1. Clone Repository
```bash
git clone https://github.com/silveradrian/cylvy-analyze-mkt-researchv1.git
cd cylvy-analyze-mkt-researchv1
```

### 2. Environment Setup
```bash
# Copy environment templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit backend/.env with your settings:
# - Set secure SECRET_KEY and JWT_SECRET_KEY
# - Configure DATABASE_URL if needed
# - Add API keys (or configure later in admin portal)
```

### 3. Quick Setup (Recommended)
```bash
# Using Makefile (recommended)
make setup    # Check environment + initialize database
make start    # Start all services

# Or manual setup
python scripts/setup.py check  # Check environment
python scripts/setup.py init   # Initialize database
docker-compose up -d           # Start services
```

### 4. Access Application
- **🎨 Admin Setup**: http://localhost:3000/admin/setup
- **📊 Dashboard**: http://localhost:3000/dashboard  
- **📖 API Docs**: http://localhost:8000/docs
- **❤️ Health Check**: http://localhost:8000/health

### 5. Initial Configuration
1. Navigate to Admin Setup Wizard
2. Configure company information & upload logo
3. Set brand colors
4. Configure API keys for external services
5. Set up personas and JTBD phases
6. Upload keywords and start first analysis

## 📊 Pipeline Workflow

### 7-Phase Batch Optimized Pipeline

```
Phase 1: 🔍 SERP Collection     → Collect search results for all keywords
Phase 2: 🏢 Company Enrichment → Enrich domains with company data  
Phase 3: 🎥 Video Enrichment   → Extract YouTube metadata/transcripts
Phase 4: 📄 Content Scraping   → Scrape content from URLs
Phase 5: 🧠 AI Analysis        → Analyze content with GPT-4
Phase 6: 📊 DSI Calculation    → Calculate competitive metrics
Phase 7: 📈 Historical Snapshot → Create monthly trend data
```

### Scheduling Options
- **Daily**: News and trending content
- **Weekly**: Competitive analysis updates  
- **Monthly**: Comprehensive landscape reviews
- **Custom**: Flexible cron-based scheduling

## 🛠️ Configuration

### Client Branding
- Upload company logo (PNG, JPG, SVG)
- Custom brand colors (primary & secondary)
- Company name throughout interface
- Personalized admin portal

### AI Analysis Setup
- **Personas**: Define target buyer personas with goals, pain points, decision criteria
- **JTBD Phases**: Configure Jobs to be Done buyer journey stages
- **Custom Prompts**: Full AI prompt engineering capabilities
- **Competitors**: Track specific competitor domains
- **Custom Dimensions**: Additional classification categories

### API Integration
- **OpenAI**: GPT-4 content analysis
- **ScaleSERP**: Search engine results collection
- **ScrapingBee**: Protected site content extraction
- **Cognism**: B2B company data enrichment
- **YouTube**: Video metadata and transcripts

## 📈 Analytics & Insights

### Digital Share of Influence (DSI)
- **Company Rankings**: Competitive positioning metrics
- **Page Performance**: Individual content performance tracking
- **Trend Analysis**: Month-over-month changes and insights
- **Market Intelligence**: Comprehensive competitive landscape view

### Historical Tracking
- **Monthly Snapshots**: Automated trend data collection
- **Page Lifecycle**: Track content discovery → peak performance → decline
- **Content Evolution**: Monitor content updates and their impact
- **Competitive Movement**: Track competitor strategy changes

## 🐳 Deployment Options

### Development
```bash
make dev    # Hot reloading for development
```

### Production
```bash
make deploy-prod    # Production deployment
```

### Management Commands
```bash
make logs           # View application logs
make health         # Check system health
make backup-db      # Backup database
make clean          # Clean up containers
make update         # Update application
```

## 📚 Documentation

- **[Deployment Guide](DEPLOYMENT_GUIDE.md)**: Detailed deployment instructions
- **[API Documentation](http://localhost:8000/docs)**: Interactive API explorer
- **[Migration Guide](CYLVY_MIGRATION_PLAN_SIMPLIFIED.md)**: Migration from legacy systems

## 🔒 Security

- **Authentication**: JWT-based user authentication
- **Authorization**: Role-based access control (viewer/analyst/admin/superadmin)
- **Data Isolation**: Complete client data separation per instance
- **API Security**: Encrypted API key storage
- **Input Validation**: Comprehensive request validation

## 🧪 Testing

```bash
make test           # Run test suite
make lint           # Code linting
make format         # Code formatting
```

## 🆘 Support

### Quick Troubleshooting
```bash
make health         # Check database connectivity
make logs           # View error logs
make restart        # Restart all services
```

### Common Issues
- **Database Connection**: Ensure PostgreSQL is running and DATABASE_URL is correct
- **API Keys**: Configure in admin portal or environment variables
- **Permissions**: Check user roles and authentication
- **Storage**: Ensure storage directories have proper permissions

## 📄 License

Proprietary - All rights reserved

---

**Built with ❤️ for competitive intelligence professionals**