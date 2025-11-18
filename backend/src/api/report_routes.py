"""API routes for report generation"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID

from src.database import get_db
from src.reports.insurance_report_generator import InsuranceReportGenerator
from src.reports.delivery_report_generator import DeliveryReportGenerator
from src.api.auth_routes import get_current_user

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/insurance-claim")
async def generate_insurance_claim_report(
    project_id: UUID,
    include_photos: bool = Query(True, description="Include photo URLs in report"),
    format: str = Query("json", description="Report format (json or pdf)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Generate an insurance claim report for a project.
    Includes damage detections, severity analysis, and recommendations.
    """
    try:
        generator = InsuranceReportGenerator(db)
        report = generator.generate_report(
            project_id=project_id,
            include_photos=include_photos,
            format=format,
        )

        return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate insurance claim report: {str(e)}",
        )


@router.post("/insurance-claim/batch")
async def generate_batch_insurance_claim_report(
    project_ids: List[UUID],
    format: str = Query("json", description="Report format"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Generate insurance claim reports for multiple projects.
    """
    try:
        generator = InsuranceReportGenerator(db)
        report = generator.generate_batch_report(
            project_ids=project_ids,
            format=format,
        )

        return report

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate batch insurance claim report: {str(e)}",
        )


@router.post("/delivery-verification")
async def generate_delivery_verification_report(
    project_id: UUID,
    expected_materials: Optional[Dict[str, int]] = None,
    include_photos: bool = Query(True, description="Include photo URLs in report"),
    format: str = Query("json", description="Report format (json or pdf)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Generate a delivery verification report for a project.
    Includes material counts, variance analysis, and alerts.
    """
    try:
        generator = DeliveryReportGenerator(db)
        report = generator.generate_report(
            project_id=project_id,
            expected_materials=expected_materials,
            include_photos=include_photos,
            format=format,
        )

        return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate delivery verification report: {str(e)}",
        )


@router.post("/delivery-verification/batch")
async def generate_batch_delivery_verification_report(
    project_ids: List[UUID],
    format: str = Query("json", description="Report format"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Generate delivery verification reports for multiple projects.
    """
    try:
        generator = DeliveryReportGenerator(db)
        report = generator.generate_batch_report(
            project_ids=project_ids,
            format=format,
        )

        return report

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate batch delivery verification report: {str(e)}",
        )


@router.post("/project-summary")
async def generate_project_summary_report(
    project_id: UUID,
    include_photos: bool = Query(True, description="Include photo URLs"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Generate a comprehensive project summary report.
    Includes all detection types, statistics, and insights.
    """
    try:
        # Generate both insurance and delivery reports
        insurance_gen = InsuranceReportGenerator(db)
        delivery_gen = DeliveryReportGenerator(db)

        insurance_report = insurance_gen.generate_report(
            project_id=project_id,
            include_photos=include_photos,
            format="json",
        )

        delivery_report = delivery_gen.generate_report(
            project_id=project_id,
            include_photos=include_photos,
            format="json",
        )

        # Combine into project summary
        summary = {
            "report_type": "project_summary",
            "project": insurance_report.get("project"),
            "damage_analysis": {
                "summary": insurance_report.get("summary"),
                "items": insurance_report.get("damage_items"),
                "recommendations": insurance_report.get("recommendations"),
            },
            "material_analysis": {
                "summary": delivery_report.get("summary"),
                "items": delivery_report.get("material_items"),
                "variance_alerts": delivery_report.get("variance_alerts"),
            },
        }

        return summary

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate project summary report: {str(e)}",
        )
