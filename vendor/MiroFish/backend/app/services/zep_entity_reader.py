"""
Zep实体读取与过滤服务
文件名保留不变，但实现可按后端切换
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

from ..config import Config
from ..utils.logger import get_logger
from .graph_backend_client import GraphBackendClient

logger = get_logger('mirofish.zep_entity_reader')

T = TypeVar('T')


@dataclass
class EntityNode:
    """实体节点数据结构"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """获取实体类型（排除默认的Entity标签）"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """过滤后的实体集合"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    实体读取与过滤服务

    主要功能：
    1. 从图谱读取所有节点
    2. 筛选出符合预定义实体类型的节点
    3. 获取每个实体的相关边和关联节点信息
    """

    def __init__(self, api_key: Optional[str] = None):
        self.backend = Config.GRAPH_BACKEND
        self.api_key = api_key or Config.ZEP_API_KEY
        self._active_graph_id: Optional[str] = None

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

    def _call_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        带重试机制的Zep API调用
        """
        last_exception = None
        delay = initial_delay

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} 第 {attempt + 1} 次尝试失败: {str(e)[:100]}, "
                        f"{delay:.1f}秒后重试..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Zep {operation_name} 在 {max_retries} 次尝试后仍失败: {str(e)}")

        raise last_exception

    def _custom_labels(self, labels: List[str]) -> List[str]:
        return [label for label in labels if label not in ["Entity", "Node"]]

    def _build_entity_node(
        self,
        entity_data: Dict[str, Any],
        *,
        enrich_with_edges: bool = True,
    ) -> EntityNode:
        related_edges = entity_data.get("related_edges", []) if enrich_with_edges else []
        related_nodes = entity_data.get("related_nodes", []) if enrich_with_edges else []
        return EntityNode(
            uuid=entity_data.get("uuid", ""),
            name=entity_data.get("name", ""),
            labels=entity_data.get("labels", []) or [],
            summary=entity_data.get("summary", "") or "",
            attributes=entity_data.get("attributes", {}) or {},
            related_edges=related_edges,
            related_nodes=related_nodes,
        )

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        获取图谱的所有节点
        """
        self._active_graph_id = graph_id
        logger.info(f"获取图谱 {graph_id} 的所有节点...")

        if self.backend == "graphiti":
            snapshot = self.client.get_snapshot(graph_id)
            nodes_data = []
            for node in snapshot.get("nodes", []):
                nodes_data.append({
                    "uuid": node.get("uuid", ""),
                    "name": node.get("name", "") or "",
                    "labels": node.get("labels", []) or [],
                    "summary": node.get("summary", "") or "",
                    "attributes": node.get("attributes", {}) or {},
                })
            logger.info(f"共获取 {len(nodes_data)} 个节点")
            return nodes_data

        nodes = self._fetch_all_nodes(graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"共获取 {len(nodes_data)} 个节点")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        获取图谱的所有边
        """
        self._active_graph_id = graph_id
        logger.info(f"获取图谱 {graph_id} 的所有边...")

        if self.backend == "graphiti":
            snapshot = self.client.get_snapshot(graph_id)
            edges_data = []
            for edge in snapshot.get("edges", []):
                edges_data.append({
                    "uuid": edge.get("uuid", ""),
                    "name": edge.get("name", "") or "",
                    "fact": edge.get("fact", "") or "",
                    "source_node_uuid": edge.get("source_node_uuid", ""),
                    "target_node_uuid": edge.get("target_node_uuid", ""),
                    "attributes": edge.get("attributes", {}) or {},
                })
            logger.info(f"共获取 {len(edges_data)} 条边")
            return edges_data

        edges = self._fetch_all_edges(graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"共获取 {len(edges_data)} 条边")
        return edges_data

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        获取指定节点的所有相关边
        """
        if self.backend == "graphiti":
            if not self._active_graph_id:
                return []
            try:
                detail = self.client.get_entity_detail(self._active_graph_id, node_uuid)
            except Exception as e:
                logger.warning(f"获取节点 {node_uuid} 的边失败: {str(e)}")
                return []

            edges_data = []
            for edge in detail.get("related_edges", []):
                edges_data.append({
                    "uuid": edge.get("uuid", ""),
                    "name": edge.get("edge_name", "") or edge.get("name", "") or "",
                    "fact": edge.get("fact", "") or "",
                    "source_node_uuid": edge.get("source_node_uuid", node_uuid),
                    "target_node_uuid": edge.get("target_node_uuid", node_uuid),
                    "attributes": edge.get("attributes", {}) or {},
                })
            return edges_data

        try:
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"获取节点边(node={node_uuid[:8]}...)"
            )

            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })

            return edges_data
        except Exception as e:
            logger.warning(f"获取节点 {node_uuid} 的边失败: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        筛选出符合预定义实体类型的节点
        """
        self._active_graph_id = graph_id
        logger.info(f"开始筛选图谱 {graph_id} 的实体...")

        if self.backend == "graphiti":
            params = None
            if defined_entity_types and len(defined_entity_types) == 1:
                params = {"entity_type": defined_entity_types[0]}

            payload = self.client.get_entities(graph_id, params=params)
            entities_data = payload.get("entities", [])
            filtered_entities = []
            entity_types_found = set()

            for entity_data in entities_data:
                labels = entity_data.get("labels", []) or []
                custom_labels = self._custom_labels(labels)
                if not custom_labels:
                    continue

                if defined_entity_types:
                    matching_labels = [label for label in custom_labels if label in defined_entity_types]
                    if not matching_labels:
                        continue
                    entity_types_found.update(matching_labels)
                else:
                    entity_types_found.update(custom_labels)

                filtered_entities.append(
                    self._build_entity_node(entity_data, enrich_with_edges=enrich_with_edges)
                )

            logger.info(
                f"筛选完成: 总节点 {payload.get('total_count', len(entities_data))}, "
                f"符合条件 {len(filtered_entities)}, 实体类型: {entity_types_found}"
            )
            return FilteredEntities(
                entities=filtered_entities,
                entity_types=entity_types_found,
                total_count=payload.get("total_count", len(entities_data)),
                filtered_count=len(filtered_entities),
            )

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities = []
        entity_types_found = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom_labels = self._custom_labels(labels)

            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })

                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"筛选完成: 总节点 {total_count}, 符合条件 {len(filtered_entities)}, "
                    f"实体类型: {entity_types_found}")

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        获取单个实体及其完整上下文
        """
        self._active_graph_id = graph_id

        if self.backend == "graphiti":
            try:
                payload = self.client.get_entity_detail(graph_id, entity_uuid)
            except Exception as e:
                logger.error(f"获取实体 {entity_uuid} 失败: {str(e)}")
                return None

            if not payload:
                return None
            return self._build_entity_node(payload, enrich_with_edges=True)

        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"获取节点详情(uuid={entity_uuid[:8]}...)"
            )

            if not node:
                return None

            edges = self.get_node_edges(entity_uuid)
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}

            related_edges = []
            related_node_uuids = set()

            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })

            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"获取实体 {entity_uuid} 失败: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        获取指定类型的所有实体
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
