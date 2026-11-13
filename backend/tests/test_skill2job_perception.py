"""Phase 2 Skill2Job Perception Agent tests.

Covers:
- provider-aware capability status (voice/image honestly unconfigured here)
- free-text perception -> deterministic structured extraction with provenance
- document perception via shared resume intelligence engine
- strict input validation (extension / empty text)
- graceful failure for voice/image inputs without a provider (never fabricated)
- perception history listing
- candidate-only authorization
"""

import pytest
from httpx import AsyncClient


def _headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _register_and_login(client: AsyncClient, email: str, password: str = "SecureP@ss123") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Perception Candidate", "email": email, "password": password},
    )
    assert resp.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()


RESUME_TEXT = b"""Alex Rivera
Bengaluru, India | alex.rivera@example.com

SUMMARY
Backend engineer with 4 years of experience building Python APIs and data pipelines.

SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS, Celery, Redis, Pytest, Git

EXPERIENCE
Backend Engineer, FinTech Labs, Remote
Jan 2022 - Present
Built REST APIs with FastAPI and PostgreSQL. Implemented async background
jobs with Celery and Redis. Containerized services with Docker on AWS.

Software Developer, CloudSoft, Remote
Jun 2020 - Dec 2021
Built Django web applications and MySQL databases.

EDUCATION
B.Tech Computer Science, Pune University, 2016 - 2020

CERTIFICATIONS
AWS Certified Developer

LANGUAGES
English, Hindi
"""


