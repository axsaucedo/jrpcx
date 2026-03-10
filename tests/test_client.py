"""Tests for BaseJSONRPCClient."""

import json

import pytest

from jrpcx._client import BaseJSONRPCClient
from jrpcx._config import Timeout
from jrpcx._exceptions import InvalidResponseError, ProtocolError
from jrpcx._id_generators import sequential
from jrpcx._types import USE_CLIENT_DEFAULT


class TestBaseClient:
    def test_default_id_generator(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        assert client._next_id() == 1
        assert client._next_id() == 2

    def test_custom_id_generator(self) -> None:
        gen = sequential(start=100)
        client = BaseJSONRPCClient("http://localhost", id_generator=gen)
        assert client._next_id() == 100
        assert client._next_id() == 101

    def test_build_request_bytes(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        data, req_id = client._build_request_bytes("eth_blockNumber")
        parsed = json.loads(data)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "eth_blockNumber"
        assert parsed["id"] == req_id
        assert "params" not in parsed

    def test_build_request_with_params(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        data, _ = client._build_request_bytes("add", [1, 2])
        parsed = json.loads(data)
        assert parsed["params"] == [1, 2]

    def test_build_request_with_dict_params(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        data, _ = client._build_request_bytes(
            "greet", {"name": "Alice"}
        )
        parsed = json.loads(data)
        assert parsed["params"] == {"name": "Alice"}

    def test_parse_response_success(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        data = json.dumps(
            {"jsonrpc": "2.0", "result": 42, "id": 1}
        ).encode()
        resp = client._parse_response(data)
        assert resp.result == 42
        assert resp.is_success

    def test_parse_response_error(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        data = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "not found"},
            "id": 1,
        }).encode()
        resp = client._parse_response(data)
        assert resp.is_error

    def test_parse_response_invalid_json(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        with pytest.raises(ProtocolError, match="Invalid JSON"):
            client._parse_response(b"not json")

    def test_parse_response_non_object(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        with pytest.raises(InvalidResponseError):
            client._parse_response(b"[1, 2, 3]")

    def test_is_closed_initially_false(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        assert not client.is_closed

    def test_ensure_open_raises_when_closed(self) -> None:
        client = BaseJSONRPCClient("http://localhost")
        client._closed = True
        with pytest.raises(RuntimeError, match="closed"):
            client._ensure_open()

    def test_timeout_float_converted(self) -> None:
        client = BaseJSONRPCClient("http://localhost", timeout=5.0)
        assert isinstance(client._timeout, Timeout)
        assert client._timeout.read == 5.0

    def test_timeout_object(self) -> None:
        t = Timeout(connect=1.0, read=5.0)
        client = BaseJSONRPCClient("http://localhost", timeout=t)
        assert client._timeout is t

    def test_resolve_timeout_use_client_default(self) -> None:
        client = BaseJSONRPCClient("http://localhost", timeout=5.0)
        resolved = client._resolve_timeout(USE_CLIENT_DEFAULT)
        assert isinstance(resolved, Timeout)

    def test_resolve_timeout_override(self) -> None:
        client = BaseJSONRPCClient("http://localhost", timeout=5.0)
        resolved = client._resolve_timeout(10.0)
        assert resolved == 10.0

    def test_resolve_timeout_none(self) -> None:
        client = BaseJSONRPCClient("http://localhost", timeout=5.0)
        resolved = client._resolve_timeout(None)
        assert resolved is None
