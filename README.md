# OpenClaw Mission Control

[![CI](https://github.com/abhi1693/openclaw-mission-control/actions/workflows/ci.yml/badge.svg)](https://github.com/abhi1693/openclaw-mission-control/actions/workflows/ci.yml) ![Static Badge](https://img.shields.io/badge/Join-Slack-active?style=flat&color=blue&link=https%3A%2F%2Fjoin.slack.com%2Ft%2Foc-mission-control%2Fshared_invite%2Fzt-3qpcm57xh-AI9C~smc3MDBVzEhvwf7gg)

OpenClaw Mission Control is the centralized operations and governance platform for running OpenClaw across teams and organizations, with unified visibility, approval controls, and gateway-aware orchestration.
It gives operators a single interface for work orchestration, agent and gateway management, approval-driven governance, and API-backed automation.

This fork extends the upstream project with a **Trust Zones governance layer** — a programmable delegation framework that adds hierarchical RBAC, intelligent human-in-the-loop approval workflows, escalation chains, and democratic decision-making to the existing agent orchestration platform. See [`AGENT_PROMPT_trust_zones_build.md`](../AGENT_PROMPT_trust_zones_build.md) for the full design specification that guided this implementation.

<img width="1896" height="869" alt="Mission Control dashboard" src="https://github.com/user-attachments/assets/49a3c823-6aaf-4c56-8328-fb1485ee940f" />
<img width="1896" height="858" alt="image" src="https://github.com/user-attachments/assets/2bfee13a-3dab-4f4a-9135-e47bb6949dcf" />
<img width="1890" height="865" alt="image" src="https://github.com/user-attachments/assets/84c2e867-5dc7-4a36-9290-e29179d2a659" />
<img width="1912" height="881" alt="image" src="https://github.com/user-attachments/assets/3bbd825c-9969-4bbf-bf31-987f9168f370" />
<img width="1902" height="878" alt="image" src="https://github.com/user-attachments/assets/eea09632-60e4-4d6d-9e6e-bdfa0ac97630" />

## Platform overview

Mission Control is designed to be the day-to-day operations surface for OpenClaw.
Instead of splitting work across multiple tools, teams can plan, execute, review, and audit activity in one system.

Core operational areas:

- Work orchestration: manage organizations, board groups, boards, tasks, and tags.
- Agent operations: create, inspect, and manage agent lifecycle from a unified control surface.
- Governance and approvals: route sensitive actions through explicit approval flows.
- Trust Zones: define programmable delegation containers with configurable roles, constraints, and decision models.
- Gateway management: connect and operate gateway integrations for distributed environments.
- Activity visibility: review a timeline of system actions for faster debugging and accountability.
- API-first model: support both web workflows and automation clients from the same platform.

## Trust Zones governance layer

Trust Zones turn Mission Control from a task/agent management dashboard into a **multiplayer agent orchestrator** where organizations can delegate work to humans and AI agents with configurable, enforceable trust boundaries.

### The Delegation Trilemma

Every delegation involves a tradeoff between three dimensions: **Effectiveness** (does the agent achieve objectives?), **Cost** (resources consumed), and **Hardness** (how reliably does the agent stay aligned?). Trust Zones let organizations make these tradeoffs explicitly and configure them per-delegation rather than per-organization.

### What is a Trust Zone?

A Trust Zone is a programmable container for delegation. Instead of delegating directly to an agent, you delegate into a zone that defines what the agent can do and under what conditions. Every zone is defined by seven configurable parameters:

| Parameter | Description |
|-----------|-------------|
| **Responsibilities** | Expected outcomes and behavioral expectations |
| **Resources** | Budget limits, API key scopes, board access, tool permissions |
| **Agent Qualifications** | Eligibility criteria: org membership, reputation, required skills, human-only vs AI-allowed |
| **Ownership Alignment** | How the agent's stake aligns with success |
| **Incentives** | Evaluation criteria that trigger positive/negative outcomes on completion |
| **Constraints** | Hard rules enforced at the API layer: spending limits, action allowlists, time bounds, rate limits |
| **Decision Model** | How decisions are made: unilateral, k-of-n threshold, majority vote, weighted vote, consensus-with-timeout |

### Role hierarchy

The system implements a layered role hierarchy for zone-scoped governance:

- **Member** — can create proposals, be selected as approver/jury, trigger escalations
- **Gardener** — the intelligence layer that selects the best approvers for each proposal (rule-based or LLM-powered)
- **Approver** — domain-specific reviewers selected per-proposal, scaled by resources at risk
- **Executor** — the agent (human or AI) doing the work within zone constraints
- **Evaluator** — determines if work was completed to spec, applies incentive signals
- **Escalator** — can escalate decisions (action escalation) or governance itself (governance escalation)

### Key capabilities

- **Hierarchical zones** with parent-child nesting — child zones can only narrow parent permissions, never widen them
- **Proposal approval workflows** with 4 proposal types and 5 decision models
- **Conflict detection** — automatically flags self-review and subject-of-proposal conflicts
- **Dual escalation paths** — action escalation ("I disagree with this decision") and governance escalation ("I don't trust who is deciding")
- **LLM-powered reviewer selection** (Gardener) with reputation tracking and outcome-based learning
- **Post-completion evaluations** with weighted scoring, automated checks, and incentive signals
- **Append-only governance audit trail** for full accountability
- **Constraint narrowing validation** ensuring child zones never exceed parent boundaries
- **Auto-escalation** on approval timeout or voting deadlock

## Use cases

- Multi-team agent operations: run multiple boards and board groups across organizations from a single control plane.
- Human-in-the-loop execution: require approvals before sensitive actions and keep decision trails attached to work.
- Programmable delegation: define trust boundaries per-role with configurable constraints, decision models, and escalation policies.
- Democratic decision-making: use threshold voting, majority, or consensus models to make collective decisions on proposals.
- Distributed runtime control: connect gateways and operate remote execution environments without changing operator workflow.
- Audit and incident review: use activity history and governance audit trails to reconstruct what happened, when, and who initiated it.
- API-backed process integration: connect internal workflows and automation clients to the same operational model used in the UI.

## What makes Mission Control different

- Operations-first design: built for running agent work reliably, not just creating tasks.
- Governance built in: trust zones, approval workflows, escalation chains, and clear control boundaries are first-class.
- Programmable trust boundaries: configurable per-zone constraints, decision models, and role-based access control.
- Gateway-aware orchestration: built to operate both local and connected runtime environments.
- Unified UI and API model: operators and automation act on the same objects and lifecycle.
- Team-scale structure: organizations, board groups, boards, trust zones, tasks, tags, and users in one system of record.

## Who it is for

- Platform teams running OpenClaw in self-hosted or internal environments.
- Operations and engineering teams that need clear approval, delegation, and auditability controls.
- Organizations that want configurable governance over human and AI agent work.
- Organizations that want API-accessible operations without losing a usable web UI.

## Architecture

### Backend (FastAPI + Python)

The governance layer adds 7 models, 7 service engines, 5 API router modules, and permission enforcement middleware to the existing FastAPI backend.

**Models:**
- `trust_zones.py` — TrustZone with hierarchical parent-child relationships and 7 governance parameters
- `zone_assignments.py` — Maps org members to zone roles (executor, approver, evaluator, gardener)
- `proposals.py` — Proposal lifecycle with status, type, risk level, and conflict tracking
- `approval_requests.py` — Individual reviewer decisions linked to proposals
- `escalations.py` — Action and governance escalations with co-signer support
- `evaluations.py` — Post-completion evaluations, weighted scores, incentive signals, gardener feedback
- `audit_entries.py` — Append-only governance audit log

**Services:**
- `trust_zones.py` — Zone CRUD with constraint narrowing validation, resource scope checks, cascade status to children
- `permission_resolver.py` — RBAC with zone tree walking: checks constraints, walks ancestry, validates resource scope
- `approval_engine.py` — Full proposal lifecycle: risk scoring, conflict detection, reviewer selection, decision model evaluation, payload execution
- `escalation_engine.py` — Action/governance escalation workflows with rate limiting and auto-escalation
- `evaluations.py` — Weighted scoring, incentive signal generation, reputation updates, auto-evaluation via LLM
- `gardener.py` — LLM-powered reviewer selection (Claude Sonnet) with candidate profiling and fallback
- `audit.py` — Append-only audit logging

**API Routers:** `trust_zones`, `proposals`, `escalations`, `evaluations`, `audit` — all registered under `/api/v1/`

**Permission Enforcement:** `zone_auth.py` provides a FastAPI dependency factory `require_zone_permission(action)` for inline permission checks.

### Frontend (Next.js + TypeScript)

The governance layer adds 5 page groups, 20+ components, and 3 utility libraries to the existing Next.js frontend.

**Pages:** `/zones` (list + tree view, create, detail, edit), `/proposals` (list with pending/all tabs, detail with voting), `/escalations` (list filtered by type), `/evaluations` (list, detail with scoring), `/audit` (trail viewer with filtering)

**Components:** `ZoneTree`, `ZonesTable`, `ZoneForm`, `ZoneStatusBadge`, `ProposalsTable`, `EscalationDialog`, `EscalationCosignDialog`, `EscalationsTable`, `EvaluationsTable`, `StatusDot`

**Libraries:** `zone-tree.ts` (tree builder), `permissions.ts` (client-side RBAC mirroring backend), `decision-model.ts` (types and defaults for all 5 decision models)

### Database migrations

6 Alembic migrations implementing the schema across all phases:
1. Trust zones, zone assignments, audit entries
2. Proposals and approval requests
3. Escalations and escalation co-signers
4. Gardener feedback tracking
5. Evaluations, evaluation scores, incentive signals
6. Gap fixes and schema adjustments

### Test coverage

16 governance-specific test files covering:
- Zone CRUD, status transitions, constraint narrowing, resource scope narrowing, circular reference detection
- Permission resolution with zone tree walking and org role fallback
- Full proposal lifecycle, risk scoring, conflict detection, reviewer selection
- All 5 decision models (unilateral, threshold, majority, weighted, consensus)
- Action and governance escalation flows with rate limiting
- LLM-powered reviewer selection with fallback
- Evaluation workflow, scoring, finalization, incentive signals
- End-to-end integration (zone creation → member assignment → proposal → voting → evaluation)
- Append-only audit trail

## Get started in minutes

### Option A: One-command production-style bootstrap

If you haven't cloned the repo yet, you can run the installer in one line:

```bash
curl -fsSL https://raw.githubusercontent.com/abhi1693/openclaw-mission-control/master/install.sh | bash
```

If you already cloned the repo:

```bash
./install.sh
```

The installer is interactive and will:

- Ask for deployment mode (`docker` or `local`).
- Install missing system dependencies when possible.
- Generate and configure environment files.
- Bootstrap and start the selected deployment mode.

Installer support matrix: [`docs/installer-support.md`](./docs/installer-support.md)

### Option B: Manual setup

### Prerequisites

- Docker Engine
- Docker Compose v2 (`docker compose`)

### 1. Configure environment

```bash
cp .env.example .env
```

Before startup:

- Set `LOCAL_AUTH_TOKEN` to a non-placeholder value (minimum 50 characters) when `AUTH_MODE=local`.
- Ensure `NEXT_PUBLIC_API_URL` is reachable from your browser.

### 2. Start Mission Control

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

### 3. Open the application

- Mission Control UI: http://localhost:3000
- Backend health: http://localhost:8000/healthz

### 4. Stop the stack

```bash
docker compose -f compose.yml --env-file .env down
```

## Authentication

Mission Control supports two authentication modes:

- `local`: shared bearer token mode (default for self-hosted use)
- `clerk`: Clerk JWT mode

Environment templates:

- Root: [`.env.example`](./.env.example)
- Backend: [`backend/.env.example`](./backend/.env.example)
- Frontend: [`frontend/.env.example`](./frontend/.env.example)

## Documentation

Complete guides for deployment, production, troubleshooting, and testing are in [`/docs`](./docs/).

## Project status

Mission Control is under active development. The Trust Zones governance layer has been implemented across all 5 phases defined in the [design specification](../AGENT_PROMPT_trust_zones_build.md):

- Phase 1: Trust Zone model + hierarchical RBAC
- Phase 2: Proposal approval workflows with 5 decision models
- Phase 3: Dual-path escalation engine (action + governance)
- Phase 4: LLM-powered Gardener reviewer selection
- Phase 5: Post-completion evaluation with incentive signals

Features and APIs may change between releases. Validate and harden your configuration before production use.

## Contributing

Issues and pull requests are welcome.

- [Contributing guide](./CONTRIBUTING.md)
- [Open issues](https://github.com/abhi1693/openclaw-mission-control/issues)

## License

This project is licensed under the MIT License. See [`LICENSE`](./LICENSE).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=abhi1693/openclaw-mission-control&type=date&legend=top-left)](https://www.star-history.com/#abhi1693/openclaw-mission-control&type=date&legend=top-left)
