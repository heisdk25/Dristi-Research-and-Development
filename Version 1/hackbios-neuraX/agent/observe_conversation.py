"""
Drishti Live LLM Conversation Observation Terminal

Runs a dedicated observation terminal that streams and displays LLM conversations,
STT speech recognition, tool calls, and latency metrics in real-time.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure standard output uses UTF-8 to prevent charmap errors on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
    COLOR_AVAILABLE = True
except ImportError:
    COLOR_AVAILABLE = False
    class _Empty:
        def __getattr__(self, name):
            return ""
    Fore = _Empty()
    Style = _Empty()

C_RESET = Style.RESET_ALL if COLOR_AVAILABLE else ""
C_BOLD = Style.BRIGHT if COLOR_AVAILABLE else ""
C_DIM = getattr(Style, "DIM", "") if COLOR_AVAILABLE else ""

C_BORDER = getattr(Fore, "CYAN", "") if COLOR_AVAILABLE else ""
C_TITLE = (Style.BRIGHT + getattr(Fore, "CYAN", "")) if COLOR_AVAILABLE else ""
C_USER_LABEL = (Style.BRIGHT + getattr(Fore, "YELLOW", "")) if COLOR_AVAILABLE else ""
C_USER_TEXT = getattr(Fore, "WHITE", "") if COLOR_AVAILABLE else ""
C_TOOL_LABEL = (Style.BRIGHT + getattr(Fore, "MAGENTA", "")) if COLOR_AVAILABLE else ""
C_TOOL_TEXT = getattr(Fore, "LIGHTWHITE_EX", "") if COLOR_AVAILABLE else ""
C_AI_LABEL = (Style.BRIGHT + getattr(Fore, "GREEN", "")) if COLOR_AVAILABLE else ""
C_AI_TEXT = (Style.BRIGHT + getattr(Fore, "LIGHTGREEN_EX", "")) if COLOR_AVAILABLE else ""
C_METRIC_LABEL = (Style.BRIGHT + getattr(Fore, "BLUE", "")) if COLOR_AVAILABLE else ""
C_METRIC_TEXT = getattr(Fore, "LIGHTCYAN_EX", "") if COLOR_AVAILABLE else ""
C_ALERT = (Style.BRIGHT + getattr(Fore, "LIGHTRED_EX", "")) if COLOR_AVAILABLE else ""


def render_card(turn: dict) -> None:
    width = 76
    h_line = "═" * (width - 2)

    turn_id = turn.get("turn_id", 1)
    timestamp = turn.get("timestamp", "")
    mode = str(turn.get("mode", "assistant")).upper()

    header = f" 💬 [LLM CONVERSATION TURN #{turn_id}]  |  {timestamp}  |  MODE: {mode} "

    lines = []
    lines.append(f"\n{C_BORDER}╔{h_line}╗{C_RESET}")
    lines.append(f"{C_BORDER}║{C_TITLE}{header.center(width - 2)}{C_BORDER}║{C_RESET}")
    lines.append(f"{C_BORDER}╠{h_line}╣{C_RESET}")

    # User
    lang = turn.get("user_language")
    lang_info = f" [Language: {lang}]" if lang else ""
    lines.append(f"{C_BORDER}║ {C_USER_LABEL}🎤 USER SPEECH (STT):{lang_info}{C_RESET}")
    user_query = turn.get("user_query") or "[No voice input]"
    lines.append(f"{C_BORDER}║   {C_USER_TEXT}\"{user_query}\"{C_RESET}")

    # Tools
    tools = turn.get("tools", [])
    if tools:
        lines.append(f"{C_BORDER}║{C_RESET}")
        lines.append(f"{C_BORDER}║ {C_TOOL_LABEL}⚙️  TOOL EXECUTIONS ({len(tools)}):{C_RESET}")
        for t in tools:
            args = f" {json.dumps(t.get('arguments', {}), ensure_ascii=False)}" if t.get("arguments") else ""
            err = f" {C_ALERT}(FAILED){C_RESET}" if t.get("is_error") else ""
            dur = f" [{t.get('duration_ms', 0):.0f}ms]" if t.get("duration_ms") else ""
            lines.append(f"{C_BORDER}║   {C_TOOL_TEXT}• {t.get('name')}({args.strip()}){err}{dur} ➔ \"{t.get('output', '')}\"{C_RESET}")

    # Vision calls
    vision = turn.get("vision", [])
    if vision:
        lines.append(f"{C_BORDER}║{C_RESET}")
        lines.append(f"{C_BORDER}║ {C_TOOL_LABEL}👁️  VISION LLM INFERENCES ({len(vision)}):{C_RESET}")
        for v in vision:
            dur = f" [{v.get('duration_ms', 0):.0f}ms]" if v.get("duration_ms") else ""
            lines.append(f"{C_BORDER}║   {C_TOOL_TEXT}• [{v.get('call_type', '').upper()}] model={v.get('model')}{dur} ➔ \"{v.get('output', '')}\"{C_RESET}")

    # Assistant Response
    lines.append(f"{C_BORDER}║{C_RESET}")
    interrupted = f" {C_ALERT}[INTERRUPTED]{C_RESET}" if turn.get("interrupted") else ""
    lines.append(f"{C_BORDER}║ {C_AI_LABEL}🤖 LLM ASSISTANT RESPONSE:{interrupted}{C_RESET}")
    assistant_resp = turn.get("assistant_response", "")
    lines.append(f"{C_BORDER}║   {C_AI_TEXT}\"{assistant_resp}\"{C_RESET}")

    # Metrics
    metrics = turn.get("metrics", {})
    lines.append(f"{C_BORDER}║{C_RESET}")
    metric_parts = []
    if "transcription_delay_ms" in metrics:
        metric_parts.append(f"STT: {metrics['transcription_delay_ms']:.0f}ms")
    if "llm_ttft_ms" in metrics:
        metric_parts.append(f"LLM TTFT: {metrics['llm_ttft_ms']:.0f}ms")
    if "llm_tps" in metrics:
        metric_parts.append(f"Speed: {metrics['llm_tps']} tok/s")
    if "tts_ttfb_ms" in metrics:
        metric_parts.append(f"TTS TTFB: {metrics['tts_ttfb_ms']:.0f}ms")
    if "e2e_latency_s" in metrics:
        metric_parts.append(f"Turn E2E: {metrics['e2e_latency_s']}s")

    metrics_summary = "  |  ".join(metric_parts) if metric_parts else "Duration: ~" + str(metrics.get("e2e_latency_s", "0.5")) + "s"
    lines.append(f"{C_BORDER}║ {C_METRIC_LABEL}⚡ LATENCY & OBSERVATION METRICS:{C_RESET}")
    lines.append(f"{C_BORDER}║   {C_METRIC_TEXT}{metrics_summary}{C_RESET}")

    lines.append(f"{C_BORDER}╚{h_line}╝\n{C_RESET}")
    print("\n".join(lines))
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Live LLM Conversation Observation Viewer")
    parser.add_argument("--history", type=int, default=5, help="Number of past turns to display immediately")
    parser.add_argument("--log-path", type=str, default="", help="Path to jsonl conversation file")
    args = parser.parse_args()

    default_jsonl = Path(__file__).resolve().parent / "logs" / "llm_conversation.jsonl"
    jsonl_path = Path(args.log_path) if args.log_path else default_jsonl

    width = 76
    bar = "=" * width
    print(f"\n{C_TITLE}{bar}{C_RESET}")
    print(f"{C_TITLE}       Drishti Live LLM Conversation Observation Terminal       {C_RESET}")
    print(f"{C_BORDER}         Streaming live conversation turns and LLM latency         {C_RESET}")
    print(f"{C_DIM} Watching: {jsonl_path}{C_RESET}")
    print(f"{C_DIM} Press Ctrl+C at any time to exit.{C_RESET}")
    print(f"{C_TITLE}{bar}{C_RESET}\n")

    # If log file doesn't exist yet, wait for agent to start
    if not jsonl_path.exists():
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"{C_DIM}Waiting for Drishti Agent to begin first conversation turn...{C_RESET}")

    # Read existing entries
    seen_lines = 0
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = [line.strip() for line in f if line.strip()]
            seen_lines = len(all_lines)
            recent = all_lines[-args.history :] if args.history > 0 else []
            if recent:
                print(f"{C_DIM}--- Showing {len(recent)} Most Recent Turn(s) ---{C_RESET}")
                for r in recent:
                    try:
                        render_card(json.loads(r))
                    except Exception:
                        pass
                print(f"{C_DIM}--- Live Observation Stream Active ---{C_RESET}\n")

    # Continuously tail file
    try:
        while True:
            if not jsonl_path.exists():
                time.sleep(0.5)
                continue

            with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]
                if len(lines) > seen_lines:
                    for new_line in lines[seen_lines:]:
                        try:
                            render_card(json.loads(new_line))
                        except Exception:
                            pass
                    seen_lines = len(lines)
            time.sleep(0.3)
    except KeyboardInterrupt:
        print(f"\n{C_TITLE}Observation session ended by user.{C_RESET}\n")


if __name__ == "__main__":
    main()
