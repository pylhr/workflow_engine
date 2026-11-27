# Workflow Automation Engine

**A standalone desktop application for visually designing, executing, and monitoring graph-based business workflows.**

The Workflow Automation Engine is a Python desktop application that enables users to construct multi-step business processes through a drag-and-drop visual designer. It combines a graph-based execution engine, conditional routing, human-in-the-loop approvals, time-based delays, workflow versioning, and execution monitoring in a single PyQt6 application.

The project explores the engineering foundations of workflow automation systems: graph validation, state-machine execution, pluggable node handlers, persistent execution state, scheduling, and layered software architecture.

---

## Overview

Business processes often involve sequences of actions, decisions, approvals, and time-dependent operations. The Workflow Automation Engine provides a visual environment for defining these processes and an execution layer for managing their progression.

A workflow is represented as a directed graph containing nodes and edges. Each node performs a specific operation, while edges determine how execution proceeds between operations.

The application supports:

- Visual workflow construction through a drag-and-drop designer.
- Graph validation, including cycle detection and reachability checks.
- Conditional branching based on workflow context.
- Human approval steps with role-based approval queues.
- Time-based delays and scheduled execution resumption.
- Versioned workflow definitions and publishing.
- Persistent execution state and transition logs.
- Dashboard monitoring and administrative audit records.

**Application model:** Standalone desktop application  
**Platform:** Windows-oriented Python desktop environment  
**Database:** Local SQLite  
**Execution:** Single-process, scheduler-assisted workflow execution

---

## Key Features

### 1. Visual Workflow Designer

Build workflows using a graphical canvas powered by PyQt6's `QGraphicsScene` and `QGraphicsView`.

- Add workflow nodes using the designer toolbar.
- Drag and reposition nodes on the canvas.
- Connect nodes through visual input and output ports.
- Configure individual nodes through property dialogs.
- Create conditional connections with explicit `true` and `false` branches.
- Save the resulting graph as a JSON workflow definition.

### 2. Graph Validation

The workflow graph is validated before publication and execution.

The graph validation layer checks:

- Exactly one Start node.
- At least one End node.
- Valid references between connected nodes.
- Cycles using depth-first traversal.
- Reachability of nodes from the workflow's starting point.

The graph module also provides successor lookup and topological ordering using Kahn's algorithm.

### 3. Graph-Based Execution Engine

The execution engine traverses workflow graphs and coordinates node execution.

Each node handler returns a structured result containing execution status, optional branch information, context updates, and a message.

The engine supports:

- Sequential node execution.
- Conditional branch selection.
- Context updates between nodes.
- Execution pausing and resumption.
- Completion and failure handling.
- Persistent execution logs.

Execution is modeled through explicit states:

`pending → running → waiting → completed / failed / cancelled`

### 4. Pluggable Node Architecture

Node handlers are implemented as independent classes and registered through `NODE_REGISTRY`.

| Node type | Functionality |
|---|---|
| Start | Defines the workflow entry point |
| End | Marks workflow completion |
| Approval | Pauses execution for a human decision |
| Condition | Evaluates an expression and selects a branch |
| Delay | Pauses execution until a configured time |
| Notification | Creates an in-app notification |
| Webhook | Currently a placeholder that logs the intended request |
| Script | Evaluates an expression and stores its result in workflow context |

The registry-based design allows additional node handlers to be introduced without restructuring the execution engine.

### 5. Human-in-the-Loop Approvals

Approval nodes introduce human decisions into automated workflows.

- Assign approval requirements to a Manager or Admin role.
- Persist approval requests against individual executions.
- Display pending approvals in the dashboard.
- Approve or reject selected requests.
- Resume execution after an approval decision.
- Record significant approval actions in the audit log.

A rejected approval marks the associated execution as failed.

### 6. Workflow Versioning

Workflow definitions are stored as versioned records.

- Save changes as new draft versions.
- Validate a graph before publication.
- Publish a valid workflow version.
- Preserve previously published versions.
- Bind each execution to the exact workflow version it started with.

Publishing a new version does not modify the definition used by an execution already in progress.

### 7. Scheduling and Delayed Execution

The application integrates APScheduler's `BackgroundScheduler` to support time-dependent workflow operations.

Implemented scheduling capabilities include:

- One-off scheduled resumption after a Delay node.
- Backend support for recurring workflow triggers.
- Cron and interval scheduling primitives.
- Scheduler operation independently of the Qt event loop.

The recurring scheduling backend exists, but a user-facing scheduling interface has not yet been implemented.

### 8. Execution Monitoring Dashboard

The dashboard provides an overview of workflow activity.

It includes six summary counters:

