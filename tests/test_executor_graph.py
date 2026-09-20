from types import SimpleNamespace

from api.executor import _ancestor_ids, topo_sort


def node(node_id):
    return SimpleNamespace(id=node_id)


def edge(source, target):
    return SimpleNamespace(source=source, target=target)


def test_target_dependency_closure_excludes_unrelated_branch():
    edges = [edge("credential", "extract_a"), edge("credential", "extract_b"), edge("extract_a", "load_a")]
    assert _ancestor_ids("load_a", edges) == {"credential", "extract_a", "load_a"}


def test_topological_sort_rejects_cycle():
    nodes = [node("a"), node("b")]
    edges = [edge("a", "b"), edge("b", "a")]
    try:
        topo_sort(nodes, edges)
    except ValueError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("cycle was not rejected")
