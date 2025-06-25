import inspect, importlib.metadata as md
from a2a.server.tasks import TaskUpdater

print("a2a-sdk package version :", md.version("a2a-sdk"))

# In the async API these return True
print("update_status is async :", inspect.iscoroutinefunction(TaskUpdater.update_status))
print("add_artifact  is async :", inspect.iscoroutinefunction(TaskUpdater.add_artifact))
print("complete      is async :", inspect.iscoroutinefunction(TaskUpdater.complete))

import a2a, inspect, sys
print("import path  :", a2a.__file__)
from a2a.server.tasks import TaskUpdater
print("update_status async?:", inspect.iscoroutinefunction(TaskUpdater.update_status))