import sys

def send(data : str, sep : str | None = " ", end : str | None = "\n") -> None :
  print(data)
  sys.stdout.flush()

send("TEST")

while True :
  pass