"""Tests for logging helpers."""

from __future__ import annotations

import contextlib
import logging

import jrpcx
from jrpcx._logging import log_request, log_response
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import MockTransport


def _echo_handler(req: Request) -> Response:
    return Response(id=req.id, result=req.params)


class TestLogRequest:
    def test_logs_method_and_params(self, caplog: logging.LogRecord) -> None:  # type: ignore[override]
        transport = MockTransport(_echo_handler)
        logger = logging.getLogger("test.jrpcx.request")
        with caplog.at_level(logging.DEBUG, logger="test.jrpcx.request"):
            client = jrpcx.Client(
                "http://test",
                transport=transport,
                event_hooks={"request": [log_request(logger)]},
            )
            client.echo("hello")
            client.close()
        assert any("echo" in r.message for r in caplog.records)

    def test_custom_level(self, caplog: logging.LogRecord) -> None:  # type: ignore[override]
        transport = MockTransport(_echo_handler)
        logger = logging.getLogger("test.jrpcx.level")
        with caplog.at_level(logging.INFO, logger="test.jrpcx.level"):
            client = jrpcx.Client(
                "http://test",
                transport=transport,
                event_hooks={"request": [log_request(logger, level=logging.INFO)]},
            )
            client.echo("test")
            client.close()
        assert any(r.levelno == logging.INFO for r in caplog.records)


class TestLogResponse:
    def test_logs_success(self, caplog: logging.LogRecord) -> None:  # type: ignore[override]
        transport = MockTransport(_echo_handler)
        logger = logging.getLogger("test.jrpcx.response")
        with caplog.at_level(logging.DEBUG, logger="test.jrpcx.response"):
            client = jrpcx.Client(
                "http://test",
                transport=transport,
                event_hooks={"response": [log_response(logger)]},
            )
            client.echo("hello")
            client.close()
        assert any("result" in r.message for r in caplog.records)

    def test_logs_error(self, caplog: logging.LogRecord) -> None:  # type: ignore[override]
        def error_handler(req: Request) -> Response:
            return Response(
                id=req.id,
                error=ErrorData(code=-32601, message="Not found"),
            )

        transport = MockTransport(error_handler)
        logger = logging.getLogger("test.jrpcx.error")
        with caplog.at_level(logging.DEBUG, logger="test.jrpcx.error"):
            client = jrpcx.Client(
                "http://test",
                transport=transport,
                event_hooks={"response": [log_response(logger)]},
            )
            with contextlib.suppress(jrpcx.MethodNotFoundError):
                client.echo("test")
            client.close()
        assert any("error" in r.message.lower() for r in caplog.records)


class TestLogIntegration:
    def test_both_hooks_with_real_server(
        self, rpc_url: str, caplog: logging.LogRecord  # type: ignore[override]
    ) -> None:
        logger = logging.getLogger("test.jrpcx.integration")
        with (
            caplog.at_level(logging.DEBUG, logger="test.jrpcx.integration"),
            jrpcx.Client(
                rpc_url,
                event_hooks={
                    "request": [log_request(logger)],
                    "response": [log_response(logger)],
                },
            ) as client,
        ):
            client.add(1, 2)
        request_logs = [r for r in caplog.records if "request" in r.message.lower()]
        response_logs = [r for r in caplog.records if "result" in r.message.lower()]
        assert len(request_logs) >= 1
        assert len(response_logs) >= 1
