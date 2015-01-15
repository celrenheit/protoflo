from zope.interface import Interface, Attribute

from twisted.internet import defer
from twisted.python import log, failure, modules
from twisted.python.reflect import namedModule, namedAny
from twisted.python.filepath import FilePath
from twisted.plugin import pickle

import os, sys

# Plugin modules "protoflo_*" must have an __init__.py with a __components__ dict attribute.
# This lists the name: class / genreator function / relative path to '.fbp' or '.json' file.
# May also have name and description attributes.

class IComponent (Interface):
	description = Attribute("""
		@type description: str
		@ivar description: A description of the component.
	""")

	icon = Attribute("""
		@type icon: str
		@ivar icon: The FontAwesome icon associated with this component.
	""")

	ready = Attribute("""
		@type ready: bool
		@ivar ready: Whether this component is ready. If ready = False, the
		component should emit a "ready" event when ready becomes True.
	""")

	subgraph = Attribute("""
		@type subgraph: bool
		@ivar subgraph: Whether this component is a subgraph.
	""")
	
	def __init__ (**options):
		"""
		Initialises the component with a set of options.

		Options may include:
			inPorts: dict or InPorts
			outPorts: dict or OutPorts
		"""

	def error (e, groups, errorPort):
		"""
		Sends an error on an error port. If the error port does not exist,
		the error is raised instead.

		@type e: Exception
		@param e: Error to send

		@type groups: list
		@param groups: Groups with which to wrap the error.

		@type errorPort: str
		@param errorPort: Name of port to send error on. Default "error"
		"""

	def initialize ():
		"""
		Set up the component
		"""

	def shutdown ():
		"""
		Actions to perform when the component is shut down.
		"""


class CachedComponent (object):
	def __init__ (self, dropin, fileName, objectName, componentName, details):
		self.dropin = dropin
		self.fileName = fileName
		self.objectName = objectName
		self.componentName = componentName
		self.details = details
		self.dropin.components.append(self)

	def __repr__ (self):
		return '<CachedComponent {:s} ({:s})>'.format(
			self.componentName,
			self.objectName or self.fileName
		)

	def load (self):
		if self.objectName is not None:
			return namedAny(self.objectName)
		else:
			return self.fileName


class CachedComponentCollection (object):
	"""
	A collection of L{CachedComponent} instances from a particular module in a
	plugin package.

	@type moduleName: C{str}
	@ivar moduleName: The fully qualified name of the module this represents.

	@type collectionName: C{str}
	@ivar collectionName: The name of the component collection.

	@type icon: C{str} or C{NoneType}
	@ivar icon: A icon for the component collection.

	@type description: C{str} or C{NoneType}
	@ivar description: A brief explanation of this component collection.

	@type components: C{list}
	@ivar components: The L{CachedComponent} instances which were loaded from this
		dropin.
	"""
	def __init__ (self, moduleName, collectionName, icon, description):
		self.moduleName = moduleName
		self.collectionName = collectionName
		self.icon = icon
		self.description = description
		self.components = []


