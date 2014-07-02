from twisted.internet import reactor
from twisted.internet.error import AlreadyCalled, AlreadyCancelled
import functools
from itertools import chain

class EventEmitter (object):
	def on (self, name, function = None):
		def _on (function):
			try:
				self._events[name]
			except (TypeError, AttributeError):
				self._events = {}
				self._events[name] = []
			except KeyError:
				self._events[name] = []

			if function not in self._events[name]:
				self._events[name].append(function)

			return function

		if function is None:
			return _on
		else:
			return _on(function)

	def once (self, name, function = None):
		def _once (function):
			@functools.wraps(function)
			def g (*args, **kwargs):
				function(*args, **kwargs)
				self.off(name, g)

			return g

		if function is None:
			return lambda function: self.on(name, _once(function))
		else:
			self.on(name, _once(function))
	
	def off (self, name = None, function = None):
		try:
			self._events
		except AttributeError:
			return
		
		# If no name is passed, remove all handlers
		if name is None:
			self._events.clear()
		
		# If no function is passed, remove all functions
		elif function is None:
			try:
				self._events[name] = []
			except KeyError:
				pass
		
		# Remove handler [function] from [name]
		else:
			self._events[name].remove(function)

	def listeners (self, event):
		try:
			return self._events[event]
		except (AttributeError, KeyError):
			return []
	
	def emit (self, _event, **data):
		handled = False

		try:
			events = self._events[_event]
		except AttributeError:
			return False # No events defined yet
		except KeyError:
			pass
		else:
			handled |= bool(len(events))

			for function in events:
				function(data)

		try:
			events = self._events["all"]
		except KeyError:
			pass
		else:
			handled |= bool(len(events))

			for function in events:
				function(_event, data)

		return handled



def debounce (wait):
	""" Decorator that will postpone a function's
		execution until after [wait] seconds
		have elapsed since the last time it was invoked. """
	def decorator (fn):
		@functools.wraps(fn)
		def debounced (*args, **kwargs):
			def call_it ():
					fn(*args, **kwargs)

			try:
				debounced.t.cancel()
			except (AttributeError, AlreadyCalled, AlreadyCancelled):
				pass
			debounced.t = reactor.callLater(wait, call_it)

		return debounced
	return decorator
