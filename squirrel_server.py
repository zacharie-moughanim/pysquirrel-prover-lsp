from typing import Any
import sys
import time
import json
import subprocess

squirrelPath = "squirrel" # TODO

DEBUG_MODE : bool = True

def send(data : str, end : str | None = "\n") -> None :
  """ Sends data to LSP client (via pipe on stdout/stdin) see [print] for a description of the parameters. """
  print(data)
  sys.stdout.flush()

def LSPAnswerQuery(id : Any, msg : str, method : str | None = None) -> None :
  """ Sends string message [msg] to LSP client as answer to the query identified by [id]. """
  if method is None :
    send(json.dumps({"id": id, "payload": msg}), end="")
  else :
    send(json.dumps({"id": id, "payload": msg, "method": method}), end="")

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
  """ Receives data until there are exactly [n] bytes received. """
  return sys.stdin.read(n)

def LSPRecv() -> dict[Any, Any] :
  """ Receives a LSP request, returns a dictionary containg the JSON received. """
  # Reading header
  reading_header : bool = True
  content_length : int = -1
  while reading_header :
    hline : str = recv()
    if hline == '' :
      reading_header = False
    else :
      hline_split = hline.split(":")
      if hline_split[0].casefold() == 'Content-Length'.casefold() :
        content_length = int(hline_split[1])
  # Reading payload
  if content_length < 0 :
    sys.stderr.write("No field Content-Length in request header.")
    raise ValueError
  payload : str = recv_until(content_length)
  parsed_payload = json.loads(payload)
  assert(isinstance(parsed_payload, dict))
  return parsed_payload

# The string output by squirrel in interactive mode that we interpret as "Squirrel is waiting for input"
squirrelInputIndicator : str = "[>  "

# TODO multiple sessions

# First waiting for a message indicating the beginning of a proof session, containing the path to squirrel.
data = LSPRecv()
if DEBUG_MODE :
  send(json.dumps({"method":"vsquirrel/debug", "data":str(data)}), end="")
if "pathToSquirrel" in data :
  if DEBUG_MODE :
    send(json.dumps({"method":"vsquirrel/debug", "data":f"path to squirrel received!{data["pathToSquirrel"]}"}), end="")
  squirrelPath = data["pathToSquirrel"]

# Keeping track of last id of a request to answer following the LSP
last_id_request : int = data["id"]

# TODO error management, display message "maybe wrong path to squirrel"
# Spawning a squirrel instance
squirrelInstance = subprocess.Popen([squirrelPath, "-i"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

while True :
  # Loading squirrel's output until [squirrelInputIndicator] is output by squirrel.
  buf : bytes = b""
  squirrelIsWaitingForInput : bool = False
  while not(squirrelIsWaitingForInput) :
    buf += squirrelInstance.stdout.read(1)
    if len(buf) >= len(squirrelInputIndicator) :
      try :
        lastChunk = buf[-len(squirrelInputIndicator):].decode()
        squirrelIsWaitingForInput = (lastChunk == squirrelInputIndicator)
      except UnicodeDecodeError :
        squirrelIsWaitingForInput = False
  # Sending to LSP client the output of squirrel.
  LSPAnswerQuery(last_id_request, buf[:-len(squirrelInputIndicator)].decode(), method = "vsquirrel/squirrelOutput")
  # Waiting for LSP client's request (e.g. a proof command to process)
  data = LSPRecv()
  if "proofCommand" not in data :
    send(json.dumps({"method":"vsquirrel/error", "data":"No proof command in request"}), end="")
  else :
    proofCommand = data["proofCommand"]
    assert(isinstance(proofCommand, str))
    if proofCommand != "" :
      # Executing proofCommand in squirrel
      squirrelInstance.stdin.write((proofCommand + "\n").encode())
      squirrelInstance.stdin.flush()
  last_id_request = data["id"]