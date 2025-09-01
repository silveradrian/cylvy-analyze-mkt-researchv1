# Cylvy Digital Landscape Analyzer

A client-agnostic, AI-powered competitive intelligence platform for B2B content analysis.

## Features

- **Multi-tenant Architecture**: Support unlimited clients with complete data isolation
- **Configurable AI Analysis**: Fully customizable prompts, personas, and JTBD phases
- **Batch-Optimized Pipeline**: Efficient processing of keywords and content at scale
- **Real-time Monitoring**: WebSocket-powered progress tracking
- **Comprehensive Analytics**: DSI rankings, content analysis, and competitive insights

## Tech Stack

- **Backend**: FastAPI, PostgreSQL (TimescaleDB), Redis
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **AI**: OpenAI GPT-4, configurable prompt engineering
- **Infrastructure**: Docker, Kubernetes-ready

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/silveradrian/cylvy-analyze-mkt-researchv1.git
cd cylvy-analyze-mkt-researchv1
```

2. Copy environment files:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

3. Start services:
```bash
docker-compose up -d
```

4. Run migrations:
```bash
docker-compose exec backend python -m app.db.migrate
```

5. Access the application:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Project Structure

```
cylvy-analyzer/
├── backend/
│   ├── app/
│   │   ├── core/        # Core functionality
│   │   ├── models/      # Data models
│   │   ├── services/    # Business logic
│   │   ├── api/         # API endpoints
│   │   └── db/          # Database
│   └── tests/
├── frontend/
│   ├── app/
│   │   ├── (auth)/      # Authentication
│   │   ├── (dashboard)/ # Main application
│   │   ├── (admin)/     # Admin portal
│   │   └── (onboarding)/# Client setup
│   └── components/
├── docker/
├── docs/
└── scripts/
```

## Configuration

### Tenant Setup
1. Create a new tenant through the admin portal
2. Configure API keys for external services
3. Set up personas and JTBD phases
4. Customize AI prompts
5. Upload keywords and start analysis

### Environment Variables

See `.env.example` files in backend and frontend directories for required configuration.

## License

Proprietary - All rights reserved

## Support

For support, email support@cylvy.com

