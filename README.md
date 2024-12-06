# Nova Search Engine

Nova is a high-performance, AI-powered search engine built with Python FastAPI. It provides intelligent web crawling, efficient indexing, and fast search capabilities with machine learning enhancements.

## Features

- 🔍 Fast and accurate search with Elasticsearch
- 🤖 AI-powered search rankings using BERT embeddings
- 🕷️ Intelligent web crawling with respect for robots.txt
- 🚀 High performance with Redis caching
- 📊 Monitoring with Prometheus & Grafana
- 🔒 Secure API with JWT authentication
- 🎯 Load balancing and rate limiting
- 📱 Responsive web interface

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- 4GB RAM minimum
- Git

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/Canopus-Development/nova.git
cd nova
```

2. Create and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configurations
```

3. Build and run with Docker Compose:
```bash
docker-compose up --build
```

4. Access the services:
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs
- Elasticsearch: http://localhost:9200
- Grafana: http://localhost:3000

## Manual Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up databases:
```bash
# Start MongoDB
mongod --dbpath /path/to/data/db

# Start Elasticsearch
./elasticsearch

# Start Redis
redis-server
```

4. Run the application:
```bash
uvicorn app:app --reload
```

## Environment Variables

Required environment variables in `.env`:

```env
# API Settings
SECRET_KEY=your-secret-key
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000

# Database URLs
MONGODB_URL=mongodb://mongodb:27017/
REDIS_URL=redis://redis:6379
ELASTICSEARCH_HOSTS=["http://elasticsearch:9200"]

# Security
BACKEND_CORS_ORIGINS=["http://localhost:8000"]
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Monitoring
SENTRY_DSN=your-sentry-dsn
```

## API Documentation

Full API documentation is available at `/api/docs` when running in development mode.

Key endpoints:
- `GET /api/v1/search` - Search content
- `POST /api/v1/crawl` - Start web crawling
- `GET /api/v1/suggestions` - Get search suggestions
- `GET /api/admin/stats` - Get system statistics (protected)

## Architecture

```
nova/
├── app/
│   ├── core/        # Core functionality
│   ├── crawler/     # Web crawler
│   ├── search/      # Search engine
│   ├── routes/      # API routes
│   ├── storage/     # Data storage
│   └── templates/   # HTML templates
├── docker/          # Docker configurations
├── tests/           # Test suite
└── app.py          # Application entry
```

## Development

1. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Run tests:
```bash
pytest
```

3. Check code style:
```bash
flake8 nova
black nova
```

## Production Deployment

For production deployment:

1. Update environment variables for production
2. Enable SSL/TLS
3. Configure proper authentication
4. Set up monitoring alerts
5. Use production-grade servers

## Monitoring

- Prometheus metrics at `/metrics`
- Grafana dashboards for visualization
- Sentry for error tracking

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Submit a pull request

## Support

- GitHub Issues: Bug reports and feature requests
- Documentation: Still Working On That
- Discord : https://discord.gg/JUhv27kzcJ


