import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.main import app
from app.modules.projects.onboarding import next_questions, onboarding_status
from app.modules.projects.router import project_response


def snapshot(**overrides):
    values = {
        "id": uuid.uuid4(),
        "project_type": "idea",
        "display_name": "Projet",
        "visibility": "private",
        "raw_description": "Idea project",
        "user_goal": None,
        "current_progress": None,
        "country_code": "FR",
        "target_market": None,
        "language": "fr",
        "owner_user_id": uuid.uuid4(),
        "activity": None,
        "sector": None,
        "technology": None,
        "data_context": None,
        "location": None,
        "onboarding_status": "in_progress",
        "confirmed_fields": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_idea_project_public_projection_does_not_expose_private_fields():
    response = project_response(snapshot(visibility="public"), None)
    assert response.is_member is False
    assert response.raw_description is None
    assert response.activity is None


def test_start_requires_activity_and_does_not_generate_business_coaching():
    questions = next_questions(snapshot())
    assert [item.field for item in questions] == ["activity", "sector", "market", "location"]
    assert all("competitive" not in item.question.lower() for item in questions)
    assert all("growth" not in item.question.lower() for item in questions)


def test_confirmed_activity_sector_market_location_survive_resume_and_are_not_reasked():
    project = snapshot(
        activity="Restaurant",
        sector="Restauration",
        target_market="France",
        location="Lyon",
        confirmed_fields={"activity": "confirmed", "sector": "confirmed", "market": "confirmed", "location": "confirmed"},
    )
    assert onboarding_status(project) == "complete"
    assert next_questions(project) == []


def test_technology_and_data_are_relevant_only_when_context_requires_them():
    digital = snapshot(activity="Plateforme web de réservation", sector="services")
    fields = [item.field for item in next_questions(digital)]
    assert "technology" in fields
    assert "data" not in fields

    data_project = snapshot(activity="Application qui collecte les données clients", sector="logiciel")
    fields = [item.field for item in next_questions(data_project)]
    assert "technology" in fields
    assert "data" in fields


def test_confirmed_field_is_not_reasked_while_unrelated_fields_remain():
    project = snapshot(activity="Application web", confirmed_fields={"activity": "confirmed"})
    fields = [item.field for item in next_questions(project)]
    assert "activity" not in fields
    assert "sector" in fields


@pytest.mark.asyncio
async def test_idea_creation_requires_authentication():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/projects/ideas", json={"display_name": "Projet"})
    assert response.status_code == 401
