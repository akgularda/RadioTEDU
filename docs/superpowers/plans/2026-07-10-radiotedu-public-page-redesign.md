# RadioTEDU Public Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an AndonFM-inspired, RadioTEDU-branded `/ai` listener page that prominently displays real cover art and remains truthful and useful when broadcast snapshot polling is interrupted.

**Architecture:** Keep the existing outward-push architecture: the broadcasting computer posts sanitized snapshots to the website server, and the browser polls only `GET /api/public/status`. Extend the public React composition and public-only CSS without changing the backend schema or admin UI. Preserve the last good snapshot during transient website polling errors and show a generic connection notice rather than internal error details.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, Lucide React, FastAPI public snapshot API.

## Global Constraints

- Exactly one public channel: RadioTEDU.
- Use the existing RadioTEDU logo and real station/program cover paths from `PublicStatusResponse`.
- Borrow AndonFM's compact hierarchy and density without copying its branding, assets, colors, or exact layout.
- The website server never calls into the broadcasting computer.
- No financial features, admin controls, local paths, logs, secrets, invented data, or private broadcast state on `/ai`.
- Missing data must render honest waiting, offline, stream-unavailable, or no-data copy.
- Keep admin behavior and backend public snapshot schema unchanged.

## File Structure

- `frontend/src/App.tsx` — polling lifecycle and last-good-public-snapshot error propagation.
- `frontend/src/components/PublicDashboard.tsx` — public page semantics, logo/cover composition, program spotlight, player, metrics, and editorial sections.
- `frontend/src/styles.css` — RadioTEDU public-only design system and responsive layout; admin selectors remain unchanged.
- `frontend/src/__tests__/dashboard.test.tsx` — public data, artwork, failure-state, and forbidden-content regression coverage.

---

### Task 1: Preserve Broadcast Snapshot Data During Polling Errors

**Files:**
- Modify: `frontend/src/App.tsx:65-113`
- Modify: `frontend/src/components/PublicDashboard.tsx:8-16, 86-90`
- Test: `frontend/src/__tests__/dashboard.test.tsx:672-709`

**Interfaces:**
- Consumes: `fetchPublicStatus(): Promise<PublicStatusResponse>` from `frontend/src/api.ts`.
- Produces: `PublicDashboardProps { status: PublicStatusResponse; connectionError?: string | null }`.

- [ ] **Step 1: Write the failing connection-resilience test**

Add this test inside `describe('PublicDashboard', ...)`:

```tsx
it('keeps the last broadcast snapshot visible when live polling is interrupted', () => {
  render(
    <PublicDashboard
      status={publicStatus}
      connectionError="Public status request failed: 503"
    />,
  );

  expect(screen.getByText('Blue Room')).toBeInTheDocument();
  expect(screen.getByText('Jazz Lab')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent(
    'Live data connection interrupted. Showing the last received broadcast snapshot.',
  );
  expect(screen.queryByText('Public status request failed: 503')).toBeNull();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm test -- --testNamePattern="keeps the last broadcast snapshot visible"
```

Expected: FAIL because `PublicDashboard` does not accept or render `connectionError`.

- [ ] **Step 3: Pass the polling error into the public dashboard**

Change the successful public render in `frontend/src/App.tsx` to:

```tsx
return <PublicDashboard status={status} connectionError={error} />;
```

Change the props in `frontend/src/components/PublicDashboard.tsx` to:

```tsx
interface PublicDashboardProps {
  status: PublicStatusResponse;
  connectionError?: string | null;
}

export function PublicDashboard({ status, connectionError = null }: PublicDashboardProps) {
```

Immediately after the existing broadcast sync message, render a generic last-good-state notice:

```tsx
{connectionError ? (
  <div className="public-connection-notice" role="status">
    Live data connection interrupted. Showing the last received broadcast snapshot.
  </div>
) : null}
```

- [ ] **Step 4: Run the focused public tests**

Run:

```bash
npm test -- --testNamePattern="PublicDashboard"
```

Expected: all `PublicDashboard` tests PASS.

- [ ] **Step 5: Commit the data-resilience change**

```bash
git add frontend/src/App.tsx frontend/src/components/PublicDashboard.tsx frontend/src/__tests__/dashboard.test.tsx
git commit -m "Keep the last public broadcast snapshot visible"
```

---

### Task 2: Add Logo-Led Branding and Real Program Artwork

**Files:**
- Modify: `frontend/src/components/PublicDashboard.tsx:11-14, 65-139, 200-227`
- Test: `frontend/src/__tests__/dashboard.test.tsx:672-709`

**Interfaces:**
- Consumes: `status.channel.cover_path`, `status.current_program.cover_path`, `status.current_minutes_left`, and `status.next_program` from `PublicStatusResponse`.
- Produces: semantic brand, station hero, and `Current program` region with real artwork and station-cover fallback.

- [ ] **Step 1: Write the failing artwork and structure assertions**

Add these assertions to the first public dashboard test:

