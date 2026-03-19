"""State manager - single source of truth for disaster simulation state."""


import asyncio
import copy
from datetime import datetime

import structlog

from src.models.enums import AlertLevel, SimulationPhase
from src.models.state import (
    ActiveIncident,
    CasualtyState,
    DisasterState,
    EvacuationOrder,
    ResourceState,
    RiverState,
    RoadState,
    ShelterState,
    WeatherState,
)

logger = structlog.get_logger()


class StateManager:
    """Manages the central disaster state with thread-safe access."""

    def __init__(self, session_id: str):
        self._state = DisasterState(
            session_id=session_id,
            sim_time=datetime.now(),
        )
        self._lock = asyncio.Lock()
        self._snapshots: list[DisasterState] = []
        self._listeners: list[asyncio.Queue] = []

    @property
    def state(self) -> DisasterState:
        return self._state

    def add_listener(self) -> asyncio.Queue:
        """Add a listener that receives state change notifications."""
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.append(q)
        return q

    def remove_listener(self, q: asyncio.Queue):
        self._listeners.discard(q) if hasattr(self._listeners, "discard") else None
        if q in self._listeners:
            self._listeners.remove(q)

    async def _notify_listeners(self, change_type: str):
        for q in self._listeners:
            await q.put({"type": change_type, "state": self._state.model_dump()})

    async def initialize(
        self,
        rivers: list[RiverState] | None = None,
        roads: list[RoadState] | None = None,
        shelters: list[ShelterState] | None = None,
        resources: ResourceState | None = None,
    ):
        """Initialize state with scenario data."""
        async with self._lock:
            if rivers:
                self._state.rivers = rivers
            if roads:
                self._state.roads = roads
            if shelters:
                self._state.shelters = shelters
            if resources:
                self._state.resources = resources
            self._state.phase = SimulationPhase.SETUP
            logger.info("state_initialized", session_id=self._state.session_id)

    async def update_sim_time(self, sim_time: datetime):
        async with self._lock:
            self._state.sim_time = sim_time

    async def update_phase(self, phase: SimulationPhase):
        async with self._lock:
            self._state.phase = phase
            await self._notify_listeners("phase_change")

    async def update_weather(self, **kwargs):
        async with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._state.weather, k):
                    setattr(self._state.weather, k, v)
            await self._notify_listeners("weather_update")

    async def update_alert_level(self, level: AlertLevel):
        async with self._lock:
            self._state.current_alert_level = level
            self._state.weather.alert_level = level
            await self._notify_listeners("alert_level_change")

    async def update_river(self, river_name: str, **kwargs):
        async with self._lock:
            for river in self._state.rivers:
                if river.river_name == river_name:
                    for k, v in kwargs.items():
                        if hasattr(river, k):
                            setattr(river, k, v)
                    break
            await self._notify_listeners("river_update")

    async def update_road(self, road_id: str, status: str, reason: str | None = None):
        async with self._lock:
            for road in self._state.roads:
                if road.road_id == road_id:
                    road.status = status
                    road.reason = reason
                    if status == "closed":
                        road.closed_at = self._state.sim_time
                    break
            await self._notify_listeners("road_update")

    async def open_shelter(self, shelter_id: str, staff_count: int = 2):
        async with self._lock:
            for shelter in self._state.shelters:
                if shelter.shelter_id == shelter_id:
                    shelter.status = "open"
                    shelter.staff_count = staff_count
                    shelter.opened_at = self._state.sim_time
                    break
            await self._notify_listeners("shelter_update")

    async def update_shelter_occupancy(self, shelter_id: str, occupancy: int):
        async with self._lock:
            for shelter in self._state.shelters:
                if shelter.shelter_id == shelter_id:
                    shelter.current_occupancy = occupancy
                    if occupancy >= shelter.capacity:
                        shelter.status = "full"
                    break

    async def deploy_resource(self, resource_type: str, count: int = 1) -> bool:
        """Deploy resources. Returns False if insufficient."""
        async with self._lock:
            res = self._state.resources
            field = f"{resource_type}_available"
            if not hasattr(res, field):
                return False
            current = getattr(res, field)
            if current < count:
                return False
            setattr(res, field, current - count)
            await self._notify_listeners("resource_update")
            return True

    async def release_resource(self, resource_type: str, count: int = 1):
        async with self._lock:
            res = self._state.resources
            avail_field = f"{resource_type}_available"
            total_field = f"{resource_type}_total"
            if hasattr(res, avail_field) and hasattr(res, total_field):
                current = getattr(res, avail_field)
                total = getattr(res, total_field)
                setattr(res, avail_field, min(current + count, total))

    async def add_incident(self, incident: ActiveIncident):
        async with self._lock:
            self._state.active_incidents.append(incident)
            await self._notify_listeners("incident_added")

    async def resolve_incident(self, incident_id: str):
        async with self._lock:
            for i, inc in enumerate(self._state.active_incidents):
                if inc.incident_id == incident_id:
                    inc.status = "resolved"
                    self._state.resolved_incidents.append(inc)
                    self._state.active_incidents.pop(i)
                    break
            await self._notify_listeners("incident_resolved")

    async def issue_evacuation_order(self, area: str, level: AlertLevel, population: int = 0):
        async with self._lock:
            order = EvacuationOrder(
                area=area,
                level=level,
                issued_at=self._state.sim_time,
                population_affected=population,
            )
            self._state.evacuation_orders.append(order)
            await self._notify_listeners("evacuation_order")

    async def update_casualties(self, **kwargs):
        async with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._state.casualties, k):
                    setattr(self._state.casualties, k, v)
            await self._notify_listeners("casualty_update")

    async def update_communication(self, system: str, operational: bool):
        async with self._lock:
            self._state.communication_systems[system] = operational
            await self._notify_listeners("communication_update")

    async def take_snapshot(self):
        """Take a deep copy snapshot of current state for logging."""
        async with self._lock:
            self._snapshots.append(copy.deepcopy(self._state))

    def get_snapshots(self) -> list[DisasterState]:
        return self._snapshots

    def get_state_summary(self) -> dict:
        """Return a concise summary for agent context."""
        s = self._state
        return {
            "sim_time": s.sim_time.strftime("%H:%M"),
            "alert_level": s.current_alert_level.value,
            "weather": {
                "rainfall_mm_h": s.weather.rainfall_intensity_mm_h,
                "alerts": s.weather.current_alerts,
            },
            "rivers": [
                {
                    "name": r.river_name,
                    "level_m": r.current_level_m,
                    "danger_m": r.danger_level_m,
                    "trend": r.trend,
                }
                for r in s.rivers
            ],
            "active_incidents": len(s.active_incidents),
            "evacuation_orders": len(s.evacuation_orders),
            "shelters_open": sum(1 for sh in s.shelters if sh.status == "open"),
            "resources": {
                "rescue_teams": f"{s.resources.rescue_teams_available}/{s.resources.rescue_teams_total}",
                "ambulances": f"{s.resources.ambulances_available}/{s.resources.ambulances_total}",
            },
            "casualties": {
                "injured": s.casualties.confirmed_injured,
                "missing": s.casualties.missing,
                "evacuated": s.casualties.evacuated,
            },
        }
