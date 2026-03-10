"""Tests for BaseJSONRPCClient, JSONRPCClient, and AsyncJSONRPCClient."""

import json

import pytest

from jrpcx._client import (
    AsyncJSONRPCClient,
    BaseJSONRPCClient,
    JSONRPCClient,
)
from jrpcx._config import Timeout
from jrpcx._exceptions import (
    InvalidResponseError,
    MethodNotFoundError,
    ProtocolError,
)
from jrpcx._id_generators import sequential
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport
from jrpcx._types import USE_CLIENT_DEFAULT


def echo_handler(request: Request) -> Response:
    return Response(id=request.id, result=request.params)


def error_handler(request: Request) -> Response:
    return Response(
        id=request.id,
        error=ErrorData(code=-32601, message="Method not found"),
    )


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


class TestJSONRPCClient:
    def test_call_basic(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        result = client.call("echo", [1, 2])
        assert result == [1, 2]

    def test_call_raises_on_error(self) -> None:
        transport = MockTransport(error_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        with pytest.raises(MethodNotFoundError):
            client.call("bad_method")

    def test_proxy_basic(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        result = client.echo(1, 2)
        assert result == [1, 2]

    def test_proxy_kwargs(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        result = client.greet(name="Alice")
        assert result == {"name": "Alice"}

    def test_proxy_no_params(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        result = client.eth_blockNumber()
        assert result is None

    def test_proxy_nested(self) -> None:
        """Nested proxy builds dotted method name."""
        methods_called: list[str] = []

        def capture_handler(request: Request) -> Response:
            methods_called.append(request.method)
            return Response(id=request.id, result="ok")

        transport = MockTransport(capture_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        client.system.listMethods()
        assert methods_called == ["system.listMethods"]

    def test_proxy_reserved_name_raises(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        with pytest.raises(AttributeError, match="call"):
            _ = client.__getattr__("call")

    def test_proxy_private_name_raises(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        with pytest.raises(AttributeError):
            _ = client.__getattr__("_private")

    def test_call_fallback_for_reserved(self) -> None:
        methods_called: list[str] = []

        def capture(request: Request) -> Response:
            methods_called.append(request.method)
            return Response(id=request.id, result="ok")

        transport = MockTransport(capture)
        client = JSONRPCClient("http://localhost", transport=transport)
        client.call("close")
        assert methods_called == ["close"]

    def test_context_manager(self) -> None:
        transport = MockTransport(echo_handler)
        with JSONRPCClient("http://localhost", transport=transport) as c:
            result = c.echo(42)
            assert result == [42]
        assert c.is_closed

    def test_explicit_close(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        client.echo("test")
        client.close()
        assert client.is_closed

    def test_call_after_close_raises(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        client.close()
        with pytest.raises(RuntimeError, match="closed"):
            client.call("test")

    def test_auto_creates_http_transport(self) -> None:
        client = JSONRPCClient("http://localhost:9999")
        assert client._sync_transport is not None
        client.close()

    def test_mixed_args_kwargs_raises(self) -> None:
        transport = MockTransport(echo_handler)
        client = JSONRPCClient("http://localhost", transport=transport)
        with pytest.raises(TypeError, match="Cannot mix"):
            client.echo(1, name="Alice")


class TestAsyncJSONRPCClient:
    @pytest.mark.asyncio
    async def test_call_basic(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        result = await client.call("echo", [1, 2])
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_call_raises_on_error(self) -> None:
        transport = AsyncMockTransport(error_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        with pytest.raises(MethodNotFoundError):
            await client.call("bad_method")

    @pytest.mark.asyncio
    async def test_proxy_basic(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        result = await client.echo(1, 2)
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_proxy_kwargs(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        result = await client.greet(name="Bob")
        assert result == {"name": "Bob"}

    @pytest.mark.asyncio
    async def test_proxy_nested(self) -> None:
        methods: list[str] = []

        def capture(request: Request) -> Response:
            methods.append(request.method)
            return Response(id=request.id, result="ok")

        transport = AsyncMockTransport(capture)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        await client.system.listMethods()
        assert methods == ["system.listMethods"]

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        async with AsyncJSONRPCClient(
            "http://localhost", transport=transport
        ) as c:
            result = await c.echo(42)
            assert result == [42]
        assert c.is_closed

    @pytest.mark.asyncio
    async def test_aclose(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        await client.echo("test")
        await client.aclose()
        assert client.is_closed

    @pytest.mark.asyncio
    async def test_call_after_close_raises(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        await client.aclose()
        with pytest.raises(RuntimeError, match="closed"):
            await client.call("test")


class TestClientConfiguration:
    """Tests for headers, auth, timeout pass-through."""

    def test_headers_passed_to_auto_transport(
        self, rpc_url: str
    ) -> None:
        client = JSONRPCClient(
            rpc_url, headers={"X-Custom": "test"}
        )
        result = client.call("echo", ["hi"])
        assert result == ["hi"]
        client.close()

    def test_timeout_float_passed_to_transport(self) -> None:
        client = JSONRPCClient(
            "http://localhost:9999", timeout=3.0
        )
        assert isinstance(client._timeout, Timeout)
        assert client._timeout.read == 3.0
        client.close()

    def test_auth_tuple_accepted(self) -> None:
        client = JSONRPCClient(
            "http://localhost:9999",
            auth=("user", "pass"),
        )
        assert client._auth == ("user", "pass")
        client.close()

    @pytest.mark.asyncio
    async def test_async_headers_config(
        self, rpc_url: str
    ) -> None:
        client = AsyncJSONRPCClient(
            rpc_url, headers={"X-Custom": "async-test"}
        )
        result = await client.call("echo", ["async"])
        assert result == ["async"]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_auto_transport(
        self, rpc_url: str
    ) -> None:
        async with AsyncJSONRPCClient(rpc_url) as c:
            result = await c.add(10, 20)
            assert result == 30

    def test_sync_auto_transport(
        self, rpc_url: str
    ) -> None:
        with JSONRPCClient(rpc_url) as c:
            result = c.add(10, 20)
            assert result == 30
