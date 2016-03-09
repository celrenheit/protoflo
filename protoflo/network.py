from twisted.internet import reactor, defer
from twisted.python import failure

from .util import EventEmitter, debounce
from .socket import InternalSocket
from .component import ComponentLoader

from collections import deque
from datetime import datetime
import functools

class Network (EventEmitter):
	@classmethod
	def create (cls, graph, delayed = False):
		network = cls(graph)
		d = defer.Deferred()

		def networkReady (network):
			d.callback(network)

			# Send IIPs
			network.start()

		def componentsLoaded (components):
			# Empty network, no need to connect it up
			if len(graph.nodes) == 0:
				return networkReady(network)

			# In case of delayed execution we don't wire it up
			if delayed:
				return d.callback(network)

			# Wire the network up and start execution
			network.connect().addCallbacks(networkReady, d.errback)

		# Ensure components are loaded before continuing
		network.loader.listComponents().addCallbacks(componentsLoaded, d.errback)

		return d

	def __init__ (self, graph):
		self.loader = ComponentLoader()
		self.processes = Processes(self, self.loader)
		self.connections = Edges(self)
		self.graph = graph

		self.startupDate = datetime.now()

	@property
	def uptime (self):
		return (datetime.now() - self.startupDate).total_seconds()

	running = False
	connectionCount = 0

	def increaseConnections (self):
		if self.connectionCount == 0 and not self.running:
			self.running = True # Otherwise can get multiple start events during IIP sending.
			self.emit("start", start = self.startupDate)

		self.connectionCount += 1

	def decreaseConnections (self):
		self.connectionCount -= 1

		if self.connectionCount == 0:
			self._end()

	@debounce(0.01)
	def _end (self):
		if self.connectionCount:
			return

		self.running = False

		self.emit("end", 
			start = self.startupDate,
			end = datetime.now(),
			uptime = self.uptime
		)

	def load (self, component, metadata = None):
		return self.loader.load(component, metadata)

	@defer.inlineCallbacks
	def connect (self):
		for node in self.graph.nodes:
			yield self.processes.add(**node)

		for edge in self.graph.edges:
			yield self.connections.add(**edge)

		for iip in self.graph.initials:
			yield self.connections.addInitial(**iip)

		self.subscribeGraph()

		defer.returnValue(self)

	def connectPort (self, socket, process, port, index, inbound):
		if inbound == True:
			socket.tgt = {
				"process": process,
				"port": port,
				"index": index
			}

			try:
				process.component.inPorts[port]
			except (AttributeError, KeyError):
				raise Error ("No inport '{:s}' defined in process {:s} ({:s})".format(port, process.id, socket.id))

			if process.component.inPorts[port].addressable:
				return process.component.inPorts[port].attach(socket, index)

			return process.component.inPorts[port].attach(socket)

		else:
			socket.src = {
				"process": process,
				"port": port,
				"index": index
			}

			try:
				process.component.outPorts[port]
			except (AttributeError, KeyError):
				raise Error ("No outport '{:s}' defined in process {:s} ({:s})".format(port, process.id, socket.id))

			if process.component.outPorts[port].addressable:
				return process.component.outPorts[port].attach(socket, index)

			return process.component.outPorts[port].attach(socket)

	# Subscribe to events from all connected sockets and re-emit them
	def subscribeSocket (self, socket):
		def socketevent (event, data):
			if event == "connect":
				self.increaseConnections()
			elif event == "disconnect":
				self.decreaseConnections()
			
			data["id"] = socket.id
			data["socket"] = socket

			self.emit(event, **data)

		for event in ('connect', 'begingroup', 'data', 'endgroup', 'disconnect'):
			socket.on(event, functools.partial(socketevent, event))

	def subscribeGraph (self):
		# A NoFlo graph may change after network initialization.
		# For this, the network subscribes to the change events from
		# the graph.
		#
		# In graph we talk about nodes and edges. Nodes correspond
		# to NoFlo processes, and edges to connections between them.
		graphOps = deque()
		processing = False

		def registerOp (op, details):
			graphOps.append({
				"op": op,
				"details": details
			})

			if not processing:
				processOps()

		def error (reason):
			# TODO: log.
			print(("subscribeGraph: Error: " + str(reason)))
			processOps()

		def processOps (result = None):
			try:
				op = graphOps.popleft()
				processing = True
				op["op"](*op["details"]).addCallbacks(processOps, error)

			except IndexError:
				processing = False

		def handler (event, item, op, keys):
			def subscribeGraphHandler (data):
				d = data[item]
				a = []

				for k in keys:
					try:
						a.append(d[k])
					except:
						a.append(None)

				registerOp(op, a)

			return subscribeGraphHandler

		for event, item, op, keys in (
			("addNode", "node", self.processes.add, ("id", "component", "metadata")),
			("removeNode", "node", self.processes.remove, ("id",)),
			("addEdge", "edge", self.connections.add, ("src", "tgt", "metadata")),
			("removeEdge", "edge", self.connections.remove, ("src", "tgt")),
			("addInitial", "edge", self.connections.addInitial, ("src", "tgt", "metadata")),
			("removeInitial", "edge", self.connections.removeInitial, ("tgt",)),
		):
			self.graph.on(event, handler(event, item, op, keys))

		@self.graph.on("renameNode")
		def subscribeGraphHandler (data):
			registerOp(self.processes.rename, {
				oldId: data["old"], 
				newId: data["new"]
			})

	def start (self):
		self.connections.sendInitials()

	def stop (self):
		# Disconnect all connections
		for connection in self.connections:
			if connection.connected:
				connection.disconnect()

		# Tell processes to shut down
		for process in self.processes:
			process.component.shutdown()


