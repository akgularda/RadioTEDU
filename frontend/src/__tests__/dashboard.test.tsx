import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Dashboard } from '../components/Dashboard';
import { PublicDashboard } from '../components/PublicDashboard';
import type { PublicStatusResponse, StatusResponse } from '../api';

const emptyStatus: StatusResponse = {
  channel: {
    id: 'radiotedu',
    name: 'RadioTEDU',
    description: 'Local AI radio running on your machine.',
    host_model: 'qwen2.5:0.5b-instruct',
    status: 'idle',
    cover_path: '/static/generated/covers/radiotedu_station.png',
  },
  now_playing: {
    type: 'idle',
    title: 'Idle — waiting for music library.',
    artist: null,
    started_at: null,
  },
  queue: [],
  current_program: {
    id: 'night_lab',
    name: 'Night Lab',
    description: 'Late-night ambient, experimental, and thoughtful tracks.',
    vibe: 'late jazz',
    start_time: '18:00',
    end_time: '23:00',
    days_of_week: 'mon,tue',
    cover_path: '/static/generated/covers/night_lab.png',
    active: 1,
  },
  programs: [
    {
      id: 'night_lab',
      name: 'Night Lab',
      description: 'Late-night ambient, experimental, and thoughtful tracks.',
      vibe: 'late jazz',
      start_time: '18:00',
      end_time: '23:00',
      days_of_week: 'mon,tue',
      cover_path: '/static/generated/covers/night_lab.png',
      active: 1,
    },
  ],
  metrics: {
    local_listeners: null,
    popularity: null,
    average_session: null,
    feedback_count: 0,
  },
  top_songs: [],
  top_genres: [],
  listener_messages: [
    {
      content: 'more mellow piano at night',
      source: 'dashboard',
      created_at: '2026-07-05T12:00:00+00:00',
    },
  ],
  incidents: [
    {
      id: 1,
      component: 'llm',
      severity: 'warning',
      status: 'open',
      summary: 'Ollama runtime is unreachable.',
      created_at: '2026-07-06T00:00:00+00:00',
      updated_at: '2026-07-06T00:00:00+00:00',
    },
  ],
  autonomous_tasks: [
    {
      id: 1,
      task_type: 'restart_llm_runtime',
      component: 'llm',
      title: 'Restart Ollama',
      status: 'queued',
      priority: 80,
      attempts: 0,
      created_at: '2026-07-06T00:00:00+00:00',
      updated_at: '2026-07-06T00:00:00+00:00',
    },
  ],
  logs: [],
  health: {
    database: 'ok',
    llm: 'qwen3.5:4b',
    llm_runtime: {
      provider: 'ollama',
      configured_model: 'qwen3.5:4b',
      base_url: 'http://127.0.0.1:11434',
      reachable: false,
      model_available: false,
      installed_models: [],
      status: 'unreachable',
      error: 'connection refused',
    },
    llm_setup: {
      provider: 'ollama',
      configured_model: 'qwen3.5:4b',
      base_url: 'http://127.0.0.1:11434',
      cli_found: false,
      cli_path: null,
      server_reachable: false,
      reachable: false,
      model_available: false,
      installed_models: [],
      status: 'cli_missing',
      summary: 'Ollama CLI was not found.',
      suggested_commands: ['winget install Ollama.Ollama', 'ollama pull qwen3.5:4b'],
      error: 'connection refused',
    },
    tts: 'dummy',
    search: 'ok',
    weather: 'disabled',
    playback: 'simulate',
  },
  weather: {
    available: false,
    location: 'Ankara',
    summary: 'No weather data.',
    temperature_c: null,
    humidity_percent: null,
    wind_kmh: null,
    condition: null,
    source: 'disabled',
  },
  observability: {
    uptime_seconds: 42,
    announcement_prebuffer: {
      ready: 0,
      used: 0,
      failed: 0,
      required: 5,
      ready_to_broadcast: false,
    },
    generated_clips: 0,
    recent_errors: [],
    supervisor_restarts: 0,
    playback_now: {
      type: 'idle',
      title: 'Idle — waiting for music library.',
      artist: null,
      started_at: null,
    },
  },
  orchestrator: {
    running: false,
    last_tick_at: null,
    last_strategy_at: null,
    last_error: null,
    strategy: 'RadioTEDU long-horizon strategy: keep one local jazz-first channel.',
    strategy_policy: {
      single_channel: true,
      library_tracks: 0,
      goals: ['Keep RadioTEDU as one channel', 'Grow useful listener memory'],
      next_actions: ['Add music or rescan the library', 'Keep prepared announcements ready'],
      constraints: ['No invented analytics'],
    },
    strategy_revision: 1,
    memory_count: 0,
    draft_count: 0,
    self_review: 'Self-review: no recent plays yet.',
  },
  liquidsoap: {
    enabled: true,
    command: 'liquidsoap',
    command_found: false,
    command_path: null,
    running: false,
    pid: null,
    rendered: true,
    script_path: 'data/liquidsoap/radiotedu.liq',
    queue_path: 'data/liquidsoap/queue.m3u',
    mount: '/ai',
    icecast_url: 'http://127.0.0.1:8001/ai',
  },
  setup: {
    has_music: false,
    message: 'No music library found. Add audio files to data/music and click Rescan.',
  },
};

