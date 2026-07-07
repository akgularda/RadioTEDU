# RadioTEDU Liquidsoap configuration
set("log.stdout", true)
set("server.telnet", false)

radio = playlist(id="RadioTEDU", mode="normal", reload=1, reload_mode="watch", "data/liquidsoap/queue.m3u")
radio = mksafe(radio)

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
