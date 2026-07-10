import pytest

from morph.registry import Registry, ConversionResult


@pytest.fixture
def clean_registry():
    """Returns a brand new empty registry to avoid polluting the global one."""
    return Registry()


def dummy_converter(input_path, output_path, **kwargs):
    return ConversionResult(output=output_path)


def test_registry_find_path(clean_registry):
    # Setup a graph: a -> b -> c
    clean_registry.register("a", "b", backend="test")(dummy_converter)
    clean_registry.register("b", "c", backend="test")(dummy_converter)

    path = clean_registry.find_path("a", "c")
    assert path is not None
    assert len(path) == 2
    assert path[0].src == "a"
    assert path[0].dst == "b"
    assert path[1].src == "b"
    assert path[1].dst == "c"


def test_registry_cycle_prevention(clean_registry):
    # Setup a cycle: a -> b -> c -> a
    clean_registry.register("a", "b", backend="test")(dummy_converter)
    clean_registry.register("b", "c", backend="test")(dummy_converter)
    clean_registry.register("c", "a", backend="test")(dummy_converter)

    # Should not infinite loop
    path = clean_registry.find_path("a", "c")
    assert path is not None
    assert len(path) == 2


def test_registry_unreachable(clean_registry):
    clean_registry.register("a", "b", backend="test")(dummy_converter)
    clean_registry.register("c", "d", backend="test")(dummy_converter)

    # Isolated subgraphs
    assert clean_registry.find_path("a", "d") is None
