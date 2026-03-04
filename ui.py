"""Architecture Council — Gradio UI."""

import threading
from collections.abc import Generator
from typing import Any

import gradio as gr

from crew import list_sessions, run_council

_YieldT = tuple[list[dict[str, str]], str, str, str, dict[str, Any]]


def run_session(feature: str, stack: str, complexity: int) -> Generator[_YieldT]:
    """Generator that yields streaming updates to the chatbot."""
    if not feature.strip():
        yield [{"role": "assistant", "content": "⚠️ Please enter a feature request."}], "", "", "", {}
        return

    chat_log = []
    results_store = {}

    def on_step(step: str, content: str):
        if step.endswith("_done"):
            key = step.replace("_done", "")
            results_store[key] = content
            truncated = content[:500] + ("..." if len(content) > 500 else "")
            chat_log.append({"role": "assistant", "content": f"✅ **{key.replace('_', ' ').title()}**\n\n{truncated}"})
        else:
            chat_log.append({"role": "assistant", "content": content})

    # Run in thread so we can yield updates
    result = {"session": None, "error": None}

    def worker():
        try:
            result["session"] = run_council(feature, stack, int(complexity), on_step=on_step)
        except Exception as e:
            result["error"] = str(e)
            chat_log.append({"role": "assistant", "content": f"❌ Error: {e}"})

    t = threading.Thread(target=worker)
    t.start()

    prev_len = 0
    while t.is_alive():
        if len(chat_log) > prev_len:
            prev_len = len(chat_log)
            yield (
                chat_log.copy(),
                results_store.get("final_decision", "_Waiting..._"),
                results_store.get("proposal_a", "_Waiting..._"),
                results_store.get("proposal_b", "_Waiting..._"),
                result.get("session") or {},
            )
        t.join(timeout=1.0)

    # Final yield
    session: dict[str, Any] = result["session"] or {}
    yield (
        chat_log.copy(),
        results_store.get("final_decision", "") or result.get("error", "No result") or "",
        results_store.get("proposal_a", ""),
        results_store.get("proposal_b", ""),
        session,
    )


def load_history() -> list[list[str]]:
    sessions = list_sessions()
    if not sessions:
        return [["No sessions yet", "", "", "", ""]]
    return [[s["id"], s["feature"], s["stack"], str(s["complexity"]), s["duration"]] for s in sessions]


def create_app() -> gr.Blocks:
    """Build and return the Gradio app."""
    with gr.Blocks(title="Architecture Council") as app:
        gr.Markdown("# 🏛️ Architecture Council\n*Three AI architects debate your feature — you get the best design.*")

        with gr.Row():
            with gr.Column(scale=3):
                feature_input = gr.Textbox(
                    label="Feature Request",
                    placeholder="e.g. Real-time notifications system for Django e-commerce platform...",
                    lines=4,
                )
            with gr.Column(scale=1):
                tech_stack = gr.Dropdown(
                    ["Django", "FastAPI", "Node.js", "Go", "Spring Boot", "Rails", "Custom"],
                    value="Django",
                    label="Tech Stack",
                )
                complexity = gr.Slider(1, 5, value=3, step=1, label="Complexity")
                btn = gr.Button("▶ Start Council", variant="primary", size="lg")

        council_log = gr.Chatbot(label="Council Discussion", height=400)

        with gr.Tabs():
            with gr.Tab("📋 Final Decision"):
                final_md = gr.Markdown("_Start a session to see the final decision._")
            with gr.Tab("🔵 Architect A (Backend)"):
                arch_a_md = gr.Markdown("_Waiting for Proposal A..._")
            with gr.Tab("🔴 Architect B (Systems)"):
                arch_b_md = gr.Markdown("_Waiting for Proposal B..._")
            with gr.Tab("📊 Session Data"):
                session_json = gr.JSON(label="Session Metadata")
            with gr.Tab("📁 History"):
                history_df = gr.Dataframe(
                    headers=["Session ID", "Feature", "Stack", "Complexity", "Duration"],
                    label="Past Sessions",
                )
                refresh_btn = gr.Button("🔄 Refresh")
                refresh_btn.click(fn=load_history, outputs=history_df)

        btn.click(
            fn=run_session,
            inputs=[feature_input, tech_stack, complexity],
            outputs=[council_log, final_md, arch_a_md, arch_b_md, session_json],
        )

        app.load(fn=load_history, outputs=history_df)

    return app
