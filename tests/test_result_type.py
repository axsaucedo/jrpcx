"""Tests for result_type parameter."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import jrpcx
from jrpcx._models import Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport


def _dict_handler(req: Request) -> Response:
    return Response(id=req.id, result={"name": "Alice", "age": 30})


def _list_handler(req: Request) -> Response:
    return Response(id=req.id, result=[1, 2, 3])


@dataclass
class User:
    name: str
    age: int


class TestResultType:
    def test_result_type_with_dataclass(self) -> None:
        transport = MockTransport(_dict_handler)
        client = jrpcx.Client("http://test", transport=transport)
        user = client.call("get_user", result_type=lambda d: User(**d))
        assert isinstance(user, User)
        assert user.name == "Alice"
        assert user.age == 30
        client.close()

    def test_result_type_none_returns_raw(self) -> None:
        transport = MockTransport(_dict_handler)
        client = jrpcx.Client("http://test", transport=transport)
        result = client.call("get_user")
        assert result == {"name": "Alice", "age": 30}
        client.close()

    def test_result_type_with_builtin(self) -> None:
        transport = MockTransport(_list_handler)
        client = jrpcx.Client("http://test", transport=transport)
        result = client.call("get_list", result_type=tuple)
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)
        client.close()

    def test_result_type_with_custom_function(self) -> None:
        def parse_sum(data: list[int]) -> int:
            return sum(data)

        transport = MockTransport(_list_handler)
        client = jrpcx.Client("http://test", transport=transport)
        result = client.call("get_list", result_type=parse_sum)
        assert result == 6
        client.close()


class TestAsyncResultType:
    @pytest.mark.asyncio
    async def test_async_result_type(self) -> None:
        transport = AsyncMockTransport(_dict_handler)
        client = jrpcx.AsyncClient("http://test", transport=transport)
        user = await client.call(
            "get_user", result_type=lambda d: User(**d)
        )
        assert isinstance(user, User)
        assert user.name == "Alice"
        await client.aclose()


class TestResultTypeIntegration:
    def test_result_type_with_real_server(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            result = client.call("add", [1, 2], result_type=str)
            assert result == "3"
