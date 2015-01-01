from protoflo.component import Component
from protoflo.port import InPorts, OutPorts

def _toNumber(s):
	"""Cast a string to an int or float"""
	if not isinstance(s, basestring):
		return s	
	try:
		return int(s)
	except ValueError:
		return float(s)

class _MathComponent (Component):
	def initialize (self, primary, secondary, res, inputType = 'number'):
		self.inPorts = InPorts({
			primary:	 { 'datatype': inputType },
			secondary: { 'datatype': inputType },
			"clear":	 { 'datatype': 'bang' }
		})
		self.outPorts = OutPorts({
			res: { 'datatype': inputType }
		})

		primaryPort = self.inPorts[primary]
		secondaryPort = self.inPorts[secondary]
		clearPort = self.inPorts["clear"]
		resPort = self.outPorts[res]

		self.primary = {
			"value": None,
			"group": [],
			"disconnect": False
		}
		self.secondary = None
		self.groups = []

		def calculate ():
			for group in self.primary["group"]:
				resPort.beginGroup(group)

			if self.outPorts[res].attached:
				resPort.send(self.calculate(self.primary['value'], self.secondary))

			for group in self.primary['group']:
				resPort.endGroup()

			if resPort.connected and self.primary["disconnect"]:
				resPort.disconnect()

		@primaryPort.on('begingroup')
		def onBeginGroup (data):
			self.groups.push(data['group'])

		@primaryPort.on('data') 
		def onData (data):
			self.primary = {
				"value": _toNumber(data['data']),
				"group": self.groups[:],
				"disconnect": False
			}
			if self.secondary is not None:
				try:
					calculate()
				except TypeError:
					self.error(TypeError("Must pass numbers to mathematical components"))
				except Exception as e:
					self.error(e)

		@primaryPort.on('endgroup')
		def onEndGroup (data):
			self.groups.pop()

		@primaryPort.on('disconnect')
		def onDisconnect (data):
			self.primary["disconnect"] = True
			return resPort.disconnect()

		@secondaryPort.on('data') 
		def onData (data):
			self.secondary = _toNumber(data['data'])
			if self.primary['value'] is not None:
				calculate()

		@clearPort.on('data') 
		def onData (data):
			if resPorts.connected:
				for group in self.primary['group']:
					self.resPort.endGroup()

				if self.primary['disconnect']:
					self.resPort.disconnect()

			self.primary = {
				"value": None,
				"group": [],
				"disconnect": False
			}
			self.secondary = None
			self.groups = []


class Add (_MathComponent):
	icon = 'plus'

	def initialize (self):
		_MathComponent.initialize(self, 'augend', 'addend', 'sum')

	def calculate (self, a, b):
		return a + b


class Subtract (_MathComponent):
	icon = 'minus'

	def initialize (self):
		_MathComponent.initialize(self, 'minuend', 'subtrahend', 'difference')

	def calculate (self, a, b):
		return a - b


class Multiply (_MathComponent):
	icon = 'asterisk'

	def initialize (self):
		_MathComponent.initialize(self, 'multiplicand', 'multiplier', 'product')

	def calculate (self, a, b):
		return a * b


class Divide (_MathComponent):
	def initialize (self):
		_MathComponent.initialize(self, 'dividend', 'divisor', 'quotient')

	def calculate (self, a, b):
		return float(a) / b

	