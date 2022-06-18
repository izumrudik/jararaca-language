import json
import logging as logs
import sys
import os
import traceback
from typing import Any, NoReturn

def main() -> None:
	dir = os.path.dirname(os.path.realpath(__file__))
	logs.basicConfig(
		filename=os.path.join(dir,f"server.logs"),
		filemode='w',
		format=f'%(asctime)s,%(msecs)d, {os.getpid()} %(name)s %(levelname)s %(message)s',
		datefmt='%H:%M:%S',
		level=logs.DEBUG)
	logs.debug("Server started")
	
	try:
		while True:
			handle_content(get_json())
	except Exception:
		logs.error(traceback.format_exc())
	logs.debug("Server stopped")

def get_json() -> Any:
	headers_string = ""
	while True:
		chunk = sys.stdin.read(1)
		headers_string += chunk
		if headers_string[-4:] == '\r\n\r\n':
			headers_string = headers_string[:-4]
			break
	headers = (header.split(': ') for header in headers_string.split('\r\n'))
	length:int
	for (name, body) in headers:
		if name == 'Content-Length':
			length = int(body)
		else:
			exit_abnormally(f"Unknown Header: {name = !r}, {body = !r}")
	length = length
	content_string = sys.stdin.read(length)
	content = json.loads(content_string)
	logs.debug(f"found request {content['method']!r} with {content_string}")
	return content

def send_msg(msg:dict[str, Any]) -> None:
	msg["jsonrpc"] = "2.0"
	content = json.dumps(msg)
	length = len(content)
	sys.stdout.write(f"Content-Length: {length}\r\n")
	sys.stdout.write(f"\r\n{content}")
	sys.stdout.flush()
	logs.debug(f"Sent: {content}")
integer = int
class ErrorCodes:
	ParseError: integer = -32700
	InvalidRequest: integer = -32600
	MethodNotFound: integer = -32601
	InvalidParams: integer = -32602
	InternalError: integer = -32603
	jsonrpcReservedErrorRangeStart: integer = -32099
	ServerNotInitialized: integer = -32002
	UnknownErrorCode: integer = -32001
	jsonrpcReservedErrorRangeEnd = -32000
	lspReservedErrorRangeStart: integer = -32899
	RequestFailed: integer = -32803
	ServerCancelled: integer = -32802
	ContentModified: integer = -32801
	RequestCancelled: integer = -32800
	lspReservedErrorRangeEnd: integer = -32800



class TextDocumentSyncKind:
	None_ = 0
	Full = 1
	Incremental = 2

def exit_abnormally(msg:str) -> NoReturn:
	logs.error(msg)
	publish_notification('exit', None)
	print(f"Server exited abnormally, due to {msg!r}", file=sys.stderr, flush=True)
	sys.exit(1)

def handle_content(request:dict[str,Any]) -> None:
	if request["jsonrpc"] != "2.0":
		exit_abnormally(f"Expected jsonrpc to be 2.0")
	params:None|dict[str,Any]|list[Any] = request.get("params")
	method:str = request["method"]
	id:int|str = request.get("id")
	if id is None:
		logs.debug(f"Received notification '{method}'")
		return handle_notification(method, params)
	logs.debug(f"Received request #{id} '{method}'")
	return handle_request(id, method, params)


def publish_notification(method:str, params:Any) -> None:
	send_msg({"method":method,"params":params})

def compute_diagnostics() -> None:
	assert False, "Not implemented"

def handle_request(id:int|str, method:str, params:None|dict[str,Any]|list[Any]) -> None:
	def reply(result:Any) -> None:
		return send_msg({"id":id,"result":result})
	def error(code:integer, message:str) -> None:
		return send_msg({"id":id,"error":{"code":code,"message":message}})
	if method == 'initialize':
		logs.info("Received initialize request")
		CAPABILITIES = {
				"textDocumentSync":TextDocumentSyncKind.Full,
				"diagnosticProvider":{
					"interFileDependencies":True,
					"workspaceDiagnostics":True,
				}
			}
		return reply({
			"capabilities": CAPABILITIES,
		})
	elif method == 'shutdown':
		logs.info("Received shutdown request, shutting down")
		return reply(None)
	elif method == 'exit':
		logs.info("Received exit request, server exits now (with 0)")
		sys.exit(0)
	else:
		logs.error(f"Received unknown method: {method!r}, params: {json.dumps(params, indent=4)}")
		return error(ErrorCodes.MethodNotFound, f"method '{method}' can't be handled on the server")

def handle_notification(method:str, params:Any) -> None:
	if method == 'initialized':
		logs.info("Received initialized notification, all good")
	elif method == 'textDocument/didSave':#ignore
		compute_diagnostics()
	elif method == 'textDocument/didOpen':
		text = params["textDocument"]["text"]
		if params["textDocument"]["languageId"] != 'jararaca':
			exit_abnormally(f"Received a request for another language, exiting")
		uri = params["textDocument"]["uri"]
		OPENED_FILES_TEXTS[uri] = text
		logs.info(f"Opened file {uri!r}")
	elif method == 'textDocument/didChange':
		text = params["contentChanges"][-1]["text"] # we need to apply all changes, so we take the last one's text 
		uri = params["textDocument"]["uri"]
		OPENED_FILES_TEXTS[uri] = text
		logs.debug(f"Changed file {uri!r}")
	elif method == 'textDocument/didClose':
		uri = params["textDocument"]["uri"]
		del OPENED_FILES_TEXTS[uri]
		logs.info(f"Closed file {uri!r}")
	elif method.startswith('$/'):#ignore
		return
	else:
		logs.warn(f"Received unknown notification: {method!r}, go check")

OPENED_FILES_TEXTS:dict[str,str] = {}

if __name__ == '__main__':
	main()