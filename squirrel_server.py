from typing import Any
import sys
import time
import json
import subprocess

squirrelPath = "squirrel"

DEBUG_MODE : bool = True

## COMMUNICATION WITH LSP CLIENT

def send(data : str, end : str | None = "\n") -> None :
  """ Sends data to LSP client (via pipe on stdout/stdin). """
  if end == None :
    end = ""
  assert(isinstance(end, str))
  utf8Data = (data + end).encode(encoding="utf-8")
  # Computing LSP header
  size = len(utf8Data)
  contentLengthHeaderField = f"Content-Length: {size}\r\n"
  header = contentLengthHeaderField
  # Sending
  sys.stdout.buffer.write((header + "\r\n").encode(encoding="utf-8") + utf8Data)
  sys.stdout.flush()

def senderr(dataJSON : dict, end : str | None = "\n") -> None : 
  """ Sends data to LSP client (via pipe on stderr). """
  if end == None :
    end = ""
  assert(isinstance(end, str))
  data : str = (json.dumps(dataJSON) + end)
  utf8Data = data.encode(encoding="utf-8")
  # Computing LSP header
  size = len(utf8Data)
  contentLengthHeaderField = f"Content-Length: {size}\r\n"
  header = contentLengthHeaderField
  # Sending
  sys.stderr.buffer.write((header + "\r\n").encode(encoding="utf-8") + utf8Data)
  sys.stderr.flush()

def LSPAnswerQuery(id : Any, msg : str, documentId : str, method : str | None = None, kind : str | None = None, resetResponses : bool = True, continuing : bool = False, commandFailed : bool = False) -> None :
  """ Sends string message [msg] to LSP client as answer to the query identified by [id]. """
  data : dict[str, Any] = {"id": id, "documentId": documentId, "payload": msg}
  if method is not None :
    data["method"] = method
  if kind is not None :
    data["kind"] = kind
  if resetResponses :
    data["resetResponses"] = "1"
  if continuing :
    data["continuing"] = "1"
  if commandFailed :
    data["commandFailed"] = "1"
  send(json.dumps(data))

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

## SQUIRREL'S OUTPUT MANAGEMENT

# The string output by squirrel in interactive mode that we interpret as "Squirrel is waiting for input"
squirrelInputIndicator : str = "[>  "
squirrelErrorIndicator : str = "[error>"
ANSIEscape : str = "\u001b".casefold()

squirrelOutputKinds = ["error", "warning", "goal", "start"]
squirrelOutputBlockBeginnings = ['[' + kind + '>' for kind in squirrelOutputKinds]

# What I understand of squirrel's interactive mode syntax:
# TODO take it fully into account: everything except [goal] should appear at the bottom-right of the screen.
# [kind>Sigma* : kind message with e.g. kind=start/warning/goal/error
# [> Indicates that it's waiting for user input
# <] seems to indicate the end of a block, allowing to have multiple kind of messages in a single output.

def parseSquirrelOutput(squirrelOutputContent : str) -> list[tuple[str, str]] :
  """ Parses `squirrelOutputContent`. This string must end with a `squirrelInputIndicator`.
    The syntax parsed is the following:
    "[kind>" with `kind` a valid squirrel output kind starts a block;
    "<]" ends a block
    `squirrelInputIndicator` also ends a block
    Returns a list of blocks present in output, in the form (kind, payload). """
  res = []
  i : int = 0
  curBlockKind : str | None = None # None correspond to being outside a block
  buf : str = ""
  while i < len(squirrelOutputContent) :
    if curBlockKind is None :
      # Detecting the start of a new block
      if squirrelOutputContent[i] == '[' :
        for j, blockBegin in enumerate(squirrelOutputBlockBeginnings) :
          if squirrelOutputContent[i:i + len(blockBegin)] == blockBegin :
            i = i + len(blockBegin)
            withinBlock = True
            curBlockKind = squirrelOutputKinds[j] # The corresponding without the leading [ and the trailing >
            if buf.strip() != "" :
              res.append(("response", buf))
            buf = ""
            break
        else :
          buf += squirrelOutputContent[i]
          i += 1
      else :
        buf += squirrelOutputContent[i]
        i += 1
    else :
      # Detecting the start of a new block
      if squirrelOutputContent[i] == '[' :
        for j, blockBegin in enumerate(squirrelOutputBlockBeginnings) :
          if squirrelOutputContent[i:i + len(blockBegin)] == blockBegin :
            i = i + len(blockBegin)
            if buf.strip() != "" :
              res.append((curBlockKind, buf))
            withinBlock = True
            curBlockKind = squirrelOutputKinds[j] # The corresponding without the leading [ and the trailing >
            buf = ""
            break
        else :
          buf += squirrelOutputContent[i]
          i += 1
      # Detecting the end of current block
      elif i + 1 < len(squirrelOutputContent) and squirrelOutputContent[i:i + 2] == "<]" :
        i += 2
        res.append((curBlockKind, buf))
        buf = ""
        curBlockKind = None
      elif i < len(squirrelOutputContent) :
        buf += squirrelOutputContent[i]
        i += 1
  # Removing squirrel's input indicator from last response
  lastKind : str | None
  if curBlockKind is not None :
    lastKind = curBlockKind
  else :
    lastKind = "response"
  lastPayload = buf[:-len(squirrelInputIndicator)]
  # if lastPayload[:len(ANSIEscape)] == ANSIEscape :
  #   i = len(ANSIEscape)
  #   if lastPayload[i] == '[' :
  #     i += 1
  #     while i < len(lastPayload) and lastPayload[i] != "m" :
  #       senderr({"method": "vsquirrel/debug", "data": "HEY"})
  #       i += 1
  #     if i == len(lastPayload) - 1 :
  #       lastPayload = None
  if lastPayload is not None :
    res.append((lastKind, lastPayload))
  return res

