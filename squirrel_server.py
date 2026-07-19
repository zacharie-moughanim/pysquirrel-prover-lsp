import sys
import time

def send(data : str, sep : str | None = " ", end : str | None = "\n") -> None :
  """ Sends data to client (via pipe on stdout/stdin) see [print] for a description of the parameters. """
  print(data)
  sys.stdout.flush()

def recv() -> None :
  """ Receives a line from the client (via pipe on stdout/stdin). """
  s = sys.stdin.readline()
  if s[-1] == '\n' :
    return s[:-1]
  else :
    return s

send("TEST")
send("Waiting for input...")
s = recv()
send(f"Received: \"{s}\"")

while True :
  pass