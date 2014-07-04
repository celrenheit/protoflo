
# MapComponent maps a single inport to a single outport, forwarding all
# groups from in to out and calling `func` on each incoming packet
def MapComponent (component, func, config = None):
	config = config or {}

	if "inPort" not in config or config["inPort"] is None:
  		config["inPort"] = 'in'

	if "outPort" not in config or config["outPort"] is None:
  		config["outPort"] = 'out'

	inPort = component.inPorts[config["inPort"]]
	outPort = component.outPorts[config["outPort"]]
	_ = {
		"groups": []
	}

  	def process (event, nodeInstance, data):
		if event == 'connect':
			outPort.connect()
		elif event == 'begingroup':
			_['groups'].push(data["group"])
			outPort.beginGroup(data["group"])
		elif event == 'data':
			func(data, _['groups'], outPort)
		elif event == 'endgroup':
			_['groups'].pop()
			outPort.endGroup()
		elif event == 'disconnect':
			_['groups'] = []
			outPort.disconnect()

	inPort.process = process

	return component
