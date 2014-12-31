from twisted.internet import defer

from util import EventEmitter

import copy
import os


class Graph (EventEmitter):
	
	def __init__ (self, name = ""):
		self.name = name
		self.properties = {}
		self.nodes = Nodes(self)
		self.edges = Edges(self)
		self.initials = Initials(self)
		self.exports = []
		self.inports = Exports(self)
		self.outports = Exports(self)
		self.groups = Groups(self)
		self.transaction = {
			"id": None,
			"depth": 0
		}

		def _event (type):
			def event (eventName, data):
				self.emit(eventName + type, **data)

			return event

		self.nodes.on("all", _event("Node"))
		self.edges.on("all", _event("Edge"))
		self.initials.on("all", _event("Initial"))
		self.inports.on("all", _event("Inport"))
		self.outports.on("all", _event("Outport"))

	def startTransaction (self, id, metadata = None):
		if self.transaction["id"] is not None:
			raise Error("Nested transactions not supported")

		self.transaction["id"] = id
		self.transaction["depth"] = 1
		self.emit('startTransaction', transaction = id, metadata = metadata)

	def endTransaction (self, id, metadata = None):
		if self.transaction["id"] is None:
			raise Error("Attempted to end non-existing transaction")

		self.transaction["id"] = None
		self.transaction["depth"] = 0
		self.emit('endTransaction', transaction = id, metadata = metadata)

	def checkTransactionStart (self):
		if self.transaction["id"] is None:
			self.startTransaction("implicit")
		elif self.transaction["id"] == "implicit":
			self.transaction["depth"] += 1

	def checkTransactionEnd (self):
		if self.transaction["id"] == "implicit":
			self.transaction["depth"] -= 1
		if self.transaction["depth"] == 0:
			self.endTransaction("implicit")


	def setProperties (self, properties):
		"""Change properties of the graph."""

		self.checkTransactionStart()
		before = copy.deepcopy(self.properties)

		for item, val in properties.iteritems():
			self.properties[item] = val

		self.emit('changeProperties', properties = self.properties, old = before)
		self.checkTransactionEnd()
		

	def addExport (self, publicPort, nodeKey, portKey, metadata = None):
		# Check that node exists
		if self.getNode(nodeKey) is None:
			return

		self.checkTransactionStart()

		exported = {
			"public": publicPort,
			"process": nodeKey,
			"port": portKey,
			"metadata": metadata
		}
		self.exports.append(exported)
		self.emit('addExport', exported = exported)

		self.checkTransactionEnd()

	def removeExport (self, publicPort):
		publicPort = publicPort.toLowerCase()

		try:
			found = next(e for e in self.exports if e["public"] == publicPort)
		except StopIteration:
			return

		self.checkTransactionStart()
		self.exports.remove(found)
		self.emit('removeExport', found = found)
		self.checkTransactionEnd()

	def toJSON (self):
		json = {
			"properties": {},
			"inports": {},
			"outports": {},
			"groups": [],
			"processes": {},
			"connections": []
		}

		if self.name is not "":
			json["properties"]["name"] = self.name

		for property, value in self.properties.iteritems():
			json["properties"][property] = value

		for key, port in self.inports.iteritems():
			json["inports"][key] = port
		for key, port in self.outports.iteritems():
			json["outports"][key] = port

		# Legacy exported ports
		if len(self.exports):
			json["exports"] = copy.deepcopy(self.exports)

		for group in self.groups:
			groupData = {
				"name": group["name"],
				"nodes": group["nodes"]
			}

			if len(group["metadata"]):
				groupData["metadata"] = copy.deepcopy(group["metadata"])

			json.groups.append(groupData)

		for node in self.nodes:
			json["processes"][node["id"]] = {
				"component": node["component"]
			}

			if len(node["metadata"]):
				json["processes"][node["id"]]["metadata"] = node["metadata"]

		for edge in self.edges:
			connection = {
				"src": {
					"process": edge["src"]["node"],
					"port":    edge["src"]["port"],
					"index":   edge["src"]["index"]
				},
				"tgt": {
					"process": edge["tgt"]["node"],
					"port":    edge["tgt"]["port"],
					"index":   edge["tgt"]["index"]
				}
			}

			if len(edge["metadata"]):
				connection["metadata"] = edge["metadata"]

			json["connections"].append(connection)

		for initial in self.initials:
			json["connections"].append({
				"data": initial["src"]["data"],
				"tgt": {
					"process": initial["tgt"]["node"],
					"port":    initial["tgt"]["port"],
					"index":   initial["tgt"]["index"]
				}
			})

		return json

	def save (self, file, success):
		from json import dumps
		json = dumps(self.toJSON(), indent = 4)
		with open("{:s}.json", 'r') as f:
			f.write(json)

		return defer.succeed(None)



