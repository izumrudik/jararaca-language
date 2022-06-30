import json
import logging as logs
import signal
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
		level=logs.DEBUG)
	logs.info(f"\n\n\nServer started ({os.getpid()})")
	
	try:
		while True:
			handle_content(get_json())
	except Exception:
		logs.error(traceback.format_exc())
	logs.info("Server stopped\n")


def read_with_timeout(timeout:int) -> str:
	signal.signal(signal.SIGALRM, lambda signum, frame: exit_abnormally("Timeout while reading from stdin. Most likely client is dead"))
	signal.alarm(timeout)
	r = sys.stdin.read(1)
	signal.alarm(0)
	return r
def get_json() -> Any:
	headers_string = ''
	while True:
		chunk = read_with_timeout(5*60) # 5 minutes timeout
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

class MarkupKind:
	PlainText = 'plaintext'
	Markdown  = 'markdown'


def exit_abnormally(msg:str) -> NoReturn:
	logs.error(msg)
	publish_notification('shutdown', None)
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
				},
				"hoverProvider":True,
			}
		return reply({
			"capabilities": CAPABILITIES,
		})
	elif method == 'shutdown':
		logs.info("Received 'shutdown' request, shutting down")
		return reply(None)
	elif method == 'textDocument/semanticTokens/full':
		uri = params["textDocument"]["uri"]
		tokens = get_semantic_tokens(uri)
		return reply({"data": tokens})
	elif method == 'textDocument/hover':
		uri = params["textDocument"]["uri"]
		line = params["position"]["line"]
		column = params["position"]["character"]
		hover = get_hover(uri, line+1, column+1)
		if hover is None:return reply(None)
		value,place = hover
		content = {'value':value,'kind':MarkupKind.Markdown}
		if place is None:return reply({"contents":content})
		return reply({"contents":content,"range":place_to_range(place)})
	else:
		logs.error(f"Received unknown method: {method!r}, params: {json.dumps(params, indent=4)}")
		return error(ErrorCodes.MethodNotFound, f"method '{method}' can't be handled on the server")

def handle_notification(method:str, params:Any) -> None:
	if method == 'initialized':
		pass
	elif method == 'exit':
		logs.info("Received 'exit' request, server exits now (with 0)")
		sys.exit(0)
	elif method == 'textDocument/didSave':
		uri = params["textDocument"]["uri"]
	elif method == 'textDocument/didOpen':
		text = params["textDocument"]["text"]
		if params["textDocument"]["languageId"] != 'jararaca':
			exit_abnormally(f"Received a request for another language, exiting")
		uri = params["textDocument"]["uri"]
		logs.debug(f"Opened file {uri!r}")
		update_opened_files(uri,text)
	elif method == 'textDocument/didChange':
		text = params["contentChanges"][-1]["text"] # we need to apply all changes, so we take the last one's text 
		uri = params["textDocument"]["uri"]
		update_opened_files(uri,text)
		logs.debug(f"Changed file {uri!r}")
	elif method == 'textDocument/didClose':
		uri = params["textDocument"]["uri"]
		delete_file(uri)
		logs.debug(f"Closed file {uri!r}")
	elif method.startswith('$/'):#ignore
		return
	else:
		logs.warn(f"Received unknown notification: {method!r}, go check")

opened_files_jararaca:dict[str,tuple[jararaca.Config,jararaca.TypeChecker]] = {}

def delete_file(uri:str) -> None:
	opened_files_jararaca.pop(uri)

def update_opened_files(uri:str, text:str) -> None:
	text+='\n'
	try:
		bin    = jararaca.ErrorBin(silent=True)
		config = jararaca.Config.use_defaults(bin, uri)
		tokens = jararaca.Lexer(text,config,uri).lex()
		module = jararaca.Parser(tokens, config).parse()
		tc = jararaca.TypeChecker(module,config, semantic=True)
	except jararaca.ErrorExit:
		exit_abnormally(f"A critical error was found while lexing/parsing file {uri!r}")
	try:
		tc.go_check()
	except jararaca.ErrorExit: # when a critical error is caught
		pass
	opened_files_jararaca[uri] = (config, tc)
	send_diagnostics(uri)

