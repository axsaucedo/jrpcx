"""Tests for custom JSON serialization."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import jrpcx
from jrpcx._models import Request, Response
from jrpcx._transports._mock import MockTransport


def _echo_handler(req: Request) -> Response:
    return Response(id=req.id, result=req.params)


class DecimalEncoder(json.JSONEncoder):
    """Encode Decimal as string."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


class TestJsonEncoder:
    def test_decimal_encoding(self) -> None:
        transport = MockTransport(_echo_handler)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            json_encoder=DecimalEncoder,
        )
        result = client.call("send", {"amount": Decimal("19.99")})
        assert result == {"amount": "19.99"}
        client.close()

    def test_default_encoder_works(self) -> None:
        transport = MockTransport(_echo_handler)
        client = jrpcx.Client("http://test", transport=transport)
        result = client.call("test", {"key": "value"})
        assert result == {"key": "value"}
        client.close()

    def test_encoder_with_proxy(self) -> None:
        transport = MockTransport(_echo_handler)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            json_encoder=DecimalEncoder,
        )
        result = client.send_payment(amount=Decimal("42.50"))
        assert result == {"amount": "42.50"}
        client.close()


class TestJsonDecoder:
    def test_custom_decoder(self) -> None:
        """Custom decoder is used when parsing responses."""

        class StrictDecoder(json.JSONDecoder):
            pass

        transport = MockTransport(_echo_handler)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            json_decoder=StrictDecoder,
        )
        result = client.call("test", [1, 2, 3])
        assert result == [1, 2, 3]
        client.close()


class TestSerializationIntegration:
    def test_encoder_with_real_server(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url, json_encoder=DecimalEncoder) as client:
            result = client.echo(amount=Decimal("9.99"))
            assert result == {"amount": "9.99"}
