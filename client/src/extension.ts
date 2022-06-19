
import * as path from 'path';

import { Disposable, ExtensionContext } from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions, DocumentSelector } from 'vscode-languageclient/node';

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
	context.subscriptions.push(startLangServer(args[0], args.slice(1), [{ scheme: 'file', language: 'jararaca' }]));
}
