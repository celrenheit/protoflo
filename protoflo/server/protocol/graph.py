from ...graph import Graph

import copy

class GraphProtocol (object):
	def __init__ (self, transport):
		self.transport = transport
		self.graphs = {}

	def send (self, topic, payload, context):
		self.transport.send('graph', topic, payload, context)

	def receive (self, topic, payload, context):
		if topic == 'clear':
			return self.initGraph(payload, context)

		try:
			# Find locally stored graph by ID
			graph = self.resolveGraph(payload)

			# Run command
			# FIXME: convert this to a dictionary
			# FIXME: add addgroup, removegroup, renamegroup, changegroup
			if topic == 'addnode':         return self.addNode       (graph, payload, context)
			elif topic == 'removenode':    return self.removeNode    (graph, payload, context)
			elif topic == 'renamenode':    return self.renameNode    (graph, payload, context)
			elif topic == 'changenode':    return self.changeNode    (graph, payload, context)
			elif topic == 'addedge':       return self.addEdge       (graph, payload, context)
			elif topic == 'removeedge':    return self.removeEdge    (graph, payload, context)
			elif topic == 'changeedge':    return self.changeEdge    (graph, payload, context)
			elif topic == 'addinitial':    return self.addInitial    (graph, payload, context)
			elif topic == 'removeinitial': return self.removeInitial (graph, payload, context)
			elif topic == 'addinport':     return self.addInport     (graph, payload, context)
			elif topic == 'removeinport':  return self.removeInport  (graph, payload, context)
			elif topic == 'renameinport':  return self.renameInport  (graph, payload, context)
			elif topic == 'addoutport':    return self.addOutport    (graph, payload, context)
			elif topic == 'removeoutport': return self.removeOutport (graph, payload, context)
			elif topic == 'renameoutport': return self.renameOutport (graph, payload, context)

		except Error as e:
			self.send('error', e, context)
			return

	def resolveGraph (self, payload):
		if "graph" not in payload:
			raise Error('No graph specified')

		if payload["graph"] not in self.graphs:
			raise Error('Requested graph not found')

		return self.graphs[payload["graph"]]

	def initGraph (self, payload, context):
		if "id" not in payload:
			raise Error('No graph ID provided')

		if "name" not in payload:
			payload["name"] = 'NoFlo runtime'

		graph = Graph(payload["name"])

		fullName = payload["id"]
		if "library" in payload:
			graph.properties["library"] = payload["library"]
			fullName = payload["library"] + "/" + fullName

		# Pass the project baseDir
		#graph.baseDir = self.transport.options.baseDir

		self.subscribeGraph(payload["id"], graph, context)

		if "main" not in payload:
			# Register to component loading
			self.transport.component.registerGraph(fullName, graph, context)

		self.graphs[payload["id"]] = graph
		self.send('clear', payload, context)

	def subscribeGraph (self, id, graph, context):
		@graph.on('addNode')
		def subscribeGraphHandler_addNode (data):
			node = copy.deepcopy(data["node"])
			node["graph"] = id
			self.send('addnode', node, context)

		@graph.on('removeNode')
		def subscribeGraphHandler_removeNode (data):
			node = copy.deepcopy(data["node"])
			node["graph"] = id
			self.send('removenode', node, context)

		@graph.on('renameNode')
		def subscribeGraphHandler_renameNode (data):
			self.send('renamenode', {
				"from": data["old"],
				"to": data["new"],
				"graph": id
			}, context)

		@graph.on('changeNode')
		def subscribeGraphHandler_changeNode (data):
			node = copy.deepcopy(data["node"])
			node["graph"] = id
			# the nodejs runtime does not provide 'component' to changenode,
			# but does to removenode. we will immitate this for now.
			# FIXME: resolve this with the noflojs team
			comp = node.pop('component')
			self.send('changenode', node, context)

		@graph.on('addEdge')
		def subscribeGraphHandler_addEdge (data):
			edge = copy.deepcopy(data["edge"])
			edge["graph"] = id

			if edge["src"]["index"] is None:
				del edge["src"]["index"]

			if edge["tgt"]["index"] is None:
				del edge["tgt"]["index"]

			self.send('addedge', edge, context)

		@graph.on('removeEdge')
		def subscribeGraphHandler_removeEdge (data):
			edge = copy.deepcopy(data["edge"])
			edge["graph"] = id

			if edge["src"]["index"] is None:
				del edge["src"]["index"]

			if edge["tgt"]["index"] is None:
				del edge["tgt"]["index"]

			self.send('removeedge', edge, context)

		@graph.on('changeEdge')
		def subscribeGraphHandler_changeEdge (data):
			edge = copy.deepcopy(data["edge"])
			edge["graph"] = id

			if edge["src"]["index"] is None:
				del edge["src"]["index"]

			if edge["tgt"]["index"] is None:
				del edge["tgt"]["index"]

			self.send('changeedge', edge, context)

		@graph.on('addInitial')
		def subscribeGraphHandler_addInitial (data):
			iip = copy.deepcopy(data["edge"])
			iip["graph"] = id

			if iip["tgt"]["index"] is None:
				del iip["tgt"]["index"]

			self.send('addinitial', iip, context)

		@graph.on('removeInitial')
		def subscribeGraphHandler_removeInitial (data):
			iip = copy.deepcopy(data["edge"])
			iip["graph"] = id

			if iip["tgt"]["index"] is None:
				del iip["tgt"]["index"]

			self.send('removeinitial', iip, context)

		@graph.on('addInport')
		@graph.on('addOutport')
		@graph.on('removeInport')
		@graph.on('removeOutport')
		def subscribeGraphHandler_modifyPorts (data):
			# FIXME: the design of the API, and lack of a proper Node object,
			# makes this much hard than it should be
			import sys
			from ... import components

			comps = components.components()
			comps = dict((c.componentName, c.details) for c in comps.result)
			print("****", list(comps.keys()), file=sys.stdout)


			def getPorts(portType):
				results = []
				src = graph.inports if portType == 'inPorts' else graph.outports
				for public, port in src.items():
					node = graph.nodes.get(port['process'])
					comp = comps[node['component']]
					for p in comp[portType]:
						if p['id'] == port['port']:
							newPort = copy.deepcopy(p)
							newPort.pop('description', None)
							results.append(newPort)
							break
					else:
						raise Error('could not find port {}'.format(port['port']))
				return results

			inPorts = getPorts('inPorts')
			outPorts = getPorts('outPorts')

			payload = {
				"graph": id,
				"inPorts": inPorts,
				"outPorts": outPorts,
			}

			self.send('ports', payload, context)

	def addNode (self, graph, payload, context):
		graph.nodes.add(**kwargs(payload, ["id", "component"], ["metadata"]))

	def removeNode (self, graph, payload, context):
		graph.nodes.remove(**kwargs(payload, ["id"]))

	def renameNode (self, graph, payload, context):
		graph.nodes.rename(*args(payload, ["from", "to"]))

	def changeNode (self, graph, payload, context):
		graph.nodes.setMetadata(**kwargs(payload, ["id", "metadata"]))

	def addEdge (self, graph, payload, context):
		graph.edges.addIndex(**kwargs(
			payload,
			["src.node", "src.port", "tgt.node", "tgt.port"],
			["src.index", "tgt.index", "metadata"]
		))

	def removeEdge (self, graph, payload, context):
		graph.edges.remove(**kwargs(payload, ["src.node"], ["src.port", "tgt.node", "tgt.port"]))

	def changeEdge (self, graph, payload, context):
		graph.edges.setMetadata(**kwargs(
			payload,
			["src.node", "src.port", "tgt.node", "tgt.port", "metadata"]
		))

	def addInitial (self, graph, payload, context):
		graph.initials.addIndex(**kwargs(payload, ["src.data", "tgt.node", "tgt.port"], ["tgt.index", "metadata"]))

	def removeInitial (self, graph, payload, context):
		graph.initials.remove(**kwargs(payload, ["tgt.node"], ["tgt.port"]))

	def addInport (self, graph, payload, context):
		# FIXME: adding a port to a graph is different than adding one to a component
		# (because a port on a graph is just a public label for a port on a component
		# within the graph) yet this code attempts to treat it the same.
		graph.inports.add(**kwargs(payload, ["public", "node", "port"], ["metadata"]))

	def removeInport (self, graph, payload, context):
		# FIXME: see addInport
		graph.inports.remove(**kwargs(payload, ["public"], errorMsg='Missing exported inport name'))

	def renameInport (self, graph, payload, context):
		# FIXME: see addInport
		graph.inports.rename(**kwargs(payload, ["from", "to"]))

	def addOutport (self, graph, payload, context):
		# FIXME: see addInport
		graph.outports.add(**kwargs(payload, ["public", "node", "port"], ["metadata"]))

	def removeOutport (self, graph, payload, context):
		# FIXME: see addInport
		graph.outports.remove(**kwargs(payload, ["public"], errorMsg='Missing exported outport name'))

	def renameOutport (self, graph, payload, context):
		# FIXME: see addInport
		graph.outports.rename(**kwargs(payload, ["from", "to"]))

def _iterargs (payload, requiredKeys, optionalKeys = (), errorMsg = None):
	requiredKeys = list(requiredKeys)
	optionalKeys = list(optionalKeys)

	def argName(key):
		parts = key.split(".")
		parts[1:] = [x.capitalize() for x in parts[1:]]
		return ''.join(parts)

	for key in requiredKeys + optionalKeys:
		value = payload
		try:
			for newKey in key.split("."):
				value = value[newKey]
		except KeyError:
			if key in requiredKeys:
				raise Error(errorMsg or ("Required parameter '%s' not supplied" % key))
			else:
				value = None
		yield argName(key), value

def args (payload, requiredKeys, optionalKeys = (), errorMsg = None):
	new = []
	for _, value in _iterargs(payload, requiredKeys, optionalKeys, errorMsg):
		new.append(value)
	return new

def kwargs (payload, requiredKeys, optionalKeys = (), errorMsg = None):
	new = {}
	for newKey, value in _iterargs(payload, requiredKeys, optionalKeys, errorMsg):
		new[newKey] = value
	return new

class Error (Exception):
	pass
