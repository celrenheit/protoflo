from ...component import ComponentLoader

class ComponentProtocol (object):

	# loaders: {}

	def __init__ (self, transport):
		self.transport = transport

	def send (self, topic, payload, context):
		self.transport.send('component', topic, payload, context)

	def receive (self, topic, payload, context):
		if topic == 'list': return self.listComponents(payload, context)
		if topic == 'getsource': return self.getSource(payload, context)
		if topic == 'source': return self.setSource(payload, context)

	def getLoader (self): #, baseDir):
		#if baseDir not in self.loaders:
		#	self.loaders[baseDir] = ComponentLoader(baseDir)

		#return self.loaders[baseDir]

		try:
			return self.loader
		except AttributeError:
			self.loader = ComponentLoader()
			return self.loader

	def listComponents (self, payload, context):
		def componentsLoaded (components):
			for component in components.itervalues():
				self.sendComponent(component, context)

		def error (failure):
			self.send('error', failure.value, context)

		#baseDir = self.transport.options.baseDir
		loader = self.getLoader() #baseDir
		loader.listComponents().addCallbacks(componentsLoaded, error)

	def getSource (self, payload, context):
		self.send('error', Error("Not Implemented"), context)

	def setSource (self, payload, context):
		self.send('error', Error("Not Implemented"), context)

	def sendComponent (self, component, context):
		self.send('component', {
			"name": component.componentName,
			"description": component.details['description'],
			"subgraph": component.details['subgraph'],
			"icon": component.details['icon'],
			"inPorts": component.details['inPorts'],
			"outPorts": component.details['outPorts']
		}, context)

	def registerGraph (self, id, graph, context):
		return self.send('error', Error("Not Implemented"), context)

		def register (result):
			loader.registerComponent('', id, graph)
			self.processComponent(loader, id, context)

		loader = self.getLoader() # graph.baseDir
		loader.listComponents().addCallback(register)

		# Send graph info again every time it changes so we get the updated ports
		events = (
			'addNode', 'removeNode', 'renameNode', 'addEdge', 'removeEdge',
			'addInitial', 'removeInitial', 'addInport', 'removeInport', 
			'renameInport','addOutport', 'removeOutport', 'renameOutport'
		)

		@graph.on("all")
		def registerGraph_handle (event, data):
			if event in events:
				self.processComponent(loader, id, context)

class Error (Exception):
	pass
