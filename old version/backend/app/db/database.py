import sqlite3
from contextlib import contextmanager

from app.core.config import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    scenario TEXT DEFAULT 'sports_digest',
    status TEXT DEFAULT 'draft',
    aspect_ratio TEXT DEFAULT '16:9',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    transcript_status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS timelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL UNIQUE,
    name TEXT DEFAULT '主时间线',
    resolution TEXT DEFAULT '1920x1080',
    fps INTEGER DEFAULT 30,
    script TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    source_video_path TEXT DEFAULT '',
    source_edl_path TEXT DEFAULT '',
    render_blueprint_json TEXT DEFAULT '{}',
    current_history_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS timeline_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timeline_id INTEGER NOT NULL,
    asset_id INTEGER,
    clip_type TEXT DEFAULT 'video',
    label TEXT DEFAULT '',
    track_type TEXT DEFAULT 'video',
    track_index INTEGER DEFAULT 0,
    start_ms INTEGER DEFAULT 0,
    end_ms INTEGER DEFAULT 0,
    source_start_ms INTEGER DEFAULT 0,
    source_end_ms INTEGER DEFAULT 0,
    content TEXT DEFAULT '',
    dubbing TEXT DEFAULT '',
    effects_json TEXT DEFAULT '{}',
    transform_json TEXT DEFAULT '{}',
    mask_json TEXT DEFAULT '{}',
    transition_json TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(timeline_id) REFERENCES timelines(id),
    FOREIGN KEY(asset_id) REFERENCES media_assets(id)
);

CREATE TABLE IF NOT EXISTS timeline_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timeline_id INTEGER NOT NULL,
    track_type TEXT DEFAULT 'video',
    track_index INTEGER DEFAULT 0,
    name TEXT DEFAULT '',
    is_locked INTEGER DEFAULT 0,
    is_muted INTEGER DEFAULT 0,
    is_visible INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timeline_id, track_type, track_index),
    FOREIGN KEY(timeline_id) REFERENCES timelines(id)
);

CREATE TABLE IF NOT EXISTS timeline_histories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    timeline_id INTEGER NOT NULL,
    action TEXT DEFAULT 'edit',
    snapshot_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(timeline_id) REFERENCES timelines(id)
);

CREATE TABLE IF NOT EXISTS export_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    timeline_id INTEGER,
    job_type TEXT DEFAULT 'preview',
    status TEXT DEFAULT 'queued',
    progress INTEGER DEFAULT 0,
    output_path TEXT DEFAULT '',
    render_config_json TEXT DEFAULT '{}',
    error_message TEXT DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(timeline_id) REFERENCES timelines(id)
);

CREATE TABLE IF NOT EXISTS effect_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    config_json TEXT DEFAULT '{}',
    is_system INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


MIGRATION_COLUMNS = {
    "timelines": {
        "source_video_path": "TEXT DEFAULT ''",
        "source_edl_path": "TEXT DEFAULT ''",
        "render_blueprint_json": "TEXT DEFAULT '{}'",
        "current_history_id": "INTEGER",
    },
    "timeline_clips": {
        "clip_type": "TEXT DEFAULT 'video'",
        "label": "TEXT DEFAULT ''",
        "transform_json": "TEXT DEFAULT '{}'",
        "mask_json": "TEXT DEFAULT '{}'",
        "transition_json": "TEXT DEFAULT '{}'",
        "metadata_json": "TEXT DEFAULT '{}'",
    },
    "export_jobs": {
        "render_config_json": "TEXT DEFAULT '{}'",
        "error_message": "TEXT DEFAULT ''",
        "started_at": "TEXT",
        "finished_at": "TEXT",
    },
    "timeline_tracks": {
        "name": "TEXT DEFAULT ''",
        "is_locked": "INTEGER DEFAULT 0",
        "is_muted": "INTEGER DEFAULT 0",
        "is_visible": "INTEGER DEFAULT 1",
        "sort_order": "INTEGER DEFAULT 0",
    },
}


DEFAULT_EFFECT_PRESETS = [
    (
        "AI 高亮",
        "clip_effect",
        '{"highlight": true, "color_boost": true, "description": "提升关键片段对比度与饱和度"}',
    ),
    (
        "黑白情绪",
        "clip_effect",
        '{"grayscale": true, "description": "将片段转为黑白，突出情绪或回忆感"}',
    ),
    (
        "轻模糊",
        "clip_effect",
        '{"blur": true, "blur_strength": 6, "description": "对片段整体做轻度模糊"}',
    ),
]


def _get_table_columns(connection: sqlite3.Connection, table_name: str):
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_columns(connection: sqlite3.Connection):
    for table_name, columns in MIGRATION_COLUMNS.items():
        existing_columns = _get_table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                )


def _seed_effect_presets(connection: sqlite3.Connection):
    for name, category, config_json in DEFAULT_EFFECT_PRESETS:
        connection.execute(
            """
            INSERT OR IGNORE INTO effect_presets (name, category, config_json, is_system)
            VALUES (?, ?, ?, 1)
            """,
            (name, category, config_json),
        )


def init_db():
    with sqlite3.connect(settings.DATABASE_PATH) as connection:
        connection.executescript(SCHEMA_SQL)
        _ensure_columns(connection)
        _seed_effect_presets(connection)
        connection.commit()


@contextmanager
def get_db_connection():
    connection = sqlite3.connect(settings.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
