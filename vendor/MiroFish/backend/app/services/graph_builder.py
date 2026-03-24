"""
图谱构建服务
接口2：按后端配置构建图谱
"""

import time
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from .graph_backend_client import GraphBackendClient
from .text_processor import TextProcessor


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    图谱构建服务
    负责根据 GRAPH_BACKEND 选择 Zep 或 graph-service
    """

    def __init__(self, api_key: Optional[str] = None):
        self.backend = Config.GRAPH_BACKEND
        self.api_key = api_key or Config.ZEP_API_KEY
        self.task_manager = TaskManager()
        self._graph_context: Dict[str, Dict[str, Any]] = {}

        if self.backend == "graphiti":
            self.client = GraphBackendClient(Config.GRAPH_SERVICE_BASE_URL)
        else:
            if not self.api_key:
                raise ValueError("ZEP_API_KEY 未配置")
            self.client = self._build_zep_client(self.api_key)

    def _build_zep_client(self, api_key: str):
        from zep_cloud.client import Zep

        return Zep(api_key=api_key)

    def _fetch_all_nodes(self, graph_id: str):
        from ..utils.zep_paging import fetch_all_nodes

        return fetch_all_nodes(self.client, graph_id)

    def _fetch_all_edges(self, graph_id: str):
        from ..utils.zep_paging import fetch_all_edges

        return fetch_all_edges(self.client, graph_id)

    def _graph_state(self, graph_id: str) -> Dict[str, Any]:
        return self._graph_context.setdefault(graph_id, {})

    def _set_graph_state(self, graph_id: str, **updates: Any) -> None:
        state = self._graph_state(graph_id)
        state.update(updates)

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        异步构建图谱

        Args:
            text: 输入文本
            ontology: 本体定义（来自接口1的输出）
            graph_name: 图谱名称
            chunk_size: 文本块大小
            chunk_overlap: 块重叠大小
            batch_size: 每批发送的块数量

        Returns:
            任务ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int
    ):
        """图谱构建工作线程"""
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="开始构建图谱..."
            )

            graph_id = self.create_graph(graph_name)
            self._set_graph_state(
                graph_id,
                graph_name=graph_name,
                ontology=ontology,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                project_id=graph_id,
            )
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"图谱已创建: {graph_id}"
            )

            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="本体已设置"
            )

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"文本已分割为 {total_chunks} 个块"
            )

            episode_uuids = self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),
                    message=msg
                )
            )

            self.task_manager.update_task(
                task_id,
                progress=60,
                message="等待图谱处理数据..."
            )

            self._wait_for_episodes(
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),
                    message=msg
                )
            )

            self.task_manager.update_task(
                task_id,
                progress=90,
                message="获取图谱信息..."
            )

            graph_info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """创建图谱（公开方法）"""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"

        if self.backend == "graphiti":
            self._set_graph_state(
                graph_id,
                graph_name=name,
                chunk_size=Config.DEFAULT_CHUNK_SIZE,
                chunk_overlap=Config.DEFAULT_CHUNK_OVERLAP,
                ontology={"entity_types": [], "edge_types": []},
                project_id=graph_id,
            )
            return graph_id

        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="MiroFish Social Simulation Graph"
        )

        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """设置图谱本体（公开方法）"""
        if self.backend == "graphiti":
            self._set_graph_state(graph_id, ontology=ontology)
            return

        import warnings
        from typing import Optional

        from pydantic import Field
        from zep_cloud import EntityEdgeSourceTarget
        from zep_cloud.external_clients.ontology import EdgeModel, EntityModel, EntityText

        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

        reserved_names = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}

        def safe_attr_name(attr_name: str) -> str:
            if attr_name.lower() in reserved_names:
                return f"entity_{attr_name}"
            return attr_name

        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")

            attrs = {"__doc__": description}
            annotations = {}

            for attr_def in entity_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])
                attr_desc = attr_def.get("description", attr_name)
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText]

            attrs["__annotations__"] = annotations

            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class

        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")

            attrs = {"__doc__": description}
            annotations = {}

            for attr_def in edge_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])
                attr_desc = attr_def.get("description", attr_name)
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str]

            attrs["__annotations__"] = annotations

            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description

            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_targets.append(
                    EntityEdgeSourceTarget(
                        source=st.get("source", "Entity"),
                        target=st.get("target", "Entity")
                    )
                )

            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)

        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=entity_types if entity_types else None,
                edges=edge_definitions if edge_definitions else None,
            )

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """分批添加文本到图谱，返回所有 episode 或 job 的 id 列表"""
        if self.backend == "graphiti":
            state = self._graph_state(graph_id)
            payload = {
                "project_id": state.get("project_id", graph_id),
                "graph_name": state.get("graph_name", "MiroFish Graph"),
                "document_text": "\n\n".join(chunk for chunk in chunks if chunk),
                "chunk_size": state.get("chunk_size", Config.DEFAULT_CHUNK_SIZE),
                "chunk_overlap": state.get("chunk_overlap", Config.DEFAULT_CHUNK_OVERLAP),
                "ontology": state.get("ontology", {"entity_types": [], "edge_types": []}),
            }
            if progress_callback:
                progress_callback("提交 graph-service 构建任务...", 0.5)
            result = self.client.build_graph(graph_id, payload)
            if progress_callback:
                progress_callback("graph-service 构建任务已提交", 1.0)
            job_id = result.get("job_id")
            return [job_id] if job_id else []

        episode_uuids = []
        total_chunks = len(chunks)

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    f"发送第 {batch_num}/{total_batches} 批数据 ({len(batch_chunks)} 块)...",
                    progress
                )

            from zep_cloud import EpisodeData

            episodes = [
                EpisodeData(data=chunk, type="text")
                for chunk in batch_chunks
            ]

            try:
                batch_result = self.client.graph.add_batch(
                    graph_id=graph_id,
                    episodes=episodes
                )

                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)

                time.sleep(1)

            except Exception as e:
                if progress_callback:
                    progress_callback(f"批次 {batch_num} 发送失败: {str(e)}", 0)
                raise

        return episode_uuids

    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """等待所有 episode 或 graph-service 构建任务完成"""
        if self.backend == "graphiti":
            if progress_callback:
                progress_callback("graph-service 构建任务已排队", 1.0)
            return

        if not episode_uuids:
            if progress_callback:
                progress_callback("无需等待（没有 episode）", 1.0)
            return

        start_time = time.time()
        pending_episodes = set(episode_uuids)
        completed_count = 0
        total_episodes = len(episode_uuids)

        if progress_callback:
            progress_callback(f"开始等待 {total_episodes} 个文本块处理...", 0)

        while pending_episodes:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        f"部分文本块超时，已完成 {completed_count}/{total_episodes}",
                        completed_count / total_episodes
                    )
                break

            for ep_uuid in list(pending_episodes):
                try:
                    episode = self.client.graph.episode.get(uuid_=ep_uuid)
                    is_processed = getattr(episode, 'processed', False)

                    if is_processed:
                        pending_episodes.remove(ep_uuid)
                        completed_count += 1

                except Exception:
                    pass

            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(
                    f"Zep处理中... {completed_count}/{total_episodes} 完成, {len(pending_episodes)} 待处理 ({elapsed}秒)",
                    completed_count / total_episodes if total_episodes > 0 else 0
                )

            if pending_episodes:
                time.sleep(3)

        if progress_callback:
            progress_callback(f"处理完成: {completed_count}/{total_episodes}", 1.0)

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱信息"""
        if self.backend == "graphiti":
            snapshot = self.client.get_snapshot(graph_id)
            nodes = snapshot.get("nodes", [])
            entity_types = set()
            for node in nodes:
                for label in node.get("labels", []):
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)
            return GraphInfo(
                graph_id=graph_id,
                node_count=snapshot.get("node_count", len(nodes)),
                edge_count=snapshot.get("edge_count", len(snapshot.get("edges", []))),
                entity_types=sorted(entity_types),
            )

        nodes = self._fetch_all_nodes(graph_id)
        edges = self._fetch_all_edges(graph_id)

        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        获取完整图谱数据（包含详细信息）

        Args:
            graph_id: 图谱ID

        Returns:
            包含nodes和edges的字典，包括时间信息、属性等详细数据
        """
        if self.backend == "graphiti":
            snapshot = self.client.get_snapshot(graph_id)
            nodes = snapshot.get("nodes", [])
            edges = snapshot.get("edges", [])
            return {
                "graph_id": snapshot.get("graph_id", graph_id),
                "nodes": nodes,
                "edges": edges,
                "node_count": snapshot.get("node_count", len(nodes)),
                "edge_count": snapshot.get("edge_count", len(edges)),
            }

        nodes = self._fetch_all_nodes(graph_id)
        edges = self._fetch_all_edges(graph_id)

        node_map = {}
        for node in nodes:
            node_map[node.uuid_] = node.name or ""

        nodes_data = []
        for node in nodes:
            created_at = getattr(node, 'created_at', None)
            if created_at:
                created_at = str(created_at)

            nodes_data.append({
                "uuid": node.uuid_,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": created_at,
            })

        edges_data = []
        for edge in edges:
            created_at = getattr(edge, 'created_at', None)
            valid_at = getattr(edge, 'valid_at', None)
            invalid_at = getattr(edge, 'invalid_at', None)
            expired_at = getattr(edge, 'expired_at', None)

            episodes = getattr(edge, 'episodes', None) or getattr(edge, 'episode_ids', None)
            if episodes and not isinstance(episodes, list):
                episodes = [str(episodes)]
            elif episodes:
                episodes = [str(e) for e in episodes]

            fact_type = getattr(edge, 'fact_type', None) or edge.name or ""

            edges_data.append({
                "uuid": edge.uuid_,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": fact_type,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            })

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        """删除图谱"""
        if self.backend == "graphiti":
            raise NotImplementedError("Graph deletion is not supported for graphiti backend in v1")
        self.client.graph.delete(graph_id=graph_id)
