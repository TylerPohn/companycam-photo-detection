# Contributing to CompanyCam Photo Detection

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Development Workflow

### 1. Set Up Your Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd companycam-photo-detection

# Set up environment
cp .env.example .env

# Install dependencies
cd backend && pip install -r requirements-dev.txt
cd ../frontend && npm install

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### 2. Create a Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name

# or for bug fixes
git checkout -b fix/bug-description
```

### 3. Make Your Changes

- Write clean, maintainable code
- Follow the project's coding standards
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 4. Commit Your Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature: description of your changes"
```

**Commit Message Format:**

```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Build process or auxiliary tool changes

**Example:**

```
feat: Add photo upload validation

- Implement file size validation
- Add MIME type checking
- Update error handling for invalid uploads

Closes #123
```

### 5. Push and Create Pull Request

```bash
# Push to your branch
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## Code Standards

### Python (Backend)

- **Style Guide**: PEP 8
- **Formatter**: Black (line length: 100)
- **Linter**: Flake8
- **Type Hints**: Use type annotations
- **Docstrings**: Google-style docstrings

**Example:**

```python
from typing import Optional

def process_photo(
    photo_id: str,
    user_id: str,
    metadata: Optional[dict] = None
) -> dict:
    """Process a photo and extract metadata.

    Args:
        photo_id: Unique identifier for the photo
        user_id: ID of the user who uploaded the photo
        metadata: Optional metadata to associate with photo

    Returns:
        Dictionary containing processed photo data

    Raises:
        ValueError: If photo_id is invalid
    """
    # Implementation
    pass
```

### TypeScript/JavaScript (Frontend)

- **Style Guide**: ESLint configuration
- **Formatter**: Prettier
- **Naming**: camelCase for variables, PascalCase for components
- **Components**: Functional components with hooks

**Example:**

```typescript
interface PhotoProps {
  photoId: string;
  onLoad?: () => void;
}

const PhotoCard: React.FC<PhotoProps> = ({ photoId, onLoad }) => {
  // Implementation
  return <div>{/* Component JSX */}</div>;
};
```

## Testing Requirements

### Backend Tests

- **Minimum Coverage**: 80%
- **Test Location**: Mirror source structure in `tests/`
- **Naming**: `test_*.py`

```python
import pytest
from fastapi.testclient import TestClient

def test_create_photo(client: TestClient):
    """Test photo creation endpoint"""
    response = client.post("/api/photos", json={"url": "test.jpg"})
    assert response.status_code == 201
    assert "photo_id" in response.json()
```

### Frontend Tests

- **Test Files**: `*.test.tsx` or `*.spec.tsx`
- **Coverage**: Aim for >80%

```typescript
import { render, screen } from '@testing-library/react';
import { PhotoCard } from './PhotoCard';

describe('PhotoCard', () => {
  it('renders photo correctly', () => {
    render(<PhotoCard photoId="123" />);
    expect(screen.getByRole('img')).toBeInTheDocument();
  });
});
```

### Running Tests

```bash
# Backend
cd backend
pytest --cov=src --cov-report=term-missing

# Frontend
cd frontend
npm test -- --coverage

# Integration tests
docker-compose up -d
pytest tests/integration/
```

## Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Pre-commit hooks pass
- [ ] No merge conflicts with main

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No new warnings
```

### Review Process

1. **Automated Checks**: CI pipeline must pass
   - Linting
   - Unit tests
   - Build process

2. **Code Review**: At least one approval required
   - Code quality
   - Test coverage
   - Documentation
   - Security considerations

3. **Merge**: Squash and merge to main

## Development Guidelines

### Adding New Endpoints (Backend)

1. Define route in appropriate module
2. Add Pydantic models for request/response
3. Implement business logic in service layer
4. Add unit tests (>80% coverage)
5. Update API documentation
6. Add integration tests

### Adding New Components (Frontend)

1. Create component in appropriate directory
2. Add TypeScript interfaces
3. Implement component with hooks
4. Add unit tests
5. Update Storybook (if applicable)
6. Document props and usage

### Database Migrations

```bash
# Create migration
cd backend
alembic revision --autogenerate -m "Description of changes"

# Review generated migration
# Edit migration file if needed

# Apply migration
alembic upgrade head

# Test rollback
alembic downgrade -1
alembic upgrade head
```

### Adding Dependencies

**Backend:**

```bash
# Add to requirements.txt
pip install package-name
pip freeze | grep package-name >> requirements.txt

# Update development dependencies
echo "package-name==version" >> requirements-dev.txt
```

**Frontend:**

```bash
# Production dependency
npm install --save package-name

# Development dependency
npm install --save-dev package-name
```

## Code Review Guidelines

### As a Reviewer

- Be constructive and respectful
- Explain the "why" behind suggestions
- Approve when changes meet standards
- Request changes for significant issues
- Comment for minor suggestions

### As an Author

- Respond to all comments
- Be open to feedback
- Make requested changes promptly
- Ask for clarification if needed
- Update PR description if scope changes

## Git Branch Strategy

- `main`: Production-ready code
- `staging`: Pre-production testing
- `feature/*`: New features
- `fix/*`: Bug fixes
- `hotfix/*`: Urgent production fixes

## Environment-Specific Testing

### Local Development

```bash
docker-compose up -d
# Test against local services
```

### Staging

```bash
# Deploy to staging
git push origin staging
# Automated tests run in staging environment
```

### Production

- Blue/green deployment
- Manual approval required
- Automated rollback on failure

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Create an issue with bug template
- **Features**: Create an issue with feature request template
- **Security**: See [SECURITY.md](SECURITY.md)

## Recognition

Contributors are recognized in:
- Release notes
- CHANGELOG.md
- Project documentation

Thank you for contributing to CompanyCam Photo Detection!
