"""Pruebas de contrato REST, errores, validaciones y módulo investigador."""

from __future__ import annotations

from app.services.assessment_service import CURRENT_CONSENT_VERSION
from app.services.dataset_service import review_session_quality


def _start_payload(demographics):
    return {
        "demographics": demographics,
        "consent": {
            "version": CURRENT_CONSENT_VERSION,
            "accepted": True,
            "data_authorization": True,
            "assent_accepted": True,
            "guardian_consent_required": True,
            "guardian_consent_reference": "GUARD-TEST-001",
            "collection_method": "institutional",
        },
    }


def test_api_rejects_missing_or_invalid_json(client, db_context):
    response = client.post("/api/assessment/start", data="no-json")
    assert response.status_code == 400
    assert response.get_json()["success"] is False

    response = client.get("/api/assessment")
    assert response.status_code == 400
    assert response.get_json()["data"] is None


def test_api_requires_legal_data_authorization(client, db_context, demographics):
    payload = _start_payload(demographics)
    payload["consent"]["data_authorization"] = False

    response = client.post("/api/assessment/start", json=payload)
    body = response.get_json()

    assert response.status_code == 422
    assert body["success"] is False
    assert "autorización" in body["message"].lower()


def test_start_state_and_questions_endpoints(client, db_context, demographics):
    start = client.post("/api/assessment/start", json=_start_payload(demographics))
    assert start.status_code == 201
    start_body = start.get_json()
    assert start_body["success"] is True
    session_id = start_body["data"]["session_id"]

    state = client.get(f"/api/assessment?session_id={session_id}")
    questions = client.get(f"/api/assessment/questions?session_id={session_id}")

    assert state.status_code == 200
    assert state.get_json()["data"]["progress"]["answered_items"] == 0
    assert questions.status_code == 200
    assert len(questions.get_json()["data"]["questions"]) == 60
    assert all(
        "area" not in question
        for question in questions.get_json()["data"]["questions"]
    )


def test_response_and_autosave_endpoints(client, db_context, demographics):
    start = client.post("/api/assessment/start", json=_start_payload(demographics))
    session_id = start.get_json()["data"]["session_id"]
    question = client.get(
        f"/api/assessment/questions?session_id={session_id}"
    ).get_json()["data"]["questions"][0]

    saved = client.post(
        "/api/assessment/response",
        json={
            "session_id": session_id,
            "item_id": question["id"],
            "response_raw": 4,
            "response_time_ms": 1200,
            "tts_used": True,
        },
    )
    autosave = client.post(
        "/api/assessment/autosave",
        json={
            "session_id": session_id,
            "stage": "onet",
            "current_item_index": 2,
        },
    )

    assert saved.status_code == 200
    assert saved.get_json()["data"]["response_score"] == 3
    assert saved.get_json()["data"]["tts_used"] is True
    assert autosave.status_code == 200
    assert autosave.get_json()["data"]["current_item_index"] == 2



def test_complementary_input_endpoints(client, db_context, demographics):
    start = client.post("/api/assessment/start", json=_start_payload(demographics))
    session_id = start.get_json()["data"]["session_id"]

    interest = client.post(
        "/api/assessment/interest-response",
        json={
            "session_id": session_id,
            "item_code": "G01",
            "response_value": 5,
        },
    )
    subjects = client.post(
        "/api/assessment/subjects",
        json={
            "session_id": session_id,
            "subject_codes": ["matematicas", "tecnologia_informatica"],
        },
    )
    activities = client.post(
        "/api/assessment/activities",
        json={
            "session_id": session_id,
            "activity_codes": ["programacion_tecnologia"],
        },
    )
    open_response = client.post(
        "/api/assessment/open-response",
        json={
            "session_id": session_id,
            "prompt_code": "T01",
            "response_text": "Me interesa aprender tecnología y crear proyectos.",
        },
    )

    assert interest.status_code == 200
    assert interest.get_json()["data"]["item_code"] == "G01"
    assert subjects.status_code == 200
    assert "matematicas" in subjects.get_json()["data"]["subject_codes"]
    assert activities.status_code == 200
    assert "programacion_tecnologia" in activities.get_json()["data"]["activity_codes"]
    assert open_response.status_code == 200
    assert open_response.get_json()["data"]["prompt_code"] == "T01"

def test_complete_and_results_api(client, assessment_builder):
    assessment = assessment_builder(fill=True, finalize=False, onet_raw=4)
    with client.session_transaction() as flask_session:
        flask_session["active_assessment_id"] = str(assessment.id)

    completed = client.post(
        "/api/assessment/complete",
        json={"session_id": str(assessment.id)},
    )
    result = client.get(f"/api/results/{assessment.id}")

    assert completed.status_code == 200
    assert completed.get_json()["data"]["status"] == "completed"
    assert result.status_code == 200
    data = result.get_json()["data"]
    assert data["scores"]["R"] == 30
    assert "interpretation" in data


