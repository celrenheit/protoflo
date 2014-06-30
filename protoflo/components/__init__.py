from zope.interface import Interface, Attribute

from twisted.python import log
from twisted.python.modules import getModule
from twisted.python.reflect import namedAny
from twisted.plugin import pluginPackagePaths, pickle

__path__.extend(pluginPackagePaths(__name__))
__all__ = []


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
	def __init__ (self, dropin, name, description):
		self.dropin = dropin
		self.fullName = dropin.moduleName.split('.')[-1] + '/' + name
		self.name = name
		self.description = description
		self.dropin.components.append(self)

	def __repr__ (self):
		return '<CachedComponent {:s}>'.format(self.fullName)

	def load (self):
		return namedAny(self.dropin.moduleName + '.' + self.name)


class CachedComponentCollection (object):
	"""
	A collection of L{CachedComponent} instances from a particular module in a
	plugin package.

	@type moduleName: C{str}
	@ivar moduleName: The fully qualified name of the plugin module this
		represents.

	@type description: C{str} or C{NoneType}
	@ivar description: A brief explanation of this collection of components
		(probably the plugin module's docstring).

	@type components: C{list}
	@ivar components: The L{CachedComponent} instances which were loaded from this
		dropin.
	"""
	def __init__ (self, moduleName, description):
		self.moduleName = moduleName
		self.description = description
		self.components = []


def _generateCacheEntry (provider):
	dropin = CachedComponentCollection(
		provider.__name__,
		provider.__doc__
	)

	for k, v in provider.__dict__.iteritems():
		if k[0] != "_" and IComponent.implementedBy(v):
			if v.__module__ != provider.__name__:
				# Ignore imported classes
				continue

			# Instantiated for its side-effects.
			CachedComponent(dropin, k, v.description)

	return dropin


def getCache ():
	"""
	Compute all the possible loadable plugins, while loading as few as
	possible and hitting the filesystem as little as possible.

	@return: A dictionary mapping component names to IComponent classes.
	"""
	allCachesCombined = {}
	mod = getModule(__name__)
	# don't want to walk deep, only immediate children.
	buckets = {}
	# Fill buckets with modules by related entry on the given package's
	# __path__.  There's an abstraction inversion going on here, because this
	# information is already represented internally in twisted.python.modules,
	# but it's simple enough that I'm willing to live with it.  If anyone else
	# wants to fix up this iteration so that it's one path segment at a time,
	# be my guest.  --glyph
	for plugmod in mod.iterModules():
		fpp = plugmod.filePath.parent()
		if fpp not in buckets:
			buckets[fpp] = []
		bucket = buckets[fpp]
		bucket.append(plugmod)
	for pseudoPackagePath, bucket in buckets.iteritems():
		dropinPath = pseudoPackagePath.child('component.cache')
		try:
			lastCached = dropinPath.getModificationTime()
			dropinDotCache = pickle.load(dropinPath.open('r'))
		except:
			dropinDotCache = {}
			lastCached = 0

		needsWrite = False
		existingKeys = {}
		
		for pluginModule in bucket:
			pluginKey = pluginModule.name.split('.')[-1]
			existingKeys[pluginKey] = True
			if ((pluginKey not in dropinDotCache) or
				(pluginModule.filePath.getModificationTime() >= lastCached)):
				needsWrite = True
				try:
					provider = pluginModule.load()
				except:
					# dropinDotCache.pop(pluginKey, None)
					log.err()
				else:
					entry = _generateCacheEntry(provider)
					dropinDotCache[pluginKey] = entry
		# Make sure that the cache doesn't contain any stale plugins.
		for pluginKey in dropinDotCache.keys():
			if pluginKey not in existingKeys:
				del dropinDotCache[pluginKey]
				needsWrite = True
		if needsWrite:
			try:
				dropinPath.setContent(pickle.dumps(dropinDotCache))
			except OSError, e:
				log.msg(
					format=(
						"Unable to write to component cache %(path)s: error "
						"number %(errno)d"),
					path=dropinPath.path, errno=e.errno)
			except:
				log.err(None, "Unexpected error while writing cache file")
		allCachesCombined.update(dropinDotCache)
	return allCachesCombined

def components ():
	cache = getCache()

	for collection in cache.itervalues():
		for components in collection.components:
			yield component