- Total executions.
- Running executions.
- Waiting executions.
- Completed executions.
- Failed executions.
- Pending approvals.

A Recent Executions table displays execution status, workflow name, current node, start time, and duration.

The dashboard refreshes automatically every five seconds.

### 9. Authentication and Role-Based Interface

The application includes three predefined roles:

- **Admin:** Access to administrative functionality, including the audit log.
- **Manager:** Access to pending approval operations.
- **Employee:** Standard workflow application access.

Authentication uses password hashing through Passlib and bcrypt.

Role-based interface visibility is implemented, although service-layer authorization is not yet comprehensive.

### 10. Audit Logging

An append-only audit log records significant system actions, including:

- Workflow creation.
- Workflow version saves.
- Workflow publication.
- Execution initiation.
- Approval decisions.

The Admin-only Audit Log tab provides a view of recent recorded actions.

---

## Architecture

The application follows a layered architecture that separates presentation, orchestration, domain logic, and persistence.

```text
┌──────────────────────────────────────────────┐
│                 UI Layer                     │
│                                              │
│  Login · Dashboard · Workflow List           │
│  Visual Designer · Node Configuration       │
├──────────────────────────────────────────────┤
│               Service Layer                  │
│                                              │
│  Workflow · Execution · Notification         │
│  Audit Services                              │
├──────────────────────────────────────────────┤
│             Core Domain Layer                │
│                                              │
│  Workflow Graph · Execution Engine           │
│  Node Registry · Scheduler                   │
├──────────────────────────────────────────────┤
│                Data Layer                    │
│                                              │
│       SQLAlchemy ORM · SQLite                │
└──────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| UI | User interaction, visual workflow design, dashboards |
| Services | Application operations, orchestration, and persistence coordination |
| Core | Graph validation, node execution, workflow state transitions, scheduling |
| Data | SQLAlchemy models, database sessions, and SQLite persistence |
| Authentication | User authentication, password verification, and role utilities |

The core and service layers are independent of PyQt6. This separation makes it possible to reuse much of the domain and application logic behind a different interface in a future architecture.

### Project Structure

```text
workflow_engine/
│
├── app/
│   ├── auth/
│   │   └── auth_service.py
│   │
│   ├── core/
│   │   ├── graph.py
│   │   ├── scheduler.py
│   │   └── engine/
│   │       ├── executor.py
│   │       └── nodes.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── workflow.py
│   │   ├── execution.py
│   │   ├── notification.py
│   │   └── audit.py
│   │
│   ├── services/
│   │   ├── workflow_service.py
│   │   ├── execution_service.py
│   │   ├── notification_service.py
│   │   └── audit_service.py
│   │
│   └── ui/
│       ├── login_dialog.py
│       ├── main_window.py
│       ├── dashboard.py
│       ├── workflow_list.py
│       ├── workflow_editor.py
│       └── designer/
│           ├── canvas.py
│           ├── node_items.py
│           ├── edge_items.py
│           └── node_properties_dialog.py
│
├── tests/
├── main.py
├── requirements.txt
└── README.md
```

---

## Technical Implementation

### Workflow Representation

Workflow definitions are stored as JSON structures containing nodes and edges.

A simplified example:

```json
{
  "nodes": [
    {"id": "1", "type": "start", "data": {}},
    {
      "id": "2",
      "type": "condition",
      "data": {"condition": "amount > 10000"}
    },
    {
      "id": "3",
      "type": "approval",
      "data": {"assigned_role": "Manager"}
    },
    {"id": "4", "type": "end", "data": {}}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {
      "from": "2",
      "to": "3",
      "data": {"branch": "true"}
    },
    {
      "from": "2",
      "to": "4",
      "data": {"branch": "false"}
    },
    {"from": "3", "to": "4"}
  ]
}
```

Each node's type determines its registered handler, while its data object contains the node-specific configuration.

### Persistent Execution State

Workflow executions are represented through database records rather than being maintained exclusively in memory.

The execution engine reloads execution state and workflow definitions when processing or resuming an execution. This allows paused executions to retain their state across application restarts.

Execution transitions are recorded in an append-only execution log.

### Database Design

The SQLAlchemy data model includes:

| Model | Purpose |
|---|---|
| User / Role | User accounts and assigned roles |
| Workflow | Named workflow definitions |
| WorkflowVersion | Versioned graph definitions |
| WorkflowSchedule | Recurring schedule configuration |
| WorkflowExecution | Individual workflow runs |
| ExecutionLog | Node transition and execution history |
| ApprovalRequest | Human approval records |
| Notification | In-app notifications |
| AuditLog | System-wide activity records |

### Threading and Scheduling

The application operates with a Qt main thread and APScheduler's background scheduler.

The scheduler can trigger delayed execution resumption independently of the GUI event loop. SQLAlchemy sessions are used for database operations across the application.

Workflow execution itself currently runs synchronously on the thread that invokes it. Long-running node operations have not yet been moved into a dedicated worker thread or queue.

---

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.12 |
| Desktop GUI | PyQt6 |
| Visual Designer | QGraphicsScene / QGraphicsView |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite |
| Scheduling | APScheduler |
| Authentication | Passlib |
| Password Hashing | bcrypt |

---

## Installation

### Prerequisites

- Python 3.10 or newer.
- Windows environment recommended for the intended desktop application.

### 1. Clone the repository

```bash
git clone https://github.com/pylhr/workflow_engine.git
cd workflow_engine
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