describe('Dashboard', () => {
  it('shows one RadioTEDU setup dashboard without invented data', () => {
    render(<Dashboard status={emptyStatus} onRefresh={() => undefined} />);

    expect(screen.getByRole('heading', { name: 'RadioTEDU' })).toBeInTheDocument();
    expect(screen.getByText('Idle — waiting for music library.')).toBeInTheDocument();
    expect(screen.getByText('No music library found. Add audio files to data/music and click Rescan.')).toBeInTheDocument();
    expect(screen.getByText('No plays yet.')).toBeInTheDocument();
    expect(screen.getByText('No genre data yet.')).toBeInTheDocument();
    expect(screen.getByText('Queue is empty.')).toBeInTheDocument();
    expect(screen.getByText('No logs yet.')).toBeInTheDocument();
    expect(screen.getByText('Long-Horizon Strategy')).toBeInTheDocument();
    expect(screen.getByText('RadioTEDU long-horizon strategy: keep one local jazz-first channel.')).toBeInTheDocument();
    expect(screen.getByText('Keep RadioTEDU as one channel')).toBeInTheDocument();
    expect(screen.getByText('Add music or rescan the library')).toBeInTheDocument();
    expect(screen.getByText('Listener Notes')).toBeInTheDocument();
    expect(screen.getByText('more mellow piano at night')).toBeInTheDocument();
    expect(screen.getByText('Autonomy Ops')).toBeInTheDocument();
    expect(screen.getByText('Ollama runtime is unreachable.')).toBeInTheDocument();
    expect(screen.getByText('Restart Ollama')).toBeInTheDocument();
    expect(screen.getByText('Air Output')).toBeInTheDocument();
    expect(screen.getByText('/ai')).toBeInTheDocument();
    expect(screen.getByText('Start Icecast Air')).toBeInTheDocument();
    expect(screen.getByText('Weather')).toBeInTheDocument();
    expect(screen.getByText('No weather data.')).toBeInTheDocument();
    expect(screen.getByText('Runtime Watch')).toBeInTheDocument();
    expect(screen.getByText('unreachable (qwen3.5:4b)')).toBeInTheDocument();
    expect(screen.getByText('cli_missing: ollama pull qwen3.5:4b')).toBeInTheDocument();
    expect(screen.getByText('0 / 5')).toBeInTheDocument();
    expect(screen.getByText('Edit')).toBeInTheDocument();
    expect(screen.queryByText(/support|balance|money|donation|payment|revenue|profit/i)).toBeNull();
    expect(screen.queryByText(/OpenAIR|Grok and Roll|Backlink Broadcast|Thinking Frequencies/i)).toBeNull();
  });

  it('sends program edits through the API', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true } as Response);
    const promptMock = vi.spyOn(window, 'prompt');
    promptMock
      .mockReturnValueOnce('19:00')
      .mockReturnValueOnce('23:30')
      .mockReturnValueOnce('fri,sat')
      .mockReturnValueOnce('deep nocturnal jazz');

    render(<Dashboard status={emptyStatus} onRefresh={() => undefined} />);
    await user.click(screen.getAllByText('Edit')[0]);

    expect(fetchMock).toHaveBeenCalledWith('/api/programs/night_lab', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_time: '19:00',
        end_time: '23:30',
        days_of_week: 'fri,sat',
        vibe: 'deep nocturnal jazz',
      }),
    });
    fetchMock.mockRestore();
    promptMock.mockRestore();
  });
});

