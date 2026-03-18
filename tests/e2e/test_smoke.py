"""Playwright smoke tests for sentyacht.es public surface.

Run:  python -m pytest tests/e2e/test_smoke.py -v
Env:  SMOKE_BASE_URL (default: https://sentyacht.es)

Requires: pip install playwright pytest-playwright && python -m playwright install chromium
"""

import os
import uuid

import pytest
from playwright.sync_api import Page, expect

BASE = os.getenv("SMOKE_BASE_URL", "https://sentyacht.es")


# --- Page loads ---


def test_home_loads(page: Page):
    resp = page.goto(BASE + "/", wait_until="domcontentloaded")
    assert resp.status == 200


def test_home_es_loads(page: Page):
    page.goto(BASE + "/es/", wait_until="domcontentloaded")
    expect(page.locator("body")).to_contain_text("SentYacht")


def test_landing_loads(page: Page):
    page.goto(BASE + "/es/vender-mi-barco/", wait_until="domcontentloaded")
    expect(page.locator("#lead-form")).to_be_visible()


# --- Form submission ---


def _fill_and_submit(page: Page, name: str, email: str):
    """Fill the minimum required fields and submit the lead form."""
    page.locator("#lead-form").scroll_into_view_if_needed()
    page.fill("#nombre", name)
    page.fill("#email", email)
    page.locator("#privacidad").check()
    page.click("#submit-btn")


def test_form_submit_new_lead(page: Page):
    page.goto(BASE + "/es/vender-mi-barco/", wait_until="networkidle")
    unique_email = f"smoke-{uuid.uuid4().hex[:8]}@test.com"

    _fill_and_submit(page, "Smoke Test", unique_email)

    expect(page.locator("#form-success")).to_be_visible(timeout=10000)
    expect(page.locator("#form-error")).to_be_hidden()


def test_form_submit_duplicate_shows_success(page: Page):
    page.goto(BASE + "/es/vender-mi-barco/", wait_until="networkidle")
    fixed_email = "smoke-duplicate-test@test.com"

    # First submit
    _fill_and_submit(page, "Smoke Dup", fixed_email)
    expect(page.locator("#form-success")).to_be_visible(timeout=10000)

    # Reload and submit same email again
    page.goto(BASE + "/es/vender-mi-barco/", wait_until="networkidle")
    _fill_and_submit(page, "Smoke Dup Again", fixed_email)

    # Should still show success, not error
    expect(page.locator("#form-success")).to_be_visible(timeout=10000)
    expect(page.locator("#form-error")).to_be_hidden()


# --- Security surface ---


def test_api_health_blocked(page: Page):
    resp = page.request.get(BASE + "/api/health")
    assert resp.status == 403


def test_api_leads_blocked(page: Page):
    resp = page.request.get(BASE + "/api/leads")
    assert resp.status == 403
