import {
  Download,
  MessageSquare,
  Play,
  RefreshCw,
  SkipForward,
  Square,
  Pencil,
} from 'lucide-react';

import { patchJson, postControl, type Program, type StatusResponse } from '../api';

interface DashboardProps {
  status: StatusResponse;
  onRefresh: () => void;
}

export function Dashboard({ status, onRefresh }: DashboardProps) {
  const cover = status.channel.cover_path || '/static/generated/covers/radiotedu_station.png';
  const isLive = status.channel.status === 'live';
  const currentProgram = status.current_program || status.programs[0] || null;

  async function control(path: string, body?: unknown) {
    await postControl(path, body);
    onRefresh();
  }

  async function sendFeedback() {
    const text = window.prompt('Send RadioTEDU a local listener note');
    if (!text?.trim()) {
      return;
    }
    await control('/api/listener/feedback', { text, source: 'dashboard' });
  }

  async function editProgram(program: Program) {
    const start = window.prompt('Start time', program.start_time);
    if (!start) return;
    const end = window.prompt('End time', program.end_time);
    if (!end) return;
    const days = window.prompt('Days', program.days_of_week);
    if (!days) return;
    const vibe = window.prompt('Vibe', program.vibe || '');
    if (vibe === null) return;
    await patchJson(`/api/programs/${program.id}`, {
      start_time: start,
      end_time: end,
      days_of_week: days,
      vibe,
    });
    onRefresh();
  }

  return (
    <main className="app-shell">
      <section className="station-card" aria-label="RadioTEDU channel">
        <img className="station-cover" src={cover} alt="" />

        <div className="station-header">
          <div className="station-title-block">
            <h1>{status.channel.name}</h1>
            <p>by {status.channel.host_model || 'qwen2.5:0.5b-instruct'}</p>
          </div>
          <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh">
            <RefreshCw size={18} />
          </button>
        </div>

        {status.setup.message ? <div className="setup-banner">{status.setup.message}</div> : null}

        <div className="now-playing-row">
          <button className="play-button" type="button" onClick={() => control('/api/control/start')} aria-label="Start">
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
          <Metric label="Local Listeners" value={formatNullable(status.metrics.local_listeners)} />
          <Metric label="Popularity" value={formatPercent(status.metrics.popularity)} />
          <Metric label="Feedback Notes" value={String(status.metrics.feedback_count)} />
          <Metric label="Avg Listening Session" value={status.metrics.average_session || 'No data'} />
        </div>

        <div className="actions-grid">
          <button className="outline-button" type="button" onClick={sendFeedback}>
            <MessageSquare size={17} />
            Message
          </button>
          <button className="outline-button outline-button--wide" type="button" onClick={() => window.alert('No generated clip is available yet.')}>
            <Download size={17} />
            Clip latest segment
          </button>
        </div>

        <div className="control-strip">
          <button type="button" onClick={() => control('/api/control/stop')}>
            <Square size={15} />
            Stop
          </button>
          <button type="button" onClick={() => control('/api/control/skip')}>
            <SkipForward size={15} />
            Skip
          </button>
          <button type="button" onClick={() => control('/api/music/rescan')}>
            <RefreshCw size={15} />
            Rescan
          </button>
        </div>

        <ScheduleSection program={currentProgram} />
        <TopSongs songs={status.top_songs} />
        <GenreBars genres={status.top_genres} />
        <ProgramsPanel programs={status.programs} currentProgramId={currentProgram?.id || null} onEdit={editProgram} />
        <QueuePanel queue={status.queue} />
        <StrategyPanel orchestrator={status.orchestrator} onCommand={control} />
        <AutonomyOps incidents={status.incidents} tasks={status.autonomous_tasks} />
        <ListenerNotes messages={status.listener_messages} />
        <WeatherPanel weather={status.weather} />
        <RuntimeWatch observability={status.observability} />
        <LogPanel logs={status.logs} />
        <SystemHealth health={status.health} />
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
          <p>{program.description}</p>
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
  onEdit: (program: Program) => Promise<void>;
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
              <span>{program.vibe || 'RadioTEDU'}</span>
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
  onCommand: (path: string, body?: unknown) => Promise<void>;
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
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Agent Logs</span>
        <span>Recent</span>
      </div>
      {logs.length ? (
        <ol className="log-list">
          {logs.slice(0, 6).map((log, index) => (
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
