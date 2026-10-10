"""
Drishti LLM Conversation Observer & Terminal Logger

Provides high-visibility, real-time terminal observation of LLM conversational turns,
speech-to-text transcriptions, tool invocations, vision analysis results,
and latency metrics.

Features:
  - Eye-catching colored terminal observation cards (colorama ANSI).
  - Synchronous / asynchronous event correlation into clean turns.
  - Dual file persistence:
      1. logs/llm_conversation.log   (Human-readable formatted log)
      2. logs/llm_conversation.jsonl (Structured JSON lines per turn)
  - Latency & token metrics breakdown (TTFT, TPS, TTS TTFB, E2E).
  - Safe Unicode & UTF-8 handling on Windows terminals.
"""

import datetime
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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

from concurrent.futures import ThreadPoolExecutor

# Ensure standard output uses UTF-8 to prevent charmap errors on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("drishti-observer")


# ── Color Palette & Styles ──────────────────────────────────────────────

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
C_NOTICE = (Style.BRIGHT + getattr(Fore, "LIGHTYELLOW_EX", "")) if COLOR_AVAILABLE else ""


# ── Data Models ─────────────────────────────────────────────────────────

@dataclass
class ToolExecutionRecord:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    output: str = ""
    is_error: bool = False
    duration_ms: float = 0.0


@dataclass
class VisionCallRecord:
    call_type: str  # "scene_description" or "ocr"
    model: str
    prompt_summary: str
    output: str
    duration_ms: float = 0.0


@dataclass
class ConversationTurn:
    turn_id: int
    timestamp: str
    mode: str = "assistant"
    user_query: str = ""
    user_language: Optional[str] = None
    tools_called: List[ToolExecutionRecord] = field(default_factory=list)
    vision_calls: List[VisionCallRecord] = field(default_factory=list)
    assistant_response: str = ""
    interrupted: bool = False
    metrics: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    completed: bool = False


# ── Conversation Observer Class ─────────────────────────────────────────

