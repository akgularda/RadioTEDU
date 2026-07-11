# RadioTEDU Public Page Redesign

## Goal

Redesign `radiotedu.com/ai` as a polished single-station listener page that uses RadioTEDU's existing logo and real cover art, follows the compact information rhythm of AndonFM, and renders only sanitized data pushed from the broadcasting computer.

## Product Boundaries

- Keep exactly one public channel: RadioTEDU.
- Programs are scheduled shows inside that channel, not separate stations.
- Preserve the RadioTEDU name, blue identity, typography direction, logo, and cover artwork.
- Learn from AndonFM's tall station card, strong player hierarchy, compact metrics, and dense editorial sections without copying its branding, assets, colors, or exact layout.
- Do not add financial features, support/donation controls, admin controls, logs, incidents, local paths, or internal agent details.
- Do not invent songs, listeners, schedules, popularity, or now-playing information.

## Recommended Visual Direction

Use a hybrid layout: an Andon-like centered station experience with a stronger RadioTEDU campus-broadcast identity.

### Visual System

- Background: quiet warm-gray paper rather than pure white.
- Primary ink: near-black navy for editorial clarity.
- Brand accent: RadioTEDU electric blue derived from the existing cover art.
- Secondary accent: pale cyan for sync/offline messages and small status surfaces.
- Borders: thin neutral lines and subtle grid rules, with restrained shadows.
- Shape: mostly square editorial panels with small radii; avoid generic rounded dashboard cards.
- Type hierarchy: compact uppercase labels, bold station/program titles, readable metadata, and tabular-looking metrics.

### Page Structure

1. **Brand header**
   - Use the existing RadioTEDU logo asset prominently.
   - Keep the header compact and centered with a small `AI Radio` descriptor.

2. **Station hero and player**
   - Show the real station cover from `status.channel.cover_path`, falling back to `radiotedu_station.png`.
   - Place channel name, host model, live/waiting badge, sync message, play/pause control, now-playing title, and artist/program directly beneath the artwork.
   - Keep the audio player URL sourced only from `status.stream.url`.

3. **Compact metrics**
   - Show approximate active player sessions, popularity when present, average session when present, and broadcast state.
   - Label unavailable values honestly as `No data`.

4. **Program spotlight and schedule**
   - Give the current program a visual spotlight using `current_program.cover_path` when available.
   - Show program name, remaining time, concise vibe/description, next program, and a compact upcoming schedule.
   - Fall back to the station cover if a program has no artwork.

5. **Listener information grid**
   - Show top songs, top genres, and content breakdown in compact editorial sections.
   - Keep ranked values and percentages easy to scan without turning the page into an admin dashboard.

6. **Public activity**
   - Show only sanitized public activity from `status.activity`.
   - Use honest empty copy when no public activity exists.

7. **Share and contact actions**
   - Keep `Message` and `Copy Stream Link` secondary to listening.
   - Use the real share-card title, subtitle, and image.

## Data Architecture

```text
Broadcasting computer
  -> builds sanitized public snapshot
  -> POST /api/public/snapshot with shared sync token
Website server
  -> validates token and strict schema
  -> sanitizes and stores recent snapshots
  -> marks snapshots stale after the configured TTL
Browser at /ai
  -> polls GET /api/public/status
  -> renders snapshot, cover paths, metrics, schedule, and activity
  -> plays the HTTPS public stream URL
```

The website server never calls into the broadcasting computer. Broadcast failure must not expose the private machine; it only changes the public page to a truthful stale/offline state.

## Components and Responsibilities

- `frontend/src/components/PublicDashboard.tsx`
  - Own public polling, audio state, copy-link behavior, and composition of public sections.
  - Reuse the existing typed `PublicStatusResponse` contract.
  - Add a focused program spotlight that consumes existing program cover fields.
- `frontend/src/styles.css`
  - Define the redesigned public-only visual system and responsive layout.
  - Keep admin styles functionally unchanged.
- `frontend/src/__tests__/dashboard.test.tsx`
  - Verify real snapshot data, logo/cover rendering, offline states, absence of admin/financial UI, and responsive-friendly semantic structure.
- Backend public snapshot modules
  - No schema change is required for this visual phase.
  - Continue sanitizing cover paths and public fields before storage/response.

## Responsive Behavior

- Desktop: centered page around 720–820px wide, with two-column editorial sections below the primary station card.
- Tablet: retain the hero and metrics grid; collapse secondary information to one column where needed.
- Mobile: full-width card, stacked program spotlight, two-column metrics, large reachable player button, and no horizontal scrolling.

## Error and Empty States

- No snapshot: display `Waiting for the broadcast computer to sync` and retain the RadioTEDU station cover.
- Stale snapshot: show an offline/stale badge while preserving the last sanitized content only if the API supplies it.
- Stream unavailable: disable play and say the stream is unavailable; do not simulate playback.
- Missing program cover: fall back to the station cover.
- Missing metrics or lists: show concise `No data yet` copy without placeholder numbers.
- Status request failure: keep the last successfully rendered public state when available and surface a small connection notice.

## Accessibility

- Maintain semantic headings and section labels.
- Give all meaningful artwork descriptive `alt` text; use empty `alt` only for purely decorative duplicates.
- Keep keyboard-operable play and copy controls with visible focus states.
- Use accessible status text in addition to colored live/offline indicators.
- Preserve sufficient contrast for small uppercase labels and muted metadata.

## Verification

- Backend tests remain green and public snapshot sanitization is unchanged.
- Frontend tests verify:
  - RadioTEDU logo and real station/program cover paths render.
  - Real now-playing, schedule, top-song, genre, breakdown, and activity values render from the public response.
  - Waiting/offline/no-data states are honest.
  - No admin controls, private paths, financial terms, or invented data appear.
- `npm run build` completes successfully.
- Browser QA covers desktop and mobile widths, visible cover art, loading/offline state, and console errors.

## Success Criteria

- A listener immediately recognizes RadioTEDU and can start the stream from the first viewport.
- The page feels structurally comparable to AndonFM while remaining visually original.
- Station and current-program artwork are visually prominent.
- Every displayed operational value originates from the sanitized website-server response.
- Loss of the broadcasting computer produces a safe, honest public state rather than broken UI or private-network access.
