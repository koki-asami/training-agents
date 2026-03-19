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
        """Change the interval between events at runtime."""
        self.clock.event_interval = seconds
        logger.info("event_interval_changed", seconds=seconds)

    async def _simulation_loop(self):
        """Event-driven simulation loop.

        Advances to the next event's time, processes it, then waits
        the configured interval before proceeding to the next event.
        """
        # Get sorted event times
        event_index = 0
        sorted_events = sorted(self.config.events, key=lambda e: e.scheduled_time)

        while self._running and event_index < len(sorted_events):
            try:
                # Wait for interval (respects pause)
                if event_index > 0:
                    await self.clock.wait_interval()

                if not self._running:
                    break

                # Advance simulation time to next event's time
                next_event = sorted_events[event_index]
                self.clock.advance_to(next_event.scheduled_time)
                await self.state_manager.update_sim_time(self.clock.current_sim_time)

                # Collect all events at this same timestamp
                current_time = next_event.scheduled_time
                batch = []
                while event_index < len(sorted_events) and sorted_events[event_index].scheduled_time == current_time:
                    batch.append(sorted_events[event_index])
                    event_index += 1

                # Mark them in scheduler and process
                for event in batch:
                    event.injected = True
                    event.injected_at = datetime.now()
                    await self._process_event(event)

                # Check for omissions on previous events
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
        """Process a single scenario event."""
        logger.info(
            "processing_event",
            event_id=event.event_id,
            title=event.title,
            target=event.target_agent.value,
        )

        # Have Scenario Master generate the injection message
        injection_text = await self.scenario_master.inject_event(event)

        # Route to appropriate agent or human
        target_role = event.target_agent
        assignment = next(
            (a for a in self.session.assignments if a.role == target_role),
            None,
        )

        if assignment and assignment.is_human:
            # Send to human participant via WebSocket
            msg = SimulationMessage(
                sender=AgentRole.SCENARIO_MASTER.value,
                receiver=f"human:{assignment.participant_id}",
                content=injection_text,
                sim_time=self.clock.current_sim_time,
                message_type=MessageType.REPORT,
                related_event_id=event.event_id,
            )
            await self.message_bus.send(msg)
            self.session.messages.append(msg)

            if self._on_message_callback:
                await self._on_message_callback(msg.model_dump())
        elif target_role.value in self.agents:
            # Send to AI agent and get response
            agent = self.agents[target_role.value]
            agent_response = await agent.respond(injection_text)

            # The AI agent's response goes to the Commander (human or AI)
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
                    sender=target_role.value,
                    receiver=receiver,
                    content=agent_response,
                    sim_time=self.clock.current_sim_time,
                    message_type=MessageType.REPORT,
                    related_event_id=event.event_id,
                )
                await self.message_bus.send(report_msg)
                self.session.messages.append(report_msg)

                if self._on_message_callback:
                    await self._on_message_callback(report_msg.model_dump())

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
