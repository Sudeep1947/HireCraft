"""Simulation Reports API (Phase 13).

Provides endpoints for generating, retrieving, listing, exporting,
and deleting simulation reports. Reports are read-only aggregations
of existing simulation data.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.logging import get_logger
from app.db.session import get_db
from app.domain.enums import AuditEventType
from app.domain.models import User
from app.domain.simulation_report_schemas import (
    SimulationReportCreate,
    SimulationReportListResponse,
    SimulationReportResponse,
    SimulationReportStatusResponse,
)
from app.services.audit_service import AuditService
from app.services.simulation.simulation_report_service import SimulationReportService

logger = get_logger(__name__)

router = APIRouter(prefix="/simulation-reports", tags=["simulation-reports"])


def _get_service(db: AsyncSession = Depends(get_db)) -> SimulationReportService:
    return SimulationReportService(db)


@router.post("", response_model=SimulationReportResponse, status_code=201)
async def create_report(
    body: SimulationReportCreate,
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Generate a simulation report from existing simulation data."""
    return await service.create_report(current_user, body)


@router.get("", response_model=SimulationReportListResponse)
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """List reports the user has access to."""
    return await service.list_reports(current_user, page=page, page_size=page_size)


@router.get("/{report_id}", response_model=SimulationReportResponse)
async def get_report(
    report_id: uuid.UUID,
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Retrieve a report with full data."""
    return await service.get_report(current_user, report_id)


@router.get("/{report_id}/status", response_model=SimulationReportStatusResponse)
async def get_report_status(
    report_id: uuid.UUID,
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Check report generation status."""
    return await service.get_report_status(current_user, report_id)


@router.get("/{report_id}/json")
async def get_report_json(
    report_id: uuid.UUID,
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Get report data as JSON."""
    return await service.get_report_json(current_user, report_id)


@router.get("/{report_id}/pdf")
async def get_report_pdf(
    report_id: uuid.UUID,
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Export report as PDF."""
    from app.services.simulation.report_pdf_service import ReportPDFService

    report = await service.get_report(current_user, report_id)
    pdf_service = ReportPDFService()
    pdf_bytes = pdf_service.generate(report)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{report_id}.pdf"',
        },
    )


@router.get("/{report_id}/csv")
async def get_report_csv(
    report_id: uuid.UUID,
    section: str = Query(default="candidate_impact", pattern="^(candidate_impact|ranking|fairness|skills)$"),
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Export report section as CSV."""
    from app.services.simulation.report_csv_service import ReportCSVService

    report = await service.get_report(current_user, report_id)
    csv_service = ReportCSVService()
    csv_content = csv_service.generate(report, section)

    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="report-{report_id}-{section}.csv"',
        },
    )


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID,
    service: SimulationReportService = Depends(_get_service),
    current_user: User = Depends(require_role("admin", "hr", "recruiter")),
):
    """Delete a report."""
    await service.delete_report(current_user, report_id)
    return None
