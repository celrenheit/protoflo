from protoflo.component import Component
from protoflo.helper import MapComponent
from protoflo.port import InPorts, OutPorts

name = "python"
description = "Protoflo Python Components"

class CastComponent (Component):
	inPorts = [
		('in', { "datatype": "all" })
	]


def Str (metadata = None):
	c = CastComponent(outPorts = [
		('out', { "datatype": "string", "required": False })
	])
	
	def process (data, groups, outPort):
		outPort.send(str(data['data']))

	return MapComponent(c, process)


def Int (metadata = None):
	c = CastComponent(outPorts = [
		('out', { "datatype": "int", "required": False })
	])
	
	def process (data, groups, outPort):
		outPort.send(int(data['data']))

	return MapComponent(c, process)


def Float (metadata = None):
	c = CastComponent(outPorts = [
		('out', { "datatype": "number", "required": False })
	])
	
	def process (data, groups, outPort):
		outPort.send(float(data['data']))

	return MapComponent(c, process)


def Boolean (metadata = None):
	c = CastComponent(outPorts = [
		('out', { "datatype": "boolean", "required": False })
	])
	
	def process (data, groups, outPort):
		d = data['data']

		if type(d) in (str, str) and d.lower() == "false":
			outPort.send(False)
		else:
			outPort.send(bool(d))

	return MapComponent(c, process)


def Invert (metadata = None):
	c = CastComponent(outPorts = [
		('out', { "datatype": "boolean", "required": False })
	])

	def process (data, groups, outPort):
		outPort.send(not data['data'])

	return MapComponent(c, process)


__components__ = {
	'Str': Str,
	'Int': Int,
	'Float': Float,
	'Boolean': Boolean,
	'Invert': Invert,
}
