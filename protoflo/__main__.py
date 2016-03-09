import sys, os
import json

def register (user_id, label, ip, port):
	import http.client
	import uuid

	runtime_id = str(uuid.uuid4())

	conn = http.client.HTTPConnection("api.flowhub.io", 80)
	conn.connect()

	url = "/runtimes/" + runtime_id
	headers = {"Content-type": "application/json"}
	data = {
		'type': 'protoflo',
		'protocol': 'websocket',
		'address': ip + ":" + str(port),
		'id': runtime_id,
		'label': label,
		'port': port,
		'user': user_id,
		'secret': "122223333",
	}

	conn.request("PUT", url, json.dumps(data).encode("UTF-8"), headers)
	response = conn.getresponse()

	if response.status != 201:
		raise ValueError("Could not create runtime " + str(response.status) + str(response.read()))
	else:
		print("Runtime registered with ID", runtime_id)

if __name__ == "__main__":

	import argparse

	parser = argparse.ArgumentParser(prog = sys.argv[0])
	subparsers = parser.add_subparsers(dest = 'command', help = '')

	parser_register = subparsers.add_parser('register', help='Register runtime with Flowhub')
	parser_register.add_argument('--user', type=str, help='User UUID to register runtime for', required=True)
	parser_register.add_argument('--label', type=str, help='Label to use in UI for this runtime', default="ProtoFlo")
	parser_register.add_argument('--ip', type=str, help='WebSocket IP for runtime', default='ws://localhost')
	parser_register.add_argument('--port', type=int, help='WebSocket port for runtime', default=3569)

	parser_runtime = subparsers.add_parser('runtime', help='Start runtime')
	parser_runtime.add_argument('--ip', type=str, help='WebSocket IP for runtime', default='localhost')
	parser_runtime.add_argument('--port', type=int, help='WebSocket port for runtime', default=3569)

	parser_run = subparsers.add_parser('run', help='Run a graph non-interactively')
	parser_run.add_argument('--file', type=str, help='Graph file .fbp|.json', required=True)

	args = parser.parse_args(sys.argv[1:])
	if args.command == 'register':
		register(args.user, args.label, args.ip, args.port)

	elif args.command == 'runtime':
		from protoflo.server.server import runtime
		runtime(args.ip, args.port)

	elif args.command == 'run':
		from twisted.internet import reactor
		from . import graph, network

		def onRunning (net):
			@net.on("end")
			def stop (data):
				reactor.stop()

		network.Network.create(graph.loadFile(args.file)).addCallback(onRunning)
		reactor.run()
