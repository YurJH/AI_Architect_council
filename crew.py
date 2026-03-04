"""Architecture Council — CrewAI orchestration."""

import json
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Normalize: CrewAI's native Gemini provider checks GOOGLE_API_KEY first
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from crewai import Agent, Crew, Task  # noqa: E402

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output" / "sessions"


def _load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


def _make_agents(agents_cfg: dict[str, Any]) -> dict[str, Agent]:
    """Create CrewAI agents from config. Model routing via LiteLLM prefixes."""
    model_map = {
        "solution_architect": os.getenv("SA_MODEL", "anthropic/claude-opus-4-6"),
        "senior_architect_a": os.getenv("ARCH_A_MODEL", "anthropic/claude-sonnet-4-6"),
        "senior_architect_b": os.getenv(
            "ARCH_B_MODEL", "gemini/gemini-3.1-pro-preview"
        ),
    }
    agents = {}
    for key, cfg in agents_cfg.items():
        agents[key] = Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            llm=model_map.get(key, "anthropic/claude-sonnet-4-6"),
            verbose=True,
            allow_delegation=False,
        )
    return agents


def _run_step(
    step_key: str,
    task_name: str,
    agent: Agent,
    format_args: dict[str, Any],
    tasks_cfg: dict[str, Any],
    results: dict[str, str],
    notify: Callable[[str, str], None],
    start_message: str,
) -> None:
    """Run a single pipeline step: create Task, Crew, kickoff, store result."""
    notify(step_key, start_message)
    task = Task(
        description=tasks_cfg[task_name]["description"].format(**format_args),
        expected_output=tasks_cfg[task_name]["expected_output"],
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    result = crew.kickoff()
    results[step_key] = str(result)
    notify(step_key + "_done", results[step_key])


def _save_session(session: dict[str, Any], results: dict[str, str]) -> None:
    """Persist session JSON, per-step markdown files, and full transcript."""
    session_dir = OUTPUT_DIR / session["id"]
    session_dir.mkdir(parents=True, exist_ok=True)

    (session_dir / "session.json").write_text(
        json.dumps(session, indent=2, ensure_ascii=False)
    )
    for key, content in results.items():
        (session_dir / f"{key}.md").write_text(content)

    transcript = f"# Architecture Council — {session['id']}\n\n"
    transcript += (
        f"**Feature:** {session['feature']}\n"
        f"**Stack:** {session['tech_stack']} | **Complexity:** {session['complexity']}/5\n\n"
    )
    for key, content in results.items():
        transcript += f"---\n## {key.replace('_', ' ').title()}\n\n{content}\n\n"
    (session_dir / "full_transcript.md").write_text(transcript)


def run_council(
    feature_request: str,
    tech_stack: str = "FastApi",
    complexity: int = 3,
    on_step: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Run a full architecture council session.

    Args:
        feature_request: The feature/system to design.
        tech_stack: Primary technology stack.
        complexity: 1-5 complexity rating.
        on_step: Callback(step_name, markdown_content) for streaming updates.

    Returns:
        Session dict with all outputs and metadata.
    """
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")
    agents = _make_agents(agents_cfg)

    def notify(step: str, content: str):
        if on_step:
            on_step(step, content)

    results: dict[str, str] = {}
    t0 = time.time()

    steps: list[
        tuple[
            str,
            str,
            str,
            dict[str, Any] | Callable[[dict[str, str]], dict[str, Any]],
            str,
        ]
    ] = [
        (
            "formulation",
            "formulate_task",
            "solution_architect",
            {
                "feature_request": feature_request,
                "tech_stack": tech_stack,
                "complexity": complexity,
            },
            "🎯 Solution Architect is formulating the challenge...",
        ),
        (
            "proposal_a",
            "proposal_a",
            "senior_architect_a",
            lambda r: {"formulated_challenge": r["formulation"]},
            "🔵 Senior Architect A (Backend) is working on proposal...",
        ),
        (
            "proposal_b",
            "proposal_b",
            "senior_architect_b",
            lambda r: {"formulated_challenge": r["formulation"]},
            "🔴 Senior Architect B (Systems) is working on proposal...",
        ),
        (
            "critique_a",
            "critique_a",
            "senior_architect_a",
            lambda r: {"proposal_b_text": r["proposal_b"]},
            "🔵 Architect A is reviewing Proposal B...",
        ),
        (
            "critique_b",
            "critique_b",
            "senior_architect_b",
            lambda r: {"proposal_a_text": r["proposal_a"]},
            "🔴 Architect B is reviewing Proposal A...",
        ),
        (
            "final_decision",
            "final_decision",
            "solution_architect",
            lambda r: {
                "proposal_a_text": r["proposal_a"],
                "proposal_b_text": r["proposal_b"],
                "critique_a_text": r["critique_a"],
                "critique_b_text": r["critique_b"],
            },
            "⚖️ Solution Architect is making the final decision...",
        ),
    ]

    for step_key, task_name, agent_key, format_args, start_msg in steps:
        if callable(format_args):
            format_args = format_args(results)
        _run_step(
            step_key,
            task_name,
            agents[agent_key],
            format_args,
            tasks_cfg,
            results,
            notify,
            start_msg,
        )

    duration = time.time() - t0

    session = {
        "id": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "feature": feature_request,
        "tech_stack": tech_stack,
        "complexity": complexity,
        "duration_sec": round(duration, 1),
        "agents": {
            "solution_architect": {
                "model": os.getenv("SA_MODEL", "anthropic/claude-opus-4-6")
            },
            "senior_architect_a": {
                "model": os.getenv("ARCH_A_MODEL", "anthropic/claude-sonnet-4-6")
            },
            "senior_architect_b": {
                "model": os.getenv("ARCH_B_MODEL", "gemini/gemini-3.1-pro-preview")
            },
        },
        "results": results,
    }

    _save_session(session, results)
    return session


def list_sessions() -> list[dict[str, Any]]:
    """List all past sessions."""
    sessions: list[dict[str, Any]] = []
    if not OUTPUT_DIR.exists():
        return sessions
    for d in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        meta = d / "session.json"
        if meta.exists():
            data = json.loads(meta.read_text())
            sessions.append(
                {
                    "id": data["id"],
                    "feature": data["feature"][:80],
                    "stack": data.get("tech_stack", "?"),
                    "complexity": data.get("complexity", "?"),
                    "duration": f"{data.get('duration_sec', 0)}s",
                }
            )
    return sessions
