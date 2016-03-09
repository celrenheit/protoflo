
from .util import EventEmitter

class InternalSocket (EventEmitter):
	src = None
	tgt = None

	def __init__ (self):
		self.connected = False
		self.groups = []

	@property
	def id (self):
		_from = lambda f: "{0:s}() {1:s}".format(f["process"].id, f["port"].upper())
		_to = lambda f: "{1:s} {0:s}()".format(f["process"].id, f["port"].upper())

		try:
			t = _to(self.tgt)
			try:
				f = _from(self.src)
				return f + " -> " + t
			except (TypeError, AttributeError):
				return "DATA -> " + t
		except (TypeError, AttributeError):
			try:
				f = _from(self.src)
				return f + " -> ANON"
			except AttributeError:
				return "UNDEFINED"

	def connect (self):
		if self.connected:
			return

		self.connected = True
		self.emit("connect", socket = self)

	def disconnect (self):
		if not self.connected:
			return

		self.connected = False
		self.emit("disconnect", socket = self)

	def send (self, data):
		if not self.connected:
			self.connect()

		self.emit('data', data = data)

	def beginGroup (self, group):
		self.groups.append(group)
		self.emit("begingroup", group = group)

	def endGroup (self):
		self.emit("endgroup", group = self.groups.pop())

