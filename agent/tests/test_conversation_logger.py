import json
import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock
from conversation_logger import (
    LLMConversationObserver,
    ConversationTurn,
    ToolExecutionRecord,
    VisionCallRecord,
)


@pytest.fixture
def temp_observer():
    temp_dir = tempfile.mkdtemp()
    observer = LLMConversationObserver(log_dir=temp_dir)
    yield observer
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_observer_initialization(temp_observer):
    assert temp_observer.log_dir.exists()
    assert temp_observer.turn_counter == 0
    assert temp_observer.current_mode == "assistant"


def test_observer_start_turn(temp_observer):
    turn = temp_observer.start_turn("सामने क्या है?", language="hi-IN")
    assert turn.turn_id == 1
    assert turn.user_query == "सामने क्या है?"
    assert turn.user_language == "hi-IN"
    assert turn.mode == "assistant"
    assert not turn.completed


def test_observer_record_tool_call(temp_observer):
    temp_observer.start_turn("describe scene")
    temp_observer.record_tool_call(
        name="describe_scene",
        arguments={},
        output="A doorway is directly ahead at 2 meters.",
        is_error=False,
        duration_ms=480.0,
    )
    assert len(temp_observer.active_turn.tools_called) == 1
    tool = temp_observer.active_turn.tools_called[0]
    assert tool.name == "describe_scene"
    assert tool.output == "A doorway is directly ahead at 2 meters."
    assert tool.duration_ms == 480.0
    assert not tool.is_error


def test_observer_record_vision_call(temp_observer):
    temp_observer.start_turn("read this label")
    temp_observer.record_vision_call(
        call_type="ocr",
        model="Google Gemini (gemini-3.5-flash-lite)",
        prompt_summary="Read visible text",
        output="Aspirin 100mg",
        duration_ms=350.0,
    )
    assert len(temp_observer.active_turn.vision_calls) == 1
    vision = temp_observer.active_turn.vision_calls[0]
    assert vision.call_type == "ocr"
    assert vision.model == "Google Gemini (gemini-3.5-flash-lite)"
    assert vision.output == "Aspirin 100mg"


def test_observer_assistant_response_and_file_logging(temp_observer):
    temp_observer.start_turn("kya samne koi rukawat hai?")
    temp_observer.record_tool_call(
        name="describe_scene",
        output="The hallway is clear.",
        duration_ms=300.0,
    )
    raw_metrics = {
        "e2e_latency": 0.85,
        "llm_node_ttft": 0.22,
        "llm_node_tps": 38.5,
        "tts_node_ttfb": 0.18,
        "transcription_delay": 0.12,
    }
    temp_observer.record_assistant_response(
        response_text="रास्ता बिल्कुल साफ है, आप आगे बढ़ सकते हैं।",
        metrics=raw_metrics,
        interrupted=False,
    )

    # Turn should be completed and finalized
    assert temp_observer.active_turn.completed
    assert temp_observer.active_turn.assistant_response == "रास्ता बिल्कुल साफ है, आप आगे बढ़ सकते हैं।"
    assert temp_observer.active_turn.metrics["e2e_latency_s"] == 0.85
    assert temp_observer.active_turn.metrics["llm_ttft_ms"] == 220.0
    assert temp_observer.active_turn.metrics["tts_ttfb_ms"] == 180.0

    # Flush background executor writes
    temp_observer.flush()

    # Verify log files written to disk
    assert temp_observer.log_file.exists()
    assert temp_observer.jsonl_file.exists()

    # Verify JSONL contents
    with open(temp_observer.jsonl_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["turn_id"] == 1
        assert data["user_query"] == "kya samne koi rukawat hai?"
        assert data["assistant_response"] == "रास्ता बिल्कुल साफ है, आप आगे बढ़ सकते हैं।"
        assert len(data["tools"]) == 1
        assert data["metrics"]["e2e_latency_s"] == 0.85


def test_observer_mode_switch(temp_observer):
    temp_observer.record_mode_switch("assistant", "navigation", source="voice_tool")
    temp_observer.flush()
    assert temp_observer.current_mode == "navigation"
    with open(temp_observer.log_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "MODE_CHANGED: assistant -> navigation" in content


def test_observer_obstacle_alert(temp_observer):
    temp_observer.record_obstacle_alert("chair", position="ahead", distance="1.5")
    temp_observer.flush()
    with open(temp_observer.log_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "OBSTACLE_ALERT: chair at ahead at 1.5m" in content


def test_observer_production_disabled():
    import tempfile, shutil
    temp_dir = tempfile.mkdtemp()
    try:
        os.environ["ENABLE_CONVERSATION_LOGS"] = "false"
        obs = LLMConversationObserver(log_dir=temp_dir)
        obs.start_turn("test query")
        obs.record_assistant_response("test answer")
        obs.flush()
        # Log file should not exist because logging is disabled
        assert not obs.jsonl_file.exists()
    finally:
        os.environ.pop("ENABLE_CONVERSATION_LOGS", None)
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_observer_state_changes(temp_observer):
    # Should not raise exception
    temp_observer.record_state_change("agent", "listening", "thinking")
    temp_observer.record_state_change("agent", "thinking", "speaking")
    temp_observer.record_state_change("agent", "speaking", "listening")


def test_observer_session_attachment(temp_observer):
    mock_session = MagicMock()
    handlers = {}

    def mock_on(event_name):
        def decorator(fn):
            handlers[event_name] = fn
            return fn
        return decorator

    mock_session.on = mock_on
    temp_observer.attach_to_session(mock_session, get_current_mode=lambda: "ocr")

    assert "user_input_transcribed" in handlers
    assert "conversation_item_added" in handlers
    assert "function_tools_executed" in handlers
    assert "agent_state_changed" in handlers
    assert "error" in handlers

    # Test user transcript event simulation
    mock_user_ev = MagicMock()
    mock_user_ev.transcript = "hello drishti"
    mock_user_ev.is_final = True
    mock_user_ev.language = "en-US"
    handlers["user_input_transcribed"](mock_user_ev)
    assert temp_observer.active_turn.user_query == "hello drishti"

    # Test tool execution event simulation
    mock_tool_ev = MagicMock()
    mock_call = MagicMock()
    mock_call.name = "describe_scene"
    mock_call.arguments = "{}"
    mock_out = MagicMock()
    mock_out.output = "All clear"
    mock_out.is_error = False
    mock_tool_ev.function_calls = [mock_call]
    mock_tool_ev.function_call_outputs = [mock_out]
    handlers["function_tools_executed"](mock_tool_ev)
    assert len(temp_observer.active_turn.tools_called) == 1

    # Test assistant response event simulation
    mock_conv_ev = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "assistant"
    mock_msg.text_content = "Hello! How can I assist you?"
    mock_msg.interrupted = False
    mock_msg.metrics = {"llm_node_ttft": 0.25, "e2e_latency": 0.9}
    mock_conv_ev.item = mock_msg
    handlers["conversation_item_added"](mock_conv_ev)
    assert temp_observer.active_turn.completed
    assert temp_observer.active_turn.assistant_response == "Hello! How can I assist you?"
