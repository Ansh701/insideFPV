from app.sources.base import RetailerAdapter
from app.sources.evelta import EveltaAdapter
from app.sources.robu import RobuAdapter
from app.sources.thinkrobotics import ThinkRoboticsAdapter
from app.sources.zbotic import ZboticAdapter


class UnsupportedRetailerError(ValueError):
    pass


class AdapterRegistry:
    def __init__(self, adapters: list[RetailerAdapter]) -> None:
        self.adapters = adapters

    @property
    def domains(self) -> set[str]:
        return {adapter.domain for adapter in self.adapters}

    def resolve(self, url: str) -> RetailerAdapter:
        for adapter in self.adapters:
            if adapter.can_handle(url):
                return adapter
        raise UnsupportedRetailerError(
            "This retailer is not supported. Use Robu, ThinkRobotics, Zbotic, or Evelta."
        )


def default_registry() -> AdapterRegistry:
    return AdapterRegistry(
        [RobuAdapter(), ThinkRoboticsAdapter(), ZboticAdapter(), EveltaAdapter()]
    )