@pytest.mark.asyncio
async def test_perception_status_candidate(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_status@test.com")
    resp = await client.get("/api/v1/skill2job/perception/status", headers=_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert body["document"]["configured"] is True
    assert body["free_text"]["configured"] is True
    assert body["voice"]["configured"] is False
    assert body["voice"]["providers"] == []
    # Image OCR may be configured (pytesseract installed) or not — check honestly
    assert isinstance(body["image"]["configured"], bool)


@pytest.mark.asyncio
async def test_perception_status_requires_candidate(client: AsyncClient, _create_user_with_role):
    user, password = await _create_user_with_role(
        "Recruiter Percept", "percept_rec@test.com", "SecureP@ss123", "recruiter"
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": password}
    )
    resp = await client.get(
        "/api/v1/skill2job/perception/status", headers=_headers(login.json())
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_free_text_perception_structured_with_provenance(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_text@test.com")
    payload = (
        "I am a software developer with 4 years of experience. Looking for a "
        "full stack developer role. I know Python, FastAPI, PostgreSQL, Docker "
        "and AWS. Based in Bengaluru."
    )
    resp = await client.post(
        "/api/v1/skill2job/perception/text",
        data={"text": payload},
        headers=_headers(tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    result = body["result"]
    assert body["perception_id"]
    assert result["input_type"] == "free_text"
    assert result["processing_status"] == "ok"

    names = {s["name"].lower() for s in result["skills"]}
    assert "python" in names
    assert "fastapi" in names
    assert "postgresql" in names
    assert "docker" in names
    assert "aws" in names
    assert "c#" not in names and "c++" not in names  # no fabricated skills

    assert any(p["source"] == "free_text" for p in result["provenance"])
    assert 0.0 <= result["field_confidence"] <= 1.0
    assert result["skills"], "skills must be extracted"


@pytest.mark.asyncio
async def test_free_text_target_role_and_location_extraction(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_text2@test.com")
    payload = "Currently in Pune. Seeking a data scientist position. I enjoy machine learning."
    resp = await client.post(
        "/api/v1/skill2job/perception/text",
        data={"text": payload},
        headers=_headers(tokens),
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["target_roles"] == ["Data Scientist"]
    assert result["location"] == "Pune"


@pytest.mark.asyncio
async def test_free_text_empty_rejected(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_empty@test.com")
    resp = await client.post(
        "/api/v1/skill2job/perception/text",
        data={"text": "   "},
        headers=_headers(tokens),
    )
    assert resp.status_code == 422
    assert "No text" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_document_perception_reuses_resume_engine(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_doc@test.com")
    resp = await client.post(
        "/api/v1/skill2job/perception/upload",
        files={"file": ("resume.txt", RESUME_TEXT, "text/plain")},
        headers=_headers(tokens),
    )
    assert resp.status_code == 200
    body = resp.json()
    result = body["result"]
    assert result["input_type"] == "document"
    assert result["processing_status"] == "ok"

    names = {s["name"].lower() for s in result["skills"]}
    for expected in ("python", "fastapi", "postgresql", "docker", "aws", "celery", "redis"):
        assert expected in names

    assert len(result["experience"]) >= 1, "at least one role should be parsed"
    first = result["experience"][0]
    assert first["company"] in {"FinTech Labs", "CloudSoft"}
    assert result["summary"]
    assert result["extracted_text"]
    # provenance is grounded in the resume sections
    assert any(p["source"] == "document" for p in result["provenance"])


@pytest.mark.asyncio
async def test_document_perception_unsupported_extension_rejected(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_badext@test.com")
    resp = await client.post(
        "/api/v1/skill2job/perception/upload",
        files={"file": ("notes.exe", b"MZ", "application/octet-stream")},
        headers=_headers(tokens),
    )
    assert resp.status_code == 422
    assert "Unsupported file type" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_voice_without_provider_fails_gracefully(client: AsyncClient, monkeypatch):
    from app.skill2job.perception import pipeline

    monkeypatch.setattr(pipeline.SpeechTranscriber, "is_configured", staticmethod(lambda: False))
    tokens = await _register_and_login(client, "percept_voice@test.com")
    resp = await client.post(
        "/api/v1/skill2job/perception/upload",
        files={"file": ("notes.mp3", b"\xff\xe3dummy", "audio/mpeg")},
        headers=_headers(tokens),
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["processing_status"] == "failed"
    assert "not configured" in result["processing_message"].lower()
    assert result["skills"] == []  # nothing fabricated


@pytest.mark.asyncio
async def test_image_without_provider_fails_gracefully(client: AsyncClient, monkeypatch):
    from app.skill2job.perception import pipeline

    monkeypatch.setattr(pipeline.OcrAdapter, "is_configured", staticmethod(lambda: False))
    tokens = await _register_and_login(client, "percept_img@test.com")
    resp = await client.post(
        "/api/v1/skill2job/perception/upload",
        files={"file": ("scan.png", b"\x89PNG\r\n\x1a\ndummy", "image/png")},
        headers=_headers(tokens),
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["processing_status"] == "failed"
    assert "ocr" in result["processing_message"].lower()


@pytest.mark.asyncio
async def test_perception_history_lists_user_inputs(client: AsyncClient):
    tokens = await _register_and_login(client, "percept_hist@test.com")
    headers = _headers(tokens)
    await client.post(
        "/api/v1/skill2job/perception/text",
        data={"text": "I know Python and FastAPI."},
        headers=headers,
    )
    resp = await client.get("/api/v1/skill2job/perception", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["input_type"] == "free_text"
    assert body["items"][0]["processing_status"] == "ok"


def test_free_text_parser_conservative():
    from app.skill2job.perception.free_text import FreeTextParser

    assert FreeTextParser.extract_target_roles(
        "Looking for a data engineer role"
    ) == ["Data Engineer"]
    assert FreeTextParser.extract_target_roles("I love Python") == []
    assert FreeTextParser.extract_location("Based in New York City") == "New York City"
    assert FreeTextParser.extract_location("no location hint here") is None
    assert FreeTextParser.extract_experience_years("5+ years of experience") == 5

    from app.skill2job.perception.schemas import PerceptionResult

    result = PerceptionResult(input_type="x", parser_version="test", skills=[], experience=[])
    from app.skill2job.perception.document import PerceptionConfidence

    assert PerceptionConfidence.score(result) == 0.0