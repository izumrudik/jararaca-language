import json
import logging as logs
import sys
import os
import traceback
from typing import Any

def main() -> None:
	dir = os.path.dirname(os.path.realpath(__file__))
	logs.basicConfig(
		filename=os.path.join(dir,f"server.logs"),
		filemode='a',
		format=f'%(asctime)s,%(msecs)d, {os.getpid()} %(name)s %(levelname)s %(message)s',
		datefmt='%H:%M:%S',
		level=logs.DEBUG)
	logs.debug("Server started")
	
	try:
		while True:
			handle_request(get_json())
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
			logs.error(f"Unknown Header: {name = !r}, {body = !r}")
			sys.exit(1)
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

def handle_request(request:dict[str,Any]) -> None:
	if request["jsonrpc"] != "2.0":
		logs.error(f"Expected jsonrpc to be 2.0")
		sys.exit(1)
	id:int = request["id"]
	params = request["params"]
	method:str = request["method"]

	result:dict[str,Any]
	if method == 'initialize':
		result = {
			"capabilities": {
				"textDocumentSync":TextDocumentSyncKind.Incremental,
				"workspace":{
					"workspaceFolders":{
						"supported":True,
					}
				}
			}
		}
	else:
		logs.error(f"Unknown method: {method!r}, params: {json.dumps(params, indent=4)}")
		return send_msg({
		"id": id,
		"error":{
			"code":ErrorCodes.MethodNotFound,
			"message":0,
		}
	})
	send_msg({
		"id": id,
		"result":result
	})

if __name__ == '__main__':
	main()