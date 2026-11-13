"""Phase 9: candidate application tracking.

The tracking view is a read projection over the ``JobApplication`` row and its
immutable ``ApplicationStatusHistory`` trail. The tests assert the four
properties that make it trustworthy:

1. **Progress is real, not predicted.** A stage is reported as reached only when
   a history row exists for it, and a status the application never held is never
   listed.
2. **Access is ownership-only and non-probing.** Another candidate's id returns
   the identical 404 as a non-existent id, so ids cannot be enumerated.
3. **The allowlist holds.** No internal note, no recruiter identity, no
   free-text reason, no history comment or metadata, no screening error text and
   no score/ranking/fairness field reaches the candidate.
4. **The tracking view agrees with the decision view.** The decision block and
   the timeline wording come from the one reviewed projection, so the two
   surfaces cannot tell a candidate two different stories.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.domain.enums import ApplicationStatus, ScreeningStatus
from app.domain.models import (
    ApplicationStatusHistory,
    Job,
    JobApplication,
    User,
)
from app.repositories.user import UserRepository

TRACK_PATH = "/api/v1/candidate/jobs/applications/{application_id}"
BATCH_DECISIONS_PATH = "/api/v1/candidate/jobs/applications/decisions"
LIST_PATH = "/api/v1/candidate/jobs/applications"

SECRET_INTERNAL_NOTE = "SECRET_INTERNAL_NOTE_do_not_leak"
SECRET_REASON_TEXT = "SECRET_REASON_TEXT_do_not_leak"


async def _register(client: AsyncClient, full_name: str, email: str):
    """Register a candidate and return (auth headers, user id)."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"full_name": full_name, "email": email, "password": "SecureP@ss123"},
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user_id


async def _register_recruiter(client: AsyncClient, session, email: str):
    """Register a recruiter without the default candidate role."""
    headers, user_id = await _register(client, "Dana Recruiter", email)
    repository = UserRepository(session)
    role = await repository.find_role_by_name("recruiter")
    assert role is not None
    await repository.assign_role(user_id, role.id)
    candidate_role = await repository.find_role_by_name("candidate")
    if candidate_role is not None:
        await repository.remove_role(user_id, candidate_role.id)
    await session.commit()
    session.expire_all()
    return headers, user_id


