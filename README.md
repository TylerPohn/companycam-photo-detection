# CompanyCam Photo Detection System

A scalable photo detection and classification system for construction photo management, built with FastAPI, React, and deployed on AWS EKS.

## Overview

This system provides automated detection, classification, and metadata extraction for construction photos, enabling efficient photo management and analysis for CompanyCam users.

### Key Features

- **Photo Upload Service**: Secure photo uploads with S3 storage
- **Detection Service**: ML-powered photo classification and object detection
- **Metadata Service**: Automatic metadata extraction and management
- **RESTful API**: FastAPI-based backend with comprehensive endpoints
- **Modern Frontend**: React-based UI with TypeScript
- **Scalable Infrastructure**: AWS EKS deployment with auto-scaling

## Architecture

The system follows a microservices architecture:

```
├── backend/          # FastAPI backend services
├── frontend/         # React frontend application
├── ml-models/        # Machine learning models
├── infrastructure/   # Terraform & Kubernetes configs
└── docs/            # Technical documentation
```

For detailed architecture information, see [docs/architecture.md](docs/architecture.md).

## Prerequisites

- **Docker** 20.10+ and Docker Compose 2.0+
- **Python** 3.11+ (for backend development)
- **Node.js** 20+ and npm (for frontend development)
- **Git** for version control
- **AWS CLI** (for deployment)
- **kubectl** (for Kubernetes management)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd companycam-photo-detection
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Start Development Environment

Using Docker Compose (recommended):

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO (ports 9000, 9001)
- Backend API (port 8000)
- Frontend Dev Server (port 5173)

### 4. Verify Services

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:5173
- **MinIO Console**: http://localhost:9001

## Development

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with hot reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Run tests
npm test

# Build for production
npm run build
```

### Code Quality

We use pre-commit hooks for code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Testing

### Backend Tests

```bash
cd backend
pytest                           # Run all tests
pytest --cov=src                 # With coverage
pytest -v tests/test_main.py     # Specific test file
pytest -k test_health_check      # Specific test
```

### Frontend Tests

```bash
cd frontend
npm test                         # Run all tests
npm run test:coverage            # With coverage
```

### Integration Tests

```bash
docker-compose up -d
# Wait for services to be healthy
pytest tests/integration/
```

## Deployment

### Staging Deployment

```bash
# Deploy to staging (requires AWS credentials)
git push origin staging

# Manual deployment
kubectl apply -f infrastructure/k8s/staging/
```

### Production Deployment

```bash
# Deploy to production (blue/green)
git push origin main

# Manual deployment with approval
kubectl apply -f infrastructure/k8s/production/
```

See [docs/deployment.md](docs/deployment.md) for detailed deployment instructions.

## CI/CD Pipeline

GitHub Actions automatically:

1. **Lint**: Checks code style (Black, Flake8, ESLint)
2. **Test**: Runs unit tests with coverage
3. **Build**: Creates Docker images
4. **Deploy**: Deploys to staging/production (with approval)

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for pipeline configuration.

## Project Structure

```
companycam-photo-detection/
├── .github/
│   └── workflows/           # CI/CD pipelines
├── backend/
│   ├── src/                # Application source code
│   ├── tests/              # Test files
│   ├── config/             # Configuration files
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/                # React components
│   ├── tests/              # Component tests
│   ├── public/             # Static assets
│   └── package.json
├── ml-models/
│   ├── models/             # Trained models
│   └── training/           # Training scripts
├── infrastructure/
│   ├── terraform/          # AWS infrastructure
│   └── k8s/               # Kubernetes manifests
├── docs/                   # Documentation
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Environment Variables

Key environment variables (see `.env.example` for complete list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `AWS_ACCESS_KEY_ID` | AWS credentials | - |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | - |
| `S3_BUCKET` | S3 bucket for photos | `companycam-photos` |
| `ENVIRONMENT` | Environment name | `development` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and guidelines.

## Documentation

- [Architecture Documentation](docs/architecture.md)
- [Product Requirements](docs/prd.md)
- [API Documentation](http://localhost:8000/docs) (when running)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

For issues or questions:
- Create an issue in the repository
- Check existing documentation in `docs/`
- Review API documentation at `/docs` endpoint

## Monitoring & Observability

- **Metrics**: Prometheus metrics at `/metrics` endpoint
- **Health Check**: `/health` endpoint
- **Logs**: Structured JSON logging with correlation IDs

## Security

- All sensitive data encrypted at rest and in transit
- AWS IAM roles for service authentication
- Regular security scans in CI/CD pipeline
- See [SECURITY.md](SECURITY.md) for reporting vulnerabilities
