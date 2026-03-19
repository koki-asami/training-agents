"""Disaster state models - the single source of truth during simulation."""


from datetime import datetime

from pydantic import BaseModel, Field

from .enums import AlertLevel, SimulationPhase


class WeatherState(BaseModel):
    rainfall_intensity_mm_h: float = 0.0
    cumulative_rainfall_mm: float = 0.0
    wind_speed_m_s: float = 0.0
    current_alerts: list[str] = Field(default_factory=list)
    alert_level: AlertLevel = AlertLevel.LEVEL_1
    forecast_next_3h: str = ""
    visibility: str = "良好"


class RiverState(BaseModel):
    river_name: str
    observation_point: str = ""
    current_level_m: float = 0.0
    warning_level_m: float = 0.0
    danger_level_m: float = 0.0
    overflow_risk: bool = False
    trend: str = "stable"  # rising, stable, falling


class RoadState(BaseModel):
    road_id: str
    road_name: str
    status: str = "open"  # open, flooded, blocked, closed
    reason: str | None = None
    closed_at: datetime | None = None


class ShelterState(BaseModel):
    shelter_id: str
    name: str
    area: str = ""  # 地区名
    capacity: int = 100
    current_occupancy: int = 0
    status: str = "closed"  # closed, open, full, damaged
    supplies_status: str = "adequate"  # adequate, low, depleted
    staff_count: int = 0
    opened_at: datetime | None = None


class ResourceState(BaseModel):
    rescue_teams_total: int = 5
    rescue_teams_available: int = 5
    fire_trucks_total: int = 8
    fire_trucks_available: int = 8
    ambulances_total: int = 4
    ambulances_available: int = 4
    staff_total: int = 50
    staff_available: int = 50
    heavy_equipment_available: int = 3
    sandbags_available: int = 1000
    boats_available: int = 2


class CasualtyState(BaseModel):
    confirmed_dead: int = 0
    confirmed_injured: int = 0
    missing: int = 0
    rescued: int = 0
    evacuated: int = 0
    sheltering: int = 0
    requiring_assistance: int = 0  # 要配慮者


class ActiveIncident(BaseModel):
    incident_id: str
    location: str
    description: str
    severity: str = "medium"  # low, medium, high, critical
    reported_at: datetime | None = None
    assigned_resources: list[str] = Field(default_factory=list)
    status: str = "active"  # active, responding, resolved


class EvacuationOrder(BaseModel):
    area: str
    level: AlertLevel
    issued_at: datetime
    population_affected: int = 0
    compliance_rate: float = 0.0  # 0.0-1.0


class DisasterState(BaseModel):
    """Central state object - the single source of truth for the simulation."""

    session_id: str
    sim_time: datetime
    phase: SimulationPhase = SimulationPhase.SETUP
    weather: WeatherState = Field(default_factory=WeatherState)
    rivers: list[RiverState] = Field(default_factory=list)
    roads: list[RoadState] = Field(default_factory=list)
    shelters: list[ShelterState] = Field(default_factory=list)
    resources: ResourceState = Field(default_factory=ResourceState)
    casualties: CasualtyState = Field(default_factory=CasualtyState)
    current_alert_level: AlertLevel = AlertLevel.LEVEL_1
    evacuation_orders: list[EvacuationOrder] = Field(default_factory=list)
    active_incidents: list[ActiveIncident] = Field(default_factory=list)
    resolved_incidents: list[ActiveIncident] = Field(default_factory=list)
    communication_systems: dict[str, bool] = Field(
        default_factory=lambda: {
            "phone": True,
            "radio": True,
            "satellite": True,
            "internet": True,
            "disaster_prevention_radio": True,  # 防災無線
        }
    )