class LLMConversationObserver:
    """
    Observes, correlates, and logs all conversational and LLM interactions
    for real-time observation in the terminal and persistence to disk.
    
    Zero-Latency Production Architecture:
      - All file I/O operations are offloaded to a non-blocking background thread pool.
      - Never blocks the real-time LiveKit audio processing or asyncio event loop.
      - Configurable for production headless deployments (Docker/Cloud) via env vars.
    """

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path(__file__).resolve().parent / "logs"

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "llm_conversation.log"
        self.jsonl_file = self.log_dir / "llm_conversation.jsonl"

        # Production toggles
        self.enabled: bool = os.getenv("ENABLE_CONVERSATION_LOGS", "true").strip().lower() in ("true", "1", "yes")
        self.enable_terminal: bool = os.getenv("OBSERVER_TERMINAL_OUTPUT", "true").strip().lower() in ("true", "1", "yes")
        self.max_log_bytes: int = int(os.getenv("OBSERVER_MAX_LOG_BYTES", str(10 * 1024 * 1024)))  # 10 MB default

        # Asynchronous non-blocking background writer to guarantee zero latency impact
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="drishti_obs_writer")

        self.turn_counter: int = 0
        self.active_turn: Optional[ConversationTurn] = None
        self.current_mode: str = "assistant"

        if self.enabled and self.enable_terminal:
            self._print_startup_banner()

    def flush(self) -> None:
        """Flushes pending asynchronous background file writes (useful for clean shutdown or tests)."""
        future = self._executor.submit(lambda: None)
        future.result(timeout=5.0)

    def _print_startup_banner(self) -> None:
        """Prints high-visibility initialization banner to terminal."""
        width = 76
        bar = "=" * width
        print(f"\n{C_TITLE}{bar}{C_RESET}")
        print(f"{C_TITLE} Drishti LLM Conversation Observation Logger Active{C_RESET}".center(width))
        print(f"{C_BORDER} Real-Time Terminal Observation & Streaming Enabled{C_RESET}".center(width))
        print(f"{C_DIM} Log File:   {self.log_file}{C_RESET}".center(width))
        print(f"{C_DIM} JSONL File: {self.jsonl_file}{C_RESET}".center(width))
        print(f"{C_TITLE}{bar}{C_RESET}\n")
        sys.stdout.flush()

    def set_mode(self, mode: str) -> None:
        self.current_mode = mode.lower()

    def start_turn(self, user_transcript: str, language: Optional[str] = None) -> ConversationTurn:
        """Starts or updates a conversation turn with user input."""
        cleaned = user_transcript.strip()
        if not cleaned:
            return self.active_turn or ConversationTurn(
                turn_id=self.turn_counter,
                timestamp=datetime.datetime.now().isoformat(),
                mode=self.current_mode,
            )

        # If previous turn wasn't finished, finalize it first
        if self.active_turn and not self.active_turn.completed and self.active_turn.assistant_response:
            self.finalize_turn()

        self.turn_counter += 1
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.active_turn = ConversationTurn(
            turn_id=self.turn_counter,
            timestamp=now_str,
            mode=self.current_mode,
            user_query=cleaned,
            user_language=language,
            start_time=time.time(),
        )

        # Immediate fast terminal alert for user utterance
        lang_tag = f" [{language}]" if language else ""
        print(f"\n{C_USER_LABEL}🎤 [USER SPEECH (Turn #{self.turn_counter})]{lang_tag}: {C_USER_TEXT}\"{cleaned}\"{C_RESET}")
        sys.stdout.flush()
        return self.active_turn

    def record_tool_call(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        output: str = "",
        is_error: bool = False,
        duration_ms: float = 0.0,
    ) -> None:
        """Records a tool or function executed by the LLM."""
        rec = ToolExecutionRecord(
            name=name,
            arguments=arguments or {},
            output=output,
            is_error=is_error,
            duration_ms=round(duration_ms, 1),
        )

        if not self.active_turn:
            self.active_turn = ConversationTurn(
                turn_id=self.turn_counter + 1,
                timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                mode=self.current_mode,
            )

        self.active_turn.tools_called.append(rec)

        # Immediate fast terminal notification
        dur_str = f" [{duration_ms:.0f}ms]" if duration_ms > 0 else ""
        err_str = f" {C_ALERT}(ERROR){C_RESET}" if is_error else ""
        arg_str = json.dumps(arguments or {}, ensure_ascii=False)
        print(f"{C_TOOL_LABEL}⚙️  [TOOL EXECUTED]{err_str}: {C_TOOL_TEXT}{name}({arg_str}){dur_str} ➔ \"{output[:120]}{'...' if len(output) > 120 else ''}\"{C_RESET}")
        sys.stdout.flush()

    def record_vision_call(
        self,
        call_type: str,
        model: str,
        prompt_summary: str,
        output: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Records a Vision analysis or OCR extraction call."""
        rec = VisionCallRecord(
            call_type=call_type,
            model=model,
            prompt_summary=prompt_summary,
            output=output,
            duration_ms=round(duration_ms, 1),
        )

        if self.active_turn:
            self.active_turn.vision_calls.append(rec)

        tag = "👁️  [VISION SCENE]" if "scene" in call_type.lower() else "📄 [VISION OCR]"
        dur_str = f" [{duration_ms:.0f}ms]" if duration_ms > 0 else ""
        print(f"{C_TOOL_LABEL}{tag} ({model}){dur_str}: {C_TOOL_TEXT}\"{output[:120]}{'...' if len(output) > 120 else ''}\"{C_RESET}")
        sys.stdout.flush()

    def record_assistant_response(
        self,
        response_text: str,
        metrics: Optional[Dict[str, Any]] = None,
        interrupted: bool = False,
    ) -> None:
        """Records the LLM's assistant response text and renders the completed turn."""
        cleaned = response_text.strip()
        if not cleaned:
            return

        if not self.active_turn:
            self.turn_counter += 1
            self.active_turn = ConversationTurn(
                turn_id=self.turn_counter,
                timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                mode=self.current_mode,
                user_query="[Voice/Direct Greeting]",
                start_time=time.time(),
            )

        self.active_turn.assistant_response = cleaned
        self.active_turn.interrupted = interrupted

        if metrics:
            self.active_turn.metrics = self._format_metrics(metrics)

        self.finalize_turn()

    def finalize_turn(self) -> None:
        """Finalizes the active turn, prints the terminal card, and writes to files."""
        if not self.active_turn or self.active_turn.completed:
            return

        turn = self.active_turn
        turn.end_time = time.time()
        turn.completed = True

        # Calculate fallback total duration if not already in metrics
        if "e2e_latency_s" not in turn.metrics and turn.start_time:
            turn.metrics["e2e_latency_s"] = round(turn.end_time - turn.start_time, 2)

        # Render full terminal card
        self._render_terminal_card(turn)

        # Write to log file and jsonl
        self._write_turn_files(turn)

    def record_mode_switch(self, old_mode: str, new_mode: str, source: str = "voice") -> None:
        """Logs mode change events in real time."""
        self.current_mode = new_mode.lower()
        border = "═" * 68
        print(f"\n{C_NOTICE}╔{border}╗{C_RESET}")
        print(f"{C_NOTICE}║ 🔄 [MODE CHANGED] {old_mode.upper()} ➔ {new_mode.upper()} (via {source}){C_RESET}")
        print(f"{C_NOTICE}╚{border}╝\n{C_RESET}")
        sys.stdout.flush()

        # Log event to disk
        self._append_event_to_log(f"MODE_CHANGED: {old_mode} -> {new_mode} ({source})")

    def record_obstacle_alert(self, obstacle: str, position: str = "ahead", distance: str = "") -> None:
        """Logs obstacle alerts received from device."""
        dist_str = f" at {distance}m" if distance else ""
        print(f"{C_ALERT}⚠️  [OBSTACLE ALERT]: {obstacle} at {position}{dist_str}{C_RESET}")
        sys.stdout.flush()
        self._append_event_to_log(f"OBSTACLE_ALERT: {obstacle} at {position}{dist_str}")

    def record_state_change(self, entity: str, old_state: str, new_state: str) -> None:
        """Logs state changes like agent listening/thinking/speaking."""
        if new_state == "thinking":
            print(f"{C_DIM}⏳ [AGENT STATE]: Thinking & generating LLM response...{C_RESET}")
        elif new_state == "speaking":
            print(f"{C_DIM}🔊 [AGENT STATE]: Speaking response via TTS...{C_RESET}")
        elif new_state == "listening" and old_state != "listening":
            print(f"{C_DIM}👂 [AGENT STATE]: Listening for user voice...{C_RESET}")
        sys.stdout.flush()

    def record_error(self, source: str, err: str) -> None:
        """Logs error conditions with high visibility."""
        print(f"{C_ALERT}❌ [ERROR in {source}]: {err}{C_RESET}")
        sys.stdout.flush()
        self._append_event_to_log(f"ERROR [{source}]: {err}")

    # ── Internal Rendering & File Persistence ────────────────────────────

    def _format_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Cleans and extracts latency/token metrics from LiveKit MetricsReport or dict."""
        out = {}
        # LiveKit ChatMessage metrics fields
        if hasattr(raw_metrics, "get"):
            if raw_metrics.get("e2e_latency") is not None:
                out["e2e_latency_s"] = round(float(raw_metrics["e2e_latency"]), 2)
            if raw_metrics.get("llm_node_ttft") is not None:
                out["llm_ttft_ms"] = round(float(raw_metrics["llm_node_ttft"]) * 1000, 0)
            if raw_metrics.get("llm_node_tps") is not None:
                out["llm_tps"] = round(float(raw_metrics["llm_node_tps"]), 1)
            if raw_metrics.get("tts_node_ttfb") is not None:
                out["tts_ttfb_ms"] = round(float(raw_metrics["tts_node_ttfb"]) * 1000, 0)
            if raw_metrics.get("transcription_delay") is not None:
                out["transcription_delay_ms"] = round(float(raw_metrics["transcription_delay"]) * 1000, 0)
        return out

    def _render_terminal_card(self, turn: ConversationTurn) -> None:
        """Renders an eye-catching, structured terminal card for the finished turn."""
        width = 76
        h_line = "═" * (width - 2)
        s_line = "─" * (width - 2)

        header = f" 💬 [LLM CONVERSATION TURN #{turn.turn_id}]  |  {turn.timestamp}  |  MODE: {turn.mode.upper()} "

        lines = []
        lines.append(f"\n{C_BORDER}╔{h_line}╗{C_RESET}")
        lines.append(f"{C_BORDER}║{C_TITLE}{header.center(width - 2)}{C_BORDER}║{C_RESET}")
        lines.append(f"{C_BORDER}╠{h_line}╣{C_RESET}")

        # User Query
        lang_info = f" [Language: {turn.user_language}]" if turn.user_language else ""
        lines.append(f"{C_BORDER}║ {C_USER_LABEL}🎤 USER SPEECH (STT):{lang_info}{C_RESET}")
        user_text = turn.user_query or "[No voice input / Direct action]"
        lines.append(f"{C_BORDER}║   {C_USER_TEXT}\"{user_text}\"{C_RESET}")

        # Tools executed
        if turn.tools_called:
            lines.append(f"{C_BORDER}║{C_RESET}")
            lines.append(f"{C_BORDER}║ {C_TOOL_LABEL}⚙️  TOOL EXECUTIONS ({len(turn.tools_called)}):{C_RESET}")
            for t in turn.tools_called:
                args = f" {json.dumps(t.arguments, ensure_ascii=False)}" if t.arguments else ""
                err = f" {C_ALERT}(FAILED){C_RESET}" if t.is_error else ""
                dur = f" [{t.duration_ms:.0f}ms]" if t.duration_ms else ""
                lines.append(f"{C_BORDER}║   {C_TOOL_TEXT}• {t.name}({args.strip()}){err}{dur} ➔ \"{t.output}\"{C_RESET}")

        # Vision calls
        if turn.vision_calls:
            lines.append(f"{C_BORDER}║{C_RESET}")
            lines.append(f"{C_BORDER}║ {C_TOOL_LABEL}👁️  VISION LLM INFERENCES ({len(turn.vision_calls)}):{C_RESET}")
            for v in turn.vision_calls:
                dur = f" [{v.duration_ms:.0f}ms]" if v.duration_ms else ""
                lines.append(f"{C_BORDER}║   {C_TOOL_TEXT}• [{v.call_type.upper()}] model={v.model}{dur} ➔ \"{v.output}\"{C_RESET}")

        # Assistant Response
        lines.append(f"{C_BORDER}║{C_RESET}")
        interrupted_tag = f" {C_ALERT}[INTERRUPTED]{C_RESET}" if turn.interrupted else ""
        lines.append(f"{C_BORDER}║ {C_AI_LABEL}🤖 LLM ASSISTANT RESPONSE:{interrupted_tag}{C_RESET}")
        lines.append(f"{C_BORDER}║   {C_AI_TEXT}\"{turn.assistant_response}\"{C_RESET}")

        # Latency / Metrics
        lines.append(f"{C_BORDER}║{C_RESET}")
        metric_parts = []
        if "transcription_delay_ms" in turn.metrics:
            metric_parts.append(f"STT Delay: {turn.metrics['transcription_delay_ms']:.0f}ms")
        if "llm_ttft_ms" in turn.metrics:
            metric_parts.append(f"LLM TTFT: {turn.metrics['llm_ttft_ms']:.0f}ms")
        if "llm_tps" in turn.metrics:
            metric_parts.append(f"Speed: {turn.metrics['llm_tps']} tok/s")
        if "tts_ttfb_ms" in turn.metrics:
            metric_parts.append(f"TTS TTFB: {turn.metrics['tts_ttfb_ms']:.0f}ms")
        if "e2e_latency_s" in turn.metrics:
            metric_parts.append(f"Turn E2E: {turn.metrics['e2e_latency_s']}s")

        metrics_summary = "  |  ".join(metric_parts) if metric_parts else "Duration: ~" + str(turn.metrics.get("e2e_latency_s", "0.5")) + "s"
        lines.append(f"{C_BORDER}║ {C_METRIC_LABEL}⚡ LATENCY & METRICS:{C_RESET}")
        lines.append(f"{C_BORDER}║   {C_METRIC_TEXT}{metrics_summary}{C_RESET}")

        lines.append(f"{C_BORDER}╚{h_line}╝\n{C_RESET}")

        # Print all lines and flush
        print("\n".join(lines))
        sys.stdout.flush()

    def _rotate_file_if_needed(self, filepath: Path) -> None:
        """Rotates log file if it exceeds maximum byte limit."""
        try:
            if filepath.exists() and filepath.stat().st_size > self.max_log_bytes:
                backup = filepath.with_suffix(filepath.suffix + ".1")
                if backup.exists():
                    backup.unlink(missing_ok=True)
                filepath.rename(backup)
        except Exception:
            pass

    def _write_turn_files(self, turn: ConversationTurn) -> None:
        """Dispatches file writes to background thread pool to ensure 0ms latency impact on voice loop."""
        if not self.enabled:
            return
        self._executor.submit(self._do_write_turn_files, turn)

    def _do_write_turn_files(self, turn: ConversationTurn) -> None:
        """Executes actual file writes in background thread."""
        try:
            self._rotate_file_if_needed(self.log_file)
            self._rotate_file_if_needed(self.jsonl_file)

            # 1. Plain-text formatted log
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{turn.timestamp}] TURN #{turn.turn_id} | MODE: {turn.mode.upper()}\n")
                f.write(f"  USER:      \"{turn.user_query}\" (lang: {turn.user_language})\n")
                for t in turn.tools_called:
                    f.write(f"  TOOL:      {t.name} -> \"{t.output}\" ({t.duration_ms}ms)\n")
                for v in turn.vision_calls:
                    f.write(f"  VISION:    [{v.call_type}] {v.model} -> \"{v.output}\" ({v.duration_ms}ms)\n")
                f.write(f"  ASSISTANT: \"{turn.assistant_response}\"\n")
                f.write(f"  METRICS:   {json.dumps(turn.metrics)}\n")
                f.write("-" * 76 + "\n")

            # 2. JSONL structured record
            record = {
                "turn_id": turn.turn_id,
                "timestamp": turn.timestamp,
                "mode": turn.mode,
                "user_query": turn.user_query,
                "user_language": turn.user_language,
                "assistant_response": turn.assistant_response,
                "interrupted": turn.interrupted,
                "tools": [asdict(t) for t in turn.tools_called],
                "vision": [asdict(v) for v in turn.vision_calls],
                "metrics": turn.metrics,
            }
            with open(self.jsonl_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write conversation log in background: {e}")

    def _append_event_to_log(self, event_str: str) -> None:
        """Dispatches standalone event writing to background executor."""
        if not self.enabled:
            return
        self._executor.submit(self._do_append_event_to_log, event_str)

    def _do_append_event_to_log(self, event_str: str) -> None:
        try:
            self._rotate_file_if_needed(self.log_file)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{now_str}] EVENT: {event_str}\n")
        except Exception:
            pass

    # ── Session Attachment Helper ────────────────────────────────────────

    def attach_to_session(self, session: Any, get_current_mode: Optional[Callable[[], str]] = None) -> None:
        """
        Registers event hooks on a LiveKit AgentSession to automatically
        capture speech, assistant messages, state changes, and tool calls.
        """
        observer = self

        @session.on("user_input_transcribed")
        def _on_user_input_transcribed(ev: Any) -> None:
            transcript = getattr(ev, "transcript", "")
            is_final = getattr(ev, "is_final", True)
            language = getattr(ev, "language", None)
            if is_final and transcript.strip():
                if get_current_mode:
                    observer.set_mode(get_current_mode())
                observer.start_turn(transcript, language=str(language) if language else None)

        @session.on("conversation_item_added")
        def _on_conversation_item_added(ev: Any) -> None:
            item = getattr(ev, "item", None)
            if item is None:
                return

            role = getattr(item, "role", "")
            if role == "assistant":
                text = getattr(item, "text_content", "") or getattr(item, "raw_text_content", "") or ""
                interrupted = getattr(item, "interrupted", False)
                metrics = getattr(item, "metrics", None)
                if text.strip():
                    if get_current_mode:
                        observer.set_mode(get_current_mode())
                    observer.record_assistant_response(text, metrics=metrics, interrupted=interrupted)

        @session.on("function_tools_executed")
        def _on_function_tools_executed(ev: Any) -> None:
            calls = getattr(ev, "function_calls", [])
            outputs = getattr(ev, "function_call_outputs", [])
            for c, o in zip(calls, outputs):
                name = getattr(c, "name", "unknown_tool")
                raw_args = getattr(c, "arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except Exception:
                    args = {"raw": str(raw_args)}
                out = getattr(o, "output", "")
                is_err = getattr(o, "is_error", False)
                observer.record_tool_call(name=name, arguments=args, output=str(out), is_error=is_err)

        @session.on("agent_state_changed")
        def _on_agent_state_changed(ev: Any) -> None:
            old_s = getattr(ev, "old_state", "")
            new_s = getattr(ev, "new_state", "")
            observer.record_state_change("agent", old_s, new_s)

        @session.on("error")
        def _on_error(ev: Any) -> None:
            err = getattr(ev, "error", str(ev))
            source = getattr(ev, "source", "session")
            observer.record_error(str(source), str(err))

        logger.info("LLM Conversation Observer successfully attached to LiveKit AgentSession")


# ── Global Singleton Accessor ───────────────────────────────────────────

_global_observer: Optional[LLMConversationObserver] = None


def get_conversation_observer() -> LLMConversationObserver:
    """Returns the global conversation observer instance."""
    global _global_observer
    if _global_observer is None:
        _global_observer = LLMConversationObserver()
    return _global_observer
