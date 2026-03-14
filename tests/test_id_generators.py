"""Tests for jrpcx._id_generators module."""

from jrpcx._id_generators import random_id, sequential, uuid4


class TestSequential:
    def test_starts_at_1_by_default(self) -> None:
        gen = sequential()
        assert next(gen) == 1
        assert next(gen) == 2
        assert next(gen) == 3

    def test_custom_start(self) -> None:
        gen = sequential(start=100)
        assert next(gen) == 100
        assert next(gen) == 101

    def test_many_values(self) -> None:
        gen = sequential()
        ids = [next(gen) for _ in range(1000)]
        assert ids == list(range(1, 1001))
        assert len(set(ids)) == 1000


class TestUUID4:
    def test_returns_strings(self) -> None:
        gen = uuid4()
        val = next(gen)
        assert isinstance(val, str)

    def test_unique_values(self) -> None:
        gen = uuid4()
        ids = {next(gen) for _ in range(100)}
        assert len(ids) == 100

    def test_uuid_format(self) -> None:
        gen = uuid4()
        val = next(gen)
        parts = val.split("-")
        assert len(parts) == 5


class TestRandomId:
    def test_default_length(self) -> None:
        gen = random_id()
        val = next(gen)
        assert isinstance(val, str)
        assert len(val) == 8

    def test_custom_length(self) -> None:
        gen = random_id(length=16)
        val = next(gen)
        assert len(val) == 16

    def test_unique_values(self) -> None:
        gen = random_id()
        ids = {next(gen) for _ in range(100)}
        assert len(ids) == 100

    def test_hex_characters(self) -> None:
        gen = random_id()
        val = next(gen)
        assert all(c in "0123456789abcdef" for c in val)
