from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from autobahn.websocket.compress import PerMessageDeflateOffer, PerMessageDeflateOfferAccept
from twisted.python import log
from twisted.internet import reactor

import json

from transport.base import BaseTransport

class WebSocketRuntime (BaseTransport):
	def __init__ (self):
		BaseTransport.__init__(self, options = {
			"capabilities": [
				'protocol:graph',
				'protocol:component',
				'protocol:network'
			]
		})

	def send (self, protocol, topic, payload, context):
		if isinstance(payload, Exception):
			payload = {
				"type": payload.__class__.__name__,
				"message": payload.message
			}

		response = {
			"protocol": protocol,
			"command": topic,
			"payload": payload,
		}

		log.msg("Response", response)

		context.sendMessage(json.dumps(response))

class NoFloUiProtocol (WebSocketServerProtocol): 
	def onConnect (self, request):
		return 'noflo'

	def onOpen (self):
		self.sendPing()
		pass

	def onClose (self, wasClean, code, reason):
		pass

	def onMessage (self, payload, isBinary):
		if isBinary:
			raise ValueError("WebSocket message must be UTF-8")

		cmd = json.loads(payload)

		log.msg("Command", cmd)

		self.factory.runtime.receive(
			cmd['protocol'], 
			cmd['command'], 
			cmd["payload"], 
			self
		)


def runtime (port):
	import sys
	log.startLogging(sys.stdout)

	factory = WebSocketServerFactory("ws://localhost:" + str(port), debug = False)
	factory.protocol = NoFloUiProtocol
	factory.runtime = WebSocketRuntime()

	# Required for Chromium ~33 and newer
	def accept (offers):
		for offer in offers:
			if isinstance(offer, PerMessageDeflateOffer):
				return PerMessageDeflateOfferAccept(offer)

	factory.setProtocolOptions(perMessageCompressionAccept = accept)

	reactor.listenTCP(port, factory)
	reactor.run()

