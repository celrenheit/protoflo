from twisted.internet import reactor, defer

import functools
from collections import OrderedDict

from util import EventEmitter

validTypes = [
  'all',
  'string',
  'number',
  'int',
  'object',
  'array',
  'boolean',
  'color',
  'date',
  'bang',
  'function',
  'buffer'
]

class Port (EventEmitter):
	name = None
	node = None
	nodeInstance = None

	def __init__ (self, datatype = "all", required = False, **options):
		if datatype == "integer":
			datatype = "int"
		elif datatype == "str":
			datatype = "string"

		if datatype not in validTypes:
			raise Error("Invalid port datatype {:s} specified".format(datatype))

		if "type" in options and "/" not in options["type"]:
			raise Error("Invalid port type {:s} specified. Should be URL or MIME type.".format(options["type"]))

		options["datatype"] = datatype
		options["required"] = required

		self.options = options
		self.sockets = {}
		self.node = None
		self.name = None

	@property
	def id (self):
		if self.node is not None and self.name is not None:
			return " ".join([self.node, self.name.upper()])

		return "Port"

	@property
	def datatype (self):
		return self.options["datatype"]

	@property
	def description (self):
		try:
			return self.options["description"]
		except KeyError:
			return None

	@property
	def addressable (self):
		return "addressable" in self.options and self.options["addressable"]

	@property
	def buffered (self):
		return "buffered" in self.options and self.options["buffered"]
	
	@property
	def required (self):
		return self.options["required"]
	
	def attach (self, socket, index = None):
		if not self.addressable or index is None:
			index = len(self.sockets)

		# What is the action if socket is already in sockets?

		self.sockets[index] = socket

		self.attachSocket(socket, index)

		if not self.addressable:
			index = None

		self.emit("attach", socket = socket, index = index)

	def attachSocket (self, socket, index):
		pass

	def detach (self, socket):
		try:
			index = next(k for k, v in self.sockets.iteritems() if v == socket)
		except StopIteration:
			return

		del self.sockets[index]

		if not self.addressable:
			index = None

		self.emit("detach", socket = socket, index = index)
		
	@property
	def attached (self, index = None):
		if self.addressable and index is not None:
			return index in self.sockets
		else:
			return len(self.sockets) > 0

	def listAttached (self):
		return list(self.sockets.itervalues())

	@property
	def connected (self, index = None):
		if self.addressable:
			if index is None:
				raise IndexError("{:s}: Socket ID required".format(self.id))

			try:
				return self.sockets[index].connected
			except KeyError:
				raise IndexError("{:s}: Socket {:d} not available".format(self.id, index))

		return any(s.connected for s in self.sockets.itervalues())


class InPort (Port):
	def __init__ (self, process = None, **options):
		if "buffered" not in options:
			options["buffered"] = False

		if process is None or callable(process):
			self.process = process
		else:
			raise Error("Process must be a function")

		Port.__init__(self, **options)

		reactor.callLater(0, self.sendDefault)

		if self.buffered:
			self.buffer = deque()

	def attachSocket (self, socket, index = None):
		handle = self.handleSocketEvent

		for e in ("connect", "disconnect"):
			socket.on(e, functools.partial(handle, e, socket = socket, index = index))

		for e in ("begingroup", "data", "endgroup"):
			socket.on(e, functools.partial(handle, e, index = index))

	def handleSocketEvent (self, event, data, index = None, socket = None):
		if self.buffered:
			self.buffer.append({
				"event": event,
				"payload": data,
				"index": index
			})

			if self.addressable:
				if self.process is not None:
					self.process(event, index)

				self.emit(event, index = index)
			else:
				if self.process is not None:
					self.process(event)

				self.emit(event)

			return

		# Call the processing function	
		if self.process is not None:
			if self.addressable:
				self.process(event, index = index, nodeInstance = self.nodeInstance, data = data)
			else:
				self.process(event, nodeInstance = self.nodeInstance, data = data)

		# Emit the event
		if self.addressable:
			self.emit(event, index = index, nodeInstance = self.nodeInstance, **data)
		else:
			self.emit(event, nodeInstance = self.nodeInstance, **data)

	def sendDefault (self):
		if "default" not in self.options:
			return

		for index, socket in self.sockets.iteritems():
			self.handleSocketEvent("data", self.options["default"], index)

	def validateData (self, data):
		return "values" not in self.options or data in self.options["values"]

	def receive (self):
		""" Returns the next packet in the buffer. """
		try:
			return self.buffer.popleft()
		except IndexError:
			return None
		except AttributeError:
			raise Error('Receive is only possible on buffered ports')

	@property
	def contains (self):
		""" The number of data packets in a buffered inport. """
		try:
			return len(p for p in self.buffer if p["event"] == "data")
		except AttributeError:
			raise Error('Contains query is only possible on buffered ports')


