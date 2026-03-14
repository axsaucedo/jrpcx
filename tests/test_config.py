"""Tests for jrpcx._config module."""

from jrpcx._config import Timeout


class TestTimeout:
    def test_default_all_none(self) -> None:
        t = Timeout()
        assert t.connect is None
        assert t.read is None
        assert t.write is None
        assert t.pool is None

    def test_float_shorthand(self) -> None:
        t = Timeout(5.0)
        assert t.connect == 5.0
        assert t.read == 5.0
        assert t.write == 5.0
        assert t.pool == 5.0

    def test_individual_values(self) -> None:
        t = Timeout(connect=5.0, read=10.0, write=3.0, pool=1.0)
        assert t.connect == 5.0
        assert t.read == 10.0
        assert t.write == 3.0
        assert t.pool == 1.0

    def test_float_with_override(self) -> None:
        t = Timeout(5.0, read=30.0)
        assert t.connect == 5.0
        assert t.read == 30.0
        assert t.write == 5.0
        assert t.pool == 5.0

    def test_frozen(self) -> None:
        import pytest

        t = Timeout(5.0)
        with pytest.raises(AttributeError):
            t.connect = 10.0  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Timeout(5.0)
        b = Timeout(5.0)
        assert a == b

    def test_repr(self) -> None:
        t = Timeout(connect=5.0, read=10.0)
        r = repr(t)
        assert "connect=5.0" in r
        assert "read=10.0" in r
