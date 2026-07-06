# RadioTEDU Liquidsoap configuration
set("log.stdout", true)
set("server.telnet", false)

radio = playlist(id="RadioTEDU", mode="normal", reload=1, "data/liquidsoap/queue.m3u")
radio = mksafe(radio)

output.icecast(
  %mp3,
  host="127.0.0.1",
  port=8001,
  password="hackme",
  mount="radiotedu.mp3",
  name="RadioTEDU",
  radio
)
