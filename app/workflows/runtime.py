from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, Protocol

from app.services.task_run_context_service import TaskRunContext


logger = logging.getLogger(__name__)

UpdateTaskCallback = Callable[..., Dict[str, Any]]
RecordTaskEventCallback = Callable[..., None]


@dataclass
class WorkflowRuntimeContext:
    task_id: str
    phase: str
    task: Dict[str, Any]
    run_context: TaskRunContext
    pipeline_mode: str
    template_title: str
    update_task: UpdateTaskCallback
    record_task_event: RecordTaskEventCallback
    data: Dict[str, Any] = field(default_factory=dict)


class WorkflowNode(Protocol):
    node_type: str
    title: str

    def run(self, context: WorkflowRuntimeContext) -> None:
        ...


class WorkflowNodeRegistry:
    def __init__(self) -> None:
        self._nodes: Dict[str, WorkflowNode] = {}

    def register(self, node: WorkflowNode) -> None:
        node_type = str(node.node_type or "").strip()
        if not node_type:
            raise ValueError("Workflow node_type is required")
        self._nodes[node_type] = node

    def get(self, node_type: str) -> WorkflowNode:
        normalized = str(node_type or "").strip()
        node = self._nodes.get(normalized)
        if not node:
            raise ValueError(f"Workflow node is not registered: {normalized}")
        return node


class WorkflowRuntime:
    def __init__(
        self,
        *,
        registry: WorkflowNodeRegistry,
        phase_sequences: Dict[str, Iterable[str]],
        runtime_version: str = "workflow_runtime_v1_coarse",
    ) -> None:
        self._registry = registry
        self._phase_sequences = {
            str(phase): [str(node_type) for node_type in node_types]
            for phase, node_types in phase_sequences.items()
        }
        self._runtime_version = runtime_version

    def run(
        self,
        context: WorkflowRuntimeContext,
        *,
        phase_sequences: Dict[str, Iterable[str]] | None = None,
        sequence_source: str = "default",
    ) -> None:
        effective_sequences = {
            **self._phase_sequences,
            **{
                str(phase): [str(node_type) for node_type in node_types]
                for phase, node_types in (phase_sequences or {}).items()
            },
        }
        node_types = effective_sequences.get(context.phase)
        if not node_types:
            raise ValueError(f"Unsupported workflow phase: {context.phase}")
        effective_sequence_source = sequence_source if context.phase in (phase_sequences or {}) else "default"

        context.record_task_event(
            context.task_id,
            event_type="workflow_started",
            detail={
                "phase": context.phase,
                "pipeline_mode": context.pipeline_mode,
                "workflow_template_title": context.template_title,
                "runtime_version": self._runtime_version,
                "sequence_source": effective_sequence_source,
                "nodes": node_types,
            },
        )
        logger.info(
            "Workflow started: task=%s phase=%s template=%s nodes=%s",
            context.task_id,
            context.phase,
            context.pipeline_mode,
            ",".join(node_types),
        )

        for node_type in node_types:
            self._run_node(context, self._registry.get(node_type))

        context.record_task_event(
            context.task_id,
            event_type="workflow_completed",
            detail={
                "phase": context.phase,
                "pipeline_mode": context.pipeline_mode,
                "runtime_version": self._runtime_version,
            },
        )

    def _run_node(self, context: WorkflowRuntimeContext, node: WorkflowNode) -> None:
        started_at = perf_counter()
        context.record_task_event(
            context.task_id,
            event_type="workflow_node_started",
            detail={
                "phase": context.phase,
                "node_type": node.node_type,
                "node_title": node.title,
                "pipeline_mode": context.pipeline_mode,
            },
        )
        try:
            node.run(context)
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            context.record_task_event(
                context.task_id,
                event_type="workflow_node_failed",
                detail={
                    "phase": context.phase,
                    "node_type": node.node_type,
                    "node_title": node.title,
                    "duration_ms": elapsed_ms,
                    "error": str(exc),
                },
            )
            raise
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        context.record_task_event(
            context.task_id,
            event_type="workflow_node_completed",
            detail={
                "phase": context.phase,
                "node_type": node.node_type,
                "node_title": node.title,
                "duration_ms": elapsed_ms,
            },
        )