async def _create_job(client: AsyncClient, headers: dict[str, str], title: str) -> uuid.UUID:
    response = await client.post(
        "/api/v1/recruiter/jobs",
        json={
            "title": title,
            "company": "Northwind",
            "employment_type": "full_time",
            "location": "Remote",
            "description": "Tracking test",
            "required_skills": ["Python"],
            "status": "published",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


async def _apply(client: AsyncClient, headers: dict[str, str], job_id: uuid.UUID) -> uuid.UUID:
    response = await client.post(
        "/api/v1/candidate/jobs/apply",
        json={"job_id": str(job_id)},
        headers=headers,
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


async def _set_status(
    client: AsyncClient,
    recruiter_headers: dict[str, str],
    application_id: uuid.UUID,
    status: str,
) -> None:
    """Move an application through the existing generic staff status endpoint."""
    response = await client.patch(
        f"/api/v1/recruiter/jobs/applications/{application_id}/status",
        json={"status": status},
        headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text


async def _decide(
    client: AsyncClient,
    recruiter_headers: dict[str, str],
    application_id: uuid.UUID,
    decision: str,
    *,
    rejection_reason: str | None = None,
    internal_note: str | None = None,
):
    payload: dict = {"decision": decision}
    if rejection_reason is not None:
        payload["rejection_reason"] = rejection_reason
    if internal_note is not None:
        payload["internal_note"] = internal_note
    response = await client.post(
        f"/api/v1/recruiter/jobs/applications/{application_id}/decision",
        json=payload,
        headers=recruiter_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_no_internal_leakage(body: dict) -> None:
    """The serialized response must not carry any staff-only field."""
    forbidden = {
        "internal_note",
        "decision_comment",
        "decided_by",
        "changed_by",
        "changed_by_name",
        "comment",
        "metadata",
        "metadata_json",
        "screening_error",
        "overall_match_score",
        "recommendation",
        "rank",
        "ranking",
        "fairness",
        "protected_attributes",
    }
    assert forbidden.isdisjoint(body.keys())
    assert forbidden.isdisjoint(body["decision"].keys())
    for event in body["timeline"]:
        assert forbidden.isdisjoint(event.keys())
    for stage in body["stages"]:
        assert forbidden.isdisjoint(stage.keys())


@pytest.mark.asyncio
async def test_tracks_a_freshly_applied_application(client: AsyncClient, session):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track1@example.com",
    )
    candidate_headers, candidate_id = await _register(
        client, "Casey Candidate", "candidate.track1@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    response = await client.get(
        TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application_id"] == str(application_id)
    assert body["job_id"] == str(job_id)
    assert body["job_title"] == "Backend Engineer"
    assert body["company"] == "Northwind"
    assert body["status"] == ApplicationStatus.APPLIED.value
    assert body["status_label"] == "Applied"
    assert body["is_decision_final"] is False
    assert body["can_withdraw"] is True
    assert body["applied_at"] is not None
    _assert_no_internal_leakage(body)


@pytest.mark.asyncio
async def test_stages_reflect_only_statuses_actually_recorded(
    client: AsyncClient, session,
):
    """A shortlist without a prior review row must not show review as passed."""
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track2@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Robin Candidate", "candidate.track2@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Platform Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    await _decide(client, recruiter_headers, application_id, "shortlist")

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    stage_statuses = [stage["status"] for stage in body["stages"]]
    assert stage_statuses == [
        ApplicationStatus.APPLIED.value,
        ApplicationStatus.SHORTLISTED.value,
    ]
    # Nothing past the shortlist is claimed, because no row records it.
    assert ApplicationStatus.INTERVIEW_SCHEDULED.value not in stage_statuses
    assert ApplicationStatus.OFFERED.value not in stage_statuses
    assert ApplicationStatus.HIRED.value not in stage_statuses
    assert [stage["is_current"] for stage in body["stages"]] == [False, True]
    assert [stage["reached"] for stage in body["stages"]] == [True, True]


@pytest.mark.asyncio
async def test_timeline_is_the_real_history_in_order(client: AsyncClient, session):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track3@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Jordan Candidate", "candidate.track3@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Data Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    await _set_status(
        client, recruiter_headers, application_id, ApplicationStatus.UNDER_REVIEW.value,
    )
    await _decide(client, recruiter_headers, application_id, "keep_under_review")
    await _decide(client, recruiter_headers, application_id, "shortlist")

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    timeline = body["timeline"]
    assert [event["status"] for event in timeline] == [
        ApplicationStatus.APPLIED.value,
        ApplicationStatus.UNDER_REVIEW.value,
        ApplicationStatus.UNDER_REVIEW.value,
        ApplicationStatus.SHORTLISTED.value,
    ]
    # The repeated status is the deliberate "keep under review" record.
    assert body["status_changed"] is True
    assert timeline[-1]["is_current"] is True
    assert timeline[0]["from_status"] is None
    assert timeline[1]["from_status"] == ApplicationStatus.APPLIED.value
    # The no-transition record carries the same status on both sides.
    assert timeline[2]["from_status"] == ApplicationStatus.UNDER_REVIEW.value
    assert timeline[2]["status"] == timeline[2]["from_status"]
    assert body["last_status_change_at"] is not None


@pytest.mark.asyncio
async def test_keep_under_review_reports_no_status_change(client: AsyncClient, session):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track4@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Sam Candidate", "candidate.track4@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Site Reliability Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    await _set_status(
        client, recruiter_headers, application_id, ApplicationStatus.UNDER_REVIEW.value,
    )
    await _decide(client, recruiter_headers, application_id, "keep_under_review")

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    assert body["status"] == ApplicationStatus.UNDER_REVIEW.value
    assert body["status_changed"] is False
    # A stage the application is in is still reported as reached.
    assert ApplicationStatus.UNDER_REVIEW.value in [
        stage["status"] for stage in body["stages"] if stage["reached"]
    ]


@pytest.mark.asyncio
async def test_rejection_is_a_terminal_stage_not_a_progress_step(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track5@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Alex Candidate", "candidate.track5@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Security Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    await _decide(
        client, recruiter_headers, application_id, "reject",
        rejection_reason="low_job_match", internal_note=SECRET_INTERNAL_NOTE,
    )

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    assert body["status"] == ApplicationStatus.REJECTED.value
    # The stored status stays truthful; only the label is softened.
    assert body["status_label"] == "Not Selected"
    assert body["is_decision_final"] is True
    assert body["can_withdraw"] is False
    assert body["stages"][-1]["status"] == ApplicationStatus.REJECTED.value
    assert body["stages"][-1]["is_current"] is True
    # No offer or hire step is projected onto a rejected application.
    assert ApplicationStatus.OFFERED.value not in [
        stage["status"] for stage in body["stages"]
    ]
    _assert_no_internal_leakage(body)
    assert SECRET_INTERNAL_NOTE not in str(body)


@pytest.mark.asyncio
async def test_withdrawal_is_terminal_and_cannot_be_withdrawn_again(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track6@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Taylor Candidate", "candidate.track6@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Mobile Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    withdrawn = await client.post(
        f"/api/v1/candidate/jobs/applications/{application_id}/withdraw",
        headers=candidate_headers,
    )
    assert withdrawn.status_code == 200

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    assert body["status"] == ApplicationStatus.WITHDRAWN.value
    assert body["can_withdraw"] is False
    assert body["is_decision_final"] is True
    assert body["stages"][-1]["status"] == ApplicationStatus.WITHDRAWN.value


@pytest.mark.asyncio
async def test_tracking_and_decision_views_agree_on_candidate_wording(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track7@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Jamie Candidate", "candidate.track7@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "ML Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    await _decide(
        client, recruiter_headers, application_id, "reject",
        rejection_reason="missing_required_skill",
        internal_note=SECRET_INTERNAL_NOTE,
    )

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()
    decision = (
        await client.get(
            f"/api/v1/candidate/jobs/applications/{application_id}/decision",
            headers=candidate_headers,
        )
    ).json()

    assert body["decision"]["candidate_message"] == decision["candidate_message"]
    assert body["decision"]["status_label"] == decision["status_label"]
    assert body["decision"]["is_decision_final"] is decision["is_decision_final"]
    # The same approved wording rides on the rejection timeline event.
    rejection_event = body["timeline"][-1]
    assert rejection_event["message"] == decision["candidate_message"]


@pytest.mark.asyncio
async def test_another_candidates_application_is_indistinguishable_from_missing(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track8@example.com",
    )
    owner_headers, _ = await _register(
        client, "Owner Candidate", "candidate.owner8@example.com",
    )
    other_headers, _ = await _register(
        client, "Other Candidate", "candidate.other8@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    application_id = await _apply(client, owner_headers, job_id)

    forbidden = await client.get(
        TRACK_PATH.format(application_id=application_id), headers=other_headers,
    )
    missing = await client.get(
        TRACK_PATH.format(application_id=uuid.uuid4()), headers=other_headers,
    )

    assert forbidden.status_code == 404
    assert missing.status_code == 404
    # The bodies differ only by the per-request trace id, so the parts a client
    # could learn from are compared explicitly.
    assert forbidden.json()["error"]["code"] == missing.json()["error"]["code"]
    assert forbidden.json()["error"]["message"] == missing.json()["error"]["message"]
    assert forbidden.json()["error"]["message"] == "Application not found"


@pytest.mark.asyncio
async def test_candidate_list_only_contains_the_callers_applications(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track9@example.com",
    )
    owner_headers, _ = await _register(
        client, "List Owner", "candidate.owner9@example.com",
    )
    other_headers, _ = await _register(
        client, "List Other", "candidate.other9@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    owner_application = await _apply(client, owner_headers, job_id)
    other_application = await _apply(client, other_headers, job_id)

    body = (
        await client.get(LIST_PATH, headers=owner_headers)
    ).json()
    ids = {item["id"] for item in body}

    assert ids == {str(owner_application)}
    assert str(other_application) not in ids


@pytest.mark.asyncio
async def test_staff_cannot_read_the_candidate_tracking_view(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track10@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Guarded Candidate", "candidate.guarded10@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    response = await client.get(
        TRACK_PATH.format(application_id=application_id), headers=recruiter_headers,
    )

    # The candidate projection is not a staff surface: the recruiter view is the
    # separate, deliberately different explainability/decision endpoint set.
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_match_explanation_flag_follows_screening_state(
    client: AsyncClient, session,
):
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track11@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Screened Candidate", "candidate.screened11@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    application = await session.get(JobApplication, application_id)
    application.screening_status = ScreeningStatus.FAILED.value
    application.screening_error = "SECRET_SCREENING_ERROR_internal detail"
    await session.commit()

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    assert body["screening_status"] == ScreeningStatus.FAILED.value
    assert body["has_match_explanation"] is False
    _assert_no_internal_leakage(body)
    assert "SECRET_SCREENING_ERROR" not in str(body)

    application.screening_status = ScreeningStatus.COMPLETED.value
    await session.commit()
    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()
    assert body["has_match_explanation"] is True


@pytest.mark.asyncio
async def test_application_survives_a_deleted_job(client: AsyncClient, session):
    """A candidate must still see their own application after the job is gone."""
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track12@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Orphan Candidate", "candidate.orphan12@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Ephemeral Role")
    application_id = await _apply(client, candidate_headers, job_id)

    # Re-point the application at a job row that does not resolve, the state a
    # candidate is left in when the posting is removed out from under them.
    application = await session.get(JobApplication, application_id)
    application.job_id = uuid.uuid4()
    application.status = ApplicationStatus.UNDER_REVIEW.value
    await session.commit()
    session.expire_all()
    assert await session.get(Job, job_id) is not None

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    assert body["application_id"] == str(application_id)
    assert body["job_title"] == ""
    assert body["company"] == ""
    assert body["status"] == ApplicationStatus.UNDER_REVIEW.value
    # The decision projection still answers for a job that no longer exists.
    assert body["decision"]["job_title"] == ""


@pytest.mark.asyncio
async def test_batch_decisions_route_is_not_shadowed_by_the_detail_route(
    client: AsyncClient, session,
):
    """The bare ``/applications/{id}`` route must not capture ``decisions``."""
    candidate_headers, _ = await _register(
        client, "Route Candidate", "candidate.route13@example.com",
    )

    batch = await client.get(BATCH_DECISIONS_PATH, headers=candidate_headers)
    assert batch.status_code == 200, batch.text
    assert batch.json() == []


@pytest.mark.asyncio
async def test_history_metadata_and_comments_never_reach_the_candidate(
    client: AsyncClient, session,
):
    """Free-text staff prose recorded in history stays out of the timeline."""
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track14@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Prose Candidate", "candidate.prose14@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    await _decide(
        client, recruiter_headers, application_id, "shortlist",
        internal_note=SECRET_INTERNAL_NOTE,
    )
    # Write staff-only prose straight into the history row the way a legacy or
    # simulation path would.
    history = (
        await session.execute(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == application_id,
            )
        )
    ).scalars().all()
    history[-1].comment = SECRET_INTERNAL_NOTE
    history[-1].reason = SECRET_REASON_TEXT
    history[-1].metadata_json = {"decision": "shortlist", "internal": SECRET_REASON_TEXT}
    await session.commit()

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    _assert_no_internal_leakage(body)
    serialized = str(body)
    assert SECRET_INTERNAL_NOTE not in serialized
    assert SECRET_REASON_TEXT not in serialized


@pytest.mark.asyncio
async def test_unrecognized_history_status_is_skipped_not_guessed(
    client: AsyncClient, session,
):
    """A status this build does not know about is dropped, not invented."""
    recruiter_headers, _ = await _register_recruiter(
        client, session, "recruiter.track15@example.com",
    )
    candidate_headers, _ = await _register(
        client, "Legacy Candidate", "candidate.legacy15@example.com",
    )
    job_id = await _create_job(client, recruiter_headers, "Backend Engineer")
    application_id = await _apply(client, candidate_headers, job_id)

    session.add(ApplicationStatusHistory(
        application_id=application_id,
        organization_id=None,
        from_status=ApplicationStatus.APPLIED.value,
        to_status="teleported",
        changed_by=None,
    ))
    await session.commit()

    body = (
        await client.get(
            TRACK_PATH.format(application_id=application_id), headers=candidate_headers,
        )
    ).json()

    assert [event["status"] for event in body["timeline"]] == [
        ApplicationStatus.APPLIED.value,
    ]
    assert "teleported" not in str(body)
    assert body["status"] == ApplicationStatus.APPLIED.value