class Exports (EventEmitter):
	def __init__ (self, graph):
		self.graph = graph
		self.ports = {}

	def __getitem__ (self, publicPort):
		return self.ports[publicPort]

	def __getattr__ (self, publicPort):
		try:
			return self.ports[publicPort]
		except KeyError:
			raise AttributeError(publicPort)

	def __iter__ (self):
		return self.ports.itervalues()

	def iteritems (self):
		return self.ports.iteritems()

	def __len__ (self):
		return len(self.ports)

	def add (self, publicPort, nodeKey, portKey, metadata = None):
		# Check that node exists
		if self.graph.getNode(nodeKey) is not None:
			return

		self.graph.checkTransactionStart()
		self.ports[publicPort] = {
			"process": nodeKey,
			"port": portKey,
			"metadata": metadata
		}
		self.emit('add', key = publicPort, port = self.ports[publicPort])
		self.graph.checkTransactionEnd()

	def remove (self, publicPort):
		publicPort = publicPort.toLowerCase()

		if publicPort not in self.ports:
			return

		self.graph.checkTransactionStart()
		port = self.ports[publicPort]

		self.setMetadata(publicPort, {})
		del self.ports[publicPort]

		self.emit('remove', key = publicPort, port = port)
		self.graph.checkTransactionEnd()

	def rename (self, oldPort, newPort):
		if oldPort not in self.ports:
			return

		self.graph.checkTransactionStart()

		self.ports[newPort] = self.ports[oldPort]
		del self.ports[oldPort]

		self.emit('rename', old = oldPort, new = newPort)
		self.graph.checkTransactionEnd()

	def setMetadata (self, publicPort, metadata):
		if publicPort not in self.ports:
			return

		self.graph.checkTransactionStart()
		before = copy.deepcopy(self.ports[publicPort]["metadata"])

		if self.ports[publicPort]["metadata"] is None:
			self.ports[publicPort]["metadata"] = {}

		for item, val in metadata.iteritems():
			if val is not None:
				self.ports[publicPort]["metadata"][item] = val
			else:
				del self.ports[publicPort]["metadata"][item]

		self.emit('change', key = publicPort, port = self.ports[publicPort], old = before)
		self.graph.checkTransactionEnd()

	def removeFromNode (self, nodeKey):
		for key in [key for key, port in self.ports.iteritems() if port["process"] == nodeKey]:
			self.remove(key)

	def renameNode (self, oldNodeKey, newNodeKey):
		for port in self.ports.itervalues():
			if port["process"] == oldNodeKey:
				port["process"] = newNodeKey


class Groups (EventEmitter):
	"""For grouping nodes in a graph"""

	def __init__ (self, graph):
		self.graph = graph
		self.groups = {}

	def __iter__ (self):
		return self.groups.itervalues()

	def __len__ (self):
		return len(self.groups)

	# ## Grouping nodes in a graph
	#
	def add (self, groupName, nodes, metadata = None):
		if groupName in self.groups:
			raise KeyError("Group with name {:s} already exists".format(groupName))

		self.graph.checkTransactionStart()

		g = {
			"name": groupName,
			"nodes": nodes,
			"metadata": metadata
		}
		self.groups[groupName] = g
		self.emit('add', group = g)

		self.graph.checkTransactionEnd()

	def rename (self, oldName, newName):
		if newName in self.groups:
			raise KeyError("Group with name {:s} already exists".format(newName))

		self.graph.checkTransactionStart()

		if oldName in self.groups:
			self.groups[oldName]["name"] = newName
			self.groups[newName] = self.groups[oldName]
			del self.groups[oldName]

			self.emit('rename', old = oldName, new = newName)

		self.graph.checkTransactionEnd()

	def remove (self, groupName):
		self.graph.checkTransactionStart()

		if groupName in self.groups:
			group = self.groups[groupName]
			self.setMetadata(groupName, {})
			del self.groups[groupName]
			self.emit('remove', group = group)

		self.graph.checkTransactionEnd()

	def setMetadata (self, groupName, metadata):
		self.graph.checkTransactionStart()

		if groupName in self.groups:
			group = self.groups[groupName]
			before = copy.deepcopy(group["metadata"])

			for item, val in metadata.iteritems():
				if val is not None:
					group["metadata"][item] = val
				else:
					del group["metadata"][item]

			self.emit('change', group = group, old = before)

		self.graph.checkTransactionEnd()

	def removeNode (self, nodeKey):
		for group in self.groups.iteritems():
			try:
				group.nodes.remove(nodeKey)
			except ValueError:
				pass

	def renameNode (self, oldNodeKey, newNodeKey):
		for group in self.groups.iteritems():
			try:
				idx = group.nodes.index(oldNodeKey)
				group.nodes[idx] = newNodeKey
			except ValueError:
				pass



class Nodes (EventEmitter):

	def __init__ (self, graph):
		self.graph = graph
		self.nodes = []

	def __iter__ (self):
		return iter(self.nodes)

	def __len__ (self):
		return len(self.nodes)

	def add (self, id, component, metadata = None):
		"""Add a node to the graph
		
		Nodes are identified by an ID unique to the graph. Additionally,
		a node may contain information on what NoFlo component it is and
		possible display coordinates.
		
		For example:
			myGraph.nodes.add('Read, 'ReadFile', {
				"x": 91
				"y": 154
			}
		
		Addition of a node will emit the 'addNode' event on the graph."""
		
		self.graph.checkTransactionStart()

		node = {
			"id": id,
			"component": component,
			"metadata": metadata or {}
		}
		self.nodes.append(node)
		self.emit('add', node = node)

		self.graph.checkTransactionEnd()

		return node

	def remove (self, id):
		"""Remove a node from the graph
		
		Existing nodes can be removed from a graph by their ID. This
		will remove the node and also remove all edges connected to it.
		
			myGraph.nodes.remove('Read')
		
		Once the node has been removed, the 'removeNode' event will be
		emitted."""

		node = self.get(id)

		if node is None:
			return

		self.graph.checkTransactionStart()

		self.graph.edges.remove(node = id)
		self.graph.initials.remove(node = id)

		toRemove = []
		for exported in self.graph.exports:
			if id.toLowerCase() == exported.process:
				toRemove.append(exported)
		for exported in toRemove:
			self.graph.exports.remove(exported.public)

		self.graph.inports.removeFromNode(id)
		self.graph.outports.removeFromNode(id)
		self.graph.groups.removeNode(id)

		self.setMetadata(id, {})

		try:
			self.nodes.remove(node)
		except ValueError:
			pass #???

		self.emit('remove', node = node)

		self.graph.checkTransactionEnd()

	def get (self, id):
		"""Get a node
		
		Node objects can be retrieved from the graph by their ID:
		
			myNode = myGraph.getNode 'Read'
		"""

		return next((node for node in self.nodes if node["id"] == id), None)

	__getattr__ = get
	__getitem__ = get

	def rename (self, oldId, newId):
		"""Rename a node"""

		node = self.get(oldId)

		if node is None:
			return

		self.graph.checkTransactionStart()

		node["id"] = newId

		self.graph.edges.renameNode(oldId, newId)
		self.graph.initials.renameNode(oldId, newId)

		for exported in self.graph.exports:
			if exported.process is oldId:
				exported.process = newId

		self.graph.inports.renameNode(oldId, newId)
		self.graph.outports.renameNode(oldId, newId)
		self.graph.groups.renameNode(oldId, newId)

		self.emit('rename', old = oldId, new = newId)
		self.graph.checkTransactionEnd()

	def setMetadata (self, id, metadata):
		"""Set or change a node's metadata"""

		node = self.get(id)

		if node is None:
			return

		self.graph.checkTransactionStart()

		before = copy.deepcopy(node["metadata"])

		for item, val in metadata.iteritems():
			if val is not None:
				node["metadata"][item] = val
			else:
				del node["metadata"][item]

		self.emit('change', node = node, old = before)
		self.graph.checkTransactionEnd()


class Edges (EventEmitter):

	def __init__ (self, graph):
		self.graph = graph
		self.edges = []

	def __iter__ (self):
		return iter(self.edges)

	def __len__ (self):
		return len(self.edges)

	def add (self, outNode, outPort, inNode, inPort, metadata = None):
		"""Connect nodes
		
		Nodes can be connected by adding edges between a node's outport
		and another node's inport:
		
			myGraph.edges.add('Read', 'out', 'Display', 'in')
			myGraph.edges.addIndex('Read', 'out', None, 'Display', 'in', 2)
		
		Adding an edge will emit the 'addEdge' event."""

		# Don't add a duplicate edge
		for edge in self.edges:
			if edge["src"]["node"] is outNode and edge["src"]["port"] is outPort and edge["tgt"]["node"] is inNode and edge["tgt"]["port"] is inPort:
				return

		return self.addIndex(outNode, outPort, None, inNode, inPort, None, metadata)

	# Adding an edge will emit the `addEdge` event.
	def addIndex (self, outNode, outPort, outIndex, inNode, inPort, inIndex, metadata = None):
		if self.graph.nodes.get(outNode) is None or self.graph.nodes.get(inNode) is None:
			return

		self.graph.checkTransactionStart()

		edge = {
			"src": {
				"node": outNode,
				"port": outPort,
				"index": outIndex
			},
			"tgt": {
				"node": inNode,
				"port": inPort,
				"index": inIndex
			},
			"metadata": metadata or {}
		}
		self.edges.append(edge)
		self.emit('add', edge = edge)

		self.graph.checkTransactionEnd()

		return edge

	def remove (self, node, port = None, node2 = None, port2 = None):
		"""Disconnect nodes
		
		Connections between nodes can be removed by providing the
		nodes and ports to disconnect.
		
			myGraph.edges.remove('Display', 'out', 'Foo', 'in')
		
		Removing a connection will emit the `removeEdge` event."""

		self.graph.checkTransactionStart()

		toRemove = []
		toKeep = []
		if port is not None and node2 is not None and port2 is not None:
			for edge in self.edges:
				if edge["src"]["node"] == node \
				and edge["src"]["port"] == port \
				and edge["tgt"]["node"] == node2 \
				and edge["tgt"]["port"] == port2:
					toRemove.append(edge)
				else:
					toKeep.append(edge)
		elif port is not None:
			for edge in self.edges:
				if (edge["src"]["node"] == node and edge["src"]["port"] == port) \
				or (edge["tgt"]["node"] == node and edge["tgt"]["port"] == port):
					toRemove.append(edge)
				else:
					toKeep.append(edge)
		else:
			for edge in self.edges:
				if edge["src"]["node"] == node or edge["tgt"]["node"] == node:
					toRemove.append(edge)
				else:
					toKeep.append(edge)

		self.edges = toKeep

		for edge in toRemove:
			self.setMetadata(edge["src"]["node"], edge["src"]["port"], edge["tgt"]["node"], edge["tgt"]["port"], {})
			self.emit('remove', edge = edge)

		self.graph.checkTransactionEnd()

	def get (self, node, port, node2, port2):
		"""Get an edge
		
		Edge objects can be retrieved from the graph by the node and port IDs:
		
			myEdge = myGraph.edges.get('Read', 'out', 'Write', 'in')
		"""

		for edge in self.edges:
			if edge["src"]["node"] is node and edge["src"]["port"] is port:
				if edge["tgt"]["node"] is node2 and edge["tgt"]["port"] is port2:
					return edge

		return None

	def setMetadata (self, node, port, node2, port2, metadata):
		"""Change an edge's metadata"""

		edge = self.get(node, port, node2, port2)

		if edge is None:
			return

		self.graph.checkTransactionStart()
		before = copy.deepcopy(edge["metadata"])

		for item, val in metadata.iteritems():
			if val is not None:
				edge["metadata"][item] = val
			else:
				del edge["metadata"][item]

		self.emit('change', edge = edge, old = before)
		self.graph.checkTransactionEnd()

	def renameNode (self, oldNodeKey, newNodeKey):
		for edge in self.edges:
			if edge["src"]["node"] == oldNodeKey:
				edge["src"]["node"] = newNodeKey
			elif edge["tgt"]["node"] == oldNodeKey:
				edge["tgt"]["node"] = newNodeKey


