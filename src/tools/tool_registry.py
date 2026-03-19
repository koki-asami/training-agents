"""Tool definitions for each agent role.

Each function returns (tools_list, handlers_dict) for use with BaseAgent.
Tools are defined in Anthropic API format.
"""


from typing import Any, Callable

from src.engine.state_manager import StateManager
from src.models.enums import AgentRole, AlertLevel


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None):
    """Helper to create a tool definition."""
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required or list(properties.keys()),
        },
    }


def get_fire_department_tools(
    state_manager: StateManager,
) -> tuple[list[dict], dict[str, Callable]]:
    """Tools for the Fire Department agent."""

    tools = [
        _tool(
            "deploy_rescue_team",
            "救助チームを指定場所に派遣する",
            {
                "location": {"type": "string", "description": "派遣先の場所"},
                "team_size": {"type": "integer", "description": "チーム人数", "default": 4},
            },
            ["location"],
        ),
        _tool(
            "check_available_resources",
            "消防局の利用可能なリソースを確認する",
            {},
            [],
        ),
        _tool(
            "request_mutual_aid",
            "近隣消防本部に相互応援を要請する",
            {
                "type": {"type": "string", "description": "応援の種類（救助、消火、救急）"},
                "reason": {"type": "string", "description": "要請理由"},
            },
        ),
        _tool(
            "report_casualties",
            "人的被害を報告する",
            {
                "location": {"type": "string"},
                "injured": {"type": "integer", "default": 0},
                "missing": {"type": "integer", "default": 0},
                "rescued": {"type": "integer", "default": 0},
            },
            ["location"],
        ),
    ]

    async def deploy_rescue_team(location: str, team_size: int = 4) -> str:
        success = await state_manager.deploy_resource("rescue_teams")
        if not success:
            return f"救助チーム派遣失敗: 利用可能なチームがありません。現在の状況を確認してください。"
        return f"救助チーム（{team_size}名）を{location}に派遣しました。"

    async def check_available_resources(**kwargs) -> str:
        res = state_manager.state.resources
        return (
            f"救助チーム: {res.rescue_teams_available}/{res.rescue_teams_total}\n"
            f"消防車: {res.fire_trucks_available}/{res.fire_trucks_total}\n"
            f"救急車: {res.ambulances_available}/{res.ambulances_total}\n"
            f"救助ボート: {res.boats_available}隻"
        )

    async def request_mutual_aid(type: str, reason: str) -> str:
        return f"相互応援要請（{type}）を送信しました。理由: {reason}。到着まで約30-60分を見込みます。"

    async def report_casualties(
        location: str, injured: int = 0, missing: int = 0, rescued: int = 0
    ) -> str:
        c = state_manager.state.casualties
        await state_manager.update_casualties(
            confirmed_injured=c.confirmed_injured + injured,
            missing=c.missing + missing,
            rescued=c.rescued + rescued,
        )
        return f"人的被害報告更新: {location} - 負傷{injured}名, 行方不明{missing}名, 救助{rescued}名"

    handlers = {
        "deploy_rescue_team": deploy_rescue_team,
        "check_available_resources": check_available_resources,
        "request_mutual_aid": request_mutual_aid,
        "report_casualties": report_casualties,
    }
    return tools, handlers