class OutPort (Port):
	def __init__ (self, *a, **k):
		Port.__init__(self, *a, **k)
		self.cache = {}

	def attach (self, socket, index = None):
		Port.attach(self, socket, index)

		if self.caching and index in self.cache:
			self.send(self.cache[index], index)

	def connect (self, socketId = None):
		sockets = self.getSockets(socketId)
		self.checkRequired(sockets)

		for socket in sockets:
			socket.connect()

	def beginGroup (self, group, socketId = None):
		sockets = self.getSockets(socketId)
		self.checkRequired(sockets)

		for socket in sockets:
			if socket.connected:
				socket.beginGroup(group)
			else:
				def beginGroup ():
					socket.off(beginGroup)
					socket.beginGroup(group)

				socket.on('connect', beginGroup)
				socket.connect()

	def send (self, data, socketId = None):
		sockets = self.getSockets(socketId)
		self.checkRequired(sockets)

		for socket in sockets:
			if socket.connected:
				socket.send(data)
			else:
				def send (_):
					socket.send(data)

				socket.once('connect', send)
				socket.connect()

	def endGroup (self, socketId = None):
		sockets = self.getSockets(socketId)
		self.checkRequired(sockets)

		for socket in sockets:
			socket.endGroup()

	def disconnect (self, socketId = None):
		sockets = self.getSockets(socketId)
		self.checkRequired(sockets)

		for socket in sockets:
			socket.disconnect()

	def checkRequired (self, sockets):
		if not len(sockets) and self.required:
			raise Exception("{:s}: No connections available".format(self.id))

	def getSockets (self, socketId = None):
		# Addressable sockets affect only one connection at time
		if self.addressable:
			if socketId is None:
				raise Exception("{:s}: Socket ID required".format(self.id))
			elif socketId not in self.sockets:
				return []
			else:
				return [self.sockets[socketId]]

		# Regular sockets affect all outbound connections
		else:
			return list(self.sockets.itervalues())

	@property
	def caching (self):
		return "caching" in self.options and self.options["caching"]


# FIXME: consider making this multiply inherit OrderedDict and EventEmitter
class Ports (EventEmitter):
	model = None

	def __init__ (self, ports = None):
		self.ports = OrderedDict()

		if ports is not None:
			for name, options in ports:
				self.add(name, options)

	def __iter__ (self):
		return self.ports.itervalues()

	def iteritems (self):
		return self.ports.iteritems()

	def __getattr__ (self, name):
		try:
			return self.ports[name]
		except KeyError:
			raise KeyError("Port {:s} not available".format(name))

	__getitem__ = __getattr__

	def __contains__ (self, name):
		return name in self.ports

	def __setitem__(self, name, options):
		self.add(name, options)

	def add (self, name, options, process = None):
		if name in ("add", "remove"):
			raise KeyError("{:s} is a restricted port name".format(name))

		if name in self.ports:
			self.remove(name)

		if isinstance(options, Port):
			self.ports[name] = options
		else:
			self.ports[name] = self.model(process = process, **options)

		self.emit('add', port = name)
		
	def remove (self, name):
		if name not in self.ports:
			raise KeyError("Port {:s} not defined".format(name))

		del self.ports[name]
		
		self.emit("remove", port = name)
		
		
class InPorts (Ports):
	model = InPort
	
	def on (self, name, event, callback):
		self[name].on(event, callback)

	def once (self, name, event, callback):
		self[name].once(event, callback)

		
class OutPorts (Ports):
	model = OutPort
	
	def connect (self, name, socket):
		self[name].connect(socket)
		
	def beginGroup (self, name, group, socket):
		self[name].beginGroup(group, socket)
	
	def connect (self, name, data, socket):
		self[name].connect(data, socket)
		
	def endGroup (self, name, socket):
		self[name].endGroup(socket)
	
	def disconnect (self, name, socket):
		self[name].disconnect(socket)


class Error (Exception):
	pass