class Process (object):
	id = None
	component = None
	metadata = None

	def __init__ (self, id, component = None, metadata = None):
		self.id = id
		self.component = component
		self.metadata = metadata	


class Processes (EventEmitter):
	def __init__ (self, network, loader):
		self.processes = {}
		self.network = network
		self.loader = loader

	def get (self, id):
		return self.processes[id]

	__getitem__ = get

	def __iter__ (self):
		return iter(self.processes.values())

	def add (self, id, component = None, metadata = None):
		if id in self.processes:
			return defer.succeed(self.processes[id])

		d = defer.Deferred()
		process = Process(id, component, metadata)

		if component is None:
			self.processes[id] = process
			return defer.succeed(process)

		def initialise (instance):
			instance.nodeId = id
			process.component = instance

			for name, port in instance.inPorts.items():
				port.node = id
				port.nodeInstance = instance
				port.name = name

			for name, port in instance.outPorts.items():
				port.node = id
				port.nodeInstance = instance
				port.name = name

			if instance.subgraph:
				self.subscribeSubgraph(process)

			self.subscribeNode(process)

			self.processes[id] = process
			d.callback(process)

		self.loader.load(component, metadata) \
			.addCallbacks(initialise, d.errback)

		return d

	def remove (self, node):
		if isinstance(node, Process):
			node = node.id

		if node not in self.processes:
			return

		try:
			self.processes[node].component.shutdown()
		except AttributeError:
			pass

		del self.processes[node]

		return defer.succeed(True)

	def rename (self, oldId, newId):
		try:
			process = self.processes[oldId]
		except KeyError:
			return

		process.id = newId

		for port in instance.inPorts.values():
			port.node = newId

		for port in instance.outPorts.values():
			port.node = newId

		self.processes[newId] = process
		del self.processes[oldId]

		return defer.succeed(True)

	def subscribeSubgraph (self, node):
		if not node.component.ready:
			@node.component.once("ready")
			def subscribeSubgraph (data):
				self.subscribeSubgraph(node)

			return

		if not hasattr(node.component, "network"):
			return

		def subscribeSubgraphHandler (event, data = None):
			if event == "connect":
				self.network.increaseConnections()
			elif event == "disconnect":
				self.network.increaseConnections()
			elif event not in ("data", "begingroup", "endgroup"):
				return
			
			if data is None:
				data = {}

			if "subgraph" in data:
				data["subgraph"].insert(node.id, 0)
			else:
				data["subgraph"] = [node.id]

			self.emit(event, **data)

		for event in ('connect', 'begingroup', 'data', 'endgroup', 'disconnect'):
			node.component.network.on(
				event, 
				functools.partial(subscribeSubgraphHandler, event)
			)

	def subscribeNode (self, node):
		if not hasattr(node.component, "icon"):
			return

		@node.component.on("icon")
		def subscribeNodeOnIcon (data):
			self.emit("icon",
				id = node.id,
				icon = data["icon"]
			)


