# RadioTEDU Liquidsoap template for local broadcast computers.
# The backend can render a concrete config into data/liquidsoap/radiotedu.liq.
set("log.stdout", true)
set("server.telnet", false)

queue = getenv(default="data/liquidsoap/queue.m3u", "LIQUIDSOAP_QUEUE_PATH")
host = getenv(default="127.0.0.1", "ICECAST_HOST")
port = int_of_string(getenv(default="8000", "ICECAST_PORT"))
password = getenv(default="hackme", "ICECAST_PASSWORD")

radio = playlist(id="RadioTEDU", mode="normal", reload=1, reload_mode="watch", queue)
radio = mksafe(radio)

output.icecast(
  %mp3,
  host=host,
  port=port,
  password=password,
  mount="/ai",
  name="RadioTEDU",
  description="RadioTEDU local broadcast stream",
  genre="RadioTEDU",
  radio
)
