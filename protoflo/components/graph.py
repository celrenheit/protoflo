from twisted.internet import reactor, defer, threads

from ..component import Component
from ..port import InPorts, OutPorts
from ..network import Network

from .. import graph as graphModule

class Graph (Component):
	subgraph = True

	def initialize (self, metadata = None):
		self.network = None
		self.ready = True
		self.started = False
		self.baseDir = None
		self.loader = None

		self.inPorts = InPorts()
		self.inPorts["graph"] = {
			"datatype": 'all',
			"description": 'NoFlo graph definition to be used with the subgraph component',
			"required": True,
			"immediate": True
		}
		self.inPorts["start"] = {
			"datatype": 'bang',
			"description": 'if attached, the network will only be started when receiving a start message',
			"required": False
		}

		self.inPorts['graph'].on('data', lambda data: self.setGraph(data['data']))
		self.inPorts['start'].on('data', lambda data: self.start())

	def setGraph (self, graph):
		self.ready = False

		# Graph object
		if isinstance(graph, graphModule.Graph):
			return self.createNetwork(graph)

		def loaded (instance):
			instance.baseDir = self.baseDir
			self.createNetwork(instance)

		# JSON definition of a graph
		if isinstance(graph, dict):
			try:
				instance = graphModule.loadJSON(graph)
				loaded(instance)
			except Exception as e:
				self.error(e)

			return

		# Graph filename
		else:
			graph = str(graph)
			# FIXME: this is not fully ported from javascript.  use os.abspath
			if graph.substr[0] != "/" and graph.substr[1] != ":":
				graph = os.path.join(os.getcwd(), graph)

			# TODO: Component.error should accept a Failure
			threads.deferToThread(graphModule.loadFile, graph) \
			.addCallbacks(loaded, self.error)

	def createNetwork (self, graph):
		try:
			self.description = graph.properties['description']
		except KeyError:
			self.description = ''

		try:
			self.icon = graph.properties['icon']
		except KeyError:
			self.icon = ''

		graph.componentLoader = self.loader

		def created (network):
			self.network = network
			self.emit('network', network = network)
			network.connect().addCallbacks(connected, self.error)
			
		def connected (network):
			self._notReady = 0
			for name, process in network.processes.items():
				if not checkComponent(name, process):
					self._notReady += 1

			if not self._notReady:
				reactor.callLater(0, setReady)

			if "start" in self.inPorts and self.inPorts['start'].attached and not self.started:
				return

			self.start(graph)

		def setReady ():
			self.ready = True
			self.emit("ready")

		def checkComponent (name, process):
			if not process.component.ready:
				@process.component.once("ready")
				def checkComponent_onReady (data):
					if checkComponent(name, process):
						self._notReady -= 1
						if self._notReady == 0:
							setReady()

				return False

			self.findEdgePorts(name, process)

		return True

		Network.create(graph, delayed = True).addCallbacks(created, self.error)

	def start (self, graph = None):
		self.started = True

		if self.network is None:
			return

		self.network.sendInitials()

		if graph is not None:
			graph.on('addInitial', lambda _: self.network.sendInitials())

	def _isExported (self, port, nodeName, portName, _ports, _add):
		# First we check disambiguated exported ports
		for pub, priv in _ports.items():
			if priv['process'] == nodeName and priv['port'] == portName:
				return pub

		# Then we check disambiguated ports, and if needed, fix them
		for exported in self.network.graph.exports:
			if exported['process'] == nodeName and exported['port'] == portName:
				self.network.graph.checkTransactionStart()
				self.network.graph.removeExport(exported['public'])
				_add(
					exported['public'], 
					exported['process'], 
					exported['port'], 
					exported['metadata']
				)
				self.network.graph.checkTransactionEnd()

				return exported['public']

		# Component has exported ports and this isn't one of them
		if len(_ports):
			return False

		if port.attached:
			return False

		return '.'.join(nodeName, portName).lower()

	def isExportedInport (self, port, nodeName, portName):
		return self._isExported(port, nodeName, portName, 
			self.network.graph.inports,
			self.network.graph.addInport
		)

	def isExportedOutport (self, port, nodeName, portName):
		return self._isExported(port, nodeName, portName, 
			self.network.graph.outports,
			self.network.graph.addOutport
		)

	def findEdgePorts (self, name, process):
		for portName, port in process.component.inPorts.items():
			targetPortName = self.isExportedInport(port, name, portName)

			if targetPortName is not False:
				self.inPorts.add(targetPortName, port)

		for portName, port in process.component.outPorts.items():
			targetPortName = self.isExportedOutport(port, name, portName)

			if targetPortName is not False:
				self.outPorts.add(targetPortName, port)

		return True

	def shutdown (self):
		if self.network is not None:
			self.network.stop()
