from __future__ import annotations

import atexit
from typing import Optional

from vsengine.policy import Policy, GlobalStore, ManagedEnvironment


policy: Policy = Policy(GlobalStore())
policy.register()
environment: ManagedEnvironment = policy.new_environment()


def reload_environment():
    global environment
    assert policy is not None
    environment.dispose()
    environment = policy.new_environment()
    environment.switch()

reload_environment()


atexit.register(lambda: environment.dispose())
