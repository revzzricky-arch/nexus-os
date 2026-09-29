// Mock runtime data - resembles future backend event architecture
// No real LLM/MCP/RAG calls, only mock

export type AgentType = "supervisor" | "researcher" | "coder" | "analyst";
export type AgentState =
  | "IDLE"
  | "PLANNING"
  | "RUNNING"
  | "WAITING"
  | "WAITING_FOR_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "PAUSED";

export type TaskState = "PENDING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "BLOCKED";
export type MissionStatus = "draft" | "running" | "awaiting_approval" | "completed" | "failed" | "paused";
export type ApprovalStatus = "PENDING" | "APPROVED" | "DENIED" | "EXPIRED";
export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface MockAgent {
  id: string;
  name: string;
  type: AgentType;
  role: string;
  state: AgentState;
  current_task_id: string | null;
  current_task_title: string | null;
  recent_activity: string;
  capabilities: string[];
  token_usage: number;
  cost_cents: number;
  model: string;
  provider: string;
  orbitIndex: number;
}

export interface MockTask {
  id: string;
  title: string;
  description: string;
  status: TaskState;
  agent_type: AgentType;
  agent_id: string | null;
  dependencies: string[];
  layer: number;
  progress: number;
  elapsed_seconds: number;
  output?: string;
}

export interface MockMission {
  id: string;
  title: string;
  goal: string;
  type: "Research" | "Code" | "Analysis" | "General";
  status: MissionStatus;
  progress: number;
  elapsed_seconds: number;
  phase: string;
  agent_count: number;
  task_count: number;
  completed_tasks: number;
  created_at: string;
  cost_cents: number;
  token_usage: number;
}

export interface MockTool {
  id: string;
  name: string;
  description: string;
  source: "builtin" | "mcp";
  mcp_transport?: "stdio" | "streamable_http" | "sse_legacy";
  risk_level: RiskLevel;
  permission: "auto" | "approval_required" | "forbidden";
  state: "active" | "inactive" | "error";
  call_count: number;
  avg_latency_ms: number;
}

export interface MockApproval {
  id: string;
  mission_id: string;
  task_id: string;
  agent_id: string;
  tool_id: string;
  type: "tool" | "task" | "mission";
  status: ApprovalStatus;
  risk_level: RiskLevel;
  requested_action: string;
  args: Record<string, unknown>;
  reasoning: string;
  created_at: string;
  agent_name: string;
}

export interface MockEvent {
  id: string;
  timestamp: string;
  mission_id: string;
  task_id?: string;
  agent_id?: string;
  type: string;
  source: string;
  payload: Record<string, unknown>;
}

// Mock missions list
export const mockMissions: MockMission[] = [
  {
    id: "mission-1",
    title: "Investigate API incident from latest deployment",
    goal: "Investigate the API incident from the latest deployment, identify root cause, and propose fix",
    type: "General",
    status: "running",
    progress: 65,
    elapsed_seconds: 342,
    phase: "Analysis",
    agent_count: 4,
    task_count: 5,
    completed_tasks: 3,
    created_at: "2026-09-29T06:00:00Z",
    cost_cents: 42,
    token_usage: 12450,
  },
  {
    id: "mission-2",
    title: "Research top 5 AI agent frameworks",
    goal: "Research and compare top 5 AI agent frameworks with detailed analysis",
    type: "Research",
    status: "completed",
    progress: 100,
    elapsed_seconds: 892,
    phase: "Completed",
    agent_count: 3,
    task_count: 3,
    completed_tasks: 3,
    created_at: "2026-09-28T14:30:00Z",
    cost_cents: 87,
    token_usage: 23400,
  },
  {
    id: "mission-3",
    title: "Implement user authentication flow",
    goal: "Implement secure user authentication with JWT and RBAC",
    type: "Code",
    status: "awaiting_approval",
    progress: 80,
    elapsed_seconds: 1240,
    phase: "Awaiting Approval",
    agent_count: 3,
    task_count: 4,
    completed_tasks: 3,
    created_at: "2026-09-28T09:15:00Z",
    cost_cents: 156,
    token_usage: 45200,
  },
  {
    id: "mission-4",
    title: "Analyze Q3 revenue metrics",
    goal: "Analyze Q3 revenue, identify trends, and generate report with visualizations",
    type: "Analysis",
    status: "running",
    progress: 40,
    elapsed_seconds: 210,
    phase: "Data Collection",
    agent_count: 2,
    task_count: 3,
    completed_tasks: 1,
    created_at: "2026-09-29T05:30:00Z",
    cost_cents: 23,
    token_usage: 8900,
  },
  {
    id: "mission-5",
    title: "Draft product launch announcement",
    goal: "Draft compelling product launch announcement for NEXUS platform",
    type: "General",
    status: "paused",
    progress: 20,
    elapsed_seconds: 95,
    phase: "Paused",
    agent_count: 2,
    task_count: 2,
    completed_tasks: 0,
    created_at: "2026-09-29T04:00:00Z",
    cost_cents: 12,
    token_usage: 3200,
  },
  {
    id: "mission-6",
    title: "Security audit for tool permissions",
    goal: "Audit tool permission model and identify potential security gaps",
    type: "Analysis",
    status: "draft",
    progress: 0,
    elapsed_seconds: 0,
    phase: "Draft",
    agent_count: 0,
    task_count: 0,
    completed_tasks: 0,
    created_at: "2026-09-29T03:00:00Z",
    cost_cents: 0,
    token_usage: 0,
  },
];

