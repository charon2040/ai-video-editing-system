from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class WorkflowPort(BaseModel):
    name: str
    schema_ref: str = ""
    required: bool = True
    description: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return self.model_dump()


class WorkflowNode(BaseModel):
    id: str
    type: str
    title: str
    description: str = ""
    inputs: List[WorkflowPort] = Field(default_factory=list)
    outputs: List[WorkflowPort] = Field(default_factory=list)
    config_schema: Dict[str, Any] = Field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return self.model_dump()


class WorkflowEdge(BaseModel):
    from_node: str
    from_port: str
    to_node: str
    to_port: str

    def to_payload(self) -> Dict[str, Any]:
        return self.model_dump()


class WorkflowTemplate(BaseModel):
    id: str
    title: str
    description: str = ""
    version: str = "1"
    entry_node: str = ""
    terminal_node: str = ""
    task_mode: str = "narration_clip"
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    runtime: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    is_default: bool = False
    enabled: bool = True

    def to_payload(self) -> Dict[str, Any]:
        return self.model_dump()