**Windows:**

```bash
venv\Scripts\activate
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

The project uses:

```text
PyQt6==6.7.0
SQLAlchemy==2.0.30
APScheduler==3.10.4
passlib==1.7.4
bcrypt==4.0.1
```

### 4. Launch the application

```bash
python main.py
```

On first launch, the application initializes the SQLite database at:

```text
data/workflow.db
```

It also creates the initial roles and default administrator account if they do not already exist.

**Default login:**

```text
Username: admin
Password: admin123
```

Change the default credentials before using the application with sensitive data.

---

## Using the Application

A typical workflow lifecycle:

1. **Log in** using an application account.
2. **Create a workflow** from the Workflows tab.
3. **Open the designer** and add nodes to the canvas.
4. **Connect nodes** using their input and output ports.
5. **Configure nodes** by double-clicking them.
6. **Save a draft** to preserve the current definition.
7. **Publish the workflow** after graph validation succeeds.
8. **Run the workflow** using Run Now.
9. **Handle approvals** through the Dashboard when required.
10. **Monitor execution** through the dashboard and audit log.

---

## Current Limitations

The following distinctions are important when evaluating the current implementation.

| Area | Current implementation |
|---|---|
| Deployment | Single-user, single-machine desktop application |
| Database | Local SQLite database |
| Starting context | Run Now starts with an empty context |
| User management | Additional accounts require direct service calls |
| Webhooks | Placeholder implementation; no outbound HTTP request |
| Notifications | In-app notification records; no email or external delivery |
| Notification inbox | No dedicated inbox interface |
| Recurring scheduling | Backend support exists; no scheduling UI |
| Execution threading | Synchronous on the calling thread |
| Parallel branches | Executor follows only the first outgoing edge for non-condition multi-edge cases |
| Expression evaluation | Restricted `eval()`; not a hardened sandbox |
| Authorization | Primarily enforced through UI visibility, not comprehensive service-layer checks |
| Automated testing | Development verification was manual and scripted; a committed automated regression suite is not documented in the project report |

The application is not currently a distributed workflow platform. Multi-user collaboration, shared server-side persistence, and network-based execution are outside the scope of this desktop edition.

---

## Potential Future Development

The existing architecture provides a foundation for further development.

Possible extensions include:

- FastAPI-based backend and shared PostgreSQL persistence.
- Multi-user access and stronger service-layer authorization.
- Dedicated user-management interface.
- Workflow execution on worker threads or a task queue.
- True parallel branch execution.
- Functional outbound webhook integration.
- Email and external notification providers.
- User-facing recurring scheduling interface.
- Starting-context forms for workflow execution.
- Safer expression parsing for Condition and Script nodes.
- Automated regression tests using pytest.
- Expanded execution inspection and workflow analytics.

These are prospective improvements, not features currently represented as complete.

---

## Engineering Concepts Demonstrated

This project brings together several practical software engineering concepts:

- Layered architecture and separation of concerns.
- Graph data structures and directed graph traversal.
- Cycle detection and reachability validation.
- State-machine-based execution.
- Registry and pluggable handler patterns.
- Object-relational mapping and database transactions.
- Persistent workflow versioning.
- Background scheduling and delayed task resumption.
- Human-in-the-loop process automation.
- GUI event handling and graphical scene interaction.
- Audit trails and execution observability.

---

## Project Information

| | |
|---|---|
| Project | Workflow Automation Engine |
| Edition | Standalone PyQt Desktop Edition |
| Version | 1.0 |
| Language | Python |
| Interface | PyQt6 |
| Architecture | Layered, single-process application |
| Repository | [pylhr/workflow_engine](https://github.com/pylhr/workflow_engine) |

---

**A practical exploration of workflow systems, graph-based execution, and the engineering principles behind business process automation.**