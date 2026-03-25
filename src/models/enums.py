"""Enumerations for the disaster training simulation."""

from enum import Enum


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"  # 体制構築訓練
    INTERMEDIATE = "intermediate"  # 指揮判断（入門）
    ADVANCED = "advanced"  # 指揮判断（上級）


class AgentRole(str, Enum):
    SCENARIO_MASTER = "scenario_master"  # シナリオマスター
    COMMANDER = "commander"  # 災害対策本部長
    GENERAL_AFFAIRS = "soumu"  # 総務部
    FIRE_DEPARTMENT = "shoubou"  # 消防局
    CONSTRUCTION = "kensetsu"  # 建設部
    WELFARE = "fukushi"  # 福祉部
    RESIDENT = "juumin"  # 住民
    WEATHER = "kishou"  # 気象情報


# Roles that can be assigned to human participants
ASSIGNABLE_ROLES = {
    AgentRole.COMMANDER,
    AgentRole.GENERAL_AFFAIRS,
    AgentRole.FIRE_DEPARTMENT,
    AgentRole.CONSTRUCTION,
    AgentRole.WELFARE,
}

ROLE_DISPLAY_NAMES = {
    AgentRole.SCENARIO_MASTER: ("シナリオマスター", "Scenario Master"),
    AgentRole.COMMANDER: ("災害対策本部長", "Emergency HQ Commander"),
    AgentRole.GENERAL_AFFAIRS: ("総務部", "General Affairs"),
    AgentRole.FIRE_DEPARTMENT: ("消防局", "Fire Department"),
    AgentRole.CONSTRUCTION: ("建設部", "Construction & Infrastructure"),
    AgentRole.WELFARE: ("福祉部", "Welfare"),
    AgentRole.RESIDENT: ("住民", "Resident"),
    AgentRole.WEATHER: ("気象情報", "Weather Information"),
}


class AlertLevel(int, Enum):
    """警戒レベル (JMA Alert Levels)"""

    LEVEL_1 = 1  # 早期注意情報
    LEVEL_2 = 2  # 大雨・洪水注意報
    LEVEL_3 = 3  # 高齢者等避難
    LEVEL_4 = 4  # 避難指示
    LEVEL_5 = 5  # 緊急安全確保


class SimulationPhase(str, Enum):
    SETUP = "setup"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class MessageType(str, Enum):
    REPORT = "report"  # 状況報告
    ORDER = "order"  # 指示・命令
    REQUEST = "request"  # 要請
    ALERT = "alert"  # 警報・通知
    HINT = "hint"  # ヒント（初級のみ）
    SYSTEM = "system"  # システムメッセージ
    CALL_119 = "call_119"  # 119通報
    CALL_110 = "call_110"  # 110通報
    CALL_CITY = "call_city"  # 市役所電話


class InformationSource(str, Enum):
    """情報源 - maps to agent roles for event routing."""

    RESIDENT = "住民"
    POLICE = "警察"
    FIRE = "消防"
    MEDIA = "報道"
    MUNICIPALITY = "市町村"
    WEATHER = "気象台"
    PREFECTURE = "県"
    SELF_DEFENSE = "自衛隊"


# Mapping from information source to the agent that *originates* this event
SOURCE_TO_AGENT: dict[str, AgentRole] = {
    "住民": AgentRole.RESIDENT,
    "警察": AgentRole.GENERAL_AFFAIRS,
    "消防": AgentRole.FIRE_DEPARTMENT,
    "報道": AgentRole.GENERAL_AFFAIRS,
    "市町村": AgentRole.GENERAL_AFFAIRS,
    "気象台": AgentRole.WEATHER,
    "県": AgentRole.GENERAL_AFFAIRS,
    "自衛隊": AgentRole.GENERAL_AFFAIRS,
}

# Mapping from information source to *responsible department* (who handles it)
# 情報源 → 対応部署: 情報を受けて対応する部署
SOURCE_TO_RESPONSIBLE_DEPT: dict[str, str] = {
    "住民": "総務部",      # 住民からの通報 → 総務部が受付
    "警察": "総務部",      # 警察からの連絡 → 総務部が対応
    "消防": "消防局",      # 消防からの報告 → 消防局が対応
    "報道": "総務部",      # 報道対応 → 総務部（広報）
    "市町村": "総務部",    # 他市町村との連絡 → 総務部
    "気象台": "総務部",    # 気象情報 → 総務部が受信・共有
    "県": "総務部",        # 県との連絡 → 総務部
    "自衛隊": "総務部",    # 自衛隊との連絡 → 総務部
}

# Responsible department name -> AgentRole
DEPT_NAME_TO_ROLE: dict[str, AgentRole] = {
    "総務部": AgentRole.GENERAL_AFFAIRS,
    "消防局": AgentRole.FIRE_DEPARTMENT,
    "建設部": AgentRole.CONSTRUCTION,
    "福祉部": AgentRole.WELFARE,
}

# Keywords in expected_actions that indicate department responsibility
DEPT_KEYWORDS: dict[str, str] = {
    "消防": "消防局",
    "救助": "消防局",
    "救急": "消防局",
    "建設": "建設部",
    "道路": "建設部",
    "土木": "建設部",
    "河川": "建設部",
    "排水": "建設部",
    "福祉": "福祉部",
    "避難所": "福祉部",
    "高齢者": "福祉部",
    "要配慮": "福祉部",
    "広報": "総務部",
    "本部": "総務部",
    "災害対策本部": "総務部",
}
