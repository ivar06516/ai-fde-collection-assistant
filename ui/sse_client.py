"""SSE stream consumer using httpx for Streamlit -> FastAPI communication."""
import json
from typing import Generator, Optional

import httpx

from collection_assistant.config import get_settings


def stream_workflow_events(workflow_id: str, timeout: int = 90) -> Generator[dict, None, None]:
    """Yields SSE event dicts as they arrive from the FastAPI backend."""
    settings = get_settings()
    url = f"{settings.streamlit_api_url}/collections/{workflow_id}/stream"
    with httpx.Client(timeout=timeout) as client:
        with client.stream("GET", url) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    payload = line[6:].strip()
                    if payload:
                        try:
                            yield json.loads(payload)
                        except json.JSONDecodeError:
                            pass


def trigger_pipeline(customer_id: str, account_id: str,
                      trigger_context: str = "routine_review") -> Optional[str]:
    """POST /collections/recommend - returns workflow_id."""
    settings = get_settings()
    url = f"{settings.streamlit_api_url}/collections/recommend"
    try:
        resp = httpx.post(url, json={
            "customer_id": customer_id,
            "account_id": account_id,
            "trigger_context": trigger_context,
        }, timeout=10)
        resp.raise_for_status()
        return resp.json()["workflow_id"]
    except Exception as e:
        raise RuntimeError(f"Failed to trigger pipeline: {e}") from e


def get_workflow_state(workflow_id: str) -> Optional[dict]:
    settings = get_settings()
    url = f"{settings.streamlit_api_url}/collections/{workflow_id}/state"
    try:
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_customers() -> list[dict]:
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.streamlit_api_url}/collections/data/customers", timeout=5)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def fetch_accounts() -> list[dict]:
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.streamlit_api_url}/collections/data/accounts", timeout=5)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def fetch_portfolio() -> list[dict]:
    """Fetch all customers with full account + hold data for the dashboard table."""
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.streamlit_api_url}/collections/data/portfolio", timeout=10)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def fetch_customer_detail(customer_id: str) -> dict | None:
    """Fetch full customer detail for Page 3 — profile view."""
    settings = get_settings()
    try:
        resp = httpx.get(
            f"{settings.streamlit_api_url}/collections/data/customer/{customer_id}",
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def fetch_last_run(customer_id: str) -> dict | None:
    """Return the most recent completed analysis run for a customer."""
    settings = get_settings()
    try:
        resp = httpx.get(
            f"{settings.streamlit_api_url}/collections/data/customer/{customer_id}/last-run",
            timeout=8,
        )
        data = resp.json() if resp.status_code == 200 else {}
        return data if data else None
    except Exception:
        return None


def fetch_customer_runs(customer_id: str) -> list[dict]:
    """Return all completed runs for a customer, newest first (max 10)."""
    settings = get_settings()
    try:
        resp = httpx.get(
            f"{settings.streamlit_api_url}/collections/data/customer/{customer_id}/runs",
            timeout=8,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []
