from __future__ import annotations

from vapoursynth import EnvironmentData, EnvironmentPolicy, EnvironmentPolicyAPI, register_policy


class VSPreviewEnvironmentPolicy(EnvironmentPolicy):
    _api: EnvironmentPolicyAPI | None = None
    _current: EnvironmentData | None = None

    def __init__(self) -> None:
        pass

    def on_policy_registered(self, special_api: EnvironmentPolicyAPI) -> None:
        self._api = special_api
        self.reload_core()

    def on_policy_cleared(self) -> None:
        self._current = None

    def get_current_environment(self) -> EnvironmentData | None:
        return self._current

    def set_environment(self, environment: EnvironmentData | None) -> None:
        if environment is not self._current:
            raise RuntimeError("The chosen environment is dead.")

    def is_alive(self, environment: EnvironmentData) -> bool:
        return environment is self._current

    def reload_core(self) -> None:
        if self._api is None:
            new_environment = VSPreviewEnvironmentPolicy()
            self._api = new_environment._api
        if self._current:
            del self._current
        try:
            self._api.unregister_policy()  # type: ignore
            self._current = self._api.create_environment()  # type: ignore
        except BaseException:
            pass


policy = VSPreviewEnvironmentPolicy()
register_policy(policy)


def get_policy() -> VSPreviewEnvironmentPolicy:
    return policy