def send_diagnostics(uri:str) -> None:
	bin = opened_files_jararaca[uri][0].errors
	logs.debug(f"Errors found: {len(bin.errors)}")	
	publish_notification("textDocument/publishDiagnostics",{
		"uri":uri,
		"diagnostics": [
			{
				"range": place_to_range(error.place),
				"message":f"{error.msg} [{error.typ}]",
			} for error in bin.errors if error.place is not None if error.place.file_path == uri
		]
	})

def place_to_range(place:jararaca.Place) -> dict[str,dict[str,int]]:
	return {
		"start":{
			"line":place.start.line-1,
			"character":place.start.cols-1,
		},#-1 because jararaca starts from 1, client starts from 0
		"end":{
			"line":place.end.line-1,
			"character":place.end.cols-1,
		}
	}

TOKEN_TYPES = [
	'namespace',
	'struct',
	'parameter',
	'variable',
	'property',
	'function',
	'method',
	'string',
	'number',
	'operator',
	'method',
]
TT_TO_TT = {
	jararaca.SemanticTokenType.MODULE           :TOKEN_TYPES.index('namespace'),
	jararaca.SemanticTokenType.STRUCT           :TOKEN_TYPES.index('struct'),
	jararaca.SemanticTokenType.ARGUMENT         :TOKEN_TYPES.index('parameter'),
	jararaca.SemanticTokenType.VARIABLE         :TOKEN_TYPES.index('variable'),
	jararaca.SemanticTokenType.PROPERTY         :TOKEN_TYPES.index('property'),
	jararaca.SemanticTokenType.FUNCTION         :TOKEN_TYPES.index('function'),
	jararaca.SemanticTokenType.MIX              :TOKEN_TYPES.index('function'),
	jararaca.SemanticTokenType.BOUND_FUNCTION   :TOKEN_TYPES.index('method'),
	jararaca.SemanticTokenType.STRING           :TOKEN_TYPES.index('string'),
	jararaca.SemanticTokenType.CHARACTER_STRING :TOKEN_TYPES.index('string'),
	jararaca.SemanticTokenType.CHARACTER_NUMBER :TOKEN_TYPES.index('number'),
	jararaca.SemanticTokenType.INTEGER          :TOKEN_TYPES.index('number'),
	jararaca.SemanticTokenType.SHORT            :TOKEN_TYPES.index('number'),
	jararaca.SemanticTokenType.OPERATOR         :TOKEN_TYPES.index('operator'),
}
assert len(jararaca.SemanticTokenType) == len(TT_TO_TT)
TOKEN_MODIFIERS:list[str] = [
	'declaration',
	'definition',
	'static',
]
TM_TO_TM = {
	jararaca.SemanticTokenModifier.DECLARATION :TOKEN_MODIFIERS.index('declaration'),
	jararaca.SemanticTokenModifier.DEFINITION  :TOKEN_MODIFIERS.index('definition'),
	jararaca.SemanticTokenModifier.STATIC      :TOKEN_MODIFIERS.index('static'),
}
assert len(jararaca.SemanticTokenModifier) == len(TOKEN_MODIFIERS) == len(TM_TO_TM)
def get_semantic_tokens(uri:str) -> list[int]:
	tc = opened_files_jararaca[uri][1]
	sk = list(tc.semantic_tokens)
	sk.sort(key=lambda x:x.place.start.idx)
	return prepare_semantic_tokens(sk)
def prepare_semantic_tokens(tokens:list[jararaca.SemanticToken]) -> list[int]:
	result:list[int] = []
	previous_line = 0
	previous_char = 0
	for token in tokens:
		if token.typ == jararaca.SemanticTokenType.OPERATOR:
			continue#ignore operators because they override word-like operators' coloring
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

def get_hover(uri:str, line:int, char:int) -> tuple[str,jararaca.Place|None]|None:
	for token in opened_files_jararaca[uri][1].semantic_tokens:
		if token.place.start.line <= line <= token.place.end.line and \
		token.place.start.cols <= char <= token.place.end.cols:
			return f"""\
### \
{'static ' if jararaca.SemanticTokenModifier.STATIC in token.modifiers else ''}\
**{token.typ}**\
{' definition' if jararaca.SemanticTokenModifier.DEFINITION in token.modifiers else ''}\
{' declaration' if jararaca.SemanticTokenModifier.DECLARATION in token.modifiers else ''}\
""", token.place
	return None

if __name__ == '__main__':
	main()