class Edge (object):
	src = None
	tgt = None
	metadata = None

	def __init__ (self, src = None, tgt = None, metadata = None):
		self.src = src
		self.tgt = tgt
		self.metadata = metadata


class Initial (object):
	socket = None
	data = None

	def __init__ (self, socket, data = None):
		self.socket = socket
		self.data = data


class Edges (object):
	def __init__ (self, network):
		self.initials = []
		self.connections = []
		self.network = network

	def __iter__ (self):
		return iter(self.connections)

	def add (self, src, tgt, metadata = None):
		socket = InternalSocket()

		# Check src node
		try:
			fromNode = self.network.processes.get(src["node"])
		except KeyError:
			raise Error("No process defined for outbound node " + src["node"])

		if fromNode.component is None:
			raise Error("No component defined for outbound node " + src["node"])

		if not fromNode.component.ready:
			d = defer.Deferred()

			@fromNode.component.once("ready")
			def addEdge (data):
				self.add(src, target, metadata).addCallbacks(d.callback, d.errback)

			return d

		# Check tgt node
		try:
			toNode = self.network.processes.get(tgt["node"])
		except KeyError:
			raise Error("No process defined for inbound node " + tgt["node"])

		if toNode.component is None:
			raise Error("No component defined for inbound node " + tgt["node"])

		if not toNode.component.ready:
			d = defer.Deferred()

			@toNode.component.once("ready")
			def addEdge (data):
				self.add(src, target, metadata).addCallbacks(d.callback, d.errback)

			return d

		# Make connections
		self.network.connectPort(socket, toNode, tgt["port"], tgt["index"], True)
		self.network.connectPort(socket, fromNode, src["port"], src["index"], False)

		self.network.subscribeSocket(socket)

		self.connections.append(socket)

		return defer.succeed(None)

	def remove (self, src, tgt):
		for connection in self.connections[:]:
			if tgt["node"] == connection.tgt["process"].id \
			and tgt["port"] == connection.tgt["port"]:
				connection.tgt["process"].component.inPorts[connection.tgt["port"]].detach(connection)

			if connection.src is not None \
			and "node" in src \
			and src["node"] is not None:
				if connection.tgt and src["node"] == connection.src["process"].id \
				and src["port"] == connection.src["port"]:
					connection.src["process"].component.outPorts[connection.src["port"]].detach(connection)

			self.connections.remove(connection)
			return defer.succeed(None)
		
	def addInitial (self, src, tgt, metadata = None):
		socket = InternalSocket()
		d = defer.Deferred()

		# Subscribe to events from the socket
		self.network.subscribeSocket(socket)

		try:
			to = self.network.processes.get(tgt["node"])
		except KeyError:
			raise Error("No process defined for inbound node {:s}".format(tgt["node"]))

		if not (to.component.ready or tgt["port"] in to.component.inPorts):
			d = defer.Deferred()

			@to.component.once("ready")
			def addInitial (data):
				self.addInitial(src, target, metadata).addCallbacks(d.callback, d.errback)

			return d

		self.network.connectPort(socket, to, tgt["port"], tgt["index"], True)

		self.connections.append(socket)
		self.initials.append(Initial(socket, src["data"]))

		return defer.succeed(None)

	def removeInitial (self, tgt):
		for connection in self.connections:
			if tgt["node"] == connection.tgt["process"].id \
			and tgt["port"] == connection.tgt["port"]:
				connection.tgt["process"].component.inPorts[connection.tgt["port"]].detach(connection)
				self.connections.remove(connection)

		return defer.succeed(None)

	def sendInitial (self, initial):
		initial.socket.connect()
		initial.socket.send(initial.data)
		initial.socket.disconnect()

		return defer.succeed(None)

	def sendInitials (self):
		d = defer.Deferred()

		def send ():
			try:
				for initial in self.initials:
					self.sendInitial(initial)

				self.initials = []
				d.callback(None)
			except:
				f = failure.Failure()
				d.errback(f)

		reactor.callLater(0, send)
		return d

class Error (Exception):
	pass