def get_construction_tools(
    state_manager: StateManager,
) -> tuple[list[dict], dict[str, Callable]]:
    """Tools for the Construction/Infrastructure agent."""

    tools = [
        _tool(
            "close_road",
            "道路を閉鎖する",
            {
                "road_name": {"type": "string", "description": "道路名"},
                "reason": {"type": "string", "description": "閉鎖理由"},
            },
        ),
        _tool(
            "check_water_levels",
            "河川の水位を確認する",
            {},
            [],
        ),
        _tool(
            "check_road_status",
            "全道路の状態を確認する",
            {},
            [],
        ),
        _tool(
            "deploy_inspection_team",
            "点検チームを派遣する",
            {
                "location": {"type": "string"},
                "target": {"type": "string", "description": "点検対象（橋梁、堤防、法面等）"},
            },
        ),
    ]

    async def close_road(road_name: str, reason: str) -> str:
        for road in state_manager.state.roads:
            if road_name in road.road_name:
                await state_manager.update_road(road.road_id, "closed", reason)
                return f"{road_name}を閉鎖しました。理由: {reason}"
        return f"{road_name}は道路リストに見つかりません。"

    async def check_water_levels(**kwargs) -> str:
        rivers = state_manager.state.rivers
        if not rivers:
            return "河川データがありません。"
        lines = []
        for r in rivers:
            status = "⚠️危険" if r.overflow_risk else "通常"
            lines.append(
                f"{r.river_name}（{r.observation_point}）: {r.current_level_m:.2f}m "
                f"[危険水位: {r.danger_level_m:.2f}m] 傾向: {r.trend} {status}"
            )
        return "\n".join(lines)

    async def check_road_status(**kwargs) -> str:
        roads = state_manager.state.roads
        if not roads:
            return "道路データがありません。"
        lines = []
        for r in roads:
            icon = "✅" if r.status == "open" else "🚫"
            lines.append(f"{icon} {r.road_name}: {r.status}" + (f" ({r.reason})" if r.reason else ""))
        return "\n".join(lines)

    async def deploy_inspection_team(location: str, target: str) -> str:
        return f"点検チームを{location}の{target}に派遣しました。報告まで約20分。"

    handlers = {
        "close_road": close_road,
        "check_water_levels": check_water_levels,
        "check_road_status": check_road_status,
        "deploy_inspection_team": deploy_inspection_team,
    }
    return tools, handlers


def get_welfare_tools(
    state_manager: StateManager,
) -> tuple[list[dict], dict[str, Callable]]:
    """Tools for the Welfare agent."""

    tools = [
        _tool(
            "open_shelter",
            "避難所を開設する",
            {
                "shelter_name": {"type": "string", "description": "避難所名"},
                "staff_count": {"type": "integer", "default": 2},
            },
            ["shelter_name"],
        ),
        _tool(
            "check_shelter_status",
            "全避難所の状態を確認する",
            {},
            [],
        ),
        _tool(
            "check_vulnerable_residents",
            "要配慮者の状況を確認する",
            {
                "area": {"type": "string", "description": "地区名"},
            },
        ),
        _tool(
            "request_supplies",
            "物資を要請する",
            {
                "supply_type": {"type": "string", "description": "物資の種類"},
                "quantity": {"type": "integer"},
                "shelter_name": {"type": "string"},
            },
        ),
    ]

    async def open_shelter(shelter_name: str, staff_count: int = 2) -> str:
        for s in state_manager.state.shelters:
            if shelter_name in s.name:
                await state_manager.open_shelter(s.shelter_id, staff_count)
                return f"避難所「{s.name}」を開設しました。配置職員: {staff_count}名、収容定員: {s.capacity}名"
        return f"避難所「{shelter_name}」が見つかりません。"

    async def check_shelter_status(**kwargs) -> str:
        shelters = state_manager.state.shelters
        if not shelters:
            return "避難所データがありません。"
        lines = []
        for s in shelters:
            icon = {"closed": "⬜", "open": "🟢", "full": "🔴", "damaged": "⚠️"}.get(
                s.status, "❓"
            )
            lines.append(
                f"{icon} {s.name}: {s.status} ({s.current_occupancy}/{s.capacity}名) "
                f"物資: {s.supplies_status}"
            )
        return "\n".join(lines)

    async def check_vulnerable_residents(area: str) -> str:
        count = state_manager.state.casualties.requiring_assistance
        return f"{area}地区の要配慮者: 約{count}名（高齢者独居、障害者、乳幼児世帯含む）"

    async def request_supplies(supply_type: str, quantity: int, shelter_name: str) -> str:
        return f"物資要請: {shelter_name}へ{supply_type} {quantity}個を手配しました。配送まで約1-2時間。"

    handlers = {
        "open_shelter": open_shelter,
        "check_shelter_status": check_shelter_status,
        "check_vulnerable_residents": check_vulnerable_residents,
        "request_supplies": request_supplies,
    }
    return tools, handlers


