from ...network import Network
from twisted.python import log

def prepareSocketEvent (event, req):
	payload = {
		"id": event["id"],
		"graph": req["graph"]
	}

	if "socket" in event:
		if event["socket"].src is not None:
			payload["src"] = {
				"node": event["socket"].src["process"].id,
				"port": event["socket"].src["port"]
			}
		if event["socket"].tgt is not None:
			payload["tgt"] = {
				"node": event["socket"].tgt["process"].id,
				"port": event["socket"].tgt["port"]
			}

	if "subgraph" in event:
		payload["subgraph"] = event["subgraph"]

	if "group" in event:
		payload["group"] = event["group"]

	if "data" in event:
		payload["data"] = event["data"]

	if "subgraph" in event:
		payload["subgraph"] = event["subgraph"]

	return payload

class NetworkProtocol (object):
	def __init__ (self, transport):
		self.transport = transport
		self.networks = {}

	def send (self, topic, payload, context):
		self.transport.send('network', topic, payload, context)

	def receive (self, topic, payload, context):
		try:
			graph = self.resolveGraph(payload, context)

			if topic == 'start':
				return self.initNetwork(graph, payload, context)
			if topic == 'stop':
				return self.stopNetwork(graph, payload, context)
			if topic == 'edges':
				return self.selectEdges(graph, payload, context)

		except Error as e:
			return self.send('error', e, context)

	def resolveGraph (self, payload, context):
		if "graph" not in payload:
			raise Error('No graph specified')

		if payload["graph"] not in self.transport.graph.graphs:
			raise Error('Requested graph not found')

		return self.transport.graph.graphs[payload["graph"]]

	def initNetwork (self, graph, payload, context):
		graph.componentLoader = self.transport.component.getLoader() #graph.baseDir

		def networkReady (network):
			self.networks[payload["graph"]] = network
			self.subscribeNetwork(network, payload, context)

			# Run the network
			return network.connect().addCallback(networkConnected)

		def networkConnected (network):
			@graph.on('addInitial')
			def initNetwork_addInitial(data):
				network.connections.sendInitials().addErrback(error)

			return network.connections.sendInitials()

		def error (failure):
			if failure.type.__name__ != "Error":
				log.err(failure)
			self.send('error', failure.value, context)

		Network.create(graph, delayed = True) \
		.addCallback(networkReady) \
		.addErrback(error)

	def subscribeNetwork (self, network, payload, context):
		@network.on('start')
		def subscribeNetwork_start (data):
			self.send('started', {
				"time": data["start"].isoformat(),
				"graph": payload["graph"]
			}, context)

		@network.on('icon')
		def subscribeNetwork_icon (data):
			data["graph"] = payload["graph"]
			self.send('icon', data, context)

		def handle (event):
			def subscribeNetwork_handle (data):
				if "socket" in data:
					if data['socket'].id not in context.selectedEdges:
						return

				self.send(event, prepareSocketEvent(data, payload), context)

			return subscribeNetwork_handle

		for event in ('connect', 'begingroup', 'data', 'endgroup', 'disconnect'):
			network.on(event, handle(event))

		@network.on('end')
		def subscribeNetwork_end (data):
			self.send('stopped', {
				"time": data["end"].isoformat(),
				"uptime": data["uptime"],
				"graph": payload["graph"]
			}, context)

	def stopNetwork (self, graph, payload, context):
		if payload["graph"] not in self.networks:
			return

		self.networks[payload["graph"]].stop()

	def selectEdges (self, graph, payload, context):
		if payload["graph"] not in self.networks:
			return

		# TODO: make this work without the network.

		network = self.networks[payload["graph"]]
		selected = []

		for edge in payload["edges"]:
			for connection in network.connections:
				if connection.src is None or "process" not in connection.src:
					continue

				if edge["tgt"]["process"] == connection.tgt["process"].id and edge["tgt"]["port"] == connection.tgt["port"]:
					if edge["src"]["process"] == connection.src["process"].id and edge["src"]["port"] == connection.src["port"]:
						selected.append(connection.id)

		# Store this in the context so that it is individual to the client
		# [ Can two clients connect to the same network?? ]
		context.selectedEdges = selected

class Error (Exception):
	pass
