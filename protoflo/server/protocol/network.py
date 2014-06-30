from ...network import Network

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
			network.connect().addCallback(networkConnected)

		def networkConnected (network):
			network.connections.sendInitials()

			@graph.on('addInitial')
			def initNetwork_addInitial(data):
				network.connections.sendInitials()

		def error (failure):
			self.send('error', failure.value, context)

		Network.create(graph, delayed = True).addCallbacks(networkReady, error)

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

		for event in ('connect', 'begingroup', 'data', 'endgroup', 'disconnect'):
			@network.on(event)
			def subscribeNetwork_handler (data):
				self.send(event, prepareSocketEvent(data, payload), context)

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

class Error (Exception):
	pass
