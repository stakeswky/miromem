"""Helpers for normalizing Thinker results into final simulation inputs."""

from __future__ import annotations

from miromem.thinker.models import (
    ThinkerAdoptedInput,
    ThinkerMaterializedPayload,
    ThinkerResult,
)


class ThinkerMaterializer:
    """Merge stored Thinker output with user-adopted overrides."""

    def materialize(
        self,
        *,
        result: ThinkerResult | None,
        adopted: ThinkerAdoptedInput,
    ) -> ThinkerMaterializedPayload:
        stored = result or ThinkerResult()
        return ThinkerMaterializedPayload(
            final_topics=(
                adopted.expanded_topics
                if adopted.expanded_topics is not None
                else stored.expanded_topics
            ),
            final_seed_text=(
                adopted.enriched_seed_text
                if adopted.enriched_seed_text is not None
                else stored.enriched_seed_text
            ),
            final_simulation_requirement=(
                adopted.suggested_simulation_prompt
                if adopted.suggested_simulation_prompt is not None
                else stored.suggested_simulation_prompt
            ),
        )