// Mock agents - Supervisor, Researcher, Coder, Analyst
export const mockAgents: MockAgent[] = [
  {
    id: "supervisor-1",
    name: "Supervisor",
    type: "supervisor",
    role: "Mission Planner & Orchestrator",
    state: "RUNNING",
    current_task_id: "task-2",
    current_task_title: "Coordinate analysis phase",
    recent_activity: "Decomposed mission into 5 tasks, assigned to specialists",
    capabilities: ["planning", "routing", "evaluation", "replanning"],
    token_usage: 3200,
    cost_cents: 12,
    model: "gpt-4o-mini",
    provider: "openai-compatible",
    orbitIndex: 0,
  },
  {
    id: "researcher-1",
    name: "Researcher",
    type: "researcher",
    role: "Web Research & RAG Specialist",
    state: "RUNNING",
    current_task_id: "task-1",
    current_task_title: "Investigate deployment logs",
    recent_activity: "Searched deployment logs, found error pattern in API gateway",
    capabilities: ["web_search", "rag_query", "memory_search"],
    token_usage: 5400,
    cost_cents: 18,
    model: "gpt-4o-mini",
    provider: "openai-compatible",
    orbitIndex: 1,
  },
  {
    id: "coder-1",
    name: "Coder",
    type: "coder",
    role: "Implementation & Fix Specialist",
    state: "WAITING_FOR_APPROVAL",
    current_task_id: "task-3",
    current_task_title: "Propose fix for API incident",
    recent_activity: "Generated fix proposal, waiting for approval to write file",
    capabilities: ["read_file", "write_file", "shell", "test_runner"],
    token_usage: 2800,
    cost_cents: 8,
    model: "claude-3-5-sonnet",
    provider: "anthropic",
    orbitIndex: 2,
  },
  {
    id: "analyst-1",
    name: "Analyst",
    type: "analyst",
    role: "Data Analysis & Synthesis",
    state: "WAITING",
    current_task_id: "task-4",
    current_task_title: "Analyze error patterns",
    recent_activity: "Waiting for researcher handoff, queued for analysis",
    capabilities: ["memory_search", "rag_query", "data_analysis"],
    token_usage: 1050,
    cost_cents: 4,
    model: "gpt-4o-mini",
    provider: "openai-compatible",
    orbitIndex: 3,
  },
];

// Mock tasks - layered DAG
export const mockTasks: MockTask[] = [
  {
    id: "task-1",
    title: "Investigate logs",
    description: "Search deployment logs and identify error patterns",
    status: "COMPLETED",
    agent_type: "researcher",
    agent_id: "researcher-1",
    dependencies: [],
    layer: 0,
    progress: 100,
    elapsed_seconds: 120,
    output: "Found 500 errors in API gateway after v0.2.1 deployment",
  },
  {
    id: "task-2",
    title: "Coordinate",
    description: "Supervisor coordination and planning",
    status: "RUNNING",
    agent_type: "supervisor",
    agent_id: "supervisor-1",
    dependencies: ["task-1"],
    layer: 1,
    progress: 65,
    elapsed_seconds: 80,
  },
  {
    id: "task-3",
    title: "Propose fix",
    description: "Generate fix proposal for API incident",
    status: "QUEUED",
    agent_type: "coder",
    agent_id: "coder-1",
    dependencies: ["task-2"],
    layer: 2,
    progress: 0,
    elapsed_seconds: 0,
  },
  {
    id: "task-4",
    title: "Analyze patterns",
    description: "Analyze error patterns and trends",
    status: "QUEUED",
    agent_type: "analyst",
    agent_id: "analyst-1",
    dependencies: ["task-1", "task-2"],
    layer: 2,
    progress: 0,
    elapsed_seconds: 0,
  },
  {
    id: "task-5",
    title: "Generate report",
    description: "Final incident report with root cause and fix",
    status: "PENDING",
    agent_type: "supervisor",
    agent_id: null,
    dependencies: ["task-3", "task-4"],
    layer: 3,
    progress: 0,
    elapsed_seconds: 0,
  },
];

