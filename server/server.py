import json
import logging as logs
import sys
import os
import traceback
from typing import Any, NoReturn

import jararaca

def main() -> None:
	dir = os.path.dirname(os.path.realpath(__file__))
	logs.basicConfig(
		filename=os.path.join(dir,f"server.logs"),
		filemode='a',
		format=f'%(asctime)s:[%(name)s:{os.getpid()}:%(levelname)s] %(message)s',
		datefmt='%H:%M:%S',
		level=logs.INFO)
	logs.info("Server started")
	
	try:
		while True:
			handle_content(get_json())
	except Exception:
		logs.error(traceback.format_exc())
	logs.info("Server stopped")

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
	id:int|str|None = request.get("id")
	if id is None:
		logs.info(f"Received notification '{method}'")
		return handle_notification(method, params)
	logs.info(f"Received request #{id} '{method}'")
	return handle_request(id, method, params)


def publish_notification(method:str, params:Any) -> None:
	logs.info(f"Publishing notification: '{method}'")
	send_msg({"method":method,"params":params})



def handle_request(id:int|str, method:str, params:Any) -> None:
	def reply(result:Any) -> None:
		logs.info(f"Replied to request #{id}")
		return send_msg({"id":id,"result":result})
	def error(code:integer, message:str) -> None:
		logs.info(f"Sent an error to request #{id}")
		return send_msg({"id":id,"error":{"code":code,"message":message}})
	if method == 'initialize':
		CAPABILITIES = {
				"textDocumentSync":TextDocumentSyncKind.Full,
				"diagnosticProvider":{
					"interFileDependencies":True,
					"workspaceDiagnostics":False,
				},
				"semanticTokensProvider":{
					"legend":{
						"tokenTypes":TOKEN_TYPES,
						"tokenModifiers":TOKEN_MODIFIERS,
					},
					"full":True
				}
			}
		return reply({
			"capabilities": CAPABILITIES,
		})
	elif method == 'shutdown':
		logs.info("Received 'shutdown' request, shutting down")
		return reply(None)
	elif method == 'exit':
		logs.info("Received 'exit' request, server exits now (with 0)")
		sys.exit(0)
	elif method == 'textDocument/semanticTokens/full':
		uri = params["textDocument"]["uri"]
		tokens = get_semantic_tokens(uri)
		if tokens is not None:
			return reply({
				"data": tokens
			})
		return error(ErrorCodes.RequestFailed, "Could not extract semantic tokens due to invalid syntax")
	else:
		logs.error(f"Received unknown method: {method!r}, params: {json.dumps(params, indent=4)}")
		return error(ErrorCodes.MethodNotFound, f"method '{method}' can't be handled on the server")

def handle_notification(method:str, params:Any) -> None:
	if method == 'initialized':
		pass
	elif method == 'textDocument/didSave':
		uri = params["textDocument"]["uri"]
	elif method == 'textDocument/didOpen':
		text = params["textDocument"]["text"]
		if params["textDocument"]["languageId"] != 'jararaca':
			exit_abnormally(f"Received a request for another language, exiting")
		uri = params["textDocument"]["uri"]
		opened_files_texts[uri] = text
		logs.debug(f"Opened file {uri!r}")
		compute_diagnostics(uri)
	elif method == 'textDocument/didChange':
		text = params["contentChanges"][-1]["text"] # we need to apply all changes, so we take the last one's text 
		uri = params["textDocument"]["uri"]
		opened_files_texts[uri] = text
		logs.debug(f"Changed file {uri!r}")
	elif method == 'textDocument/didClose':
		uri = params["textDocument"]["uri"]
		del opened_files_texts[uri]
		logs.debug(f"Closed file {uri!r}")
	elif method.startswith('$/'):#ignore
		return
	else:
		logs.warn(f"Received unknown notification: {method!r}, go check")

