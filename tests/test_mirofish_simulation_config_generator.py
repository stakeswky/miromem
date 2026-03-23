from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_simulation_config_module():
    module_name = "app.services.simulation_config_generator"
    if module_name in sys.modules:
        return sys.modules[module_name]

    path = Path("vendor/MiroFish/backend/app/services/simulation_config_generator.py")

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = []
    services_pkg = types.ModuleType("app.services")
    services_pkg.__path__ = []
    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = []
    sys.modules["app"] = app_pkg
    sys.modules["app.services"] = services_pkg
    sys.modules["app.utils"] = utils_pkg

    config_mod = types.ModuleType("app.config")

    class Config:
        LLM_API_KEY = "test-key"
        LLM_BASE_URL = "http://example.com/v1"
        LLM_MODEL_NAME = "test-model"

    config_mod.Config = Config
    sys.modules["app.config"] = config_mod

    logger_mod = types.ModuleType("app.utils.logger")

    class DummyLogger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

        def debug(self, *args, **kwargs):
            return None

    logger_mod.get_logger = lambda name=None: DummyLogger()
    sys.modules["app.utils.logger"] = logger_mod

    zep_mod = types.ModuleType("app.services.zep_entity_reader")

    class EntityNode:
        def __init__(self, name="Entity", summary="Summary", uuid="entity-1", entity_type="Person"):
            self.name = name
            self.summary = summary
            self.uuid = uuid
            self._entity_type = entity_type

        def get_entity_type(self):
            return self._entity_type

    class ZepEntityReader:
        pass

    zep_mod.EntityNode = EntityNode
    zep_mod.ZepEntityReader = ZepEntityReader
    sys.modules["app.services.zep_entity_reader"] = zep_mod

    openai_mod = types.ModuleType("openai")

    class OpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_mod.OpenAI = OpenAI
    sys.modules["openai"] = openai_mod

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MODULE = _load_simulation_config_module()
SimulationConfigGenerator = MODULE.SimulationConfigGenerator
AgentActivityConfig = MODULE.AgentActivityConfig
EventConfig = MODULE.EventConfig
EntityNode = sys.modules["app.services.zep_entity_reader"].EntityNode


def _make_generator() -> SimulationConfigGenerator:
    generator = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
    generator.AGENTS_PER_BATCH = 15
    generator.MAX_CONTEXT_LENGTH = 50000
    generator.TIME_CONFIG_CONTEXT_LENGTH = 10000
    generator.EVENT_CONFIG_CONTEXT_LENGTH = 8000
    generator.ENTITY_SUMMARY_LENGTH = 300
    generator.AGENT_SUMMARY_LENGTH = 300
    generator.ENTITIES_PER_TYPE_DISPLAY = 20
    generator.model_name = "test-model"
    generator.base_url = "http://example.com/v1"
    return generator


def test_generate_config_falls_back_when_llm_returns_float():
    generator = _make_generator()
    generator._build_context = lambda **kwargs: "context"
    generator._generate_time_config = lambda context, num_entities: 0.5
    generator._generate_event_config = lambda context, simulation_requirement, entities: {
        "initial_posts": [],
        "hot_topics": [],
        "narrative_direction": "",
    }
    generator._generate_agent_configs_batch = lambda **kwargs: []
    generator._assign_initial_post_agents = lambda event_config, agent_configs: event_config

    params = generator.generate_config(
        simulation_id="sim-1",
        project_id="proj-1",
        graph_id="graph-1",
        simulation_requirement="test requirement",
        document_text="document",
        entities=[EntityNode()],
    )

    assert params.time_config.total_simulation_hours == 72
    assert params.event_config.initial_posts == []
    assert "时间配置" in params.generation_reasoning


def test_assign_initial_post_agents_skips_non_mapping_posts():
    generator = _make_generator()
    event_config = EventConfig(
        initial_posts=[0.5, {"content": "hello", "poster_type": "person"}],
        hot_topics=[],
        narrative_direction="",
    )
    agent_configs = [
        AgentActivityConfig(
            agent_id=7,
            entity_uuid="entity-7",
            entity_name="Alice",
            entity_type="Person",
        )
    ]

    updated = generator._assign_initial_post_agents(event_config, agent_configs)

    assert updated.initial_posts == [
        {"content": "hello", "poster_type": "person", "poster_agent_id": 7}
    ]
