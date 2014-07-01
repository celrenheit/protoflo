from zope.interface import implements

from twisted.internet import defer, threads

from util import EventEmitter
from port import InPorts, OutPorts, InPort, OutPort
from components import IComponent

class Component (EventEmitter):
	implements(IComponent)

	description = ""
	_icon = None
	ready = True
	subgraph = False

	@property
	def icon (self):
		return self._icon

	@icon.setter
	def icon (self, icon):
		self._icon = icon
		self.emit("icon", icon = icon)

	def __init__ (self, inPorts = None, outPorts = None, metadata = None, **options):
		if isinstance(inPorts, InPorts):
			self.inPorts = inPorts
		else:
			self.inPorts = InPorts(inPorts)

		if isinstance(outPorts, OutPorts):
			self.outPorts = outPorts
		else:
			self.outPorts = OutPorts(outPorts)

		self.metadata = metadata
		self.options = options

		self.initialize(**options)

	def error (self, e, groups = None, errorPort = 'error'):
		if groups is None:
			groups = []

		if not isinstance(e, Exception):
			e = Exception(e)

		if errorPort in self.outPorts:
			port = self.outPorts[errorPort]

			if port.attached or not port.required:
				for group in groups:
					port.beginGroup(group)

				port.send(e)

				for group in groups:
					port.endGroup(group)

				port.disconnect()
		else:
			raise e

	def initialize (**options):
		pass

	def shutdown (self):
		pass


class ComponentLoader (EventEmitter):
	processing = False
	components = None
	ready = False

	def listComponents (self):
		d = defer.Deferred()

		if self.processing:
			@self.once("ready")
			def listComponentsOnReady (data):
				d.callback(self.components)

			return d

		if self.components is not None:
			d.callback(self.components)
			return d

		self.processing = True

		def complete (cache):
			self.components = {}

			for name, collection in cache.iteritems():
				for component in collection.components:
					self.components[component.fullName] = component

			d.callback(self.components)
			
			self.processing = False
			self.ready = True
			self.emit("ready")

		from components import getCache
		threads.deferToThread(getCache).addCallback(complete)

		return d

	def load (self, name, delayed = False, metadata = None):
		if not self.ready:
			d = defer.Deferred()

			@self.once("ready")
			def load_onReady (data):
				self.load(name, delayed, metadata).addCallbacks(d.callback, d.errback)

			return d

		try:
			component = self.components[name]
		except KeyError:
			for key in self.components.iterkeys():
				if key.split('/')[1] == name:
					component = self.components[key]
					name = key
					break
			else:
				return defer.fail(Error("Component {:s} not available".format(name)))

		# TODO: deal with graphs.
		componentClass = component.load()
		componentObject = componentClass(metadata = metadata)
		self.setIcon(name, componentObject)

		return defer.succeed(componentObject)

	def setIcon (self, name, instance):
		if instance.icon is not None:
			return

		if instance.subgraph:
			instance.icon = "sitemap"

		instance.icon = "square"


class Error (Exception):
	pass