"""Tests for trajectory parser with real cortex exec JSON format."""

from __future__ import annotations

from inspect_coco.trajectory.parser import parse_stream_json

# Fixture data based on real cortex exec --format json output
SIMPLE_RESPONSE = """\
{"type":"system","subtype":"init","session_id":"abc-123","model":"auto","tools":["read","write","bash"],"skills":["sql-author","cortex-agent"],"plugins":[]}
{"type":"assistant","session_id":"abc-123","message":{"id":"msg_1","type":"message","role":"assistant","content":[{"type":"text","text":"Hello! How can I help you today?"}],"model":"auto"}}
{"type":"result","session_id":"abc-123","subtype":"success","result":"Hello! How can I help you today?","is_error":false,"duration_ms":5000,"num_turns":1,"usage":{"input_tokens":1000,"output_tokens":12,"cache_creation_input_tokens":900,"cache_read_input_tokens":0}}
"""

TOOL_USE_RESPONSE = """\
{"type":"system","subtype":"init","session_id":"def-456","model":"auto","tools":["read","bash","glob"],"skills":[],"plugins":[]}
{"type":"assistant","session_id":"def-456","message":{"id":"msg_2","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_001","name":"bash","input":{"command":"ls /workspace"}}],"model":"auto"}}
{"type":"user","session_id":"def-456","message":{"id":"msg_3","type":"message","role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_001","content":"file1.py\\nfile2.py"}]}}
{"type":"assistant","session_id":"def-456","message":{"id":"msg_4","type":"message","role":"assistant","content":[{"type":"text","text":"Found 2 files: file1.py and file2.py"}],"model":"auto"}}
{"type":"result","session_id":"def-456","subtype":"success","result":"Found 2 files: file1.py and file2.py","is_error":false,"duration_ms":8000,"num_turns":2,"usage":{"input_tokens":5000,"output_tokens":50,"cache_creation_input_tokens":4000,"cache_read_input_tokens":1000}}
"""

ERROR_RESPONSE = """\
{"type":"system","subtype":"init","session_id":"err-789","model":"auto","tools":[],"skills":[],"plugins":[]}
{"type":"result","session_id":"err-789","subtype":"error_max_turns","is_error":true,"errors":["Max tool call iterations reached"],"duration_ms":30000,"num_turns":10,"usage":{"input_tokens":50000,"output_tokens":500,"cache_creation_input_tokens":0,"cache_read_input_tokens":50000}}
"""

WITH_NOISE = """\
Update available!
Current: 1.1.10
Latest:  1.1.14

Downloading and installing update...
{"type":"system","subtype":"init","session_id":"noisy-1","model":"auto","tools":["bash"],"skills":[],"plugins":[]}
{"type":"assistant","session_id":"noisy-1","message":{"id":"msg_5","type":"message","role":"assistant","content":[{"type":"text","text":"Done."}],"model":"auto"}}
{"type":"result","session_id":"noisy-1","subtype":"success","result":"Done.","is_error":false,"duration_ms":3000,"num_turns":1,"usage":{"input_tokens":100,"output_tokens":5,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}
"""


class TestParseSimpleResponse:
    def test_final_response(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert t.final_response == "Hello! How can I help you today?"

    def test_metadata(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert t.session_id == "abc-123"
        assert t.model == "auto"

    def test_skills_loaded(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert "sql-author" in t.skills_loaded
        assert "cortex-agent" in t.skills_loaded

    def test_tools_available(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert "read" in t.tools_available
        assert "bash" in t.tools_available

    def test_usage(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert t.usage.input_tokens == 1000
        assert t.usage.output_tokens == 12
        assert t.total_tokens == 1012

    def test_duration(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert t.duration_ms == 5000
        assert t.num_turns == 1

    def test_not_error(self):
        t = parse_stream_json(SIMPLE_RESPONSE)
        assert not t.is_error


class TestParseToolUse:
    def test_tool_calls_extracted(self):
        t = parse_stream_json(TOOL_USE_RESPONSE)
        assert len(t.tool_calls) == 1
        assert t.tool_calls[0].name == "bash"
        assert t.tool_calls[0].tool_use_id == "toolu_001"
        assert t.tool_calls[0].input == {"command": "ls /workspace"}

    def test_tool_results_extracted(self):
        t = parse_stream_json(TOOL_USE_RESPONSE)
        assert len(t.tool_results) == 1
        assert t.tool_results[0].tool_use_id == "toolu_001"
        assert "file1.py" in t.tool_results[0].content

    def test_final_response_after_tool(self):
        t = parse_stream_json(TOOL_USE_RESPONSE)
        assert t.final_response == "Found 2 files: file1.py and file2.py"

    def test_num_turns(self):
        t = parse_stream_json(TOOL_USE_RESPONSE)
        assert t.num_turns == 2


class TestParseError:
    def test_is_error(self):
        t = parse_stream_json(ERROR_RESPONSE)
        assert t.is_error

    def test_error_messages(self):
        t = parse_stream_json(ERROR_RESPONSE)
        assert "Max tool call iterations reached" in t.error_messages

    def test_no_final_response(self):
        t = parse_stream_json(ERROR_RESPONSE)
        assert t.final_response == ""

    def test_exit_code_marks_error(self):
        t = parse_stream_json(SIMPLE_RESPONSE, exit_code=1)
        assert t.is_error


class TestParseWithNoise:
    def test_skips_non_json_lines(self):
        t = parse_stream_json(WITH_NOISE)
        assert t.final_response == "Done."
        assert t.session_id == "noisy-1"

    def test_empty_input(self):
        t = parse_stream_json("")
        assert t.final_response == ""
        assert not t.is_error

    def test_malformed_json(self):
        t = parse_stream_json(
            '{"broken\n{"type":"system","subtype":"init","session_id":"x","model":"y","tools":[],"skills":[],"plugins":[]}'
        )
        assert t.session_id == "x"
