"""Simulation runner - main loop that orchestrates the entire training session."""


import asyncio
import json
from datetime import datetime

import structlog

from src.agents.department_agents import (
    ConstructionAgent,
    FireDepartmentAgent,
    GeneralAffairsAgent,
    WelfareAgent,
)
from src.agents.resident_agent import ResidentAgent, WeatherAgent
from src.agents.scenario_master import ScenarioMaster
from src.engine.adaptation_engine import AdaptationEngine
from src.engine.event_scheduler import EventScheduler
from src.engine.message_bus import MessageBus
from src.engine.simulation_clock import SimulationClock
from src.engine.state_manager import StateManager
from src.engine.scenario_updater import ScenarioUpdater
from src.engine.task_manager import TaskManager
from src.models.enums import AgentRole, DifficultyLevel, MessageType, SimulationPhase
from src.models.messages import SimulationMessage
from src.models.scenario import ScenarioConfig, ScenarioEvent
from src.models.scoring import EventScore
from src.models.session import AgentAssignment, SimulationSession
from src.models.state import ResourceState, RiverState, RoadState, ShelterState

logger = structlog.get_logger()


class SimulationRunner:
    """Main simulation orchestrator.

    Manages the simulation loop:
    1. Advance clock
    2. Check for due events
    3. Inject events via Scenario Master -> target agents
    4. Route messages between agents and humans
    5. Check for omissions and adapt
    6. Repeat
    """

    def __init__(self, session: SimulationSession):
        self.session = session
        self.config = session.config

        # Core engine components
        self.state_manager = StateManager(session.session_id)
        self.message_bus = MessageBus()
        self.clock = SimulationClock.from_difficulty(
            self.config.difficulty, self.config.sim_start_time
        )
        self.scheduler = EventScheduler()

        # Agents
        self.scenario_master: ScenarioMaster | None = None
        self.agents: dict[str, object] = {}  # role_value -> BaseAgent

        # Adaptation
        self.adaptation_engine: AdaptationEngine | None = None

        # Task tracking
        self.task_manager = TaskManager()

        # Scenario revision tracking
        self.scenario_updater: ScenarioUpdater | None = None

        # Control
        self._running = False

        # Callbacks for WebSocket integration
        self._on_message_callback = None
        self._on_state_change_callback = None

    def set_message_callback(self, callback):
        """Set callback for when messages should be sent to frontend."""
        self._on_message_callback = callback

    def set_state_change_callback(self, callback):
        """Set callback for state changes to broadcast to frontend."""
        self._on_state_change_callback = callback

    async def initialize(self):
        """Set up all components for the simulation."""
        logger.info("initializing_simulation", session_id=self.session.session_id)

        # Initialize state with sample data (in production, load from GeoJSON)
        await self.state_manager.initialize(
            rivers=self._create_sample_rivers(),
            roads=self._create_sample_roads(),
            shelters=self._create_sample_shelters(),
            resources=ResourceState(),
        )

        # Load events into scheduler
        self.scheduler.load_events(self.config.events)

        # Create Scenario Master
        self.scenario_master = ScenarioMaster(
            config=self.config,
            state_manager=self.state_manager,
            message_bus=self.message_bus,
        )

        # Create AI agents for non-human roles
        municipality = self.config.municipality
        for assignment in self.session.assignments:
            if assignment.is_human:
                continue  # Humans connect via WebSocket

            role = assignment.role
            if role == AgentRole.FIRE_DEPARTMENT:
                self.agents[role.value] = FireDepartmentAgent(municipality, self.state_manager)
            elif role == AgentRole.CONSTRUCTION:
                self.agents[role.value] = ConstructionAgent(municipality, self.state_manager)
            elif role == AgentRole.WELFARE:
                self.agents[role.value] = WelfareAgent(municipality, self.state_manager)
            elif role == AgentRole.GENERAL_AFFAIRS:
                self.agents[role.value] = GeneralAffairsAgent(
                    municipality, self.state_manager, self.config.difficulty
                )
            elif role == AgentRole.WEATHER:
                self.agents[role.value] = WeatherAgent(municipality, self.state_manager)
            elif role == AgentRole.RESIDENT:
                instance_id = assignment.agent_instance_id or "resident_0"
                self.agents[instance_id] = ResidentAgent(
                    municipality=municipality,
                    area="中央地区",
                    state_manager=self.state_manager,
                    instance_id=instance_id,
                )

        # Set up adaptation engine
        self.adaptation_engine = AdaptationEngine(
            self.scenario_master, self.state_manager, self.config.difficulty
        )

        # Set up scenario updater
        self.scenario_updater = ScenarioUpdater(self.scenario_master, self.state_manager)
        # Register all events for revision tracking
        for event in self.config.events:
            self.scenario_updater.register_event(event)

        # Subscribe Scenario Master to all messages
        self.message_bus.subscribe_broadcast()

        self.session.state = self.state_manager.state
        logger.info("simulation_initialized", agent_count=len(self.agents))

    async def start(self):
        """Start the simulation loop."""
        if not self.scenario_master:
            await self.initialize()

        self._running = True
        self.clock.start()
        await self.state_manager.update_phase(SimulationPhase.RUNNING)
        self.session.phase = SimulationPhase.RUNNING
        self.session.started_at = datetime.now()

        logger.info("simulation_started", session_id=self.session.session_id)

        # Start the main loop
        asyncio.create_task(self._simulation_loop())

    async def stop(self):
        """Stop the simulation."""
        self._running = False
        self.clock.stop()
        await self.state_manager.update_phase(SimulationPhase.COMPLETED)
        self.session.phase = SimulationPhase.COMPLETED
        self.session.ended_at = datetime.now()
        logger.info("simulation_stopped", session_id=self.session.session_id)

    async def handle_human_message(
        self,
        participant_id: str,
        role: AgentRole,
        content: str,
        target_role: AgentRole | None = None,
    ) -> list[SimulationMessage]:
        """Process a message from a human participant.

        Returns response messages from AI agents.
        """
        sim_time = self.clock.current_sim_time

        # Create the incoming message
        sender = f"human:{participant_id}"
        receiver = target_role.value if target_role else "broadcast"

        msg = SimulationMessage(
            sender=sender,
            receiver=receiver,
            content=content,
            sim_time=sim_time,
            message_type=MessageType.ORDER if role == AgentRole.COMMANDER else MessageType.REPORT,
        )
        await self.message_bus.send(msg)
        self.session.messages.append(msg)

        # Match human action against tracked tasks
        self.task_manager.match_action(content, role.value)

        # Check if this responds to any tracked events
        for event in self.scheduler.get_unresponded_events():
            # Simple heuristic: if the message relates to the event's topic
            if not event.response_received:
                event.response_received = True
                event.response_at = datetime.now()
                self.adaptation_engine.mark_responded(event.event_id)

                # Evaluate the response
                elapsed = (datetime.now() - event.injected_at).total_seconds() / 60 if event.injected_at else 0
                evaluation = await self.adaptation_engine.evaluate_and_adapt(
                    event, content, elapsed
                )
                score = EventScore(
                    event_id=event.event_id,
                    participant_id=participant_id,
                    score=evaluation.get("score", 3),
                    response_time_minutes=elapsed,
                    action_taken=content,
                    expected_action=event.expected_actions,
                    evaluation_notes=evaluation.get("evaluation_notes", ""),
                )
                self.session.scores.append(score)

                # Update scenario based on evaluation
                if self.scenario_updater:
                    await self.scenario_updater.update_event_from_action(
                        event, content, evaluation.get("score", 3),
                        self.clock.sim_time_str,
                    )
                break

        # Get responses from target AI agents
        responses = []
        if target_role and target_role.value in self.agents:
            agent = self.agents[target_role.value]
            response_text = await agent.respond(content)
            response_msg = SimulationMessage(
                sender=target_role.value,
                receiver=sender,
                content=response_text,
                sim_time=sim_time,
                message_type=MessageType.REPORT,
            )
            await self.message_bus.send(response_msg)
            self.session.messages.append(response_msg)
            responses.append(response_msg)
        elif receiver == "broadcast":
            # Broadcast: get responses from all AI department agents
            for role_val, agent in self.agents.items():
                if role_val in [r.value for r in [
                    AgentRole.GENERAL_AFFAIRS,
                    AgentRole.FIRE_DEPARTMENT,
                    AgentRole.CONSTRUCTION,
                    AgentRole.WELFARE,
                ]]:
                    response_text = await agent.respond(content)
                    response_msg = SimulationMessage(
                        sender=role_val,
                        receiver=sender,
                        content=response_text,
                        sim_time=sim_time,
                        message_type=MessageType.REPORT,
                    )
                    await self.message_bus.send(response_msg)
                    self.session.messages.append(response_msg)
                    responses.append(response_msg)

        return responses

    async def set_event_interval(self, seconds: float):
        """Change the time scale (real seconds per sim minute) at runtime."""
        self.clock.seconds_per_sim_minute = seconds
        logger.info("time_scale_changed", seconds_per_sim_minute=seconds)

    async def _simulation_loop(self):
        """Scenario-interval-driven simulation loop.

        Waits proportional to the time gap between consecutive events
        in the uploaded scenario. The sim_time is rebased from the
        scenario's first event time to the training start time.
        """
        sorted_events = sorted(self.config.events, key=lambda e: e.scheduled_time)
        if not sorted_events:
            return

        # Rebase: compute offset from scenario's first event to training start time
        # e.g., scenario starts at 13:18, training starts now -> offset applied
        scenario_base = sorted_events[0].scheduled_time
        training_base = self.config.sim_start_time  # defaults to scenario's first event
        self.clock.advance_to(training_base)

        logger.info(
            "simulation_loop_starting",
            scenario_time_range=f"{sorted_events[0].scheduled_time}-{sorted_events[-1].scheduled_time}",
            training_start=training_base,
            total_events=len(sorted_events),
            seconds_per_sim_minute=self.clock.seconds_per_sim_minute,
        )

        event_index = 0
        prev_time = scenario_base

        while self._running and event_index < len(sorted_events):
            try:
                next_event = sorted_events[event_index]
                current_scenario_time = next_event.scheduled_time

                # Wait proportional to scenario time gap
                if event_index > 0 and current_scenario_time != prev_time:
                    await self.clock.wait_for_gap(prev_time, current_scenario_time)
                elif event_index > 0:
                    # Same timestamp as previous -> small pause for readability
                    await asyncio.sleep(2.0)

                if not self._running:
                    break

                # Compute rebased sim time: training_base + (current - scenario_base)
                bh, bm = map(int, scenario_base.split(":"))
                ch, cm = map(int, current_scenario_time.split(":"))
                th, tm = map(int, training_base.split(":"))
                offset_min = (ch * 60 + cm) - (bh * 60 + bm)
                rebased_min = (th * 60 + tm) + offset_min
                rebased_time = f"{rebased_min // 60:02d}:{rebased_min % 60:02d}"

                self.clock.advance_to(rebased_time)
                await self.state_manager.update_sim_time(self.clock.current_sim_time)

                # Collect all events at this same scenario timestamp
                batch = []
                while (
                    event_index < len(sorted_events)
                    and sorted_events[event_index].scheduled_time == current_scenario_time
                ):
                    batch.append(sorted_events[event_index])
                    event_index += 1

                # Process batch
                for event in batch:
                    event.injected = True
                    event.injected_at = datetime.now()
                    # Update event's scheduled_time to rebased time for display
                    event.scheduled_time = rebased_time
                    self.task_manager.extract_from_event(event)
                    await self._process_event(event)

                prev_time = current_scenario_time

                # Mark overdue tasks
                self.task_manager.mark_overdue(self.clock.sim_time_str)

                # Check for omissions
                if self.adaptation_engine:
                    consequences = await self.adaptation_engine.check_omissions(
                        self.clock.current_sim_time
                    )
                    for consequence in consequences:
                        await self._handle_consequence(consequence)

                # Periodic snapshot
                if event_index % 5 == 0:
                    await self.state_manager.take_snapshot()

                # Notify frontend
                if self._on_state_change_callback:
                    await self._on_state_change_callback(self.state_manager.get_state_summary())

            except Exception as e:
                logger.error("simulation_loop_error", error=str(e))
                await asyncio.sleep(1)

        # All events processed
        if self._running:
            logger.info("all_events_processed", total=len(sorted_events))
            if self._on_state_change_callback:
                await self._on_state_change_callback(self.state_manager.get_state_summary())

    async def _process_event(self, event: ScenarioEvent):
        """Process a single scenario event.

        Flow:
        1. Build injection text (LLM-generated or fallback from event data)
        2. Route to the *responsible department* (not source agent)
        3. If dept is human → send directly via WebSocket
        4. If dept is AI → AI processes and reports to Commander
        """
        from src.models.enums import DEPT_NAME_TO_ROLE

        # Resolve responsible department role
        dept_role = DEPT_NAME_TO_ROLE.get(
            event.responsible_department, event.target_agent
        )

        logger.info(
            "processing_event",
            event_id=event.event_id,
            title=event.title,
            source=event.source,
            responsible_dept=event.responsible_department,
            dept_role=dept_role.value,
        )

        # Build injection text: try LLM, fall back to structured text
        try:
            injection_text = await self.scenario_master.inject_event(event)
        except Exception as e:
            logger.warning("llm_injection_failed", event_id=event.event_id, error=str(e))
            injection_text = ""

        if not injection_text or len(injection_text.strip()) < 10:
            # Fallback: structured message from event data
            injection_text = self._build_fallback_injection(event)

        # Find assignment for responsible department
        assignment = next(
            (a for a in self.session.assignments if a.role == dept_role),
            None,
        )

        # Send to all human participants (broadcast approach for training)
        await self._deliver_event_message(event, injection_text, dept_role, assignment)

    def _build_fallback_injection(self, event: ScenarioEvent) -> str:
        """Build a structured injection message without LLM."""
        lines = []
        lines.append(f"【状況付与 #{event.event_id}】")
        lines.append(f"情報源: {event.source}")
        lines.append(f"")
        if event.content_trainee:
            lines.append(event.content_trainee)
        elif event.title:
            lines.append(event.title)
        if event.weather_info:
            lines.append(f"\n[気象情報] {event.weather_info}")
        if event.river_info:
            lines.append(f"[河川情報] {event.river_info}")
        return "\n".join(lines)

    async def _deliver_event_message(
        self,
        event: ScenarioEvent,
        injection_text: str,
        dept_role: AgentRole,
        assignment,
    ):
        """Deliver an event message to the responsible department."""
        if assignment and assignment.is_human:
            # Send to human participant via WebSocket
            msg = SimulationMessage(
                sender=event.source,
                receiver=f"human:{assignment.participant_id}",
                content=injection_text,
                sim_time=self.clock.current_sim_time,
                message_type=MessageType.REPORT,
                related_event_id=event.event_id,
                metadata={
                    "source": event.source,
                    "responsible_department": event.responsible_department,
                    "event_title": event.title,
                },
            )
            await self.message_bus.send(msg)
            self.session.messages.append(msg)

            if self._on_message_callback:
                await self._on_message_callback(msg.model_dump())
        elif dept_role.value in self.agents:
            # Send to AI agent and get response
            agent = self.agents[dept_role.value]
            try:
                agent_response = await agent.respond(injection_text)
            except Exception as e:
                logger.warning("agent_respond_failed", role=dept_role.value, error=str(e))
                agent_response = f"（{event.responsible_department}が対応を検討中...）"

            # Report to Commander (human or AI)
            commander_assignment = next(
                (a for a in self.session.assignments if a.role == AgentRole.COMMANDER),
                None,
            )
            if commander_assignment:
                receiver = (
                    f"human:{commander_assignment.participant_id}"
                    if commander_assignment.is_human
                    else AgentRole.COMMANDER.value
                )
                report_msg = SimulationMessage(
                    sender=dept_role.value,
                    receiver=receiver,
                    content=agent_response,
                    sim_time=self.clock.current_sim_time,
                    message_type=MessageType.REPORT,
                    related_event_id=event.event_id,
                    metadata={
                        "source": event.source,
                        "responsible_department": event.responsible_department,
                    },
                )
                await self.message_bus.send(report_msg)
                self.session.messages.append(report_msg)

                if self._on_message_callback:
                    await self._on_message_callback(report_msg.model_dump())
        else:
            # No assignment found - broadcast to all
            logger.warning("no_assignment_for_dept", dept=event.responsible_department, role=dept_role.value)
            msg = SimulationMessage(
                sender=event.source,
                receiver="broadcast",
                content=injection_text,
                sim_time=self.clock.current_sim_time,
                message_type=MessageType.REPORT,
                related_event_id=event.event_id,
                metadata={
                    "source": event.source,
                    "responsible_department": event.responsible_department,
                },
            )
            await self.message_bus.send(msg)
            self.session.messages.append(msg)

            if self._on_message_callback:
                await self._on_message_callback(msg.model_dump())

        # Track for omission detection
        if self.adaptation_engine:
            self.adaptation_engine.track_event(event, self.clock.current_sim_time)

    async def _handle_consequence(self, consequence: dict):
        """Handle an adaptation consequence (hint or escalation)."""
        if consequence["type"] == "hint" and self.scenario_master:
            hint = await self.scenario_master.provide_hint(consequence["message"])
            if hint:
                # Deliver hint via General Affairs agent
                msg = SimulationMessage(
                    sender=AgentRole.GENERAL_AFFAIRS.value,
                    receiver="broadcast",
                    content=hint,
                    sim_time=self.clock.current_sim_time,
                    message_type=MessageType.HINT,
                )
                await self.message_bus.send(msg)
                self.session.messages.append(msg)

                if self._on_message_callback:
                    await self._on_message_callback(msg.model_dump())

    def _create_sample_rivers(self) -> list[RiverState]:
        return [
            RiverState(
                river_name="白川",
                observation_point="代継橋",
                current_level_m=2.5,
                warning_level_m=4.0,
                danger_level_m=5.2,
            ),
            RiverState(
                river_name="緑川",
                observation_point="中甲橋",
                current_level_m=1.8,
                warning_level_m=3.5,
                danger_level_m=4.5,
            ),
        ]

    def _create_sample_roads(self) -> list[RoadState]:
        return [
            RoadState(road_id="R1", road_name="国道3号"),
            RoadState(road_id="R2", road_name="国道57号"),
            RoadState(road_id="R3", road_name="県道28号"),
            RoadState(road_id="R4", road_name="市道中央通り"),
        ]

    def _create_sample_shelters(self) -> list[ShelterState]:
        return [
            ShelterState(shelter_id="S1", name="中央公民館", area="中央地区", capacity=200),
            ShelterState(shelter_id="S2", name="東部体育館", area="東部地区", capacity=300),
            ShelterState(shelter_id="S3", name="西部小学校", area="西部地区", capacity=150),
            ShelterState(shelter_id="S4", name="南部コミュニティセンター", area="南部地区", capacity=100),
        ]