```tsx
expect(screen.getByRole('img', { name: 'RadioTEDU' })).toHaveAttribute(
  'src',
  '/static/generated/covers/radiotedu_logo_source.png',
);
expect(screen.getByRole('img', { name: 'RadioTEDU station cover' })).toHaveAttribute(
  'src',
  '/static/generated/covers/radiotedu_station.png',
);
expect(screen.getByRole('region', { name: 'Current program' })).toBeInTheDocument();
expect(screen.getByRole('img', { name: 'Jazz Lab program cover' })).toHaveAttribute(
  'src',
  '/static/generated/covers/night_lab.png',
);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm test -- --testNamePattern="renders the public RadioTEDU card"
```

Expected: FAIL because the wide brand logo, descriptive station-cover alt text, and current-program region do not exist.

- [ ] **Step 3: Use the wide RadioTEDU logo and descriptive station cover**

Use these asset constants:

```tsx
const stationCover = status.channel.cover_path || '/static/generated/covers/radiotedu_station.png';
const logo = '/static/generated/covers/radiotedu_logo_source.png';
const currentProgram = status.current_program || status.programs[0] || null;
```

Render the brand and hero images as:

```tsx
<header className="public-brand">
  <img className="public-logo" src={logo} alt="RadioTEDU" />
  <span className="public-brand-kicker">AI Radio · Ankara</span>
</header>

<img
  className="station-cover public-cover"
  src={stationCover}
  alt="RadioTEDU station cover"
/>
```

- [ ] **Step 4: Replace the schedule section with an artwork-led current-program region**

Call the section with the station-cover fallback:

```tsx
<ScheduleSection
  program={currentProgram}
  minutesLeft={status.current_minutes_left}
  nextProgram={status.next_program}
  fallbackCover={stationCover}
/>
```

Use this complete component implementation:

```tsx
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
  const cover = program?.cover_path || fallbackCover;

  return (
    <section className="detail-section public-program-section" aria-labelledby="current-program-title">
      <div className="section-title-row">
        <h2 id="current-program-title">Current program</h2>
        <span>{minutesLeft === null ? 'Schedule' : `${minutesLeft}m left`}</span>
      </div>
      {program ? (
        <div className="public-program-spotlight">
          <img src={cover} alt={`${program.name} program cover`} />
          <div>
            <strong>{program.name}</strong>
            <span>{program.description || program.vibe}</span>
            <small>{program.start_time}–{program.end_time} · {program.host_name || 'RadioTEDU host'}</small>
          </div>
        </div>
      ) : (
        <div className="empty-panel">Nothing scheduled</div>
      )}
      {nextProgram ? (
        <p className="public-up-next">
          Up next at {nextProgram.start_time}: {nextProgram.name}
        </p>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 5: Group the public information sections into an editorial grid**

Replace the sequential public detail section calls with:

```tsx
<div className="public-editorial-grid">
  <ScheduleSection
    program={currentProgram}
    minutesLeft={status.current_minutes_left}
    nextProgram={status.next_program}
    fallbackCover={stationCover}
  />
  <ShareCard card={status.share_card} />
  <TopSongs songs={status.top_songs} />
  <GenreBars genres={status.top_genres} />
  <ContentBreakdown items={status.content_breakdown} />
  <ActivityFeed items={status.activity} />
