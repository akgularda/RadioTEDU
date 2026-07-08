# RadioTEDU Broadcast Server Codex Prompt

You are Codex on the RadioTEDU broadcast computer.

Repository:
https://github.com/akgularda/RadioTEDU

Goal:
Run the real RadioTEDU broadcast machine. This machine owns the music library, AI host, Qwen/Ollama, TTS, announcement prebuffer, playback, Liquidsoap/Icecast source, and snapshot push to the website server. It must stream to the `/ai` mount and push sanitized public state to `radiotedu.com/ai`.

Repository setup:
1. Clone or pull:
   ```bash
   git clone https://github.com/akgularda/RadioTEDU
   cd RadioTEDU
   ```
   If the repo already exists:
   ```bash
   git pull --ff-only
   ```

2. Create `.env` from `.env.example` if needed.

Core config:
```env
MUSIC_DIR=F:/Songs/Jazz
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_URL=http://127.0.0.1:11434
PLAYBACK_BACKEND=liquidsoap
AUTONOMY_ENABLED=true
MIN_READY_ANNOUNCEMENTS=5
MAX_READY_ANNOUNCEMENTS=8
NEWS_ENABLED=true
WEATHER_ENABLED=true
```

TTS:
```env
TTS_PROVIDER=qwen
QWEN_TTS_COMMAND=<your real Qwen TTS command wrapper>
FALLBACK_TTS_PROVIDER=sapi
```

Liquidsoap/Icecast:
```env
LIQUIDSOAP_ENABLED=true
LIQUIDSOAP_QUEUE_PATH=data/liquidsoap/queue.m3u
LIQUIDSOAP_SCRIPT_PATH=data/liquidsoap/radiotedu.liq
LIQUIDSOAP_COMMAND=liquidsoap
LIQUIDSOAP_HOST=<correct Icecast host/IP>
LIQUIDSOAP_PORT=8001
LIQUIDSOAP_MOUNT=/ai
LIQUIDSOAP_ICECAST_PASSWORD=1234Qwer
ICECAST_HOST=<correct Icecast host/IP>
ICECAST_PORT=8001
ICECAST_MOUNT=/ai
ICECAST_PASSWORD=1234Qwer
```

Website sync:
```env
PUBLIC_SYNC_URL=https://radiotedu.com/api/public/snapshot
PUBLIC_SYNC_TOKEN=<same shared secret configured on website server>
PUBLIC_STREAM_URL=http://<public-or-LAN-stream-IP>:8001/ai
PUBLIC_SYNC_INTERVAL_SECONDS=10
```

Optional admin protection:
```env
ADMIN_API_TOKEN=<local admin token, or empty if LAN-only>
```

Important network task:
Find the correct IP address for the Broadcast Wall app / Icecast source target.
- Inspect the machine network interfaces.
- Determine which IP the Broadcast Wall app or Icecast server expects.
- Use that IP for `LIQUIDSOAP_HOST` / `ICECAST_HOST` if Icecast is not local.
- Confirm the mount is exactly `/ai`.
- Confirm source password is exactly `1234Qwer`.
- Do not guess silently. Log the detected candidate IPs and choose the reachable one.
- If multiple candidates exist, test connectivity to the Icecast port and use the reachable one.

Install/verify:
```bash
pip install -r requirements.txt
npm install
python scripts/check_ollama.py --install --start --pull
python scripts/scan_music.py
python -m pytest tests/backend -q
npm test
npm run build
```

Broadcast workflow:
1. Start or verify Ollama.
2. Pull/verify `qwen3.5:4b`.
3. Scan `MUSIC_DIR=F:/Songs/Jazz`.
4. Confirm playable tracks > 0.
5. Render Liquidsoap config:
   `POST /api/liquidsoap/render`
6. Verify Liquidsoap/Icecast:
   `POST /api/liquidsoap/verify`
   This must confirm:
   - queue file is readable
   - script references queue
   - Icecast mount `/ai` is reachable/active when running
7. Start Icecast/Liquidsoap output:
   `POST /api/liquidsoap/start`
8. Start air:
   `POST /api/air/start`

Hard broadcast constraints:
- Exactly one channel: RadioTEDU.
- Programs are schedule blocks, not stations.
- No fake tracks, fake artists, fake play history, fake listeners, fake analytics, fake donations, or financial features.
- Use real files from `F:/Songs/Jazz`.
- Maintain 5-8 prepared announcements.
- Do not block live playback waiting for the 4B model.
- Generate announcements 4-5 songs ahead.
- If AI is unavailable, try to start/fix/pull Ollama/Qwen instead of silently living in fallback.
- Fallback is dead-air prevention only.
- Weather/news/song-context announcements must be sourced. Do not invent facts.
- Snapshot push must never include local paths, secrets, logs, incidents, internal task details, or generated private file paths.

Admin app:
- Run the local admin dashboard.
- Use it to see health, prebuffer, TTS, Liquidsoap, website sync, fallback playlist, weekly strategy, and logs.
- Use Run Air / Stop Air / Skip / Rescan from the admin app.
- Use Verify Icecast Air before going live.
- Use Clip Latest Segment only for real generated clips.

Public sync:
- Every few seconds, push sanitized status to `https://radiotedu.com/api/public/snapshot`.
- Header: `X-RadioTEDU-Sync-Token: <shared secret>`.
- If website sync fails, keep local broadcast running and log locally only.

Final verification:
- `/api/status` shows music indexed.
- `/api/status` shows prebuffer ready >= 5.
- `/api/liquidsoap/verify` reports queue readable.
- Icecast `/ai` mount is reachable.
- `/api/air/start` starts without dead air.
- `https://radiotedu.com/ai` shows real now-playing after snapshot sync.
- No local file paths appear on `radiotedu.com/ai`.
- No fake or financial fields appear anywhere public.