def get_general_affairs_tools(
    state_manager: StateManager,
) -> tuple[list[dict], dict[str, Callable]]:
    """Tools for the General Affairs agent."""

    tools = [
        _tool(
            "check_staff_status",
            "職員の参集状況を確認する",
            {},
            [],
        ),
        _tool(
            "check_communication_systems",
            "通信システムの稼働状況を確認する",
            {},
            [],
        ),
        _tool(
            "send_notification",
            "関係機関に通知を送る",
            {
                "target": {"type": "string", "description": "送信先（県、自衛隊、報道等）"},
                "content": {"type": "string", "description": "通知内容"},
            },
        ),
    ]

    async def check_staff_status(**kwargs) -> str:
        res = state_manager.state.resources
        return f"職員参集状況: {res.staff_available}/{res.staff_total}名が参集済み"

    async def check_communication_systems(**kwargs) -> str:
        comms = state_manager.state.communication_systems
        lines = []
        for sys_name, operational in comms.items():
            icon = "✅" if operational else "❌"
            names = {
                "phone": "固定電話",
                "radio": "無線",
                "satellite": "衛星電話",
                "internet": "インターネット",
                "disaster_prevention_radio": "防災無線",
            }
            lines.append(f"{icon} {names.get(sys_name, sys_name)}")
        return "\n".join(lines)

    async def send_notification(target: str, content: str) -> str:
        return f"通知送信完了: {target}宛「{content}」"

    handlers = {
        "check_staff_status": check_staff_status,
        "check_communication_systems": check_communication_systems,
        "send_notification": send_notification,
    }
    return tools, handlers


def get_weather_tools(
    state_manager: StateManager,
) -> tuple[list[dict], dict[str, Callable]]:
    """Tools for the Weather agent."""

    tools = [
        _tool(
            "issue_alert",
            "気象警報・注意報を発表する",
            {
                "alert_type": {"type": "string", "description": "警報の種類（大雨警報、洪水警報等）"},
                "level": {"type": "integer", "description": "警戒レベル (1-5)"},
                "areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "対象地域",
                },
            },
        ),
        _tool(
            "get_forecast",
            "今後の気象予報を提供する",
            {
                "hours_ahead": {"type": "integer", "default": 3},
            },
            [],
        ),
        _tool(
            "get_river_levels",
            "河川水位情報を提供する",
            {},
            [],
        ),
    ]

    async def issue_alert(alert_type: str, level: int, areas: list[str]) -> str:
        alert_level = AlertLevel(min(level, 5))
        await state_manager.update_alert_level(alert_level)
        areas_str = "、".join(areas)
        return f"【{alert_type}】警戒レベル{level} 対象地域: {areas_str}"

    async def get_forecast(hours_ahead: int = 3) -> str:
        w = state_manager.state.weather
        return (
            f"今後{hours_ahead}時間の予報:\n"
            f"現在の降水量: {w.rainfall_intensity_mm_h}mm/h\n"
            f"{w.forecast_next_3h}"
        )

    async def get_river_levels(**kwargs) -> str:
        rivers = state_manager.state.rivers
        if not rivers:
            return "河川水位データなし"
        lines = []
        for r in rivers:
            lines.append(
                f"{r.river_name}: {r.current_level_m:.2f}m (氾濫危険水位: {r.danger_level_m:.2f}m) "
                f"[{r.trend}]"
            )
        return "\n".join(lines)

    handlers = {
        "issue_alert": issue_alert,
        "get_forecast": get_forecast,
        "get_river_levels": get_river_levels,
    }
    return tools, handlers


def get_resident_tools(
    state_manager: StateManager,
) -> tuple[list[dict], dict[str, Callable]]:
    """Tools for Resident agents."""

    tools = [
        _tool(
            "call_119",
            "119番に通報する（消防・救急）",
            {"message": {"type": "string", "description": "通報内容"}},
        ),
        _tool(
            "call_city_hall",
            "市役所に電話する",
            {"message": {"type": "string", "description": "電話内容"}},
        ),
        _tool(
            "observe_surroundings",
            "周囲の状況を確認する",
            {},
            [],
        ),
    ]

    async def call_119(message: str) -> str:
        return f"119番通報受理: 「{message}」消防局に転送されました。"

    async def call_city_hall(message: str) -> str:
        return f"市役所電話受理: 「{message}」総務部に転送されました。"

    async def observe_surroundings(**kwargs) -> str:
        w = state_manager.state.weather
        return (
            f"現在の状況:\n"
            f"- 雨の強さ: {w.rainfall_intensity_mm_h}mm/h\n"
            f"- 警戒レベル: {w.alert_level.value}\n"
            f"- 視界: {w.visibility}"
        )

    handlers = {
        "call_119": call_119,
        "call_city_hall": call_city_hall,
        "observe_surroundings": observe_surroundings,
    }
    return tools, handlers