class Initials (EventEmitter):

	def __init__ (self, graph):
		self.graph = graph
		self.initials = []

	def __iter__ (self):
		return iter(self.initials)

	def __len__ (self):
		return len(self.initials)

	def add (self, data, node, port, metadata = None):
		"""Adding Initial Information Packets
		
		Initial Information Packets (IIPs) can be used for sending data
		to specified node inports without a sending node instance.
		
		IIPs are especially useful for sending configuration information
		to components at NoFlo network start-up time. This could include
		filenames to read, or network ports to listen to.
		
			myGraph.initials.add('somefile.txt', 'Read', 'source')
			myGraph.initials.addIndex('somefile.txt', 'Read', 'source', 2)
		
		Adding an IIP will emit a 'addInitial' event."""
		
		return self.addIndex(data, node, port, None, metadata)
		
	def addIndex (self, data, node, port, index, metadata = None):
		if self.graph.nodes.get(node) is None:
			return

		self.graph.checkTransactionStart()
		initial = {
			"src": {
				"data": data
			},
			"tgt": {
				"node": node,
				"port": port,
				"index": None
			},
			"metadata": metadata or {}
		}
		self.initials.append(initial)
		self.emit('add', edge = initial)

		self.graph.checkTransactionEnd()
		return initial

	def remove (self, node, port = None):
		"""Remove Initial Information Packets
		
		IIPs can be removed by calling the `removeInitial` method.
		
			myGraph.initials.remove('Read', 'source')
		
		Remove an IIP will emit a 'removeInitial' event."""

		self.graph.checkTransactionStart()

		toRemove = []
		toKeep = []
		if port is None:
			for edge in self.initials:
				if edge["tgt"]["node"] == node:
					toRemove.append(edge)
				else:
					toKeep.append(edge)
		else:
			for edge in self.initials:
				if edge["tgt"]["node"] == node and edge["tgt"]["port"] == port:
					toRemove.append(edge)
				else:
					toKeep.append(edge)

		self.initials = toKeep

		for edge in toRemove:
			self.emit('remove', edge = edge)

		self.graph.checkTransactionEnd()

	def renameNode (self, oldNodeKey, newNodeKey):
		for edge in self.initials:
			if edge["tgt"]["node"] == oldNodeKey:
				edge["tgt"]["node"] = newNodeKey


