"""Pytest configuration and shared fixtures"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """FastAPI test client fixture"""
    return TestClient(app)


@pytest.fixture
def test_data():
    """Sample test data fixture"""
    return {
        "test_user": {"username": "testuser", "email": "test@example.com"},
        "test_photo": {"filename": "test.jpg", "size": 1024},
    }
