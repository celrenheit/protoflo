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
			for component in components:
				print "Processing %s" % component
				self.processComponent(loader, component, context)

		def error (failure):
			self.send('error', failure.value, context)

		#baseDir = self.transport.options.baseDir
		loader = self.getLoader() #baseDir
		loader.listComponents().addCallbacks(componentsLoaded, error)

	def getSource (self, payload, context):
		self.send('error', Error("Not Implemented"), context)

	def setSource (self, payload, context):
		self.send('error', Error("Not Implemented"), context)

	def processComponent (self, loader, component, context):
		def componentLoaded (instance):
			# Ensure graphs are not run automatically when just querying their ports
			if not instance.ready:
				@instance.once('ready')
				def processComponent_instanceReady (data):
					self.sendComponent(component, instance, context)

			else:
				self.sendComponent(component, instance, context)

		def error (failure):
			self.send('error', failure.value, context)

		loader.load(component, delayed = True).addCallbacks(componentLoaded, error)

	def sendComponent (self, component, instance, context):
		inPorts = []
		outPorts = []

		for portName, port in instance.inPorts.iteritems():
			inPort = {
				"id": portName,
				"type": port.datatype,
				"required": port.required,
				"addressable": port.addressable,
				"description": port.description
			}

			if "values" in port.options and port.options["values"] is not None:
				inPort["values"] = port.options["values"]

			if "default" in port.options and port.options["default"] is not None:
				inPort["default"] = port.options["default"]
			
			inPorts.append(inPort)

		for portName, port in instance.outPorts.iteritems():
			outPorts.append({
				"id": portName,
				"type": port.datatype,
				"required": port.required,
				"addressable": port.addressable,
				"description": port.description
			})

		self.send('component', {
			"name": component,
			"description": instance.description,
			"subgraph": instance.subgraph,
			"icon": instance.icon,
			"inPorts": inPorts,
			"outPorts": outPorts
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
