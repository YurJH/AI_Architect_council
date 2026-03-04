"""Architecture Council — CrewAI orchestration."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml
from crewai import Agent, Crew, Task, Process

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output" / "sessions"


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


def _make_agents(agents_cfg: dict) -> dict[str, Agent]:
    """Create CrewAI agents from config. Model routing via LiteLLM prefixes."""
    model_map = {
        "solution_architect": os.getenv("SA_MODEL", "anthropic/claude-opus-4-6"),
        "senior_architect_a": os.getenv("ARCH_A_MODEL", "anthropic/claude-sonnet-4-6"),
        "senior_architect_b": os.getenv("ARCH_B_MODEL", "gemini/gemini-3.1-pro-preview"),
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


def run_council(
    feature_request: str,
    tech_stack: str = "Django",
    complexity: int = 3,
    on_step: Callable[[str, str], None] | None = None,
) -> dict:
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

    session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    token_counts = {}
    t0 = time.time()

    # --- Step 1: Formulate the challenge ---
    notify("formulation", "🎯 Solution Architect is formulating the challenge...")
    task_formulate = Task(
        description=tasks_cfg["formulate_task"]["description"].format(
            feature_request=feature_request,
            tech_stack=tech_stack,
            complexity=complexity,
        ),
        expected_output=tasks_cfg["formulate_task"]["expected_output"],
        agent=agents["solution_architect"],
    )
    crew1 = Crew(agents=[agents["solution_architect"]], tasks=[task_formulate], verbose=True)
    result1 = crew1.kickoff()
    results["formulation"] = str(result1)
    notify("formulation_done", results["formulation"])

    # --- Step 2: Proposals (could be parallel, but sequential for clarity) ---
    notify("proposal_a", "🔵 Senior Architect A (Backend) is working on proposal...")
    task_prop_a = Task(
        description=tasks_cfg["proposal_a"]["description"].format(
            formulated_challenge=results["formulation"],
        ),
        expected_output=tasks_cfg["proposal_a"]["expected_output"],
        agent=agents["senior_architect_a"],
    )
    crew2a = Crew(agents=[agents["senior_architect_a"]], tasks=[task_prop_a], verbose=True)
    result2a = crew2a.kickoff()
    results["proposal_a"] = str(result2a)
    notify("proposal_a_done", results["proposal_a"])

    notify("proposal_b", "🔴 Senior Architect B (Systems) is working on proposal...")
    task_prop_b = Task(
        description=tasks_cfg["proposal_b"]["description"].format(
            formulated_challenge=results["formulation"],
        ),
        expected_output=tasks_cfg["proposal_b"]["expected_output"],
        agent=agents["senior_architect_b"],
    )
    crew2b = Crew(agents=[agents["senior_architect_b"]], tasks=[task_prop_b], verbose=True)
    result2b = crew2b.kickoff()
    results["proposal_b"] = str(result2b)
    notify("proposal_b_done", results["proposal_b"])

    # --- Step 3: Cross-critiques ---
    notify("critique_a", "🔵 Architect A is reviewing Proposal B...")
    task_crit_a = Task(
        description=tasks_cfg["critique_a"]["description"].format(
            proposal_b_text=results["proposal_b"],
        ),
        expected_output=tasks_cfg["critique_a"]["expected_output"],
        agent=agents["senior_architect_a"],
    )
    crew3a = Crew(agents=[agents["senior_architect_a"]], tasks=[task_crit_a], verbose=True)
    result3a = crew3a.kickoff()
    results["critique_a"] = str(result3a)
    notify("critique_a_done", results["critique_a"])

    notify("critique_b", "🔴 Architect B is reviewing Proposal A...")
    task_crit_b = Task(
        description=tasks_cfg["critique_b"]["description"].format(
            proposal_a_text=results["proposal_a"],
        ),
        expected_output=tasks_cfg["critique_b"]["expected_output"],
        agent=agents["senior_architect_b"],
    )
    crew3b = Crew(agents=[agents["senior_architect_b"]], tasks=[task_crit_b], verbose=True)
    result3b = crew3b.kickoff()
    results["critique_b"] = str(result3b)
    notify("critique_b_done", results["critique_b"])

    # --- Step 4: Final decision ---
    notify("final", "⚖️ Solution Architect is making the final decision...")
    task_final = Task(
        description=tasks_cfg["final_decision"]["description"].format(
            proposal_a_text=results["proposal_a"],
            proposal_b_text=results["proposal_b"],
            critique_a_text=results["critique_a"],
            critique_b_text=results["critique_b"],
        ),
        expected_output=tasks_cfg["final_decision"]["expected_output"],
        agent=agents["solution_architect"],
    )
    crew4 = Crew(agents=[agents["solution_architect"]], tasks=[task_final], verbose=True)
    result4 = crew4.kickoff()
    results["final_decision"] = str(result4)
    notify("final_done", results["final_decision"])

    duration = time.time() - t0

    # --- Save session ---
    session = {
        "id": session_id,
        "feature": feature_request,
        "tech_stack": tech_stack,
        "complexity": complexity,
        "duration_sec": round(duration, 1),
        "agents": {
            "solution_architect": {"model": os.getenv("SA_MODEL", "anthropic/claude-opus-4-6")},
            "senior_architect_a": {"model": os.getenv("ARCH_A_MODEL", "anthropic/claude-sonnet-4-6")},
            "senior_architect_b": {"model": os.getenv("ARCH_B_MODEL", "gemini/gemini-3.1-pro-preview")},
        },
        "results": results,
    }

    (session_dir / "session.json").write_text(json.dumps(session, indent=2, ensure_ascii=False))
    for key, content in results.items():
        (session_dir / f"{key}.md").write_text(content)

    # Full transcript
    transcript = f"# Architecture Council — {session_id}\n\n"
    transcript += f"**Feature:** {feature_request}\n**Stack:** {tech_stack} | **Complexity:** {complexity}/5\n\n"
    for key, content in results.items():
        transcript += f"---\n## {key.replace('_', ' ').title()}\n\n{content}\n\n"
    (session_dir / "full_transcript.md").write_text(transcript)

    return session


def list_sessions() -> list[dict]:
    """List all past sessions."""
    sessions = []
    if not OUTPUT_DIR.exists():
        return sessions
    for d in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        meta = d / "session.json"
        if meta.exists():
            data = json.loads(meta.read_text())
            sessions.append({
                "id": data["id"],
                "feature": data["feature"][:80],
                "stack": data.get("tech_stack", "?"),
                "complexity": data.get("complexity", "?"),
                "duration": f"{data.get('duration_sec', 0)}s",
            })
    return sessions
