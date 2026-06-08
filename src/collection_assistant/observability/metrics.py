"""OTel metric instruments and convenience recording functions."""
import logging
import time
from typing import Optional

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instrument singletons — populated by create_instruments()
# ---------------------------------------------------------------------------
_workflow_counter = None       # Counter: workflows started/completed/errored
_workflow_duration = None      # Histogram(s): end-to-end pipeline seconds
_agent_duration = None         # Histogram: per-agent seconds
_nba_counter = None            # Counter: NBA actions recommended
_dispute_hold_counter = None   # Counter: collection holds triggered
_token_counter = None          # Counter: LLM tokens consumed


def create_instruments(meter) -> None:
    """
    Instantiate all metric instruments from *meter*.
    Called once during setup_observability() after the MeterProvider is ready.
    """
    global _workflow_counter, _workflow_duration, _agent_duration
    global _nba_counter, _dispute_hold_counter, _token_counter

    _workflow_counter = meter.create_counter(
        name="collection_assistant.workflow.total",
        description="Total number of collection workflows",
        unit="1",
    )

    _workflow_duration = meter.create_histogram(
        name="collection_assistant.workflow.duration_seconds",
        description="End-to-end collection pipeline duration",
        unit="s",
    )

    _agent_duration = meter.create_histogram(
        name="collection_assistant.agent.duration_seconds",
        description="Duration of individual agent execution",
        unit="s",
    )

    _nba_counter = meter.create_counter(
        name="collection_assistant.nba.total",
        description="Next Best Action recommendations by action type",
        unit="1",
    )

    _dispute_hold_counter = meter.create_counter(
        name="collection_assistant.dispute_hold.total",
        description="Number of workflows blocked by collection hold",
        unit="1",
    )

    _token_counter = meter.create_counter(
        name="collection_assistant.llm.tokens_total",
        description="LLM tokens consumed by agent and type",
        unit="1",
    )

    _log.info("OTel metric instruments created")


# ---------------------------------------------------------------------------
# Convenience recording functions
# ---------------------------------------------------------------------------

def record_workflow_start(trigger_context: str) -> float:
    """
    Record a workflow start event and return a monotonic start timestamp
    (seconds) suitable for passing to record_workflow_end().
    """
    if _workflow_counter is not None:
        _workflow_counter.add(
            1,
            attributes={
                "status": "started",
                "trigger_context": trigger_context,
            },
        )
    return time.monotonic()


def record_workflow_end(
    start_time: float,
    status: str,
    trigger_context: str,
    nba_action: Optional[str] = None,
    collection_hold: bool = False,
) -> None:
    """
    Record workflow completion metrics:
    - increments workflow_counter with final status
    - records pipeline duration in workflow_duration histogram
    - increments nba_counter if an action was recommended
    - increments dispute_hold_counter if a collection hold was active
    """
    elapsed = time.monotonic() - start_time

    if _workflow_counter is not None:
        _workflow_counter.add(
            1,
            attributes={
                "status": status,
                "trigger_context": trigger_context,
            },
        )

    if _workflow_duration is not None:
        _workflow_duration.record(
            elapsed,
            attributes={"trigger_context": trigger_context},
        )

    if nba_action and _nba_counter is not None:
        _nba_counter.add(
            1,
            attributes={
                "action": nba_action,
                "trigger_context": trigger_context,
            },
        )

    if collection_hold and _dispute_hold_counter is not None:
        _dispute_hold_counter.add(1)


def record_agent_run(
    agent_name: str,
    stage: int,
    elapsed_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """
    Record per-agent execution duration and token usage.

    Parameters
    ----------
    agent_name:
        Name of the agent (e.g. "customer_profile", "nba").
    stage:
        Pipeline stage number (1, 2, or 3).
    elapsed_seconds:
        Wall-clock duration of the agent's run.
    input_tokens:
        Prompt tokens consumed (0 if unavailable).
    output_tokens:
        Completion tokens consumed (0 if unavailable).
    """
    stage_label = str(stage)

    if _agent_duration is not None:
        _agent_duration.record(
            elapsed_seconds,
            attributes={
                "agent_name": agent_name,
                "stage": stage_label,
            },
        )

    if _token_counter is not None:
        if input_tokens:
            _token_counter.add(
                input_tokens,
                attributes={
                    "agent_name": agent_name,
                    "token_type": "input",
                },
            )
        if output_tokens:
            _token_counter.add(
                output_tokens,
                attributes={
                    "agent_name": agent_name,
                    "token_type": "output",
                },
            )