def test_api_404_is_json(client, db_context):
    response = client.get("/api/ruta-inexistente")
    body = response.get_json()

    assert response.status_code == 404
    assert body == {
        "success": False,
        "data": None,
        "message": "Recurso API no encontrado.",
    }


def test_research_module_requires_login_and_exports_csv(
    client,
    assessment_builder,
):
    assessment = assessment_builder(fill=True, finalize=True, onet_raw=4)
    review_session_quality(
        assessment,
        quality_status="valid",
        included_ml=True,
        dataset_version="RIASEC_TEST_V1",
    )

    protected = client.get("/investigacion", follow_redirects=False)
    assert protected.status_code == 302
    assert "/investigacion/login" in protected.headers["Location"]

    client.get("/investigacion/login")
    with client.session_transaction() as flask_session:
        csrf_token = flask_session["research_csrf_token"]

    login = client.post(
        "/investigacion/login",
        data={
            "csrf_token": csrf_token,
            "username": "investigador",
            "password": "ClavePrueba123!",
        },
        follow_redirects=True,
    )
    assert login.status_code == 200
    assert b"Panel de investigaci" in login.data

    exported = client.get("/investigacion/datasets/export/ml/csv")
    assert exported.status_code == 200
    assert exported.mimetype == "text/csv"
    assert b"participant_code" in exported.data
    assert b"score_r" in exported.data

    from sqlalchemy import select

    from app.extensions import db
    from app.models import ResearchAuditEvent

    events = db.session.execute(
        select(ResearchAuditEvent).where(
            ResearchAuditEvent.action == "dataset_export"
        )
    ).scalars().all()
    assert any(event.resource_id == "ml" for event in events)



def test_assessment_uuid_alone_does_not_grant_access(
    app,
    client,
    db_context,
    demographics,
):
    start = client.post("/api/assessment/start", json=_start_payload(demographics))
    assert start.status_code == 201
    data = start.get_json()["data"]
    session_id = data["session_id"]
    access_token = data["access_token"]

    stranger = app.test_client()
    denied = stranger.get(f"/api/assessment?session_id={session_id}")
    allowed = stranger.get(
        f"/api/assessment?session_id={session_id}",
        headers={data["access_header"]: access_token},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_api_start_does_not_accept_client_selected_participant_code(
    client,
    db_context,
    demographics,
):
    payload = _start_payload(demographics)
    payload["participant_code"] = "RIA-FORZADO"

    response = client.post("/api/assessment/start", json=payload)

    assert response.status_code == 201
    assert response.get_json()["data"]["participant_code"] != "RIA-FORZADO"


def test_viewer_cannot_export_master_dataset(
    app,
    db_context,
):
    from werkzeug.security import generate_password_hash

    previous_accounts = app.config["RESEARCHER_ACCOUNTS"]
    app.config["RESEARCHER_ACCOUNTS"] = [
        {
            "username": "solo_lectura",
            "display_name": "Solo lectura",
            "password_hash": generate_password_hash("ClavePrueba123!"),
            "role": "viewer",
        }
    ]

    try:
        viewer = app.test_client()
        viewer.get("/investigacion/login")
        with viewer.session_transaction() as flask_session:
            csrf_token = flask_session["research_csrf_token"]

        login = viewer.post(
            "/investigacion/login",
            data={
                "csrf_token": csrf_token,
                "username": "solo_lectura",
                "password": "ClavePrueba123!",
            },
        )
        assert login.status_code == 302

        denied = viewer.get("/investigacion/datasets/export/master/csv")
        assert denied.status_code == 403
    finally:
        app.config["RESEARCHER_ACCOUNTS"] = previous_accounts



def test_researcher_session_invalidates_after_credential_change(
    app,
    client,
    db_context,
):
    from werkzeug.security import generate_password_hash

    previous_accounts = app.config["RESEARCHER_ACCOUNTS"]
    original_hash = generate_password_hash("ClavePrueba123!")
    app.config["RESEARCHER_ACCOUNTS"] = [
        {
            "username": "investigador",
            "display_name": "Investigador",
            "password_hash": original_hash,
            "role": "data_manager",
        }
    ]

    try:
        client.get("/investigacion/login")
        with client.session_transaction() as flask_session:
            csrf_token = flask_session["research_csrf_token"]

        login = client.post(
            "/investigacion/login",
            data={
                "csrf_token": csrf_token,
                "username": "investigador",
                "password": "ClavePrueba123!",
            },
        )
        assert login.status_code == 302

        dashboard = client.get("/investigacion")
        assert dashboard.status_code == 200

        app.config["RESEARCHER_ACCOUNTS"] = [
            {
                "username": "investigador",
                "display_name": "Investigador",
                "password_hash": generate_password_hash("NuevaClave123!"),
                "role": "data_manager",
            }
        ]

        invalidated = client.get("/investigacion", follow_redirects=False)
        assert invalidated.status_code == 302
        assert "/investigacion/login" in invalidated.headers["Location"]
        with client.session_transaction() as flask_session:
            assert "researcher_username" not in flask_session
    finally:
        app.config["RESEARCHER_ACCOUNTS"] = previous_accounts
