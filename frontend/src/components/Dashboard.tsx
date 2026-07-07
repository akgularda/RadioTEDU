import {
  Image,
  MessageSquare,
  Play,
  RefreshCw,
  SkipForward,
  Square,
  Pencil,
} from 'lucide-react';
import { type FormEvent, useState } from 'react';

import { patchJson, postControl, type Program, type StatusResponse } from '../api';

interface DashboardProps {
  status: StatusResponse;
  onRefresh: () => void;
}

type Notice = {
  tone: 'info' | 'error';
  text: string;
};

type ProgramDraft = {
  start_time: string;
  end_time: string;
  days_of_week: string;
  vibe: string;
  host_name: string;
  host_gender: string;
  voice: string;
  personality: string;
};

export function Dashboard({ status, onRefresh }: DashboardProps) {
  const cover = status.channel.cover_path || '/static/generated/covers/radiotedu_station.png';
  const logo = '/static/generated/covers/radiotedu_logo.png';
  const isLive = status.channel.status === 'live';
  const currentProgram = status.current_program || status.programs[0] || null;
  const [notice, setNotice] = useState<Notice | null>(null);
  const [sayOpen, setSayOpen] = useState(false);
  const [sayText, setSayText] = useState('');
  const [editingProgram, setEditingProgram] = useState<Program | null>(null);
  const [programDraft, setProgramDraft] = useState<ProgramDraft | null>(null);

  async function control(path: string, body?: unknown) {
    const result = await postControl(path, body);
    onRefresh();
    return result;
  }

  async function runAir() {
    const result = await control('/api/air/start');
    if (result.started === false) {
      const stream = result.stream as { reason?: string; command?: string; icecast_url?: string } | undefined;
      setNotice({
        tone: 'error',
        text: stream?.reason === 'liquidsoap_missing'
          ? `Run Air cannot start yet: Liquidsoap is not installed or not in PATH. Icecast mount is configured as ${stream.icecast_url || '/ai'}.`
          : `Run Air could not start: ${stream?.reason || 'unknown error'}`,
      });
      return;
    }
    setNotice({ tone: 'info', text: 'Broadcast loop started.' });
  }

  async function stopAir() {
    await control('/api/air/stop');
  }

  async function submitSayNow(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = sayText.trim();
    if (!text) {
      return;
    }
    await control('/api/control/say', { text });
    setSayText('');
    setSayOpen(false);
    setNotice({ tone: 'info', text: 'Announcement queued.' });
  }

  function editProgram(program: Program) {
    setEditingProgram(program);
    setProgramDraft({
      start_time: program.start_time,
      end_time: program.end_time,
      days_of_week: program.days_of_week,
      vibe: program.vibe || '',
      host_name: program.host_name || '',
      host_gender: program.host_gender || '',
      voice: program.voice || '',
      personality: program.personality || '',
    });
  }

  function updateProgramDraft(key: keyof ProgramDraft, value: string) {
    setProgramDraft((draft) => (draft ? { ...draft, [key]: value } : draft));
  }

  async function submitProgramEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingProgram || !programDraft) {
      return;
    }
    await patchJson(`/api/programs/${editingProgram.id}`, {
      start_time: programDraft.start_time,
      end_time: programDraft.end_time,
      days_of_week: programDraft.days_of_week,
      vibe: programDraft.vibe,
      host_name: programDraft.host_name,
      host_gender: programDraft.host_gender,
      voice: programDraft.voice,
      personality: programDraft.personality,
    });
    setEditingProgram(null);
    setProgramDraft(null);
    setNotice({ tone: 'info', text: 'Program updated.' });
    onRefresh();
  }

  return (
    <main className="app-shell admin-shell">
      <section className="station-card admin-console" aria-label="RadioTEDU channel">
        <div className="admin-brandbar">
          <img src={logo} alt="RadioTEDU" />
          <div>
            <strong>RadioTEDU Air</strong>
            <span>{status.health.playback} / {status.liquidsoap.mount}</span>
          </div>
          <i className={status.channel.status === 'live' ? 'signal-line signal-line--live' : 'signal-line'} />
        </div>

        <img className="station-cover admin-cover" src={cover} alt="" />

        <div className="station-header">
          <div className="station-title-block">
            <h1>{status.channel.name}</h1>
            <p>{status.health.llm_runtime.status} / {status.channel.host_model || 'qwen2.5:0.5b-instruct'}</p>
          </div>
          <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh">
            <RefreshCw size={18} />
          </button>
        </div>

        {status.setup.message ? <div className="setup-banner">{status.setup.message}</div> : null}

        <div className="now-playing-row">
          <button className="play-button" type="button" onClick={runAir} aria-label="Run Air">
            <Play size={25} fill="currentColor" />
          </button>
          <div className="now-playing-copy">
            <div className="eyebrow">
              Now Playing
              {isLive ? <span className="live-dot">Live</span> : null}
            </div>
            <strong>{status.now_playing.title}</strong>
            <span>{status.now_playing.artist || (currentProgram ? currentProgram.name : 'RadioTEDU')}</span>
          </div>
        </div>

        <div className="metric-grid">
          <Metric label="Listeners" value={formatNullable(status.metrics.local_listeners)} />
          <Metric label="Prebuffer" value={`${status.observability.announcement_prebuffer.ready}/${status.observability.announcement_prebuffer.required}`} />
          <Metric label="Air" value={status.liquidsoap.running ? 'On' : 'Off'} />
          <Metric label="LLM" value={status.health.llm_runtime.status} />
        </div>

        <div className="actions-grid">
          <button className="outline-button" type="button" onClick={() => setSayOpen((open) => !open)}>
            <MessageSquare size={17} />
            Say Now
          </button>
          <button className="outline-button" type="button" onClick={() => control('/api/art/generate-program-covers')}>
            <Image size={17} />
            Generate Covers
          </button>
        </div>

        {notice ? (
          <div className={`action-message action-message--${notice.tone}`} role={notice.tone === 'error' ? 'alert' : 'status'}>
            {notice.text}
          </div>
        ) : null}

        {sayOpen ? (
          <form className="quick-form" onSubmit={submitSayNow}>
            <label>
              <span>Announcement text</span>
              <textarea value={sayText} onChange={(event) => setSayText(event.currentTarget.value)} rows={3} />
            </label>
            <div className="form-actions">
              <button className="outline-button" type="submit">
                Send announcement
              </button>
              <button className="inline-tool" type="button" onClick={() => setSayOpen(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : null}

        <div className="control-strip">
          <button type="button" onClick={runAir}>
            <Play size={15} />
            Run Air
          </button>
          <button type="button" onClick={stopAir}>
            <Square size={15} />
            Stop Air
          </button>
          <button type="button" onClick={() => control('/api/control/skip')}>
            <SkipForward size={15} />
            Skip Track
          </button>
          <button type="button" onClick={() => control('/api/music/rescan')}>
            <RefreshCw size={15} />
            Rescan Music
          </button>
        </div>

        <ScheduleSection program={currentProgram} />
        <ProgramsPanel programs={status.programs} currentProgramId={currentProgram?.id || null} onEdit={editProgram} />
        {editingProgram && programDraft ? (
          <ProgramEditPanel
            program={editingProgram}
            draft={programDraft}
            onChange={updateProgramDraft}
            onSubmit={submitProgramEdit}
            onCancel={() => {
              setEditingProgram(null);
              setProgramDraft(null);
            }}
          />
        ) : null}
        <QueuePanel queue={status.queue} />
        <AirOutputPanel liquidsoap={status.liquidsoap} onCommand={control} />
        <MusicLibraryPanel library={status.music_library} />
        <ConfigurationPanel configuration={status.configuration} />
        <WebsiteSyncPanel sync={status.website_sync} />
        <StrategyPanel orchestrator={status.orchestrator} onCommand={control} />
        <AutonomyOps incidents={status.incidents} tasks={status.autonomous_tasks} />
        <RuntimeWatch observability={status.observability} />
        <SystemHealth health={status.health} />
        <LogPanel logs={status.logs} />
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-cell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ScheduleSection({ program }: { program: StatusResponse['current_program'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Schedule</span>
        {program ? <span>{program.end_time}</span> : null}
      </div>
      {program ? (
        <>
          <div className="schedule-title">{program.name}</div>
          <div className="progress-track"><span /></div>
          <p className="compact-copy">{program.vibe || program.description}</p>
        </>
      ) : (
        <p className="muted">Nothing scheduled</p>
      )}
    </section>
  );
}

function TopSongs({ songs }: { songs: StatusResponse['top_songs'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Top Songs</span>
        <span>Last 14 Days</span>
      </div>
      {songs.length ? (
        <ol className="rank-list">
          {songs.map((song) => (
            <li key={song.id}>
              <span>{song.title} <em>— {song.artist}</em></span>
              <strong>{song.plays}</strong>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No plays yet.</p>
      )}
    </section>
  );
}

function GenreBars({ genres }: { genres: StatusResponse['top_genres'] }) {
  const total = genres.reduce((sum, genre) => sum + genre.plays, 0);
  const colors = ['#8b6ee9', '#f0be49', '#e65f8f', '#64b96a', '#e86c2d', '#4da3b5'];
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Top Genres</span>
        <span>Last 14 Days</span>
      </div>
      {genres.length ? (
        <>
          <div className="genre-track">
            {genres.map((genre, index) => (
              <span
                key={genre.genre}
                style={{
                  backgroundColor: colors[index % colors.length],
                  width: `${Math.max(8, (genre.plays / total) * 100)}%`,
                }}
              />
            ))}
          </div>
          <div className="genre-legend">
            {genres.map((genre, index) => (
              <span key={genre.genre}>
                <i style={{ backgroundColor: colors[index % colors.length] }} />
                {genre.genre} {Math.round((genre.plays / total) * 100)}%
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className="muted">No genre data yet.</p>
      )}
    </section>
  );
}

function ProgramsPanel({
  programs,
  currentProgramId,
  onEdit,
}: {
  programs: StatusResponse['programs'];
  currentProgramId: string | null;
  onEdit: (program: Program) => void;
}) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Programs</span>
        <span>{programs.length}</span>
      </div>
      <div className="program-list">
        {programs.map((program) => (
          <article key={program.id} className={program.id === currentProgramId ? 'program-item program-item--active' : 'program-item'}>
            <img src={program.cover_path || '/static/generated/covers/radiotedu_station.png'} alt="" />
            <div>
              <strong>{program.name}</strong>
              <span>{program.host_name ? `${program.host_name} / ${program.host_gender || 'host'}` : program.vibe || 'RadioTEDU'}</span>
              <small>{program.voice || 'voice'}</small>
              <small>{program.start_time}-{program.end_time}</small>
              <button className="inline-tool" type="button" onClick={() => onEdit(program)}>
                <Pencil size={13} />
                Edit
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

const programEditFields: Array<{ key: keyof ProgramDraft; label: string }> = [
  { key: 'start_time', label: 'Start time' },
  { key: 'end_time', label: 'End time' },
  { key: 'days_of_week', label: 'Days' },
  { key: 'vibe', label: 'Vibe' },
  { key: 'host_name', label: 'Host name' },
  { key: 'host_gender', label: 'Host gender' },
  { key: 'voice', label: 'Voice id' },
  { key: 'personality', label: 'Personality' },
];

function ProgramEditPanel({
  program,
  draft,
  onChange,
  onSubmit,
  onCancel,
}: {
  program: Program;
  draft: ProgramDraft;
  onChange: (key: keyof ProgramDraft, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCancel: () => void;
}) {
  return (
    <form className="section-block program-editor" onSubmit={onSubmit}>
      <div className="section-heading">
        <span>Edit {program.name}</span>
        <span>{program.id}</span>
      </div>
      <div className="form-grid">
        {programEditFields.map((field) => (
          <label key={field.key}>
            <span>{field.label}</span>
            <input value={draft[field.key]} onChange={(event) => onChange(field.key, event.currentTarget.value)} />
          </label>
        ))}
      </div>
      <div className="form-actions">
        <button className="outline-button" type="submit">
          Save program
        </button>
        <button className="inline-tool" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function AirOutputPanel({
  liquidsoap,
  onCommand,
}: {
  liquidsoap: StatusResponse['liquidsoap'];
  onCommand: (path: string, body?: unknown) => Promise<unknown>;
}) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Air Output</span>
        <span>{liquidsoap.health}</span>
      </div>
      <div className="health-grid">
        <div>
          <span>Icecast Mount</span>
          <strong>{liquidsoap.mount}</strong>
        </div>
        <div>
          <span>Stream URL</span>
          <strong>{liquidsoap.icecast_url}</strong>
        </div>
        <div>
          <span>Liquidsoap</span>
          <strong>{liquidsoap.command_found ? liquidsoap.command : 'Not installed'}</strong>
        </div>
        <div>
          <span>Queue</span>
          <strong>{liquidsoap.queue_exists ? `${liquidsoap.queue_length} items` : 'Not rendered'}</strong>
        </div>
      </div>
      <div className="strategy-actions">
        <button type="button" onClick={() => onCommand('/api/liquidsoap/render')}>
          <RefreshCw size={15} />
          Render Config
        </button>
        <button type="button" onClick={() => onCommand('/api/liquidsoap/start')}>
          <Play size={15} />
          Start Icecast Air
        </button>
        <button type="button" onClick={() => onCommand('/api/liquidsoap/stop')}>
          <Square size={15} />
          Stop Icecast Air
        </button>
      </div>
    </section>
  );
}

function MusicLibraryPanel({ library }: { library: StatusResponse['music_library'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Music Library</span>
        <span>{library.playable_track_count ? 'Ready' : 'Empty'}</span>
      </div>
      <div className="health-grid">
        <div>
          <span>Total Indexed Tracks</span>
          <strong>{library.total_indexed_tracks}</strong>
        </div>
        <div>
          <span>Playable Tracks</span>
          <strong>{library.playable_track_count}</strong>
        </div>
        <div>
          <span>Last Scan</span>
          <strong>{library.last_scan_time ? new Date(library.last_scan_time).toLocaleString() : 'No data'}</strong>
        </div>
      </div>
    </section>
  );
}

function ConfigurationPanel({ configuration }: { configuration: StatusResponse['configuration'] }) {
  const entries = Object.entries(configuration);
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Configuration</span>
        <span>Local</span>
      </div>
      <div className="health-grid config-grid">
        {entries.map(([key, value]) => (
          <div key={key}>
            <span>{key}</span>
            <strong>{formatConfigValue(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function WebsiteSyncPanel({ sync }: { sync: StatusResponse['website_sync'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Website Sync</span>
        <span>{sync.health}</span>
      </div>
      <div className="health-grid">
        <div>
          <span>Snapshot Push</span>
          <strong>{sync.pusher?.running ? 'Running' : sync.configured ? 'Configured' : 'Not configured'}</strong>
        </div>
        <div>
          <span>Interval</span>
          <strong>{sync.interval_seconds}s</strong>
        </div>
        <div>
          <span>Failures</span>
          <strong>{sync.pusher ? sync.pusher.consecutive_failures : 'No data'}</strong>
        </div>
        <div>
          <span>Public Stream</span>
          <strong>{sync.public_stream_url ? 'Configured' : 'Not configured'}</strong>
        </div>
      </div>
    </section>
  );
}

function QueuePanel({ queue }: { queue: StatusResponse['queue'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Queue</span>
        <span>{queue.length}</span>
      </div>
      {queue.length ? (
        <ol className="rank-list">
          {queue.map((item, index) => (
            <li key={`${item.title}-${index}`}>
              <span>{item.title} <em>{item.artist ? `— ${item.artist}` : item.type}</em></span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">Queue is empty.</p>
      )}
    </section>
  );
}

function StrategyPanel({
  orchestrator,
  onCommand,
}: {
  orchestrator: StatusResponse['orchestrator'];
  onCommand: (path: string, body?: unknown) => Promise<unknown>;
}) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Long-Horizon Strategy</span>
        <span>{orchestrator.running ? 'Running' : 'Idle'}</span>
      </div>
      <p className="strategy-copy">
        {orchestrator.strategy || 'No long-horizon strategy has been written yet.'}
      </p>
      {orchestrator.self_review ? <p className="strategy-copy">{orchestrator.self_review}</p> : null}
      {orchestrator.strategy_policy ? (
        <div className="strategy-policy">
          <div>
            <span>Goals</span>
            {orchestrator.strategy_policy.goals.map((goal) => (
              <strong key={goal}>{goal}</strong>
            ))}
          </div>
          <div>
            <span>Next Actions</span>
            {orchestrator.strategy_policy.next_actions.map((action) => (
              <strong key={action}>{action}</strong>
            ))}
          </div>
        </div>
      ) : null}
      <div className="strategy-actions">
        <button type="button" onClick={() => onCommand('/api/autonomy/strategy')}>
          <RefreshCw size={15} />
          Refresh strategy
        </button>
        <button type="button" onClick={() => onCommand('/api/autonomy/tick')}>
          <SkipForward size={15} />
          Run tick
        </button>
      </div>
      <div className="strategy-meta">
        <span>Revision {orchestrator.strategy_revision}</span>
        <span>{orchestrator.memory_count} memory notes</span>
        <span>{orchestrator.draft_count} local drafts</span>
        <span>{orchestrator.last_strategy_at ? `Updated ${new Date(orchestrator.last_strategy_at).toLocaleString()}` : 'Awaiting first strategy refresh'}</span>
      </div>
      {orchestrator.last_error ? <p className="error-copy">{orchestrator.last_error}</p> : null}
    </section>
  );
}

function AutonomyOps({
  incidents,
  tasks,
}: {
  incidents: StatusResponse['incidents'];
  tasks: StatusResponse['autonomous_tasks'];
}) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Autonomy Ops</span>
        <span>{incidents.length ? `${incidents.length} open` : 'Clear'}</span>
      </div>
      {incidents.length ? (
        <ol className="note-list">
          {incidents.map((incident) => (
            <li key={incident.id}>
              <span>{incident.summary}</span>
              <small>{incident.severity} / {incident.component}</small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No open incidents.</p>
      )}
      {tasks.length ? (
        <ol className="note-list">
          {tasks.map((task) => (
            <li key={task.id}>
              <span>{task.title}</span>
              <small>{task.status} / priority {task.priority}</small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No queued autonomy tasks.</p>
      )}
    </section>
  );
}

function ListenerNotes({ messages }: { messages: StatusResponse['listener_messages'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Listener Notes</span>
        <span>{messages.length}</span>
      </div>
      {messages.length ? (
        <ol className="note-list">
          {messages.slice(0, 5).map((item) => (
            <li key={`${item.created_at}-${item.source}`}>
              <span>{item.content}</span>
              <small>{item.source}</small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No listener notes yet.</p>
      )}
    </section>
  );
}

function WeatherPanel({ weather }: { weather: StatusResponse['weather'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Weather</span>
        <span>{weather.available ? weather.location : 'No data'}</span>
      </div>
      <p className={weather.available ? 'strategy-copy' : 'muted'}>{weather.summary || 'No weather data.'}</p>
      {weather.available ? (
        <div className="strategy-meta">
          {weather.temperature_c !== null ? <span>{Math.round(weather.temperature_c)} C</span> : null}
          {weather.humidity_percent !== null ? <span>Humidity {weather.humidity_percent}%</span> : null}
          {weather.wind_kmh !== null ? <span>Wind {Math.round(weather.wind_kmh)} km/h</span> : null}
          {weather.condition ? <span>{weather.condition}</span> : null}
        </div>
      ) : null}
    </section>
  );
}

function RuntimeWatch({ observability }: { observability: StatusResponse['observability'] }) {
  const prebuffer = observability.announcement_prebuffer;
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Runtime Watch</span>
        <span>{prebuffer.ready_to_broadcast ? 'Ready' : 'Warming'}</span>
      </div>
      <div className="health-grid">
        <div>
          <span>Prebuffer</span>
          <strong>{prebuffer.ready} / {prebuffer.required}</strong>
        </div>
        <div>
          <span>Uptime</span>
          <strong>{formatDuration(observability.uptime_seconds)}</strong>
        </div>
        <div>
          <span>Generated Clips</span>
          <strong>{observability.generated_clips}</strong>
        </div>
        <div>
          <span>Recent Errors</span>
          <strong>{observability.recent_errors.length}</strong>
        </div>
        <div>
          <span>Restarts</span>
          <strong>{observability.supervisor_restarts}</strong>
        </div>
      </div>
    </section>
  );
}

function LogPanel({ logs }: { logs: StatusResponse['logs'] }) {
  const [level, setLevel] = useState<'all' | 'info' | 'warning' | 'error'>('all');
  const filtered = level === 'all' ? logs : logs.filter((log) => log.level.toLowerCase() === level);
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Agent Logs</span>
        <span>{filtered.length}</span>
      </div>
      <div className="log-filter">
        <button type="button" aria-pressed={level === 'all'} onClick={() => setLevel('all')}>All</button>
        <button type="button" aria-pressed={level === 'info'} onClick={() => setLevel('info')}>Info</button>
        <button type="button" aria-pressed={level === 'warning'} onClick={() => setLevel('warning')}>Warnings</button>
        <button type="button" aria-pressed={level === 'error'} onClick={() => setLevel('error')}>Errors</button>
      </div>
      {filtered.length ? (
        <ol className="log-list">
          {filtered.slice(0, 12).map((log, index) => (
            <li key={`${log.created_at}-${index}`}>
              <strong>{log.level}</strong>
              <span>{log.message}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No logs yet.</p>
      )}
    </section>
  );
}

function SystemHealth({ health }: { health: StatusResponse['health'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>System Health</span>
        <span>Local</span>
      </div>
      <div className="health-grid">
        {Object.entries(health).map(([key, value]) => (
          <div key={key}>
            <span>{key}</span>
            <strong>{formatHealthValue(key, value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatHealthValue(key: string, value: StatusResponse['health'][keyof StatusResponse['health']]) {
  if (key === 'llm_runtime' && typeof value === 'object' && value !== null) {
    return `${value.status} (${value.configured_model})`;
  }
  if (key === 'llm_setup' && typeof value === 'object' && value !== null && 'suggested_commands' in value) {
    const setup = value as StatusResponse['health']['llm_setup'];
    const pullCommand = setup.suggested_commands.find((command) => command.startsWith('ollama pull'));
    const command = pullCommand ?? setup.suggested_commands[0];
    return command ? `${setup.status}: ${command}` : `${setup.status}: ${setup.summary}`;
  }
  return String(value);
}

function formatNullable(value: number | null) {
  return value === null ? 'No data' : String(value);
}

function formatPercent(value: number | null) {
  return value === null ? 'No data' : `${value}%`;
}

function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

function formatConfigValue(value: unknown) {
  if (value && typeof value === 'object') {
    const buffer = value as { min?: number; max?: number };
    if ('min' in buffer || 'max' in buffer) {
      return `${buffer.min ?? 0} / ${buffer.max ?? 0}`;
    }
    return JSON.stringify(value);
  }
  return String(value || 'Not configured');
}
