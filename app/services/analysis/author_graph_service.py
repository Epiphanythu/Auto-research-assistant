"""author_graph_service 作者机构图谱构建。"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models.research_models import Paper


class AuthorGraphService:
    """AuthorGraphService 基于论文列表构建作者-机构共现图谱。"""

    def build(self, papers: List[Paper]) -> Dict[str, Any]:
        """build 构建作者-机构图谱（节点 + 边）。"""
        # 1. 累计节点权重（出现次数）和边权重（共现次数）
        node_weights: Dict[str, Dict[str, Any]] = {}
        edge_weights: Dict[tuple, int] = {}
        for paper in papers or []:
            authors = [name.strip() for name in paper.authors if name and name.strip()]
            affiliations = [
                inst.strip() for inst in paper.affiliations if inst and inst.strip()
            ]
            # 1.1 作者节点 & 机构节点累计
            for name in authors:
                node_id = self._build_node_id("author", name)
                self._touch_node(node_weights, node_id, "author", name)
            for inst in affiliations:
                node_id = self._build_node_id("institution", inst)
                self._touch_node(node_weights, node_id, "institution", inst)
            # 1.2 作者-机构边
            for name in authors:
                author_id = self._build_node_id("author", name)
                for inst in affiliations:
                    inst_id = self._build_node_id("institution", inst)
                    self._touch_edge(edge_weights, author_id, inst_id)
            # 1.3 作者-作者共著边（同篇论文内两两连接）
            for i in range(len(authors)):
                src_id = self._build_node_id("author", authors[i])
                for j in range(i + 1, len(authors)):
                    tgt_id = self._build_node_id("author", authors[j])
                    self._touch_edge(edge_weights, src_id, tgt_id)
        # 2. 构造序列化结果
        nodes = [
            {
                "id": node_id,
                "type": payload["type"],
                "label": payload["label"],
                "weight": payload["weight"],
            }
            for node_id, payload in node_weights.items()
        ]
        edges = [
            {"source": src, "target": tgt, "weight": weight}
            for (src, tgt), weight in edge_weights.items()
        ]
        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _build_node_id(node_type: str, label: str) -> str:
        """_build_node_id 生成稳定的节点 ID。"""
        return f"{node_type}::{label.strip().lower()}"

    @staticmethod
    def _touch_node(
        node_weights: Dict[str, Dict[str, Any]],
        node_id: str,
        node_type: str,
        label: str,
    ) -> None:
        """_touch_node 累加节点出现次数。"""
        existing = node_weights.get(node_id)
        if existing is None:
            node_weights[node_id] = {"type": node_type, "label": label, "weight": 1}
        else:
            existing["weight"] += 1

    @staticmethod
    def _touch_edge(
        edge_weights: Dict[tuple, int],
        source: str,
        target: str,
    ) -> None:
        """_touch_edge 累加边权重，按字典序统一无向边方向。"""
        if source == target:
            return
        key = (source, target) if source < target else (target, source)
        edge_weights[key] = edge_weights.get(key, 0) + 1