def loadJSON (definition, metadata = None):
	"""Load a graph from a JSON-style dict

	@type definition: C{dict}
	@param definition: Graph definition.

	@type metadata: C{dict} or C{NoneType}
	@param metadata: metadata to pass to startTransaction.
	"""

	if "properties" not in definition:
		definition['properties'] = {}

	if "processes" not in definition:
		definition['processes'] = {}

	if "connections" not in definition:
		definition['connections'] = []

	try:
		graph = Graph(definition['properties']['name'])
	except KeyError:
		graph = Graph()

	graph.startTransaction('loadJSON', metadata)

	# Set Graph Properties
	properties = {}
	for property, value in definition['properties'].iteritems():
		if property is not 'name':
			properties[property] = value

	graph.setProperties(properties)

	# Add Nodes
	for id, process in definition['processes'].iteritems():
		graph.nodes.add(
			id,
			process['component'],
			process['metadata'] if "metadata" in process else {}
		)

	# Add Connections
	for conn in definition['connections']:
		metadata = conn['metadata'] if "metadata" in conn else {}

		if "data" in conn:
			if "index" in conn['tgt'] and conn['tgt']['index'] is not None:
				index = int(conn['tgt']['index'])
			else:
				index = None

			graph.initials.addIndex(
				conn['data'],
				conn['tgt']['process'],
				conn['tgt']['port'].lower(),
				index,
				metadata
			)

			continue

		if "index" in conn['tgt'] and conn['tgt']['index'] is not None:
			tgtIndex = int(conn['tgt']['index'])
		else:
			tgtIndex = None

		if "index" in conn['src'] and conn['src']['index'] is not None:
			srcIndex = int(conn['tgt']['index'])
		else:
			srcIndex = None

		graph.edges.addIndex(
			conn['src']['process'],
			conn['src']['port'].lower(),
			srcIndex,
			conn['tgt']['process'],
			conn['tgt']['port'].lower(),
			tgtIndex,
			metadata
		)

	# Add exports
	if "exports" in definition:
		for exported in definition['exports']:
			if "private" in exported:
				# Translate legacy ports to new
				split = exported['private'].split('.')

				if split.length != 2:
					continue

				processId, portId = split

				# Get properly cased process id
				for id in definition['processes']:
					if id.lower() == processId.lower():
						processId = id
			else:
				processId = exported['process']
				portId = exported['port']

			metadata = exported['metadata'] if "metadata" in exported else {}

			graph.addExport(exported['public'], processId, portId, metadata)

	if "inports" in definition:
		for pub, priv in definition['inports'].iteritems():
			metadata = priv['metadata'] if "metadata" in priv else {}
			graph.addInport(pub, priv['process'], priv['port'], metadata)

	if "outports" in definition:
		for pub, priv in definition['outports'].iteritems():
			metadata = priv['metadata'] if "metadata" in priv else {}
			graph.addOutport(pub, priv['process'], priv['port'], metadata)

	if "groups" in definition:
		for group in definition['groups']:
			metadata = group['metadata'] if "metadata" in group else {}
			graph.addGroup(group['name'], group['nodes'], metadata)

	graph.endTransaction('loadJSON')

	return graph


def loadFile (filename, metadata = None):
	"""Load a graph from a file

	Currently accepts .json and .fbp files.
	N.B. Blocking function.

	@type fileName: C{str}
	@param fileName: Full file name of the file to load

	@type metadata: C{dict} or C{NoneType}
	@param metadata: metadata to pass to loadJSON
	"""

	ext = os.path.splitext(os.path.basename(filename))[1]
	if ext == ".fbp":
		from json import loads
		from subprocess import check_output
		return loadJSON(
			loads(check_output(["fbp", filename])),
			metadata
		)
	elif ext == ".json":
		from json import load
		with open(filename) as fp:
			return loadJSON(load(fp), metadata)
	else:
		raise Error("Unsupported file type for {:s}".format(fileName))
