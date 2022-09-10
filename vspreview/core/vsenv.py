from __future__ import annotations

import atexit
from typing import Optional

from vsengine.policy import Policy, GlobalStore, ManagedEnvironment


policy: Policy = Policy(GlobalStore())
policy.register()
environment: ManagedEnvironment = policy.new_environment()
environment.switch()


def get_current_environment():
    return environment


def make_environment():
    global environment
    assert policy is not None
    environment = policy.new_environment()
    environment.switch()


atexit.register(lambda: environment.dispose())
