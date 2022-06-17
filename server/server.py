import json
import logging as logs
import sys
import os
import traceback
from typing import Any

def main() -> None:
	dir = os.path.dirname(os.path.realpath(__file__))
	try:
		logs.basicConfig(filename=os.path.join(dir,"server.logs"),
						filemode='w',
						format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
						datefmt='%H:%M:%S',
						level=logs.DEBUG)
		logs.debug("Server started")
		content = get_json()
		content
		logs.debug("Server stopped")
	except Exception:
		logs.error(traceback.format_exc())

def get_json() -> Any:
	headers_string = ""
	while True:
		chunk = sys.stdin.read(1)
		headers_string += chunk
		if headers_string[-4:] == '\r\n\r\n':
			headers_string = headers_string[:-4]
			logs.debug(f"found term: '\\r\\n\\r\\n', headers: {headers_string!r}")
			break
	headers = (header.split(': ') for header in headers_string.split('\r\n'))
	length:int
	for (name, body) in headers:
		if name == 'Content-Length':
			length = int(body)
		else:
			logs.error(f"Unknown Header: {name = !r}, {body = !r}")
			sys.exit(1)
	logs.debug(f"Read length: {length!r}")
	length = length
	content = json.loads(sys.stdin.read(length))
	logs.debug(f"content is {content!r}")
	return content

if __name__ == '__main__':
	main()