"""Integration tests - FastAPI endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from collection_assistant.api.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_recommend_404_unknown_customer():
    """AC-002-05: POST /recommend returns 404 immediately for unknown customer_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/collections/recommend", json={
            "customer_id": "CUST-INVALID",
            "account_id": "ACC-001",
            "trigger_context": "routine_review",
        })
    assert response.status_code == 404
    assert "CUST-INVALID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_recommend_404_unknown_account():
    """AC-002-05 (account variant): POST /recommend returns 404 for unknown account_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/collections/recommend", json={
            "customer_id": "CUST-001",
            "account_id": "ACC-INVALID",
            "trigger_context": "routine_review",
        })
    assert response.status_code == 404
    assert "ACC-INVALID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_recommend_202_valid_input():
    """POST /recommend returns 202 with workflow_id for valid customer + account."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/collections/recommend", json={
            "customer_id": "CUST-001",
            "account_id": "ACC-001",
            "trigger_context": "routine_review",
        })
    assert response.status_code == 202
    body = response.json()
    assert "workflow_id" in body
    assert body["workflow_id"].startswith("wf-")
    assert body["status"] == "in_progress"
