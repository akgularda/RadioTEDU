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
    name: 'Jazz Lab',
    description: 'Evening selections with deeper jazz context, experiments, and smart transitions.',
    vibe: 'late jazz',
    host_name: 'Selin',
    host_gender: 'female',
    voice: 'tr_female_cool',
    personality: 'cool, informed, playful, music-first',
    start_time: '18:00',
    end_time: '23:00',
    days_of_week: 'mon,tue',
    cover_path: '/static/generated/covers/night_lab.png',
    active: 1,
  },
  programs: [
    {
      id: 'night_lab',
      name: 'Jazz Lab',
      description: 'Evening selections with deeper jazz context, experiments, and smart transitions.',
      vibe: 'late jazz',
      host_name: 'Selin',
      host_gender: 'female',
      voice: 'tr_female_cool',
      personality: 'cool, informed, playful, music-first',
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
    website_sync: 'not_configured',
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
    health: 'missing',
    command: 'liquidsoap',
    command_found: false,
    command_path: null,
    running: false,
    pid: null,
    rendered: true,
    script_path: 'data/liquidsoap/radiotedu.liq',
    queue_path: 'data/liquidsoap/queue.m3u',
    queue_exists: true,
    queue_length: 0,
    mount: '/ai',
    icecast_url: 'http://127.0.0.1:8001/ai',
  },
  music_library: {
    total_indexed_tracks: 0,
    playable_track_count: 0,
    last_scan_time: null,
  },
  configuration: {
    MUSIC_DIR: 'data/music',
    OLLAMA_MODEL: 'qwen3.5:4b',
    TTS_COMMAND: 'dummy',
    LIQUIDSOAP_PATH: 'liquidsoap',
    LIQUIDSOAP_SCRIPT: 'data/liquidsoap/radiotedu.liq',
    ICECAST_URL: 'http://127.0.0.1:8001/ai',
    ICECAST_MOUNT: '/ai',
    PUBLIC_SYNC_URL: '',
    PUBLIC_STREAM_URL: '',
    BUFFER_SIZES: { min: 5, max: 8 },
  },
  website_sync: {
    configured: false,
    health: 'not_configured',
    public_sync_url: '',
    public_stream_url: '',
    interval_seconds: 10,
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
    expect(screen.getByText('Queue is empty.')).toBeInTheDocument();
    expect(screen.getByText('No logs yet.')).toBeInTheDocument();
    expect(screen.getByText('Long-Horizon Strategy')).toBeInTheDocument();
    expect(screen.getByText('RadioTEDU long-horizon strategy: keep one local jazz-first channel.')).toBeInTheDocument();
    expect(screen.getByText('Keep RadioTEDU as one channel')).toBeInTheDocument();
    expect(screen.getByText('Add music or rescan the library')).toBeInTheDocument();
    expect(screen.queryByText('Listener Notes')).toBeNull();
    expect(screen.queryByText('more mellow piano at night')).toBeNull();
    expect(screen.getByText('Autonomy Ops')).toBeInTheDocument();
    expect(screen.getByText('Ollama runtime is unreachable.')).toBeInTheDocument();
    expect(screen.getByText('Restart Ollama')).toBeInTheDocument();
    expect(screen.getByText('Air Output')).toBeInTheDocument();
    expect(screen.getByText('Selin / female')).toBeInTheDocument();
    expect(screen.getByText('tr_female_cool')).toBeInTheDocument();
    expect(screen.getAllByText('/ai').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: 'Run Air' }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole('button', { name: 'Stop Air' })).toBeInTheDocument();
    expect(screen.getByText('Start Icecast Air')).toBeInTheDocument();
    expect(screen.queryByText('Weather')).toBeNull();
    expect(screen.queryByText('No weather data.')).toBeNull();
    expect(screen.getByText('Runtime Watch')).toBeInTheDocument();
    expect(screen.getByText('unreachable (qwen3.5:4b)')).toBeInTheDocument();
    expect(screen.getByText('cli_missing: ollama pull qwen3.5:4b')).toBeInTheDocument();
    expect(screen.getByText('0 / 5')).toBeInTheDocument();
    expect(screen.getByText('Edit')).toBeInTheDocument();
    expect(screen.queryByText(/support|balance|money|donation|payment|revenue|profit/i)).toBeNull();
    expect(screen.queryByText(/OpenAIR|Grok and Roll|Backlink Broadcast|Thinking Frequencies/i)).toBeNull();
  });

  it('shows local operator controls, configuration, library stats, and log filters', async () => {
    const user = userEvent.setup();
    const operatorStatus = {
      ...emptyStatus,
      logs: [
        {
          level: 'info',
          message: 'Music scan complete',
          created_at: '2026-07-07T08:29:00+00:00',
          metadata: {},
        },
        {
          level: 'error',
          message: 'Icecast unreachable',
          created_at: '2026-07-07T08:30:00+00:00',
          metadata: {},
        },
      ],
      music_library: {
        total_indexed_tracks: 1,
        playable_track_count: 1,
        last_scan_time: '2026-07-07T08:29:00+00:00',
      },
      configuration: {
        MUSIC_DIR: 'F:/Songs/Jazz',
        OLLAMA_MODEL: 'qwen3.5:4b',
        TTS_COMMAND: 'python scripts/qwen_tts_command.py',
        LIQUIDSOAP_SCRIPT: 'liquidsoap/radiotedu.liq',
        ICECAST_URL: 'http://127.0.0.1:8000/ai',
        ICECAST_MOUNT: '/ai',
        PUBLIC_SYNC_URL: 'https://radiotedu.com/api/public/snapshot',
        PUBLIC_STREAM_URL: 'https://radiotedu.com/ai/stream',
        BUFFER_SIZES: { min: 5, max: 8 },
      },
      website_sync: {
        configured: true,
        health: 'configured',
        public_sync_url: 'https://radiotedu.com/api/public/snapshot',
        public_stream_url: 'https://radiotedu.com/ai/stream',
        interval_seconds: 10,
      },
    } as unknown as StatusResponse;

    render(<Dashboard status={operatorStatus} onRefresh={() => undefined} />);

    expect(screen.getByRole('button', { name: 'Say Now' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate Covers' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rescan Music' })).toBeInTheDocument();
    expect(screen.getByText('Music Library')).toBeInTheDocument();
    expect(screen.getByText('Total Indexed Tracks')).toBeInTheDocument();
    expect(screen.getByText('Playable Tracks')).toBeInTheDocument();
    expect(screen.getByText('Configuration')).toBeInTheDocument();
    expect(screen.getByText('MUSIC_DIR')).toBeInTheDocument();
    expect(screen.getByText('F:/Songs/Jazz')).toBeInTheDocument();
    expect(screen.getByText('PUBLIC_SYNC_URL')).toBeInTheDocument();
    expect(screen.getByText('Website Sync')).toBeInTheDocument();
    expect(screen.getByText('https://radiotedu.com/ai/stream')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Errors' }));

    expect(screen.getByText('Icecast unreachable')).toBeInTheDocument();
    expect(screen.queryByText('Music scan complete')).toBeNull();
  });

  it('sends manual announcements and cover generation through local admin APIs', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ queued: true }),
    } as unknown as Response);

    render(<Dashboard status={emptyStatus} onRefresh={() => undefined} />);

    await user.click(screen.getByRole('button', { name: 'Say Now' }));
    await user.type(screen.getByLabelText('Announcement text'), 'A short RadioTEDU bulletin');
    await user.click(screen.getByRole('button', { name: 'Send announcement' }));
    await user.click(screen.getByRole('button', { name: 'Generate Covers' }));

    expect(fetchMock).toHaveBeenCalledWith('/api/control/say', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'A short RadioTEDU bulletin' }),
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/art/generate-program-covers', {
      method: 'POST',
      headers: undefined,
      body: undefined,
    });
    fetchMock.mockRestore();
  });

  it('shows broadcast startup failures inline', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        started: false,
        stream: {
          reason: 'liquidsoap_missing',
          icecast_url: 'http://127.0.0.1:8001/ai',
        },
      }),
    } as unknown as Response);

    render(<Dashboard status={emptyStatus} onRefresh={() => undefined} />);
    await user.click(screen.getAllByRole('button', { name: 'Run Air' })[1]);

    expect(await screen.findByText('Run Air cannot start yet: Liquidsoap is not installed or not in PATH. Icecast mount is configured as http://127.0.0.1:8001/ai.')).toBeInTheDocument();
    fetchMock.mockRestore();
  });

  it('sends program edits through the API', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true } as Response);

    render(<Dashboard status={emptyStatus} onRefresh={() => undefined} />);
    await user.click(screen.getAllByText('Edit')[0]);
    await user.clear(screen.getByLabelText('Start time'));
    await user.type(screen.getByLabelText('Start time'), '19:00');
    await user.clear(screen.getByLabelText('End time'));
    await user.type(screen.getByLabelText('End time'), '23:30');
    await user.clear(screen.getByLabelText('Days'));
    await user.type(screen.getByLabelText('Days'), 'fri,sat');
    await user.clear(screen.getByLabelText('Vibe'));
    await user.type(screen.getByLabelText('Vibe'), 'deep nocturnal jazz');
    await user.clear(screen.getByLabelText('Host name'));
    await user.type(screen.getByLabelText('Host name'), 'Selin');
    await user.clear(screen.getByLabelText('Host gender'));
    await user.type(screen.getByLabelText('Host gender'), 'female');
    await user.clear(screen.getByLabelText('Voice id'));
    await user.type(screen.getByLabelText('Voice id'), 'tr_female_cool');
    await user.clear(screen.getByLabelText('Personality'));
    await user.type(screen.getByLabelText('Personality'), 'cool, informed, playful');
    await user.click(screen.getByRole('button', { name: 'Save program' }));

    expect(fetchMock).toHaveBeenCalledWith('/api/programs/night_lab', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_time: '19:00',
        end_time: '23:30',
        days_of_week: 'fri,sat',
        vibe: 'deep nocturnal jazz',
        host_name: 'Selin',
        host_gender: 'female',
        voice: 'tr_female_cool',
        personality: 'cool, informed, playful',
      }),
    });
    fetchMock.mockRestore();
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
    name: 'Jazz Lab',
    description: 'Evening selections with deeper jazz context, experiments, and smart transitions.',
    vibe: 'late jazz',
    host_name: 'Selin',
    host_gender: 'female',
    voice: 'tr_female_cool',
    personality: 'cool, informed, playful, music-first',
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
      name: 'Jazz Lab',
      description: 'Evening selections with deeper jazz context, experiments, and smart transitions.',
      vibe: 'late jazz',
      host_name: 'Selin',
      host_gender: 'female',
      voice: 'tr_female_cool',
      personality: 'cool, informed, playful, music-first',
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
  current_minutes_left: 42,
  next_program: {
    id: 'morning_signal',
    name: 'TEDU Dawn',
    description: 'A gentle campus morning handoff.',
    vibe: 'morning jazz',
    host_name: 'Ece',
    host_gender: 'female',
    voice: 'tr_female_warm',
    personality: 'warm, precise',
    start_time: '06:00',
    end_time: '10:00',
    days_of_week: 'mon,tue,wed,thu,fri',
    cover_path: '/static/generated/covers/morning_signal.png',
    active: 1,
  },
  content_breakdown: [
    { label: 'Music', percent: 84 },
    { label: 'Talking', percent: 16 },
  ],
  activity: [
    {
      kind: 'listener',
      actor: 'Listener',
      content: 'more mellow piano after midnight',
      created_at: '2026-07-06T00:02:00+00:00',
    },
    {
      kind: 'broadcast',
      actor: 'RadioTEDU',
      content: 'Queued Blue Room by Alice.',
      created_at: '2026-07-06T00:03:00+00:00',
    },
  ],
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
    expect(screen.getByText('Broadcast Status')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy Stream Link' })).toBeInTheDocument();
    expect(screen.getByText('Blue Room')).toBeInTheDocument();
    expect(screen.getByText('42m left')).toBeInTheDocument();
    expect(screen.getByText(/Up next at 06:00: TEDU Dawn/)).toBeInTheDocument();
    expect(screen.getByText(/Jazz 100%/)).toBeInTheDocument();
    expect(screen.getByText('Content Breakdown')).toBeInTheDocument();
    expect(screen.getByText(/Music 84%/)).toBeInTheDocument();
    expect(screen.getByText('RadioTEDU Activity')).toBeInTheDocument();
    expect(screen.getByText('more mellow piano after midnight')).toBeInTheDocument();
    expect(screen.getByText('Queued Blue Room by Alice.')).toBeInTheDocument();
    expect(screen.queryByText(/Start|Stop|Skip|Rescan|Long-Horizon Strategy|Autonomy Ops|No logs yet/i)).toBeNull();
    expect(screen.queryByText(/support|balance|money|donation|payment|revenue|profit/i)).toBeNull();
    expect(screen.queryByText(/OpenAIR|Grok and Roll|Backlink Broadcast|Thinking Frequencies/i)).toBeNull();
  });

  it('acknowledges copying the stream link when Clipboard API is unavailable', async () => {
    const user = userEvent.setup();

    render(<PublicDashboard status={publicStatus} />);

    await user.click(screen.getByRole('button', { name: 'Copy Stream Link' }));

    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
  });
});
