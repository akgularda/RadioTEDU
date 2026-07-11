# RadioTEDU Liquidsoap configuration
set("log.stdout", true)
set("server.telnet", false)

radio = playlist(id="RadioTEDU", mode="normal", reload=1, reload_mode="watch", "data/liquidsoap/queue.m3u")
radio = mksafe(radio)

# Measured playout guards: T17 transition decisions are cue-aware.  Generic
# crossfades remain zero-length unless a decision supplies liq_cross_duration,
# so speech, jingles, and unverified intros stay sequential.
radio = crossfade(
  duration=0.0,
  fade_in=0.0,
  fade_out=0.0,
  smart=true,
  conservative=true,
  assume_autocue=true,
  radio
)

# A continuous source below -60 dBFS is degraded after 1.0 second and skipped
# at 1.5 seconds, allowing the next queued music/fallback item to take over.
radio = blank.detect(
  max_blank=1.0,
  min_noise=0.05,
  threshold=-60.0,
  track_sensitive=false,
  fun () -> log("RadioTEDU primary source degraded after 1.0s below -60 dBFS"),
  radio
)
radio = blank.skip(
  threshold=-60.0,
  max_blank=1.5,
  min_noise=0.05,
  track_sensitive=false,
  radio
)

# input level control
radio = amplify(1.000000, radio)

# gentle wideband AGC
radio = normalize(target=-16.0, lufs=true, gain_min=-3.0, gain_max=3.0, radio)

# restrained multiband dynamics
radio = compress.multiband(radio, [
  {frequency=250., attack=25., release=250., ratio=1.5, threshold=-18., gain=0.},
  {frequency=2500., attack=20., release=200., ratio=1.5, threshold=-16., gain=0.},
  {frequency=12000., attack=15., release=150., ratio=1.5, threshold=-14., gain=0.}
])

# final true-peak limiter
radio = limit(threshold=-1.0, radio)

# encoder
output.icecast(
  %mp3,
  host="127.0.0.1",
  port=8001,
  password="hackme",
  mount="/ai",
  name="RadioTEDU",
  description="RadioTEDU AI radio",
  genre="AI Radio",
  radio
)
