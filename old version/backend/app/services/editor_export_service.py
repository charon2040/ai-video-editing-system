from typing import Dict, List, Optional

from app.services.studio_service import studio_service


class EditorExportService:
    def list_export_jobs(self, project_id: int) -> List[Dict]:
        return studio_service.list_export_jobs(project_id)

    def create_export_job(self, project_id: int, payload: Dict) -> Dict:
        return studio_service.create_export_job(project_id, payload)

    def get_export_job(self, project_id: int, job_id: int) -> Optional[Dict]:
        return studio_service.get_export_job(project_id, job_id)


editor_export_service = EditorExportService()
