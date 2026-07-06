import { MessageSquare, Play, Radio } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { postPublicSession, type PublicStatusResponse } from '../api';

interface PublicDashboardProps {
  status: PublicStatusResponse;
}

export function PublicDashboard({ status }: PublicDashboardProps) {
  const cover = status.channel.cover_path || '/static/generated/covers/radiotedu_station.png';
  const currentProgram = status.current_program || status.programs[0] || null;
  const sessionId = useMemo(() => getSessionId(), []);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!playing) return;
    void postPublicSession('/api/public/session/start', sessionId);
    const timer = window.setInterval(() => {
      void postPublicSession('/api/public/session/heartbeat', sessionId);
    }, 15000);
    return () => {
      window.clearInterval(timer);
      void postPublicSession('/api/public/session/end', sessionId);
    };
  }, [playing, sessionId]);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio || !status.stream.url) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
      void postPublicSession('/api/public/session/end', sessionId);
      return;
    }
    void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  }

  return (
    <main className="app-shell public-shell">
      <div className="public-page">
        <header className="public-brand">
          <div className="radiotedu-mark">RT</div>
          <div>
            <strong>RadioTEDU</strong>
            <span>AI Radio</span>
          </div>
        </header>

      <section className="station-card public-card" aria-label="RadioTEDU public channel">
        <img className="station-cover" src={cover} alt="" />
        <div className="station-header">
          <div className="station-title-block">
            <h1>{status.channel.name}</h1>
            <p>by {status.channel.host_model || 'Qwen Radio Host'}</p>
          </div>
          <div className={status.online ? 'public-status public-status--live' : 'public-status'}>
            <Radio size={15} />
            {status.online ? 'Live' : 'Waiting'}
          </div>
        </div>

        {status.message ? <div className="setup-banner">{status.message}</div> : null}

        <div className="now-playing-row">
          <button className="play-button" type="button" onClick={togglePlay} aria-label={playing ? 'Pause stream' : 'Play stream'} disabled={!status.stream.url}>
            <Play size={25} fill="currentColor" />
          </button>
          <div className="now-playing-copy">
            <div className="eyebrow">
              Now Playing
              {status.online && status.channel.status === 'live' ? <span className="live-dot">Live</span> : null}
            </div>
            <strong>{status.now_playing.title}</strong>
            <span>{status.now_playing.artist || currentProgram?.name || 'RadioTEDU'}</span>
          </div>
        </div>

        {status.stream.url ? (
          <audio ref={audioRef} src={status.stream.url} preload="none" onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
        ) : (
          <div className="public-stream-empty">Stream URL is not configured yet.</div>
        )}

        <div className="metric-grid">
          <Metric label="Current Listeners" value={String(status.metrics.current_listeners)} />
          <Metric label="Popularity" value={formatPercent(status.metrics.popularity)} />
          <Metric label="Avg Listening Session" value={status.metrics.average_session || 'No data'} />
        </div>

        <div className="public-actions">
          <button className="outline-button" type="button" onClick={() => window.location.href = 'mailto:hello@radiotedu.com'}>
            <MessageSquare size={17} />
            Message
          </button>
        </div>

        <ScheduleSection program={currentProgram} />
        <TopSongs songs={status.top_songs} />
        <GenreBars genres={status.top_genres} />
      </section>
      </div>
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

function ScheduleSection({ program }: { program: PublicStatusResponse['current_program'] }) {
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

function TopSongs({ songs }: { songs: PublicStatusResponse['top_songs'] }) {
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
              <span>{song.title} <em>- {song.artist}</em></span>
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

function GenreBars({ genres }: { genres: PublicStatusResponse['top_genres'] }) {
  const total = genres.reduce((sum, genre) => sum + genre.plays, 0);
  const colors = ['#8b6ee9', '#f0be49', '#e65f8f', '#64b96a', '#e86c2d', '#4da3b5'];
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Top Genres</span>
        <span>Last 14 Days</span>
      </div>
      {genres.length && total > 0 ? (
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

function formatPercent(value: number | null) {
  return value === null ? 'No data' : `${value}%`;
}

function getSessionId() {
  const key = 'radiotedu_public_session';
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const next = `session_${crypto.randomUUID().replace(/-/g, '')}`;
  window.localStorage.setItem(key, next);
  return next;
}
