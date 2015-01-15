[![Build Status](https://travis-ci.org/chadrik/protoflo.svg?branch=master)](https://travis-ci.org/chadrik/protoflo)

ProtoFlo
======
Experiments in dataflow and Flow-based programming based on Python,
compatible and integrated with [NoFlo](http://noflojs.org)

Installing
----------
After having Python 2.7 installed, from the clone:
```
git clone https://github.com/chadrik/protoflo
cd protoflo
sudo pip install -r requirements.txt
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

License
=======
MIT


TODO:
======
* Write tests
* Implement components for glib/GI, incl mainloop. GTK+ example
* Implement port2port NoFlo Websocket protocol
* Implement MicroFlo serial-protocol components

