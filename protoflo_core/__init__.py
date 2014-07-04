from protoflo.component import Component
from protoflo.port import InPorts, OutPorts

name = "core"
description = "Protoflo Core Components"


class Kick (Component):

	description = """This component generates a single packet and sends it to
		the output port. Mostly usable for debugging, but can also be useful
		for starting up networks."""

	icon = "share"

	def initialize (self, **options):
		self.data = {
			"packet": None,
			"group": []
		}

		self.groups = []

		self.inPorts = InPorts({
			"in": { 
				"datatype": "bang",
				"description": "Signal to send the data packet"
			},
			"data": {
				"datatype": "all",
				"description": "Packet to be sent"
			}
		})

		self.outPorts = OutPorts({
			"out": { "datatype": "all" }
		})

		self.inPorts["in"].on("begingroup", lambda data: self.groups.append(data["group"]))
		self.inPorts["in"].on("endgroup", lambda data: self.groups.pop())
		self.inPorts["in"].on("data", self._on_in_data)
		self.inPorts["in"].on("disconnect", self._on_in_disconnect)
		self.inPorts["data"].on("data", self._on_data_data)

	def _on_in_data (self, data):
		self.data["group"] = self.groups[:1]

	def _on_in_disconnect (self, data):
		self.sendKick(self.data)
		self.groups = []

	def _on_data_data (self, data):
		self.data["packet"] = data["data"]

	def sendKick (self, kick):
		port = self.outPorts["out"]

		for group in kick["group"]:
			port.beginGroup(group)

		port.send(kick["packet"])

		for group in kick["group"]:
			port.endGroup(group)

		port.disconnect()


class Drop (Component):

	description = """This component drops every packet 
		it receives with no	action"""
	icon = 'trash-o'

	def initialize (self, **options):
		self.inPorts = InPorts({
			"in": {
				"datatype": 'all',
				"description": 'Packet to be dropped'
			}
		})
		self.outPorts = OutPorts()


class Output (Component):

	description = """This component receives input on a single inport, and
		sends the data items directly to the console"""
	icon = 'bug'

	def initialize (self, **options):
		self.inPorts = InPorts({
			"in": {
				"datatype": 'all',
				"description": 'Packet to be printed through console.log'
			}
		})
		self.outPorts = OutPorts({
			"out": { "datatype": 'all' }
		})

		inPort = self.inPorts["in"]
		outPort = self.outPorts["out"]

		@inPort.on('data')
		def onData (data):
			self.log(data["data"])
			
			if outPort.attached:
				outPort.send(data["data"])

		@inPort.on('disconnect')
		def onDisconnect (data):
			if outPort.attached:
				outPort.disconnect()

	def log (self, data):
		print data


__components__ = {
	'Kick': Kick,
	'Drop': Drop,
	'Output': Output
}