</div>
```

- [ ] **Step 6: Run public tests**

Run:

```bash
npm test -- --testNamePattern="PublicDashboard"
```

Expected: all public tests PASS, including existing forbidden admin/financial/Andon-brand checks.

- [ ] **Step 7: Commit the semantic redesign**

```bash
git add frontend/src/components/PublicDashboard.tsx frontend/src/__tests__/dashboard.test.tsx
git commit -m "Feature RadioTEDU artwork on the public page"
```

---

### Task 3: Apply the Andon-Inspired RadioTEDU Visual System

**Files:**
- Modify: `frontend/src/styles.css:173-250, 349-399, 470-500, 561-585, 772-805, responsive media queries`
- Test: `frontend/src/__tests__/dashboard.test.tsx`

**Interfaces:**
- Consumes: public class names introduced in Tasks 1–2.
- Produces: responsive 780px editorial page, logo-led header, blue station hero, program artwork, dense two-column information grid, and mobile collapse.

- [ ] **Step 1: Add the public design tokens and primary layout**

Replace the current public shell/page/brand/card rules with:

```css
.public-shell {
  --public-ink: #101525;
  --public-muted: #667085;
  --public-line: #d8dbe2;
  --public-paper: #f4f3ef;
  --public-blue: #303ecb;
  --public-cyan: #e8f9fc;
  min-height: 100vh;
  align-items: flex-start;
  padding: 34px 18px 64px;
  background:
    linear-gradient(rgba(16, 21, 37, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(16, 21, 37, 0.035) 1px, transparent 1px),
    var(--public-paper);
  background-size: 28px 28px;
  color: var(--public-ink);
}

.public-page {
  width: min(100%, 780px);
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.public-card {
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--public-line);
  border-radius: 4px;
  background: #fff;
  box-shadow: 0 20px 52px rgba(16, 21, 37, 0.10);
}

.public-brand {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.public-logo {
  display: block;
  width: min(280px, 64vw);
  height: auto;
  border: 0;
  border-radius: 0;
  object-fit: contain;
}

.public-brand-kicker {
  color: var(--public-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  white-space: nowrap;
}

.public-cover {
  aspect-ratio: 16 / 7;
  object-fit: cover;
  background: var(--public-blue);
}
```

- [ ] **Step 2: Style connection, metrics, program artwork, and editorial sections**

Add these public-only rules after the existing public status styles:

```css
.public-connection-notice {
  margin: 0 18px 12px;
  padding: 10px 12px;
  border: 1px solid #efc8a9;
  background: #fff8ef;
  color: #7a421a;
  font-size: 12px;
  line-height: 1.4;
}

.public-metrics .metric-cell {
  min-height: 88px;
  background: #fff;
}

.public-editorial-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--public-line);
}

.public-editorial-grid > .detail-section {
  min-width: 0;
  border-right: 1px solid var(--public-line);
  border-bottom: 1px solid var(--public-line);
}

.public-editorial-grid > .detail-section:nth-child(2n) {
  border-right: 0;
}

.public-program-section {
  grid-column: 1 / -1;
}

.public-program-spotlight {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
}

.public-program-spotlight img {
  display: block;
  width: 148px;
  aspect-ratio: 1;
  object-fit: cover;
  background: var(--public-blue);
}

.public-program-spotlight div {
  display: grid;
  gap: 7px;
}

.public-program-spotlight strong {
  font-size: 24px;
  line-height: 1.05;
}

.public-program-spotlight span,
.public-program-spotlight small {
  color: var(--public-muted);
  line-height: 1.4;
}

.public-program-spotlight span {
  font-size: 13px;
}

.public-program-spotlight small {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

- [ ] **Step 3: Add the mobile collapse and focus treatment**

Add this responsive block at the end of `styles.css`:

```css
@media (max-width: 640px) {
  .public-shell {
    padding: 18px 10px 40px;
  }

  .public-brand {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .public-editorial-grid {
    grid-template-columns: 1fr;
  }

  .public-editorial-grid > .detail-section,
  .public-editorial-grid > .detail-section:nth-child(2n) {
    border-right: 0;
  }

  .public-program-spotlight {
    grid-template-columns: 96px minmax(0, 1fr);
    gap: 12px;
  }

  .public-program-spotlight img {
    width: 96px;
  }

  .public-actions {
    grid-template-columns: 1fr;
  }
}

.public-card button:focus-visible,
.public-card a:focus-visible {
  outline: 3px solid rgba(48, 62, 203, 0.35);
  outline-offset: 3px;
}
```

- [ ] **Step 4: Run frontend tests and production build**

Run:

```bash
npm test
npm run build
```

Expected: 10 or more frontend tests PASS and Vite produces `dist/frontend` without errors.

- [ ] **Step 5: Commit the visual system**

```bash
git add frontend/src/styles.css
git commit -m "Redesign the RadioTEDU public listener page"
```

---

### Task 4: Browser and Data-Flow Verification

**Files:**
- Verify: `frontend/src/App.tsx`
- Verify: `frontend/src/components/PublicDashboard.tsx`
- Verify: `frontend/src/styles.css`
- Verify: `frontend/src/__tests__/dashboard.test.tsx`

**Interfaces:**
- Consumes: built `/ai` page and existing `GET /api/public/status` response.
- Produces: verified desktop/mobile listener page and documented evidence that the browser fetches only the website server.

- [ ] **Step 1: Run the complete backend and frontend verification**

Run:

```bash
python -m pytest tests/backend -q
npm test
npm run build
```

Expected: backend suite PASS, frontend suite PASS, and Vite build exit code 0.

- [ ] **Step 2: Launch a safe local website-server preview**

Run the FastAPI app with autonomy and playback disabled and a temporary database, then open:

```text
http://127.0.0.1:8765/ai
```

Expected: the public page loads without starting music, AI, TTS, Liquidsoap, or broadcast output.

- [ ] **Step 3: Verify the real public data flow in the browser**

Check all of the following:

```text
GET /api/public/status returns 200 from the same local website origin.
The page requests no broadcast-computer LAN address.
The RadioTEDU logo and station/program cover images return 200.
No admin endpoint is requested by the public page.
No console errors are present.
```

- [ ] **Step 4: Verify responsive layout**

Inspect at desktop and mobile widths:

```text
Desktop: 1440 x 1000
Mobile: 390 x 844
```

Expected: no horizontal scroll, cover art remains visible, the player stays in the first viewport, and editorial sections collapse to one column on mobile.

- [ ] **Step 5: Verify the offline state**

With no stored broadcast snapshot, confirm:

```text
RadioTEDU branding and cover art remain visible.
The page says it is waiting for the broadcasting computer.
Play is disabled when the stream is unavailable.
No placeholder metrics or invented content appear.
```

- [ ] **Step 6: Commit any verification-only test adjustments**

If verification required a test-only correction, commit only the changed test file:

```bash
git add frontend/src/__tests__/dashboard.test.tsx
git commit -m "Verify the RadioTEDU public listener experience"
```