// Mock tools
export const mockTools: MockTool[] = [
  {
    id: "web_search",
    name: "Web Search",
    description: "Search web for information",
    source: "builtin",
    risk_level: "low",
    permission: "auto",
    state: "active",
    call_count: 24,
    avg_latency_ms: 320,
  },
  {
    id: "read_file",
    name: "Read File",
    description: "Read file via SandboxService",
    source: "builtin",
    risk_level: "low",
    permission: "auto",
    state: "active",
    call_count: 45,
    avg_latency_ms: 45,
  },
  {
    id: "write_file",
    name: "Write File",
    description: "Write file via SandboxService with approval",
    source: "builtin",
    risk_level: "high",
    permission: "approval_required",
    state: "active",
    call_count: 12,
    avg_latency_ms: 120,
  },
  {
    id: "shell",
    name: "Shell",
    description: "Shell via SandboxService container isolation, always approval",
    source: "builtin",
    risk_level: "critical",
    permission: "approval_required",
    state: "active",
    call_count: 8,
    avg_latency_ms: 850,
  },
  {
    id: "memory_search",
    name: "Memory Search",
    description: "Search shared mission memory",
    source: "builtin",
    risk_level: "low",
    permission: "auto",
    state: "active",
    call_count: 67,
    avg_latency_ms: 85,
  },
  {
    id: "rag_query",
    name: "RAG Query",
    description: "Query RAG collections with local-first embedding",
    source: "builtin",
    risk_level: "low",
    permission: "auto",
    state: "active",
    call_count: 34,
    avg_latency_ms: 180,
  },
  {
    id: "filesystem",
    name: "Filesystem MCP",
    description: "Filesystem MCP server via stdio",
    source: "mcp",
    mcp_transport: "stdio",
    risk_level: "medium",
    permission: "approval_required",
    state: "active",
    call_count: 18,
    avg_latency_ms: 95,
  },
  {
    id: "fetch",
    name: "Fetch MCP",
    description: "Fetch MCP via Streamable HTTP",
    source: "mcp",
    mcp_transport: "streamable_http",
    risk_level: "medium",
    permission: "auto",
    state: "active",
    call_count: 29,
    avg_latency_ms: 420,
  },
  {
    id: "github",
    name: "GitHub MCP",
    description: "GitHub MCP read-only",
    source: "mcp",
    mcp_transport: "streamable_http",
    risk_level: "medium",
    permission: "auto",
    state: "inactive",
    call_count: 0,
    avg_latency_ms: 0,
  },
  {
    id: "postgres",
    name: "Postgres MCP",
    description: "Postgres MCP via Streamable HTTP",
    source: "mcp",
    mcp_transport: "streamable_http",
    risk_level: "high",
    permission: "approval_required",
    state: "inactive",
    call_count: 0,
    avg_latency_ms: 0,
  },
  {
    id: "legacy-sse",
    name: "Legacy SSE Tool",
    description: "Legacy SSE transport - compatibility only",
    source: "mcp",
    mcp_transport: "sse_legacy",
    risk_level: "low",
    permission: "forbidden",
    state: "inactive",
    call_count: 0,
    avg_latency_ms: 0,
  },
];