opened_files_texts:dict[str,str] = {}
def compute_diagnostics(file_uri:str) -> None:
	text = opened_files_texts[file_uri] + '\n'
	bin    = jararaca.ErrorBin(silent=True)
	config = jararaca.Config.use_defaults(bin, file_uri)
	try:
		tokens = jararaca.Lexer(text,config,file_uri).lex()
		module = jararaca.Parser(tokens, config).parse()
		jararaca.TypeChecker(module,config).go_check()
	except jararaca.ErrorExit: # when a critical error is caught
		pass
	send_diagnostics(bin, file_uri)
def send_diagnostics(bin:jararaca.ErrorBin,file_uri:str) -> None:
	logs.debug(f"Errors found: {len(bin.errors)}")	
	publish_notification("textDocument/publishDiagnostics",{
		"uri":file_uri,
		"diagnostics": [
			{
				"range":{
					"start":{
						"line":error.place.start.line-1,
						"character":error.place.start.cols-1,
					},#-1 because jararaca starts from 1, client starts from 0
					"end":{
						"line":error.place.end.line-1,
						"character":error.place.end.cols-1,
					}
				},
				"message":f"{error.msg} [{error.typ}]",
			} for error in bin.errors if error.place is not None if error.place.file_path == file_uri
		]
	})

TOKEN_TYPES = [
	'namespace',
	'struct',
	'parameter',
	'variable',
	'property',#order matters
	'function',
	'string',
	'number',
	'operator',
]
TT_TO_TT = {
	jararaca.SemanticTokenType.MODULE   :0,
	jararaca.SemanticTokenType.STRUCT   :1,
	jararaca.SemanticTokenType.ARGUMENT :2,
	jararaca.SemanticTokenType.VARIABLE :3,
	jararaca.SemanticTokenType.PROPERTY :4,
	jararaca.SemanticTokenType.FUNCTION :5,
	jararaca.SemanticTokenType.STRING   :6,
	jararaca.SemanticTokenType.NUMBER   :7,
	jararaca.SemanticTokenType.OPERATOR :8,
}
assert len(jararaca.SemanticTokenType) == len(TOKEN_TYPES) == len(TT_TO_TT)
TOKEN_MODIFIERS:list[str] = [
	'declaration',
	'definition',#order matters
	'static',
]
TM_TO_TM = {
	jararaca.SemanticTokenModifier.DECLARATION :0,
	jararaca.SemanticTokenModifier.DEFINITION  :1,
	jararaca.SemanticTokenModifier.STATIC      :2,
}
assert len(jararaca.SemanticTokenModifier) == len(TOKEN_MODIFIERS) == len(TM_TO_TM)
def get_semantic_tokens(file_uri:str) -> list[int]:
	text = opened_files_texts[file_uri] + '\n'
	bin    = jararaca.ErrorBin(silent=True)
	config = jararaca.Config.use_defaults(bin, file_uri)
	tokens = jararaca.Lexer(text,config,file_uri).lex()
	module = jararaca.Parser(tokens, config).parse()
	tc = jararaca.TypeChecker(module,config,semantic=True)
	try:
		tc.go_check()
	except jararaca.ErrorExit:
		pass
	send_diagnostics(bin, file_uri)
	sk = list(tc.semantic_tokens)
	sk.sort(key=lambda x:x.place.start.idx)
	return prepare_semantic_tokens(sk)
def prepare_semantic_tokens(tokens:list[jararaca.SemanticToken]) -> list[int]:
	result:list[int] = []
	previous_line = 0
	previous_char = 0
	for token in tokens:
		line = token.place.start.line-1
		diff_line = line-previous_line
		result.append(diff_line)
		previous_line = line
		if diff_line != 0:
			previous_char = 0
		start = token.place.start.cols-1
		diff_char = start-previous_char
		result.append(diff_char)
		previous_char = start
		result.append(token.place.length)
		result.append(TT_TO_TT[token.typ])
		modifier = 0b0
		for mod in token.modifiers:
			modifier |= 1 << TM_TO_TM[mod]
		result.append(modifier)
	return result

if __name__ == '__main__':
	main()
