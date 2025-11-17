# Backend Services

This directory contains the backend API services for the CompanyCam Photo Detection system.

## Structure

- `src/` - Source code for backend services
  - FastAPI application
  - Service layer (Photo Upload, Detection, Metadata)
  - Database models and schemas
  - API routes and controllers

- `tests/` - Unit and integration tests
  - Mirrors the src/ structure
  - Pytest test suites
  - Test fixtures and mocks

- `config/` - Configuration files
  - Environment-specific configs
  - Database connection settings
  - AWS service configurations

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy (PostgreSQL ORM)
- Pytest
- AWS SDK (boto3)

## Running Locally

See root README.md for setup instructions.