// Mock approvals - balanced policy, shell always approval
export const mockApprovals: MockApproval[] = [
  {
    id: "approval-1",
    mission_id: "mission-1",
    task_id: "task-3",
    agent_id: "coder-1",
    tool_id: "write_file",
    type: "tool",
    status: "PENDING",
    risk_level: "high",
    requested_action: "Write fix to /workspace/api/gateway.py",
    args: {
      path: "/workspace/api/gateway.py",
      content: "Fixed error handling for 500 errors...",
    },
    reasoning: "Generated fix for API gateway 500 error, need to write file to propose fix",
    created_at: "2026-09-29T06:10:00Z",
    agent_name: "Coder",
  },
  {
    id: "approval-2",
    mission_id: "mission-3",
    task_id: "task-3",
    agent_id: "coder-1",
    tool_id: "shell",
    type: "tool",
    status: "PENDING",
    risk_level: "critical",
    requested_action: "Run tests via shell",
    args: {
      command: "pytest tests/test_gateway.py -v",
    },
    reasoning: "Need to run tests to verify fix, shell always requires approval per D6",
    created_at: "2026-09-29T05:45:00Z",
    agent_name: "Coder",
  },
  {
    id: "approval-3",
    mission_id: "mission-1",
    task_id: "task-5",
    agent_id: "supervisor-1",
    tool_id: "write_file",
    type: "task",
    status: "APPROVED",
    risk_level: "medium",
    requested_action: "Publish incident report",
    args: {
      path: "/workspace/reports/incident-2026-09-29.md",
    },
    reasoning: "Final report ready for publishing",
    created_at: "2026-09-29T04:20:00Z",
    agent_name: "Supervisor",
  },
];

// Mock events - resembles future backend event architecture
export const mockEvents: MockEvent[] = [
  {
    id: "evt-1",
    timestamp: "2026-09-29T06:00:00Z",
    mission_id: "mission-1",
    type: "mission_created",
    source: "system",
    payload: { title: "Investigate API incident" },
  },
  {
    id: "evt-2",
    timestamp: "2026-09-29T06:00:30Z",
    mission_id: "mission-1",
    agent_id: "supervisor-1",
    type: "agent_state_changed",
    source: "agent_runner",
    payload: { from: "IDLE", to: "PLANNING", agent_type: "supervisor" },
  },
  {
    id: "evt-3",
    timestamp: "2026-09-29T06:01:00Z",
    mission_id: "mission-1",
    task_id: "task-1",
    agent_id: "researcher-1",
    type: "task_status_changed",
    source: "supervisor",
    payload: { from: "PENDING", to: "RUNNING", title: "Investigate logs" },
  },
  {
    id: "evt-4",
    timestamp: "2026-09-29T06:02:15Z",
    mission_id: "mission-1",
    task_id: "task-1",
    agent_id: "researcher-1",
    type: "tool_call_started",
    source: "tool_registry",
    payload: { tool_id: "web_search", args: { query: "API gateway 500 errors deployment" } },
  },
  {
    id: "evt-5",
    timestamp: "2026-09-29T06:02:45Z",
    mission_id: "mission-1",
    task_id: "task-1",
    agent_id: "researcher-1",
    type: "tool_call_completed",
    source: "tool_registry",
    payload: { tool_id: "web_search", status: "success", latency_ms: 320 },
  },
  {
    id: "evt-6",
    timestamp: "2026-09-29T06:03:00Z",
    mission_id: "mission-1",
    task_id: "task-1",
    agent_id: "researcher-1",
    type: "memory_accessed",
    source: "memory_service",
    payload: { query: "deployment logs", results: 3 },
  },
  {
    id: "evt-7",
    timestamp: "2026-09-29T06:05:00Z",
    mission_id: "mission-1",
    task_id: "task-1",
    type: "task_status_changed",
    source: "supervisor",
    payload: { from: "RUNNING", to: "COMPLETED", title: "Investigate logs" },
  },
  {
    id: "evt-8",
    timestamp: "2026-09-29T06:05:30Z",
    mission_id: "mission-1",
    agent_id: "researcher-1",
    type: "handoff",
    source: "agent_runner",
    payload: { from_agent: "researcher-1", to_agent: "supervisor-1", summary: "Found error pattern" },
  },
  {
    id: "evt-9",
    timestamp: "2026-09-29T06:06:00Z",
    mission_id: "mission-1",
    task_id: "task-2",
    agent_id: "supervisor-1",
    type: "task_status_changed",
    source: "supervisor",
    payload: { from: "PENDING", to: "RUNNING", title: "Coordinate" },
  },
  {
    id: "evt-10",
    timestamp: "2026-09-29T06:10:00Z",
    mission_id: "mission-1",
    task_id: "task-3",
    agent_id: "coder-1",
    type: "approval_requested",
    source: "approval_service",
    payload: { tool_id: "write_file", risk_level: "high", approval_id: "approval-1" },
  },
];
