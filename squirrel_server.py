from typing import Any
import sys
import time
import json
import subprocess
import time

squirrelPath = "squirrel" # TODO

DEBUG_MODE : bool = True

def send(data : str, end : str | None = "\n") -> None :
  """ Sends data to LSP client (via pipe on stdout/stdin) see [print] for a description of the parameters. """
  print(data)
  sys.stdout.flush()

def LSPAnswerQuery(id : Any, msg : str) -> None :
  """ Sends string message [msg] to LSP client as answer to the query identified by [id]. """
  send(json.dumps({"id": id, "payload": msg}), end="")

def remove_trailing_nl_cr(s : str) -> str :
  if s[-1] == '\n' :
    s2 = s[:-1]
    if s2 == '\r' :
      return s2[:-1]
    else :
      return s2
  else :
    return s

def recv() -> str :
  """ Receives a line from the client (via pipe on stdout/stdin). """
  return remove_trailing_nl_cr(sys.stdin.readline())

def recv_until(n : int) -> str :
  """ Receives data line by line until there are exactly [n] bytes received. """
  n_bytes_recvd : int = 0
  data : str = ""
  while n_bytes_recvd < n :
    line = sys.stdin.readline()
    n_bytes_recvd += len(line)
    data += remove_trailing_nl_cr(line)
  return data

def LSPRecv() -> dict[Any, Any] :
  """ Receives a LSP request, returns a dictionary containg the JSON received. """
  # send("Entering LSPRecv...", end="")
  # Reading header
  reading_header : bool = True
  content_length : int = -1
  while reading_header :
    # send("Looping while reading header...", end="")
    hline : str = recv()
    if hline == '' :
      reading_header = False
    else :
      hline_split = hline.split(":")
      if hline_split[0] == 'Content-Length' :
        content_length = int(hline_split[1])
  # Reading body
  if content_length < 0 :
    sys.stderr.write("No field Content-Length in request header.")
    raise ValueError
  payload : str = recv_until(content_length)
  parsed_payload = json.loads(payload)
  assert(isinstance(parsed_payload, dict))
  return parsed_payload

squirrelInputIndicator : str = "[>  "

data = LSPRecv()
if DEBUG_MODE :
  send(json.dumps({"method":"vsquirrel/debug", "data":str(data)}), end="")
if "pathToSquirrel" in data :
  if DEBUG_MODE :
    send(json.dumps({"method":"vsquirrel/debug", "data":f"path to squirrel received!{data["pathToSquirrel"]}"}), end="")
  squirrelPath = data["pathToSquirrel"]

last_id_request : int = data["id"]

squirrelInstance = subprocess.Popen([squirrelPath, "-i"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

while True :
  buf = ''
  while len(buf) < len(squirrelInputIndicator) or buf[-len(squirrelInputIndicator):] != squirrelInputIndicator :
    buf += squirrelInstance.stdout.read(1).decode()
  LSPAnswerQuery(last_id_request, buf)
  data = LSPRecv()
  if "proofCommand" not in data :
    send(json.dumps({"method":"vsquirrel/error", "data":"No proof command in request"}), end="")
  else :
    proofCommand = data["proofCommand"]
    assert(isinstance(proofCommand, str))
    if proofCommand != "" :
      squirrelInstance.stdin.write((proofCommand + "\n").encode())
      squirrelInstance.stdin.flush()
  last_id_request = data["id"]

# TODO replace send by LSPSend