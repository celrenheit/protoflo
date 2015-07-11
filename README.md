[![Build Status](https://travis-ci.org/chadrik/protoflo.svg?branch=master)](https://travis-ci.org/chadrik/protoflo)

ProtoFlo
========
Experiments in dataflow and Flow-based programming based on Python,
compatible and integrated with [NoFlo](http://noflojs.org)

Installing
----------
After installing python 2.7:
```
git clone https://github.com/chadrik/protoflo
cd protoflo
sudo pip install -r requirements.txt
```

If you want to use the NoFlo web UI, install and run that as well:

```
npm install -g n
npm install -g bower
npm install -g grunt-cli
sudo n 0.10

mkdir noflo
cd noflo

git clone https://github.com/noflo/noflo-ui
cd noflo-ui
git checkout 0.9.0
npm install
# running bower before grunt prompts to resolve a dependency conflict which otherwise causes grunt to fail
bower install
grunt build
python -m SimpleHTTPServer
```

Running
-------
1. `cd` into the directory that you cloned ProtoFlo into.
2. Register ProtoFlo as a NoFlo runtime (discover what is your UID
   on NoFlo)
   ```
   python -m protoflo register --user YOUR_UID --label ProtoFlo
   ```
3. Start the ProtoFlo runtime.
   ```
   python -m protoflo runtime
   ```
4. Create a new project in NoFlo selecting the ProtoFlo runtime
5. Inside the new project/graph, select the appropriate ProtoFlo
   runtime clicking on the top-right menu
6. Green arrows should appear on the top-right menu, right before
   `ws:\\localhost:3569`
7. Try typing `Add` into the component search box on top-left

Testing
=======
First install the test suite:
```
nmp install -g fbp-protocol
```

Then, from the repo directory, run the tests
```
fbp-test
```

Components
==========

Modules with names beginning with "protoflo" on the Python Path
are searched for components - they must have a `__components__` attribute which is
a dict listing the components. Components should be sub-classes of `protoflo.components.IComponent` or methods which return `IComponent` objects. Alternatively,
they can be a filename pointing to a json or fbp graph file.


Status
=======
Prototyping

Can create and run graphs using the NoFlo UI protocol.

Conversion from Noflo
=====================

The code in this repo is based on a direct conversion from coffeescript+node into python+twisted of [noflo-runtime-websocket](github.com/noflo/noflo-runtime-websocket) and its dependencies.

Below are several charts showing what repos and files the protoflo source code is based on.  The code is based on Noflo 0.5.4 (and needs to be updated).

[noflo](github.com/noflo/noflo)
-------------------------------

| Source File               | Converted File                            |
|---------------------------|-------------------------------------------|
| components/Graph.coffee   | protoflo/components/graph.py              |
| lib/Helpers.coffee        | protoflo/helper.py                        |


[noflo-runtime-base](github.com/noflo/noflo-runtime-base)
---------------------------------------------------------

| Source File               | Converted File                            |
|---------------------------|-------------------------------------------|
| Base.coffee               | protoflo/server/transport/base.py         |
| protocol/Component.coffee | protoflo/server/protocol/component.py     |
| protocol/Graph.coffee     | protoflo/server/protocol/graph.py         |
| protocol/Network.coffee   | protoflo/server/protocol/network.py       |
| protocol/Runtime.coffee   | protoflo/server/protocol/runtime.py       |


[noflo-runtime-websocket](github.com/noflo/noflo-runtime-websocket)
-------------------------------------------------------------------

| Source File               | Converted File                            |
|---------------------------|-------------------------------------------|
| network.js                | protoflo/server/server.py                 |

License
=======
MIT

TODO:
======
* Update to latest Noflo
* Write tests
* Implement components for glib/GI, incl mainloop. GTK+ example
* Implement port2port NoFlo Websocket protocol
* Implement MicroFlo serial-protocol components

