import asyncio
import logging
import smtplib
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="send_email", bind=True, max_retries=3)
def send_email(self, to: str, subject: str, body: str) -> dict:
    from app.services.email_service import EmailService

    email_svc = EmailService()
    try:
        result = email_svc.send_html(to_email=to, subject=subject, html_body=body)
        return {"to": to, "subject": subject, "status": result.get("status", "sent")}
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error sending email to %s: %s", to, exc)
        raise self.retry(exc=exc, countdown=30)
    except Exception as exc:
        logger.exception("Failed to send email to %s", to)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="run_simulation", bind=True)
def run_simulation(self, scenario_id: str, execution_id: str) -> dict:
    """Execute one simulation run to completion.

    The engine itself is idempotent for completed/cancelled/running executions
    and records failure + audit on its own, so the worker does not retry: a
    transient error is surfaced on the execution row and the recruiter can
    simply re-run the scenario.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session_factory
    from app.services.simulation.execution_service import SimulationExecutionService

    async def _run() -> None:
        async with async_session_factory() as session:
            service = SimulationExecutionService(session)
            execution = await service.execute(uuid.UUID(execution_id))
            logger.info(
                "Simulation worker finished: execution=%s status=%s",
                execution.id, execution.status,
            )

    try:
        _run_async(_run())
        return {
            "scenario_id": scenario_id,
            "execution_id": execution_id,
            "status": "completed",
        }
    except Exception as exc:
        logger.exception("Simulation run failed for execution %s", execution_id)
        return {
            "scenario_id": scenario_id,
            "execution_id": execution_id,
            "status": "error",
            "error": str(exc)[:1000],
        }


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="process_resume", bind=True, max_retries=2, default_retry_delay=60)
def process_resume(self, resume_id: str) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session_factory
    from app.services.candidate.resume import ResumeService

    async def _run() -> None:
        async with async_session_factory() as session:
            service = ResumeService(session)
            await service.process_resume(uuid.UUID(resume_id))

    try:
        _run_async(_run())
        return {"resume_id": resume_id, "status": "parsed"}
    except Exception as exc:
        logger.exception("Resume processing failed for %s", resume_id)
        raise self.retry(exc=exc)


@celery_app.task(name="screen_application", bind=True, max_retries=3, default_retry_delay=15)
def screen_application(self, application_id: str) -> dict:
    """Run automatic screening for one application.

    Idempotent (the service claims the row with a CAS). Transient failures are
    retried with backoff; the service records a ``FAILED`` state with the reason
    on every attempt, and a bounded retry may re-claim it.
    """
    from app.db.session import async_session_factory
    from app.domain.enums import ScreeningStatus
    from app.services.applications.automatic_screening_service import (
        AutomaticScreeningService,
    )

    async def _run() -> str:
        async with async_session_factory() as session:
            service = AutomaticScreeningService(session)
            status = await service.process(uuid.UUID(application_id))
            await session.commit()
            return status

    try:
        status = _run_async(_run())
    except Exception as exc:
        logger.exception("Automatic screening task crashed: application=%s", application_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1))
        return {"application_id": application_id, "status": "failed", "error": str(exc)[:1000]}

    if status == ScreeningStatus.FAILED.value and self.request.retries < self.max_retries:
        raise self.retry(countdown=15 * (self.request.retries + 1))
    return {"application_id": application_id, "status": status}


@celery_app.task(name="send_invitation_email", bind=True, max_retries=3, default_retry_delay=60)
def send_invitation_email(
    self,
    to_email: str,
    invited_by_name: str,
    organization_name: str,
    role_label: str,
    accept_url: str,
    expires_at: str,
    app_name: str = "AI Hiring Copilot",
) -> dict:
    from app.services.email_service import EmailService

    email_svc = EmailService()

    subject = f"You've been invited to join {organization_name}"
    try:
        html_body = email_svc.render_template(
            "invitation_email.html",
            invited_by_name=invited_by_name,
            organization_name=organization_name,
            role_label=role_label,
            accept_url=accept_url,
            expires_at=expires_at,
            app_name=app_name,
        )
    except Exception:
        logger.exception("Failed to render invitation email template for %s", to_email)
        return {"to": to_email, "status": "template_error"}

    try:
        result = email_svc.send_html(to_email=to_email, subject=subject, html_body=html_body)
        return {"to": to_email, "status": result.get("status", "sent")}
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error sending invitation email to %s: %s", to_email, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Failed to send invitation email to %s", to_email)
        raise self.retry(exc=exc)


@celery_app.task(name="send_access_request_verification_email", bind=True, max_retries=3, default_retry_delay=60)
def send_access_request_verification_email(
    self,
    to_email: str,
    full_name: str,
    organization_name: str,
    role_label: str,
    verify_url: str,
    expires_in: str,
    app_name: str = "AI Hiring Copilot",
) -> dict:
    from app.services.email_service import EmailService
    email_svc = EmailService()
    subject = f"Verify your email to join {organization_name}"
    try:
        html_body = email_svc.render_template(
            "access_request_verification_email.html",
            full_name=full_name,
            organization_name=organization_name,
            role_label=role_label,
            verify_url=verify_url,
            expires_in=expires_in,
            app_name=app_name,
        )
    except Exception:
        logger.exception("Failed to render verification email template for %s", to_email)
        return {"to": to_email, "status": "template_error"}
    try:
        result = email_svc.send_html(to_email=to_email, subject=subject, html_body=html_body)
        return {"to": to_email, "status": result.get("status", "sent")}
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error sending verification email to %s: %s", to_email, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Failed to send verification email to %s", to_email)
        raise self.retry(exc=exc)


@celery_app.task(name="send_access_request_admin_notification_email", bind=True, max_retries=3, default_retry_delay=60)
def send_access_request_admin_notification_email(
    self,
    to_email: str,
    requester_name: str,
    requester_email: str,
    organization_name: str,
    role_label: str,
    admin_url: str,
    request_id: str,
    app_name: str = "AI Hiring Copilot",
) -> dict:
    from app.services.email_service import EmailService
    email_svc = EmailService()
    subject = f"New access request from {requester_name}"
    try:
        html_body = email_svc.render_template(
            "access_request_admin_notification_email.html",
            requester_name=requester_name,
            requester_email=requester_email,
            organization_name=organization_name,
            role_label=role_label,
            admin_url=admin_url,
            request_id=request_id,
            app_name=app_name,
        )
    except Exception:
        logger.exception("Failed to render admin notification email template for %s", to_email)
        return {"to": to_email, "status": "template_error"}
    try:
        result = email_svc.send_html(to_email=to_email, subject=subject, html_body=html_body)
        return {"to": to_email, "status": result.get("status", "sent")}
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error sending admin notification email to %s: %s", to_email, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Failed to send admin notification email to %s", to_email)
        raise self.retry(exc=exc)


@celery_app.task(name="send_access_request_approved_email", bind=True, max_retries=3, default_retry_delay=60)
def send_access_request_approved_email(
    self,
    to_email: str,
    full_name: str,
    organization_name: str,
    role_label: str,
    activate_url: str,
    expires_in: str,
    app_name: str = "AI Hiring Copilot",
) -> dict:
    from app.services.email_service import EmailService
    email_svc = EmailService()
    subject = f"Your access request for {organization_name} has been approved"
    try:
        html_body = email_svc.render_template(
            "access_request_approved_email.html",
            full_name=full_name,
            organization_name=organization_name,
            role_label=role_label,
            activate_url=activate_url,
            expires_in=expires_in,
            app_name=app_name,
        )
    except Exception:
        logger.exception("Failed to render approved email template for %s", to_email)
        return {"to": to_email, "status": "template_error"}
    try:
        result = email_svc.send_html(to_email=to_email, subject=subject, html_body=html_body)
        return {"to": to_email, "status": result.get("status", "sent")}
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error sending approved email to %s: %s", to_email, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Failed to send approved email to %s", to_email)
        raise self.retry(exc=exc)


@celery_app.task(name="send_access_request_rejected_email", bind=True, max_retries=3, default_retry_delay=60)
def send_access_request_rejected_email(
    self,
    to_email: str,
    full_name: str,
    organization_name: str,
    role_label: str,
    reason: str = "",
    app_name: str = "AI Hiring Copilot",
) -> dict:
    from app.services.email_service import EmailService
    email_svc = EmailService()
    subject = f"Your access request for {organization_name}"
    try:
        html_body = email_svc.render_template(
            "access_request_rejected_email.html",
            full_name=full_name,
            organization_name=organization_name,
            role_label=role_label,
            reason=reason,
            app_name=app_name,
        )
    except Exception:
        logger.exception("Failed to render rejected email template for %s", to_email)
        return {"to": to_email, "status": "template_error"}
    try:
        result = email_svc.send_html(to_email=to_email, subject=subject, html_body=html_body)
        return {"to": to_email, "status": result.get("status", "sent")}
    except smtplib.SMTPException as exc:
        logger.warning("SMTP error sending rejected email to %s: %s", to_email, exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Failed to send rejected email to %s", to_email)
        raise self.retry(exc=exc)


@celery_app.task(name="generate_simulation_report", bind=True)
def generate_simulation_report(
    self,
    report_id: str,
    user_id: str,
    report_type: str,
    simulation_id: str | None = None,
    execution_id: str | None = None,
    sandbox_id: str | None = None,
) -> dict:
    """Async report generation via Celery.

    Updates the report status to COMPLETED or FAILED. The report record
    must already exist (status=REQUESTED) before dispatching this task.
    """
    import uuid as _uuid
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session_factory
    from app.services.simulation.simulation_report_service import SimulationReportService
    from app.domain.simulation_report_schemas import SimulationReportCreate

    async def _run() -> None:
        async with async_session_factory() as session:
            service = SimulationReportService(session)
            # Load user
            from app.domain.models import User
            from sqlalchemy import select
            user = await session.get(User, _uuid.UUID(user_id))
            if not user:
                raise ValueError(f"User {user_id} not found")

            request = SimulationReportCreate(
                report_type=report_type,
                simulation_id=_uuid.UUID(simulation_id) if simulation_id else None,
                execution_id=_uuid.UUID(execution_id) if execution_id else None,
                sandbox_id=_uuid.UUID(sandbox_id) if sandbox_id else None,
            )
            await service.create_report(user, request)

    try:
        _run_async(_run())
        return {"report_id": report_id, "status": "completed"}
    except Exception as exc:
        logger.exception("Report generation failed for %s", report_id)
        return {"report_id": report_id, "status": "error", "error": str(exc)[:1000]}


# ── Phase 14: Experiment Execution ─────────────────────────────────


@celery_app.task(bind=True, max_retries=1, acks_late=False)
def run_experiment(self, experiment_id: str, user_id: str) -> dict:
    """Execute a research experiment asynchronously.

    Generates simulation configurations, runs them through the existing
    simulation engine, and aggregates sensitivity/robustness/stability metrics.
    All execution is READ-ONLY with respect to live hiring data.
    """
    import asyncio as _asyncio

    def _run_async(coro):
        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    import uuid as _uuid
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session_factory
    from app.services.simulation.experiment_service import ExperimentService
    from app.services.simulation.execution_service import SimulationExecutionService
    from app.domain.simulation_models import SimulationExperiment, SimulationExperimentResult
    from app.domain.enums import ExperimentStatus
    from sqlalchemy import select
    from datetime import datetime, timezone

    async def _run() -> None:
        async with async_session_factory() as session:
            experiment = await session.get(
                SimulationExperiment, _uuid.UUID(experiment_id),
            )
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")

            experiment.status = ExperimentStatus.RUNNING.value
            experiment.updated_at = datetime.now(timezone.utc)
            await session.commit()

            generated = experiment.generated_configs or {}
            configs = generated.get("configurations", [])
            hashes = generated.get("hashes", [])

            from app.services.simulation.perturbation_engine import PerturbationEngine
            engine = PerturbationEngine()

            completed = 0
            failed = 0

            for i, config in enumerate(configs):
                try:
                    # Create an isolated scenario for each config
                    from app.domain.simulation_models import SimulationScenario
                    from app.domain.enums import SimulationStatus

                    scenario = SimulationScenario(
                        id=_uuid.uuid4(),
                        organization_id=experiment.organization_id,
                        job_id=experiment.job_id,
                        created_by=_uuid.UUID(user_id),
                        name=f"Experiment {experiment.name} - Config {i + 1}",
                        description=f"Auto-generated for experiment {experiment.name}",
                        status=SimulationStatus.READY.value,
                        baseline_config=config,
                        simulation_config=config,
                        config_version=1,
                    )
                    session.add(scenario)
                    await session.flush()

                    # Run the existing simulation engine
                    exec_svc = SimulationExecutionService(session)
                    execution = await exec_svc.run_scenario(
                        scenario, _uuid.UUID(user_id),
                    )

                    # Collect metrics from execution
                    metrics = execution.summary or {}

                    # Extract candidate-level metrics from results
                    from app.repositories.simulation_execution import SimulationResultRepository
                    result_repo = SimulationResultRepository(session)
                    sim_results = await result_repo.list_by_execution(execution.id)

                    candidate_metrics = {}
                    for sr in sim_results:
                        candidate_metrics[str(sr.candidate_id)] = {
                            "name": sr.candidate_name,
                            "score": sr.simulation_score,
                            "rank": sr.simulation_rank,
                            "qualified": sr.simulation_status == "qualified",
                            "shortlisted": sr.simulation_shortlisted,
                        }

                    # Store experiment result
                    exp_result = SimulationExperimentResult(
                        id=_uuid.uuid4(),
                        experiment_id=_uuid.UUID(experiment_id),
                        simulation_scenario_id=scenario.id,
                        simulation_execution_id=execution.id,
                        parameter_values=config.get("simulation", {}),
                        configuration_hash=hashes[i] if i < len(hashes) else None,
                        execution_status="completed",
                        metrics=metrics,
                        candidate_metrics=candidate_metrics,
                    )
                    session.add(exp_result)
                    completed += 1

                    # Clean up the isolated scenario
                    scenario.status = SimulationStatus.CANCELLED.value
                    await session.flush()

                except Exception as e:
                    logger.warning("Config %d failed: %s", i + 1, str(e))
                    failed += 1
                    exp_result = SimulationExperimentResult(
                        id=_uuid.uuid4(),
                        experiment_id=_uuid.UUID(experiment_id),
                        parameter_values=config.get("simulation", {}),
                        configuration_hash=hashes[i] if i < len(hashes) else None,
                        execution_status="failed",
                        error_message=str(e)[:500],
                    )
                    session.add(exp_result)

                experiment.completed_configurations = completed
                experiment.failed_configurations = failed
                experiment.updated_at = datetime.now(timezone.utc)
                await session.commit()

            # Run analysis on completed results
            if completed > 0:
                from app.services.simulation.sensitivity_analyzer import SensitivityAnalyzer
                from app.services.simulation.robustness_analyzer import RobustnessAnalyzer
                from app.services.simulation.stability_analyzer import StabilityAnalyzer

                result_repo = SimulationExperimentResultRepository(session)
                all_results = await result_repo.list_by_experiment(_uuid.UUID(experiment_id))
                result_dicts = [
                    {
                        "parameter_values": r.parameter_values,
                        "metrics": r.metrics,
                        "candidate_metrics": r.candidate_metrics,
                        "execution_status": r.execution_status,
                        "configuration_hash": r.configuration_hash,
                    }
                    for r in all_results
                ]

                sensitivity = SensitivityAnalyzer()
                stability = StabilityAnalyzer()

                experiment.sensitivity_results = sensitivity.analyze(
                    experiment_id, result_dicts, experiment.parameter_ranges,
                ).model_dump()

                experiment.stability_results = stability.analyze(
                    experiment_id, result_dicts,
                ).model_dump()

            experiment.status = ExperimentStatus.COMPLETED.value
            experiment.completed_at = datetime.now(timezone.utc)
            experiment.updated_at = datetime.now(timezone.utc)
            await session.commit()

    try:
        _run_async(_run())
        return {"experiment_id": experiment_id, "status": "completed"}
    except Exception as exc:
        logger.exception("Experiment execution failed for %s", experiment_id)
        # Mark as failed
        async def _mark_failed():
            async with async_session_factory() as session:
                exp = await session.get(SimulationExperiment, _uuid.UUID(experiment_id))
                if exp:
                    exp.status = ExperimentStatus.FAILED.value
                    exp.error_message = str(exc)[:1000]
                    exp.updated_at = datetime.now(timezone.utc)
                    await session.commit()
        _run_async(_mark_failed())
        return {"experiment_id": experiment_id, "status": "error", "error": str(exc)[:1000]}
