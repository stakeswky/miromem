"""Foresight memory validation — compare predictions against simulation outcomes."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from openai import AsyncOpenAI

from miromem.bridge.memory_client import EverMemClient
from miromem.config.settings import load_config

logger = logging.getLogger(__name__)


class ForesightValidator:
    """Validates Foresight predictions against actual simulation results."""

    def __init__(
        self,
        db: AsyncIOMotorDatabase | None = None,
        evermem_client: EverMemClient | None = None,
    ) -> None:
        cfg = load_config()
        if db is not None:
            self._db = db
        else:
            client: AsyncIOMotorClient = AsyncIOMotorClient(cfg.infra.mongodb_uri)
            self._db = client[cfg.infra.mongodb_db]

        self._col = self._db["foresight_validations"]
        self._evermem = evermem_client or EverMemClient()
        self._llm = AsyncOpenAI(api_key=cfg.llm.api_key, base_url=cfg.llm.base_url)
        self._model = cfg.llm.model

    async def ensure_indexes(self) -> None:
        await self._col.create_index("sim_id")
        await self._col.create_index("agent_id")

    # --- Core validation ---

    async def validate_predictions(self, sim_id: str) -> dict[str, Any]:
        """Compare Foresight predictions with actual outcomes for a simulation.

        Retrieves Foresight memories via EverMemOS, fetches actual outcomes
        (EpisodicMemory / EventLog), and uses LLM to score semantic similarity.
        """
        # Fetch foresight predictions tagged with this sim
        predictions: list[dict[str, Any]] = []
        try:
            predictions = await self._evermem.search_memories(
                query=f"simulation {sim_id}",
                user_id=sim_id,
                memory_type="Foresight",
                top_k=50,
            )
        except Exception:
            logger.warning("Failed to fetch Foresight memories for sim %s", sim_id)

        if not predictions:
            return {"sim_id": sim_id, "predictions": 0, "accuracy": None, "detail": []}

        # Fetch actual outcomes
        outcomes: list[dict[str, Any]] = []
        try:
            outcomes = await self._evermem.get_memories(
                user_id=sim_id, memory_type="EpisodicMemory",
            )
        except Exception:
            logger.warning("Failed to fetch outcomes for sim %s", sim_id)

        accuracy = await self.compute_accuracy(predictions, outcomes)

        # Persist validation result
        record = {
            "sim_id": sim_id,
            "validated_at": datetime.now(timezone.utc),
            **accuracy,
        }
        await self._col.insert_one(record)

        feedback = self.generate_feedback(accuracy)
        return {"sim_id": sim_id, **accuracy, "feedback": feedback}

    async def compute_accuracy(
        self,
        predictions: list[dict[str, Any]],
        outcomes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Score each prediction against outcomes using LLM semantic comparison."""
        if not predictions or not outcomes:
            return {"predictions": len(predictions), "outcomes": len(outcomes), "detail": []}

        outcome_text = "\n".join(
            o.get("content", "")[:200] for o in outcomes[:30]
        )

        detail: list[dict[str, Any]] = []
        total_score = 0.0

        for pred in predictions:
            pred_content = pred.get("content", "")
            if not pred_content:
                continue

            score = await self._score_prediction(pred_content, outcome_text)
            detail.append({
                "prediction": pred_content[:200],
                "similarity": score,
                "accurate": score >= 0.7,
            })
            total_score += score

        n = len(detail) or 1
        return {
            "predictions": len(predictions),
            "outcomes": len(outcomes),
            "exact_match_rate": sum(1 for d in detail if d["accurate"]) / n,
            "semantic_similarity_avg": total_score / n,
            "detail": detail,
        }

    @staticmethod
    def generate_feedback(validation_results: dict[str, Any]) -> str:
        """Produce human-readable feedback for improving Foresight extraction."""
        avg = validation_results.get("semantic_similarity_avg", 0)
        exact = validation_results.get("exact_match_rate", 0)
        n = validation_results.get("predictions", 0)

        lines = [f"Validated {n} predictions."]
        lines.append(f"Semantic similarity avg: {avg:.2%}")
        lines.append(f"Exact match rate (>=0.7): {exact:.2%}")

        if avg < 0.4:
            lines.append("Recommendation: Foresight extraction is producing low-accuracy predictions. "
                         "Consider narrowing prediction scope or increasing context window.")
        elif avg < 0.7:
            lines.append("Recommendation: Moderate accuracy. Review prediction categories with "
                         "lowest scores and refine extraction prompts for those topics.")
        else:
            lines.append("Foresight predictions are performing well. Maintain current strategy.")

        return "\n".join(lines)

    async def get_prediction_history(
        self,
        *,
        agent_id: str | None = None,
        topic: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historical prediction accuracy tracking."""
        query: dict[str, Any] = {}
        if agent_id:
            query["agent_id"] = agent_id
        if topic:
            query["detail.prediction"] = {"$regex": topic, "$options": "i"}

        cursor = self._col.find(query).sort("validated_at", -1).limit(limit)
        results: list[dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    # --- Internal ---

    async def _score_prediction(self, prediction: str, outcomes_text: str) -> float:
        """Use LLM to score how well a prediction matches actual outcomes (0-1)."""
        prompt = (
            "Rate how accurately the following prediction matches the actual outcomes. "
            "Return ONLY a JSON object: {\"score\": <float 0.0 to 1.0>}\n\n"
            f"Prediction: {prediction}\n\n"
            f"Actual outcomes:\n{outcomes_text[:2000]}"
        )
        try:
            resp = await self._llm.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            data = json.loads(raw)
            return float(data.get("score", 0.0))
        except Exception:
            logger.warning("LLM scoring failed, defaulting to 0.0")
            return 0.0
