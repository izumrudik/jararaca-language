
import * as path from 'path';

import { workspace, Disposable, ExtensionContext } from 'vscode';
import { LanguageClient, LanguageClientOptions, SettingMonitor, ServerOptions, DocumentSelector, ErrorAction, ErrorHandler, CloseAction, TransportKind } from 'vscode-languageclient/node';

function startLangServer(command: string, args: string[], documentSelector: DocumentSelector | string[]): Disposable {
	const serverOptions: ServerOptions = {
		command,
		args,
	};
	const clientOptions: LanguageClientOptions = {
		documentSelector: documentSelector,
	}
	return new LanguageClient(command, serverOptions, clientOptions).start();
}

export function activate(context: ExtensionContext) {
	let args = ['python3.10', context.asAbsolutePath(path.join('server', 'server.py'))]
	if (false) {// if debug
		args = ['tmux', 'new-session', '-d', '-s', 'language-server', args.join(' ')]
	}
	context.subscriptions.push(startLangServer(args[0], args.slice(1), [{ scheme: 'file', language: 'jararaca' }]));
	// For TCP server needs to be started separately
	// context.subscriptions.push(startLangServerTCP(2087, ["python"]));
}
