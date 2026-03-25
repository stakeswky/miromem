# MiroMem — Memory-Driven Prediction Engine

**MiroMem** fuses [EverMemOS](https://github.com/EverMind-AI/EverMemOS) (memory operating system) with [MiroFish](https://github.com/666ghj/MiroFish) (multi-agent prediction engine) into a unified platform where AI agents build persistent memory, extract knowledge graphs, and evolve across simulations.

**MiroMem** 将 [EverMemOS](https://github.com/EverMind-AI/EverMemOS)（记忆操作系统）与 [MiroFish](https://github.com/666ghj/MiroFish)（多智能体预测引擎）融合为统一平台，使 AI 智能体能够构建持久记忆、提取知识图谱，并在跨模拟中持续进化。

## Architecture / 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    MiroMem Gateway (:8000)                   │
│              FastAPI — unified API entry point                │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Bridge  │  Graph   │Simulation│Evolution │    Proxy to     │
│  Module  │Extension │ Memory   │  Engine  │ EverMemOS/Fish  │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│                                                              │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  EverMemOS (:1995)  │    │  MiroFish Backend (:5001)   │ │
│  │  Memory OS Layer    │    │  Multi-Agent Simulation     │ │
│  └────────┬────────────┘    └──────────┬──────────────────┘ │
│           │                            │                     │
├───────────┴────────────────────────────┴─────────────────────┤
│              Shared Infrastructure                            │
│  MongoDB(:27017)  Milvus(:19530)  ES(:9200)  Redis(:6379)   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start / 快速开始

### Prerequisites / 前置条件

- Docker & Docker Compose
- Git
- API keys for LLM, Embedding, and Reranker providers (see `.env.template`)

### Setup / 部署

```bash
# Clone the repository
git clone <repo-url> && cd miromem

# One-click setup (clones vendors, creates .env, starts stack)
bash scripts/setup.sh

# Or manually:
git clone https://github.com/EverMind-AI/EverMemOS.git vendor/EverMemOS
git clone https://github.com/666ghj/MiroFish.git vendor/MiroFish
cp .env.template .env   # edit with your API keys
docker compose up -d

# Run the demo
python scripts/demo.py
```

### Graphiti Rollout

Start the internal graph path with `docker compose up -d --build graph-service falkordb`, or let `docker compose up -d --build` bring those services up alongside the rest of the stack. `mirofish` reaches Graphiti through `GRAPH_SERVICE_BASE_URL=http://graph-service:8001`, while Gateway keeps its current proxy paths unchanged.

To enable the Graphiti path, set the following in `.env` before starting or rebuilding the stack:

```bash
GRAPH_BACKEND=graphiti
GRAPH_SERVICE_BASE_URL=http://graph-service:8001
FALKORDB_HOST=falkordb
FALKORDB_PORT=6379
```

To roll back to the previous Zep-backed path, set `GRAPH_BACKEND=zep` and restart the stack with `docker compose up -d --build`. This keeps the existing MiroFish flow in place while disabling the Graphiti backend wiring.

Thinker remains upstream and unchanged. It still enriches inputs before the normal graph build and simulation flow, and it does not take on any Graphiti-specific or FalkorDB-specific configuration.

<!-- PLACEHOLDER_MODULES -->

## Modules / 模块概览

### 1. Gateway (`miromem/gateway/`)
Unified FastAPI entry point. Proxies requests to EverMemOS and MiroFish, and hosts native MiroMem extensions (Graph, Evolution).

统一 FastAPI 入口。代理请求到 EverMemOS 和 MiroFish，并托管 MiroMem 原生扩展（图谱、进化）。

### 2. Bridge (`miromem/bridge/`)
Adapter layer replacing Zep Cloud with EverMemOS. Provides `EverMemClient` (async HTTP wrapper) and `ZepAdapter` (Zep-compatible interface backed by EverMemOS).

适配层，用 EverMemOS 替代 Zep Cloud。提供 `EverMemClient`（异步 HTTP 封装）和 `ZepAdapter`（基于 EverMemOS 的 Zep 兼容接口）。

### 3. Graph (`miromem/graph/`)
Self-hosted knowledge graph (GraphRAG) replacing Zep Cloud's graph. Entity/relationship extraction via LLM, MongoDB storage, hybrid search combining vector similarity with graph traversal.

自托管知识图谱（GraphRAG），替代 Zep Cloud 的图谱功能。通过 LLM 进行实体/关系抽取，MongoDB 存储，向量相似度 + 图遍历的混合检索。

### 4. Simulation (`miromem/simulation/`)
Memory hooks for MiroFish simulation lifecycle. Syncs agent profiles, provides memory context during simulation rounds, and captures memories at simulation boundaries.

MiroFish 模拟生命周期的记忆钩子。同步 Agent 档案，在模拟轮次中提供记忆上下文，并在模拟边界捕获记忆。

### 5. Evolution (`miromem/evolution/`)
Cross-simulation memory persistence and agent evolution. Memories survive across simulations with importance scoring, time decay, and foresight prediction validation.

跨模拟记忆持久化与 Agent 进化。记忆通过重要性评分、时间衰减和预见性预测验证在模拟间持续存在。

### 6. Tests (`miromem/tests/`)
Integration and unit tests for all modules.

所有模块的集成测试和单元测试。

<!-- PLACEHOLDER_API -->

## API Reference / API 参考

All endpoints are served through the Gateway at `http://localhost:8000`.

### Memory (proxied to EverMemOS)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/memories` | Store a memory |
| GET | `/api/v1/memories/search` | Search memories (hybrid/vector/keyword) |
| GET | `/api/v1/memories` | List memories for a user |
| DELETE | `/api/v1/memories` | Delete memories |

### Knowledge Graph (native)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/graph/ingest` | Ingest documents → extract entities/edges |
| POST | `/api/v1/graph/search` | Hybrid graph + vector search |
| GET | `/api/v1/graph/context/{name}` | Entity context with neighbors + facts |
| POST/GET/PUT/DELETE | `/api/v1/graph/entities/...` | Entity CRUD |
| POST/GET/DELETE | `/api/v1/graph/edges/...` | Edge CRUD |
| GET | `/api/v1/graph/neighbors/{id}` | Graph traversal |
| GET | `/api/v1/graph/path/{src}/{tgt}` | Shortest path |

### Evolution (native)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/evolution/inject` | Inject historical memories for new sim |
| POST | `/api/v1/evolution/mark` | Mark memories as cross-sim available |
| GET | `/api/v1/evolution/history/{agent}` | Agent evolution summary |
| POST | `/api/v1/evolution/validate/{sim_id}` | Validate foresight predictions |
| GET | `/api/v1/evolution/predictions` | Prediction accuracy history |
| GET | `/api/v1/evolution/simulations` | List past simulations |

### Simulation (proxied to MiroFish)
| Method | Endpoint | Description |
|--------|----------|-------------|
| * | `/api/simulation/*` | MiroFish simulation API |
| * | `/api/graph/*` | MiroFish ontology graph API |
| * | `/api/report/*` | MiroFish report API |

<!-- PLACEHOLDER_CONFIG -->

## Configuration / 配置

Copy `.env.template` to `.env` and fill in your values. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | OpenAI-compatible LLM API key | — |
| `LLM_BASE_URL` | LLM provider base URL | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Model name | `x-ai/grok-4-fast` |
| `EMBEDDING_API_KEY` | Embedding model API key | — |
| `EMBEDDING_MODEL` | Embedding model name | `Qwen/Qwen3-Embedding-4B` |
| `GRAPH_BACKEND` | Graph backend switch for MiroFish rollout | `zep` |
| `GRAPH_SERVICE_BASE_URL` | Internal URL used by MiroFish to reach graph-service | `http://graph-service:8001` |
| `FALKORDB_HOST` | FalkorDB host for graph-service | `falkordb` |
| `MONGODB_URI` | MongoDB connection string | `mongodb://root:miromem@mongodb:27017` |
| `MONGODB_DB` | Database name | `miromem` |
| `MILVUS_HOST` | Milvus vector DB host | `milvus-standalone` |
| `EVERMEMOS_HOST` | EverMemOS service host | `evermemos` |
| `MIROFISH_HOST` | MiroFish backend host | `mirofish-backend` |

See `.env.template` for the complete list.

完整变量列表请参考 `.env.template`。

## License / 许可证

MiroMem is licensed under **AGPL-3.0**.

MiroMem 采用 **AGPL-3.0** 许可证。

- **EverMemOS** is licensed under Apache 2.0. MiroMem communicates with EverMemOS exclusively via its REST API, maintaining license compatibility.
- **MiroFish** — see its repository for license terms.

- **EverMemOS** 采用 Apache 2.0 许可证。MiroMem 仅通过 REST API 与 EverMemOS 通信，保持许可证兼容性。
- **MiroFish** — 请参阅其仓库的许可证条款。
