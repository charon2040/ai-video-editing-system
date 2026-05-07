from typing import Dict, List

from app.services.editor_logic_registry import get_logic_catalog
from app.services.studio_service import studio_service


class EditorProjectService:
    def get_blueprint(self) -> Dict:
        return studio_service.get_blueprint()

    def get_overview(self) -> Dict:
        return studio_service.get_overview()

    def list_effect_presets(self) -> List[Dict]:
        db_items = studio_service.list_effect_presets()
        db_keys = set()
        for item in db_items:
            key = str(item.get("name") or "").strip().lower()
            if key:
                db_keys.add(key)

        catalog = get_logic_catalog()
        generated_items: List[Dict] = []
        for group in ("filters", "animations", "transitions"):
            for preset in catalog.get(group, []):
                name = str(preset.get("name") or preset.get("id") or "").strip()
                if not name or name.lower() in db_keys:
                    continue
                generated_items.append(
                    {
                        "id": None,
                        "name": name,
                        "category": f"{group[:-1]}_preset",
                        "config": preset,
                        "is_system": 1,
                    }
                )
        return db_items + generated_items

    def get_effect_catalog(self) -> Dict:
        return get_logic_catalog()

    def list_projects(self) -> List[Dict]:
        return studio_service.list_projects()

    def create_project(self, payload: Dict) -> Dict:
        return studio_service.create_project(payload)

    def get_project_detail(self, project_id: int) -> Dict:
        return studio_service.get_project_detail(project_id)

    def create_asset(self, project_id: int, payload: Dict) -> Dict:
        return studio_service.create_asset(project_id, payload)

    def register_existing_asset(self, project_id: int, payload: Dict) -> Dict:
        return studio_service.register_existing_asset(project_id, payload)

    def extract_audio_from_asset(self, project_id: int, asset_id: int) -> Dict:
        return studio_service.extract_audio_from_asset(project_id, asset_id)

    def delete_asset(self, project_id: int, asset_id: int) -> bool:
        return studio_service.delete_asset(project_id, asset_id)

    def cleanup_missing_assets(self, project_id: int) -> Dict:
        return studio_service.cleanup_missing_assets(project_id)

    def reset_project_data(self, project_id: int, *, clear_assets: bool = True) -> Dict:
        return studio_service.reset_project_data(project_id, clear_assets=clear_assets)

    def resolve_storage_path(self, file_path: str) -> str:
        return studio_service._resolve_storage_path(file_path)


editor_project_service = EditorProjectService()
