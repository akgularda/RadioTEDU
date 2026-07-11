import { Copy, MessageSquare, Pause, Play, Radio } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { postPublicSession, type PublicStatusResponse } from '../api';

interface PublicDashboardProps {
  status: PublicStatusResponse;
  connectionError?: string | null;
}

export function PublicDashboard({ status, connectionError = null }: PublicDashboardProps) {
  const cover = status.channel.cover_path || '/static/generated/covers/radiotedu_station.png';
  const logo = '/static/generated/covers/radiotedu_logo_source.png';
  const currentProgram = status.current_program || status.programs[0] || null;
  const sessionId = useMemo(() => getSessionId(), []);
  const [playing, setPlaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const copyResetRef = useRef<number | null>(null);

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

  useEffect(() => {
    return () => {
      if (copyResetRef.current) {
        window.clearTimeout(copyResetRef.current);
      }
    };
  }, []);

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

  async function copyStreamLink() {
    if (!status.stream.url) return;
    setCopied(true);
    if (copyResetRef.current) {
      window.clearTimeout(copyResetRef.current);
    }
    copyResetRef.current = window.setTimeout(() => setCopied(false), 2000);
    await copyText(status.stream.url);
  }

  const broadcastStatus = status.online && status.channel.status === 'live' ? 'Live' : 'Waiting';

  return (
    <main className="app-shell public-shell">
      <div className="public-page">
        <header className="public-brand">
          <img className="public-logo" src={logo} alt="RadioTEDU" />
          <div className="public-brand-copy">
            <strong>RadioTEDU</strong>
            <span>AI Radio · Ankara</span>
          </div>
        </header>

        <section className="station-card public-card" aria-label="RadioTEDU public channel">
          <img className="station-cover public-cover" src={cover} alt="RadioTEDU station cover" />
          <div className="station-header public-station-header">
            <div className="station-title-block">
              <h1>{status.channel.name}</h1>
              <p>by {status.channel.host_model || 'Qwen Radio Host'}</p>
            </div>
            <div className={status.online ? 'public-status public-status--live' : 'public-status'}>
              <Radio size={15} />
              {broadcastStatus}
            </div>
          </div>

          {status.message ? <div className="setup-banner">{status.message}</div> : null}
          {connectionError ? (
            <div className="public-connection-notice" role="status">
              Live data connection interrupted. Showing the last received broadcast snapshot.
            </div>
          ) : null}

          <div className="now-playing-row public-now-playing">
            <button className="play-button" type="button" onClick={togglePlay} aria-label={playing ? 'Pause stream' : 'Play stream'} disabled={!status.stream.url}>
              {playing ? <Pause size={25} fill="currentColor" /> : <Play size={25} fill="currentColor" />}
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
            <>
              <audio ref={audioRef} src={status.stream.url} preload="none" onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
              <div className="public-stream-line">
                <span>Stream</span>
                <strong>{status.stream.status === 'configured' ? 'Configured' : status.stream.status}</strong>
              </div>
            </>
          ) : (
            <div className="public-stream-empty">Stream URL is not configured yet.</div>
          )}

          <div className="metric-grid public-metrics">
            <Metric label="Current Listeners" value={String(status.metrics.current_listeners)} />
            <Metric label="Popularity" value={formatPercent(status.metrics.popularity)} />
            <Metric label="Avg Listening Session" value={status.metrics.average_session || 'No data'} />
            <Metric label="Broadcast Status" value={broadcastStatus} />
          </div>

          <div className="public-actions">
            <button className="outline-button" type="button" onClick={() => window.location.href = 'mailto:hello@radiotedu.com'}>
              <MessageSquare size={17} />
              Message
            </button>
            <button className="outline-button" type="button" onClick={copyStreamLink} disabled={!status.stream.url}>
              <Copy size={17} />
              {copied ? 'Copied' : 'Copy Stream Link'}
            </button>
          </div>

          <div className="public-editorial-grid">
            <ScheduleSection
              program={currentProgram}
              minutesLeft={status.current_minutes_left}
              nextProgram={status.next_program}
              fallbackCover={cover}
            />
            <ShareCard card={status.share_card} />
            <TopSongs songs={status.top_songs} />
            <GenreBars genres={status.top_genres} />
            <ContentBreakdown items={status.content_breakdown} />
            <ActivityFeed items={status.activity} />
          </div>
        </section>
      </div>
    </main>
  );
}

function ShareCard({ card }: { card: PublicDashboardProps['status']['share_card'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Share Card</span>
        <span>Now Playing</span>
      </div>
      <div className="share-card-preview">
        <img src={card.image} alt="" />
        <div>
          <strong>{card.title}</strong>
          <span>{card.text}</span>
        </div>
      </div>
    </section>
  );
}

async function copyText(value: string) {
  try {
    if (window.navigator.clipboard?.writeText) {
      await window.navigator.clipboard.writeText(value);
      return;
    }
  } catch {
    // Fall back for browsers that expose Clipboard API but reject the call.
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '0';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand?.('copy');
  } catch {
    // The visible confirmation is still useful when programmatic copy is unavailable.
  } finally {
    textarea.remove();
  }
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-cell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ScheduleSection({
  program,
  minutesLeft,
  nextProgram,
  fallbackCover,
}: {
  program: PublicStatusResponse['current_program'];
  minutesLeft: number | null;
  nextProgram: PublicStatusResponse['next_program'];
  fallbackCover: string;
}) {
  return (
    <section className="section-block public-program-section" aria-label="Current program">
      <div className="section-heading">
        <span>Current Program</span>
        {program && minutesLeft !== null ? <span>{minutesLeft}m left</span> : program ? <span>{program.end_time}</span> : null}
      </div>
      {program ? (
        <div className="public-program-layout">
          <img
            className="public-program-cover"
            src={program.cover_path || fallbackCover}
            alt={`${program.name} program cover`}
          />
          <div className="public-program-copy">
            <div className="schedule-title">{program.name}</div>
            <p className="public-program-time">{program.start_time}–{program.end_time}{program.host_name ? ` · ${program.host_name}` : ''}</p>
            <div className="progress-track"><span /></div>
            <p>{program.description}</p>
            {nextProgram ? <p className="public-up-next">Up next at {nextProgram.start_time}: {nextProgram.name}</p> : null}
          </div>
        </div>
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

function ContentBreakdown({ items }: { items: PublicStatusResponse['content_breakdown'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>Content Breakdown</span>
        <span>Last 14 Days</span>
      </div>
      {items.length ? (
        <div className="content-breakdown-list">
          {items.map((item) => (
            <div key={item.label} className="content-breakdown-row">
              <span>{item.label} {item.percent}%</span>
              <div className="content-breakdown-track">
                <i style={{ width: `${Math.max(4, item.percent)}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">No content split yet.</p>
      )}
    </section>
  );
}

function ActivityFeed({ items }: { items: PublicStatusResponse['activity'] }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <span>RadioTEDU Activity</span>
        <span>Public Feed</span>
      </div>
      {items.length ? (
        <ol className="public-activity-list">
          {items.map((item, index) => (
            <li key={`${item.created_at || 'activity'}-${index}`}>
              <small>{item.actor}</small>
              <span>{item.content}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">No public activity yet.</p>
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