const publicStatus: PublicStatusResponse = {
  online: false,
  received_at: null,
  generated_at: null,
  expires_at: null,
  message: 'Waiting for the broadcast computer to sync.',
  channel: {
    id: 'radiotedu',
    name: 'RadioTEDU',
    description: 'AI radio from RadioTEDU.',
    host_model: 'qwen3.5:4b',
    status: 'idle',
    cover_path: '/static/generated/covers/radiotedu_station.png',
  },
  now_playing: {
    type: 'idle',
    title: 'Waiting for RadioTEDU broadcast.',
    artist: null,
    started_at: null,
  },
  current_program: {
    id: 'night_lab',
    name: 'Night Lab',
    description: 'Late-night ambient, experimental, and thoughtful tracks.',
    vibe: 'late jazz',
    start_time: '18:00',
    end_time: '23:00',
    days_of_week: 'mon,tue',
    cover_path: '/static/generated/covers/night_lab.png',
    active: 1,
  },
  next_programs: [],
  programs: [
    {
      id: 'night_lab',
      name: 'Night Lab',
      description: 'Late-night ambient, experimental, and thoughtful tracks.',
      vibe: 'late jazz',
      start_time: '18:00',
      end_time: '23:00',
      days_of_week: 'mon,tue',
      cover_path: '/static/generated/covers/night_lab.png',
      active: 1,
    },
  ],
  top_songs: [{ id: 1, title: 'Blue Room', artist: 'Alice', plays: 3 }],
  top_genres: [{ genre: 'Jazz', plays: 3 }],
  stream: { url: 'https://radiotedu.com/live.mp3', status: 'configured' },
  metrics: {
    current_listeners: 0,
    popularity: null,
    average_session: null,
  },
};

describe('PublicDashboard', () => {
  it('renders the public RadioTEDU card without operator controls or fake financial data', () => {
    window.localStorage.setItem('radiotedu_public_session', 'session_testpublic123');

    render(<PublicDashboard status={publicStatus} />);

    expect(screen.getByRole('heading', { name: 'RadioTEDU' })).toBeInTheDocument();
    expect(screen.getByText('Waiting for the broadcast computer to sync.')).toBeInTheDocument();
    expect(screen.getByText('Waiting for RadioTEDU broadcast.')).toBeInTheDocument();
    expect(screen.getByText('Current Listeners')).toBeInTheDocument();
    expect(screen.getByText('Blue Room')).toBeInTheDocument();
    expect(screen.getByText(/Jazz 100%/)).toBeInTheDocument();
    expect(screen.queryByText(/Start|Stop|Skip|Rescan|Long-Horizon Strategy|Autonomy Ops|No logs yet/i)).toBeNull();
    expect(screen.queryByText(/support|balance|money|donation|payment|revenue|profit/i)).toBeNull();
    expect(screen.queryByText(/OpenAIR|Grok and Roll|Backlink Broadcast|Thinking Frequencies/i)).toBeNull();
  });
});
