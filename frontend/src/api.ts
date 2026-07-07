export type ChannelStatus = 'live' | 'idle' | 'stopped' | 'error';

export interface Channel {
  id: string;
  name: string;
  description: string;
  host_model: string;
  status: ChannelStatus;
  cover_path: string | null;
}

export interface PlaybackItem {
  type: string;
  title: string;
  artist: string | null;
  file_path?: string;
  started_at: string | null;
}

export interface Program {
  id: string;
  name: string;
  description: string;
  vibe: string | null;
  start_time: string;
  end_time: string;
  days_of_week: string;
  cover_path: string | null;
  host_name?: string | null;
  host_gender?: string | null;
  voice?: string | null;
  personality?: string | null;
  active?: number;
}

export interface Metrics {
  local_listeners: number | null;
  popularity: number | null;
  average_session: string | null;
  feedback_count: number;
}

export interface TopSong {
  id: number;
  title: string;
  artist: string;
  plays: number;
}

export interface TopGenre {
  genre: string;
  plays: number;
}

export interface ListenerMessage {
  content: string;
  source: string;
  created_at: string;
}

export interface AutonomyIncident {
  id: number;
  component: string;
  severity: string;
  status: string;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface AutonomousTask {
  id: number;
  task_type: string;
  component: string;
  title: string;
  status: string;
  priority: number;
  attempts: number;
  created_at: string;
  updated_at: string;
}

export interface AgentLog {
  level: string;
  message: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface LlmRuntimeHealth {
  provider: string;
  configured_model: string;
  base_url: string;
  reachable: boolean;
  model_available: boolean;
  installed_models: string[];
  status: string;
  error: string | null;
}

export interface LlmSetupHealth extends LlmRuntimeHealth {
  cli_found: boolean;
  cli_path: string | null;
  server_reachable: boolean;
  summary: string;
  suggested_commands: string[];
}

export interface SystemHealth {
  database: string;
  llm: string;
  llm_runtime: LlmRuntimeHealth;
  llm_setup: LlmSetupHealth;
  tts: string;
  search: string;
  weather: string;
  playback: string;
}

export interface OrchestratorState {
  running: boolean;
  last_tick_at: string | null;
  last_strategy_at: string | null;
  last_error: string | null;
  strategy: string | null;
  strategy_policy: {
    single_channel: boolean;
    library_tracks: number;
    library_signals?: string;
    listener_memory?: string;
    goals: string[];
    next_actions: string[];
    constraints: string[];
  } | null;
  strategy_revision: number;
  memory_count: number;
  draft_count: number;
  self_review: string | null;
}

export interface RuntimeObservability {
  uptime_seconds: number;
  announcement_prebuffer: {
    ready: number;
    used: number;
    failed: number;
    required: number;
    ready_to_broadcast: boolean;
  };
  generated_clips: number;
  recent_errors: Array<{ message: string; created_at: string }>;
  supervisor_restarts: number;
  playback_now: PlaybackItem;
}

export interface LiquidsoapState {
  enabled: boolean;
  command: string;
  command_found: boolean;
  command_path: string | null;
  running: boolean;
  pid: number | null;
  rendered: boolean;
  script_path: string;
  queue_path: string;
  mount: string;
  icecast_url: string;
}

export interface SetupState {
  has_music: boolean;
  message: string;
}

export interface WeatherContext {
  available: boolean;
  location: string;
  summary: string;
  temperature_c: number | null;
  humidity_percent: number | null;
  wind_kmh: number | null;
  condition: string | null;
  source: string;
}

export interface StatusResponse {
  channel: Channel;
  now_playing: PlaybackItem;
  queue: PlaybackItem[];
  current_program: Program | null;
  programs: Program[];
  next_programs?: Program[];
  metrics: Metrics;
  top_songs: TopSong[];
  top_genres: TopGenre[];
  listener_messages: ListenerMessage[];
  incidents: AutonomyIncident[];
  autonomous_tasks: AutonomousTask[];
  weather: WeatherContext;
  logs: AgentLog[];
  health: SystemHealth;
  observability: RuntimeObservability;
  orchestrator: OrchestratorState;
  liquidsoap: LiquidsoapState;
  setup: SetupState;
}

export interface PublicStream {
  url: string;
  status: string;
}

export interface PublicMetrics {
  current_listeners: number;
  popularity: number | null;
  average_session: string | null;
}

export interface PublicStatusResponse {
  online: boolean;
  received_at: string | null;
  generated_at: string | null;
  expires_at: string | null;
  message: string;
  channel: Channel;
  now_playing: PlaybackItem;
  current_program: Program | null;
  next_programs: Program[];
  programs: Program[];
  top_songs: TopSong[];
  top_genres: TopGenre[];
  stream: PublicStream;
  metrics: PublicMetrics;
}

export async function fetchStatus(): Promise<StatusResponse> {
  const response = await fetch('/api/status');
  if (!response.ok) {
    throw new Error(`Status request failed: ${response.status}`);
  }
  return response.json() as Promise<StatusResponse>;
}

export async function fetchPublicStatus(): Promise<PublicStatusResponse> {
  const response = await fetch('/api/public/status');
  if (!response.ok) {
    throw new Error(`Public status request failed: ${response.status}`);
  }
  return response.json() as Promise<PublicStatusResponse>;
}

export async function postPublicSession(path: string, sessionId: string): Promise<void> {
  await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function postControl(path: string, body?: unknown): Promise<Record<string, unknown>> {
  const response = await fetch(path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<Record<string, unknown>>;
}

export async function patchJson(path: string, body: unknown): Promise<void> {
  const response = await fetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
}