def _generateCacheEntry (provider):
	try:
		collectionName = provider.name
	except AttributeError:
		collectionName = provider.__name__

	try:
		description = provider.description
	except AttributeError:
		description = provider.__doc__

	try:
		icon = provider.icon
	except AttributeError:
		icon = None

	try:
		components = provider.__components__
	except AttributeError:
		components = {}

	d = defer.Deferred()
	dropin = CachedComponentCollection(
		provider.__name__,
		collectionName,
		icon,
		description
	)

	moduleDir = os.path.dirname(provider.__file__)

	def processComponent (componentName, v):
		if collectionName is not None:
			componentName = "{:s}/{:s}".format(collectionName, componentName)

		# It's a class
		if IComponent.implementedBy(v):
			fileName = namedModule(v.__module__).__file__
			objectName = "{:s}.{:s}".format(v.__module__, v.__name__)
			component = v()

		# It's a function (eg getComponent)
		elif callable(v):
			fileName = namedModule(v.__module__).__file__
			objectName = "{:s}.{:s}".format(v.__module__, v.__name__)
			component = v()

			if not IComponent.providedBy(component):
				raise Error(
					"{:s}.{:s}() does not produce a valid Component".format(
						v.__module__,
						v.__name__
				))

		# It's a string - hopefully a '.fbp' or '.json'
		else:
			import graph
			fileName = os.path.join(moduleDir, str(v))
			objectName = None
			component = graph.loadFile(fileName)

			if not IComponent.providedBy(component):
				raise Error(
					"{:s} does not produce a valid Component".format(
						componentName
				))

		# Make sure we will check the ".py" file
		if fileName[-4:] == ".pyc":
			fileName = fileName[:-1]

		if component.ready:
			return defer.succeed((fileName, objectName, componentName, component))
		else:
			d = defer.Deferred()
			component.once("ready", lambda data: d.callback(
				(fileName, objectName, componentName, component)
			))
			return d

	def collectDetails (components):
		for fileName, objectName, componentName, component in components:
			details = {
				"description": str(component.description),
				"icon": str(component.icon),
				"subgraph": bool(component.subgraph),
				"inPorts": [],
				"outPorts": []
			}

			for portName, port in component.inPorts.iteritems():
				inPort = {
					"id": str(portName),
					"type": str(port.datatype),
					"required": bool(port.required),
					"addressable": bool(port.addressable),
					"description": str(port.description),
				}

				if "values" in port.options and port.options["values"] is not None:
					inPort["values"] = port.options["values"]

				if "default" in port.options and port.options["default"] is not None:
					inPort["default"] = port.options["default"]

				details["inPorts"].append(inPort)

			for portName, port in component.outPorts.iteritems():
				details["outPorts"].append({
					"id": str(portName),
					"type": str(port.datatype),
					"required": bool(port.required),
					"addressable": bool(port.addressable),
					"description": str(port.description),
				})

			# Instantiated for its side-effects.
			CachedComponent(dropin, fileName, objectName, componentName, details)

		d.callback(dropin)

	try:
		results = [processComponent(k, v) for k, v in components.iteritems()]
	except:
		return defer.fail(failure.Failure())

	defer.gatherResults(results).addCallbacks(collectDetails, d.errback)

	return d


def getCache ():
	results = []

	for moduleObj in getSearchDirectories():
		componentPath = moduleObj.filePath
		dropinPath = componentPath.parent().child('components.cache')

		# Look for cache
		try:
			lastCached = dropinPath.getModificationTime()
			collection = pickle.load(dropinPath.open('r'))
		# FIXME: what kind of error do we expect?
		except:
			stale = True
		else:
			stale = False
			for path in componentPath.parent().walk():
				if path.isfile() and path.splitext()[-1] == '.py':
					try:
						lastModified = path.getModificationTime()
					except:
						log.err("Could not stat {:s}".format(str(componentPath)))
					else:
						if lastModified > lastCached:
							stale = True
							break

		if stale:
			try:
				module = moduleObj.load()

				if type(module.__components__) is dict:
					def loaded (collection):
						try:
							dropinPath.setContent(pickle.dumps(collection))
						except OSError as e:
							log.err("Unable to write cache file {:s}".format(dropinPath))

						return collection

					results.append(_generateCacheEntry(module).addCallback(loaded))
			except (KeyError, AttributeError) as e:
				log.err("Component module {:s} failed to load".format(componentPath))
			except:
				log.err()
		else:
			results.append(defer.succeed(collection))

	d = defer.Deferred()
	defer.gatherResults(results).addCallbacks(d.callback, d.errback)
	return d


def components ():
	def complete (cache):
		return [
			component
			for collection in cache
			for component in collection.components
		]

	return getCache().addCallback(complete)


def getSearchDirectories ():
	"""
	Return a list of additional directories which should be searched for
	modules to be included as part of the named plugin package.

	@rtype: C{list} of C{str}
	@return: A list of modules whose names start with "protoflo"
	"""

	return (m for m in modules.theSystemPath.iterModules() if m.name[:8] == "protoflo")


class Error (Exception):
	pass