## MANAGING PROOFS STATE

class ProofState :
  squirrelPath : str
  documentId : str
  squirrelInstance : subprocess.Popen

  def __init__(self, documentId : str, squirrelPath : str = "squirrel") :
    self.documentId = documentId
    self.squirrelPath = squirrelPath
    self.squirrelInstance = subprocess.Popen([squirrelPath, "-i"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # TODO error management on Popen

  def processCommand(self, cmd : bytes) :
    assert self.squirrelInstance.stdin is not None
    self.squirrelInstance.stdin.write(cmd)
    self.squirrelInstance.stdin.flush()

  def transmitSquirrelOutput(self, id : int) :
    """ Read all squirrel's output until squirrel waits for input, and send it to LSP client. """
    # Loading squirrel's output until [squirrelInputIndicator] is output by squirrel.
    buf : bytes = b""
    squirrelIsWaitingForInput : bool = False
    while not(squirrelIsWaitingForInput) :
      assert self.squirrelInstance.stdout is not None
      buf += self.squirrelInstance.stdout.read(1)
      if len(buf) >= len(squirrelInputIndicator) :
        try :
          lastChunk = buf[-len(squirrelInputIndicator):].decode()
          squirrelIsWaitingForInput = (lastChunk == squirrelInputIndicator)
        except UnicodeDecodeError :
          squirrelIsWaitingForInput = False
    # if DEBUG_MODE :
    #   senderr({"method": "vsquirrel/debug", "data": "Finished reading squirrel's output."})
    squirrelOutputContent : str = buf.decode()
    parsedOutput = parseSquirrelOutput(squirrelOutputContent)
    # Determining whether the command failed or not
    commandFailed : bool = ("error" in [x for (x, y) in parsedOutput])
    # Sending to LSP client the output of squirrel, resetting answers only on first message.
    for j, (kind, payload) in enumerate(parsedOutput) :
      LSPAnswerQuery(
        id, payload,
        self.documentId,
        method = "vsquirrel/squirrelProofOutput",
        kind = kind,
        resetResponses = (j == 0),
        continuing = (j < len(parsedOutput) - 1),
        commandFailed = commandFailed
      )
  
proofStates : dict[str, ProofState] = {}

## LSP SERVER ROUTINE

def mainRoutine() -> None :
  data = LSPRecv()
  if "method" not in data :
    senderr({"method": "vsquirrel/lsperror", "data": "No method field in message."})
  else :
    if data["method"] == "vsquirrel/startProof" :
      # if DEBUG_MODE :
      #   senderr({"method":"vsquirrel/debug", "data":"waiting"})
      if "pathToSquirrel" not in data :
        senderr({"method": "vsquirrel/lsperror", "data": "No path to squirrel received, defaulting to \"squirrel\"."})
      else :
        # if DEBUG_MODE :
        #   senderr({"method":"vsquirrel/debug", "data":f"path to squirrel received!{data["pathToSquirrel"]}"})
        squirrelPath = data["pathToSquirrel"]
      request_id : int = data["id"]
      # TODO error management, display message "maybe wrong path to squirrel"
      # Spawning a squirrel instance
      if "documentId" not in data :
        senderr({"method": "vsquirrel/lsperror", "data": "No document id received, proof is not started."})
      else :
        documentId = data["documentId"]
        newProofState = ProofState(documentId, squirrelPath)
        proofStates[documentId] = newProofState
        newProofState.transmitSquirrelOutput(request_id)
    elif data["method"] == "vsquirrel/closeProof" :
      if "documentId" not in data :
        senderr({"method": "vsquirrel/lsperror", "data": "No document id received, proof is not closed."})
      else :
        documentId = data["documentId"]
        proofStates[documentId].squirrelInstance.kill() # There may be a cleaner way to close the instance
        proofStates.pop(documentId)
    elif data["method"] == "vsquirrel/proofCommand" :
      # Sending proof command to squirrel
      if "proofCommand" not in data :
        senderr({"method": "vsquirrel/lsperror", "data": "No proof command in vsquirrel/proofCommand request."})
      else :
        if "documentId" not in data :
          senderr({"method": "vsquirrel/lsperror", "data": "No document id in vsquirrel/proofCommand request, command is not processed."})
        else :
          documentId = data["documentId"]
          proofCommand = data["proofCommand"]
          proofState = proofStates[documentId]
          assert(isinstance(proofCommand, str))
          if proofCommand != "" :
            # Executing proofCommand in squirrel
            proofState.processCommand((proofCommand + "\n").encode())
            request_id = -1
            if "id" not in data :
              senderr({"method": "vsquirrel/lsperror", "data": "No id in vsquirrel/proofCommand request."})
            else :
              request_id = data["id"] # TODO wrap in a state dictionary
            proofState.transmitSquirrelOutput(request_id)

while True :
  mainRoutine()