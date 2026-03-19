"""Task manager - tracks disaster response tasks extracted from scenario events."""

import structlog

from src.models.scenario import ScenarioEvent
from src.models.tasks import DisasterTask, TaskPriority, TaskStatus, extract_tasks_from_event

logger = structlog.get_logger()


class TaskManager:
    """Manages disaster response tasks throughout the simulation.

    Tasks are automatically extracted from scenario events when they are injected.
    Human actions are matched against tasks to update their status.
    """

    def __init__(self):
        self._tasks: list[DisasterTask] = []

    @property
    def tasks(self) -> list[DisasterTask]:
        return self._tasks

    def extract_from_event(self, event: ScenarioEvent) -> list[DisasterTask]:
        """Extract tasks from a scenario event and add to tracking."""
        new_tasks = extract_tasks_from_event(
            event_id=event.event_id,
            sim_time=event.scheduled_time,
            expected_actions=event.expected_actions,
            training_objective=event.training_objective,
            source=event.source,
            target_agent=event.target_agent.value,
        )
        for task in new_tasks:
            task.status = TaskStatus.ACTIVE
        self._tasks.extend(new_tasks)

        logger.info(
            "tasks_extracted",
            event_id=event.event_id,
            task_count=len(new_tasks),
        )
        return new_tasks

    def match_action(self, action_text: str, participant_role: str) -> list[DisasterTask]:
        """Try to match a human action against active tasks.

        Returns list of tasks that were updated.
        """
        matched = []
        for task in self._tasks:
            if task.status not in (TaskStatus.ACTIVE, TaskStatus.OVERDUE):
                continue

            # Keyword matching: check if action text contains key terms from the task
            task_keywords = _extract_keywords(task.title)
            action_lower = action_text.lower()

            match_score = sum(1 for kw in task_keywords if kw in action_lower)
            if match_score >= 2 or (match_score >= 1 and len(task_keywords) <= 2):
                task.status = TaskStatus.IN_PROGRESS
                task.assigned_to = participant_role
                task.notes = action_text[:200]
                matched.append(task)

        return matched

    def complete_task(self, task_id: str, sim_time: str, score: int | None = None):
        """Mark a task as completed."""
        for task in self._tasks:
            if task.task_id == task_id:
                task.status = TaskStatus.COMPLETED
                task.sim_time_completed = sim_time
                if score:
                    task.score = score
                return

    def mark_overdue(self, sim_time: str):
        """Mark active tasks as overdue if they've been waiting too long.

        Simple heuristic: tasks from events > 2 time steps ago.
        """
        active_tasks = [t for t in self._tasks if t.status == TaskStatus.ACTIVE]
        for task in active_tasks:
            if task.sim_time_created and task.sim_time_created < sim_time:
                # If task has been active for a while, check threshold
                try:
                    created_h, created_m = map(int, task.sim_time_created.split(":"))
                    now_h, now_m = map(int, sim_time.split(":"))
                    elapsed_minutes = (now_h * 60 + now_m) - (created_h * 60 + created_m)
                    if elapsed_minutes > 20:  # 20 sim-minutes threshold
                        task.status = TaskStatus.OVERDUE
                except (ValueError, IndexError):
                    pass

    def get_summary(self) -> dict:
        """Get task status summary."""
        total = len(self._tasks)
        by_status = {}
        by_priority = {}
        by_role = {}

        for task in self._tasks:
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1
            by_priority[task.priority.value] = by_priority.get(task.priority.value, 0) + 1
            role = task.responsible_role or "unassigned"
            by_role[role] = by_role.get(role, 0) + 1

        completed = by_status.get("completed", 0) + by_status.get("in_progress", 0)
        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_role": by_role,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
        }

    def get_tasks_for_api(self) -> list[dict]:
        """Serialize all tasks for the API."""
        return [
            {
                "task_id": t.task_id,
                "event_id": t.event_id,
                "title": t.title,
                "description": t.description,
                "responsible_role": t.responsible_role,
                "status": t.status.value,
                "priority": t.priority.value,
                "sim_time_created": t.sim_time_created,
                "sim_time_completed": t.sim_time_completed,
                "assigned_to": t.assigned_to,
                "notes": t.notes,
                "score": t.score,
            }
            for t in self._tasks
        ]


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a task title for matching."""
    # Key action/noun words that are useful for matching
    important_words = [
        "避難", "救助", "救急", "消防", "通行止", "交通規制", "道路", "閉鎖",
        "避難所", "開設", "派遣", "要請", "物資", "給水", "医療", "搬送",
        "警戒", "監視", "水位", "河川", "堤防", "土砂", "倒木",
        "広報", "周知", "防災無線", "住民", "要配慮者", "高齢者",
        "電力", "停電", "通信", "連絡", "報告", "確認", "調査",
        "自衛隊", "県", "応援", "相互",
    ]
    text_lower = text.lower()
    return [w for w in important_words if w in text_lower]
