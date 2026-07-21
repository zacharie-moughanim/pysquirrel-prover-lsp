from typing import Any
import sys
import time
import json
import subprocess

squirrelPath = "squirrel" # TODO

DEBUG_MODE : bool = True

def send(data : str, end : str | None = "\n") -> None :
  """ Sends data to LSP client (via pipe on stdout/stdin) see [print] for a description of the parameters. """
  sys.stdout.write(data)
  sys.stdout.flush()

def senderr(dataJSON : dict) -> None :
  """ Sends data to LSP client (via pipe on stderr). """
  sys.stderr.write(json.dumps(dataJSON))
  sys.stderr.flush()

def LSPAnswerQuery(id : Any, msg : str, method : str | None = None, kind : str | None = None) -> None :
  """ Sends string message [msg] to LSP client as answer to the query identified by [id]. """
  data : dict[str, Any] = {"id": id, "payload": msg}
  if method is not None :
    data["method"] = method
  if kind is not None :
    data["kind"] = kind
  send(json.dumps(data), end="")

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
    senderr({"method": "vsquirrel/debug", "data": "No field Content-Length in request header."})
    raise ValueError
  payload : str = recv_until(content_length)
  parsed_payload = json.loads(payload)
  assert(isinstance(parsed_payload, dict))
  return parsed_payload

# What I understand of squirrel's interactive mode syntax:
# TODO take it fully into account: everything except [goal] should appear at the bottom-right of the screen.
# [kind>Sigma*<] : kind message with e.g. kind=start/warning/goal
# [error>Sigma* : error message
# [> Indicates that it's waiting for user input

# The string output by squirrel in interactive mode that we interpret as "Squirrel is waiting for input"
squirrelInputIndicator : str = "[>  "
squirrelErrorIndicator : str = "[error>"
ANSIEscape : str = "\u001b".casefold()

# TODO multiple sessions
senderr({"method":"vsquirrel/debug", "data":"waiting"})
# First waiting for a message indicating the beginning of a proof session, containing the path to squirrel.
data = LSPRecv()
senderr({"method":"vsquirrel/debug", "data":"aaaaaaaaaaaaaaaaaaaaaaaahhhhhhhhhhhhhhhhhhhhhhhhhhhh"})
if "pathToSquirrel" in data :
  if DEBUG_MODE :
    senderr({"method":"vsquirrel/debug", "data":f"path to squirrel received!{data["pathToSquirrel"]}"})
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
  if DEBUG_MODE :
    senderr({"method": "vsquirrel/debug", "data": "Finished reading squirrel's output."})
  squirrelOutputContent : str = buf.decode()
  # Deciding the kind of output: error or output
  squirrelMessageBeginningIndex : int = 0
  outputKind : str = "output"
  # Eliminating ANSI starting character, if any
  if squirrelOutputContent[:len(ANSIEscape)].casefold() == ANSIEscape :
    squirrelMessageBeginningIndex += len(ANSIEscape)
    if squirrelOutputContent[squirrelMessageBeginningIndex] != '[' :
      senderr({"method": "vsquirrel/lsperror", "data": "Invalid ANSI character in Squirrel's output."})
    squirrelMessageBeginningIndex += 1
    while squirrelOutputContent[squirrelMessageBeginningIndex] != 'm' and squirrelMessageBeginningIndex < len(squirrelOutputContent) :
      squirrelMessageBeginningIndex += 1
    squirrelMessageBeginningIndex += 1
    if squirrelMessageBeginningIndex >= len(squirrelOutputContent) :
      squirrelMessageBeginningIndex = 0
      senderr({"method": "vsquirrel/lsperror", "data": "Invalid ANSI character in Squirrel's output."})
  # TODO here parse more smartly the output description
  if squirrelOutputContent[squirrelMessageBeginningIndex:squirrelMessageBeginningIndex + len(squirrelErrorIndicator)] == squirrelErrorIndicator :
    outputKind = "error"
  # Sending to LSP client the output of squirrel.
  if DEBUG_MODE :
    senderr({"method": "vsquirrel/debug", "data": "Sending..."})
  LSPAnswerQuery(last_id_request, squirrelOutputContent[:-len(squirrelInputIndicator)], method = "vsquirrel/squirrelProofOutput", kind = outputKind)
  if DEBUG_MODE :
    senderr({"method": "vsquirrel/debug", "data": "Sent."})
  # Waiting for LSP client's request (e.g. a proof command to process)
  data = LSPRecv()
  if "proofCommand" not in data :
    senderr({"method": "vsquirrel/lsperror", "data": "No proof command in request"})
  else :
    proofCommand = data["proofCommand"]
    assert(isinstance(proofCommand, str))
    if proofCommand != "" :
      # Executing proofCommand in squirrel
      squirrelInstance.stdin.write((proofCommand + "\n").encode())
      squirrelInstance.stdin.flush()
  last_id_request = data["id"]