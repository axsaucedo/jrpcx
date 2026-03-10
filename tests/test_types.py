"""Tests for jrpcx._types module."""

from jrpcx._types import USE_CLIENT_DEFAULT, _UseClientDefault


class TestUseClientDefault:
    def test_singleton(self) -> None:
        a = _UseClientDefault()
        b = _UseClientDefault()
        assert a is b

    def test_is_same_as_module_constant(self) -> None:
        assert _UseClientDefault() is USE_CLIENT_DEFAULT

    def test_repr(self) -> None:
        assert repr(USE_CLIENT_DEFAULT) == "USE_CLIENT_DEFAULT"

    def test_falsy(self) -> None:
        assert not USE_CLIENT_DEFAULT
        assert bool(USE_CLIENT_DEFAULT) is False

    def test_identity_check(self) -> None:
        sentinel = USE_CLIENT_DEFAULT
        assert sentinel is USE_CLIENT_DEFAULT

    def test_not_equal_to_none(self) -> None:
        assert USE_CLIENT_DEFAULT is not None
        assert USE_CLIENT_DEFAULT != None  # noqa: E711
