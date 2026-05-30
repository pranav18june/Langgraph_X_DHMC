from __future__ import annotations
import asyncio
import threading
from typing import Any, Dict, Iterator, Sequence, Optional, Mapping, AsyncIterator

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    ChannelVersions,
    CheckpointTuple,
    DeltaChannelHistory,
)
from langchain_core.runnables import RunnableConfig

from dhmc.langgraph_checkpointer import DHMCCheckpointer
from dhmc.schema_envelope import StepType

# Helper for recursive serialization of Pydantic models to standard Python dicts/lists
def serialize_for_dhmc(obj: Any) -> Any:
    if obj is None:
        return None
    # Check for Pydantic V2 and V1 models without explicitly requiring importing pydantic
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return serialize_for_dhmc(obj.model_dump())
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return serialize_for_dhmc(obj.dict())
    if isinstance(obj, dict):
        return {k: serialize_for_dhmc(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [serialize_for_dhmc(v) for v in obj]
    return obj

class DHMCWrappedCheckpointer(BaseCheckpointSaver):
    """
    Wraps any existing LangGraph checkpointer (MemorySaver, SqliteSaver, PostgresSaver)
    with DHMC provenance tracking.
    """

    def __init__(
        self,
        underlying: BaseCheckpointSaver,
        dhmc_instance: DHMCCheckpointer,
        node_to_module: Dict[str, str],
        node_to_step_type: Dict[str, StepType],
    ) -> None:
        # Base class init
        super().__init__(serde=underlying.serde)
        self.underlying = underlying
        self.dhmc = dhmc_instance
        self.node_to_module = node_to_module
        self.node_to_step_type = node_to_step_type
        
        # State tracking
        self.current_module: Optional[str] = None
        # Race-free thread synchronization buffers
        self.write_events: Dict[tuple[str, Optional[str]], threading.Event] = {}
        self.buffered_writes: Dict[tuple[str, Optional[str]], tuple[str, Sequence[tuple[str, Any]]]] = {}
        # Transient in-memory list of spawned child checkpointers waiting to be collapsed
        self.active_child_dhmcs: list[DHMCCheckpointer] = []

    def register_child_dhmc(self, child_dhmc: DHMCCheckpointer) -> None:
        """Register a child sub-agent checkpointer to be collapsed at the step boundary."""
        self.active_child_dhmcs.append(child_dhmc)

    def _register_step_internal(self, node_name: str, writes: Sequence[tuple[str, Any]], checkpoint_values: dict[str, Any]) -> None:
        """Unified step registration logic."""
        module_id = self.node_to_module.get(node_name)
        step_type = self.node_to_step_type.get(node_name)

        if module_id and step_type:
            # Module boundary detection: close previous active module if we are moving to a new one
            if self.current_module is not None and self.current_module != module_id:
                self.dhmc.close_module(self.current_module)
            self.current_module = module_id

            # Handle conditional branch id for fraud_check
            branch_id = "fraud_check" if node_name == "fraud_check" else None

            # Serialize payloads to avoid Pydantic issues and ensure pure Python types
            serialized_writes = serialize_for_dhmc(writes)
            serialized_channels = serialize_for_dhmc(checkpoint_values)

            if self.active_child_dhmcs:
                child_dhmc = self.active_child_dhmcs.pop(0)
                print(f"  [DHMC-WRAPPER] Collapsing subagent child chain into parent MMR: node={node_name}")
                self.dhmc.collapse_subagent(
                    parent_module_id=module_id,
                    step_type=step_type,
                    child_dhmc=child_dhmc,
                    input_payload=serialized_writes,
                )
            else:
                print(f"  [DHMC-WRAPPER] Registering step: node={node_name} | module={module_id} | step_type={step_type}")
                self.dhmc.register_step(
                    module_id=module_id,
                    step_type=step_type,
                    input_payload=serialized_writes,
                    output_payload=serialized_channels,
                    branch_id=branch_id,
                )

            # Synthesis is the final step; close M3 and reset active module tracking
            if node_name == "synthesis":
                self.dhmc.close_module(module_id)
                self.current_module = None

    # --- DHMC Intercepts ---

    def _dhmc_put_writes_intercept(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        # Identify executing node name from task_path
        node_name = None
        for name in self.node_to_module:
            if name in task_path:
                node_name = name
                break

        print(f"  [DHMC-WRAPPER] Intercepted put_writes | task_path='{task_path}' | thread={thread_id} | checkpoint={checkpoint_id} -> node={node_name}")
        if node_name:
            key = (thread_id, checkpoint_id)
            self.buffered_writes[key] = (node_name, writes)
            
            # Signal to the waiting put() thread that writes are ready
            if key in self.write_events:
                self.write_events[key].set()

    def _dhmc_put_intercept(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        new_checkpoint_id = checkpoint["id"]

        print(f"  [DHMC-WRAPPER] Intercepted put | thread_id='{thread_id}' | parent_checkpoint_id='{parent_checkpoint_id}' | new_checkpoint_id='{new_checkpoint_id}'")

        key = (thread_id, parent_checkpoint_id)
        
        # If writes have not been buffered yet, wait for them sequentially!
        if key not in self.buffered_writes:
            # We skip waiting if this is a genesis checkpoint with no node execution
            # In LangGraph, the genesis checkpoint has metadata["source"] == "input"
            # or parent_checkpoint_id is None, so we don't wait for it.
            if parent_checkpoint_id is not None:
                print(f"  [DHMC-WRAPPER] Sequential Sync: Waiting for put_writes of checkpoint={parent_checkpoint_id}...")
                event = self.write_events.setdefault(key, threading.Event())
                # Wait up to 5 seconds for background thread to execute and buffer the writes
                event.wait(timeout=5.0)

        # Retrieve the buffered writes and register the step
        if key in self.buffered_writes:
            node_name, writes = self.buffered_writes.pop(key)
            print(f"  [DHMC-WRAPPER] Found writes for node={node_name}. Registering step sequentially.")
            self._register_step_internal(node_name, writes, checkpoint.get("channel_values", {}))
            
        # Clean up events
        self.write_events.pop(key, None)

    # --- Abstract & Overridden checkpointer methods ---

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self._dhmc_put_writes_intercept(config, writes, task_id, task_path)
        self.underlying.put_writes(config, writes, task_id, task_path)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self._dhmc_put_writes_intercept(config, writes, task_id, task_path)
        await self.underlying.aput_writes(config, writes, task_id, task_path)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        self._dhmc_put_intercept(config, checkpoint, metadata, new_versions)
        return self.underlying.put(config, checkpoint, metadata, new_versions)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        self._dhmc_put_intercept(config, checkpoint, metadata, new_versions)
        return await self.underlying.aput(config, checkpoint, metadata, new_versions)

    # --- Transparent Pass-Throughs to Underlying ---

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.underlying.get_tuple(config)

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await self.underlying.aget_tuple(config)

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        return self.underlying.list(config, filter=filter, before=before, limit=limit)

    def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        return self.underlying.alist(config, filter=filter, before=before, limit=limit)

    def delete_thread(self, thread_id: str) -> None:
        self.underlying.delete_thread(thread_id)

    async def adelete_thread(self, thread_id: str) -> None:
        await self.underlying.adelete_thread(thread_id)

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        self.underlying.delete_for_runs(run_ids)

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        await self.underlying.adelete_for_runs(run_ids)

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        self.underlying.copy_thread(source_thread_id, target_thread_id)

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        await self.underlying.acopy_thread(source_thread_id, target_thread_id)

    def prune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        self.underlying.prune(thread_ids, strategy=strategy)

    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        await self.underlying.aprune(thread_ids, strategy=strategy)

    def get_delta_channel_history(
        self, *, config: RunnableConfig, channels: Sequence[str]
    ) -> Mapping[str, DeltaChannelHistory]:
        return self.underlying.get_delta_channel_history(config=config, channels=channels)

    async def aget_delta_channel_history(
        self, *, config: RunnableConfig, channels: Sequence[str]
    ) -> Mapping[str, DeltaChannelHistory]:
        return await self.underlying.aget_delta_channel_history(config=config, channels=channels)

    def get_next_version(self, current: Optional[Any], channel: None) -> Any:
        return self.underlying.get_next_version(current, channel)
