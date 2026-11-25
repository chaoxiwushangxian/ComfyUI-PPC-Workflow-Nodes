"""Reversible native-graph migration for the 19 first-batch instances.

The transformer copies the graph and edits only those instances and the link
slots that terminate on them. It does not execute node source. Revert copies
the same instances back from the unmodified original graph.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from .fixed_text_nodes import FIXED_TEXT_REGISTRY
from .tranche5 import TRANCHE5_BY_ID
from .contracts import (
    ADAPTER_CODE_SHA256,
    ADAPTER_ID,
    BUSINESS_INPUT_IDS,
    EXECUTOR_TYPES,
    GUARD_CODE_SHA256,
    GUARD_IDS,
    MEDIA_CODE_SHA256,
    MEDIA_IDS,
    PARSER_CODE_SHA256,
    PARSER_ID,
    PARTIAL_REASON,
    PARTIAL_STATUS,
    REMAINING_EXECUTORS,
    SOURCE_LINK_COUNT,
    SOURCE_NODE_COUNT,
    VIDEO_CODE_SHA256,
    VIDEO_ID,
    VOICE_CODE_SHA256,
    VOICE_ID,
    RUNNER_OUTPUTS,
    TRANCHE2_BY_ID,
    TRANCHE2_IDS,
    TRANCHE3_BY_ID,
    TRANCHE3_IDS,
)

BATCH_IDS = (
    *MEDIA_IDS,
    VIDEO_ID,
    ADAPTER_ID,
    PARSER_ID,
    VOICE_ID,
    *GUARD_IDS,
    *TRANCHE2_IDS,
    *TRANCHE3_IDS,
    *(item["id"] for item in FIXED_TEXT_REGISTRY),
    *TRANCHE5_BY_ID,
)

FIXED_TEXT_BY_ID = {item["id"]: item for item in FIXED_TEXT_REGISTRY}
RUNNER_NODES = {**TRANCHE2_BY_ID, **TRANCHE3_BY_ID, **FIXED_TEXT_BY_ID}


class MigrationError(ValueError):
    pass


def _code_of(node: dict) -> str:
    named = node.get("widgets_values_named") or {}
    if isinstance(named, dict):
        for key in ("pycode", "python_code"):
            value = named.get(key)
            if isinstance(value, str):
                return value
    return ""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _index_nodes(graph: dict) -> dict[int, dict]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise MigrationError("graph has no nodes list")
    found = {}
    for node in nodes:
        if not isinstance(node, dict) or "id" not in node:
            raise MigrationError("a node is missing an id")
        node_id = node["id"]
        if node_id in found:
            raise MigrationError(f"duplicate node id {node_id}")
        found[node_id] = node
    return found


def _expected_code(node_id: int) -> tuple[str, str]:
    if node_id in MEDIA_IDS:
        return "IDENode", MEDIA_CODE_SHA256
    if node_id == VIDEO_ID:
        return "IDENode", VIDEO_CODE_SHA256
    if node_id == ADAPTER_ID:
        return "VRGDG_PythonCodeRunner", ADAPTER_CODE_SHA256
    if node_id == PARSER_ID:
        return "VRGDG_PythonCodeRunner", PARSER_CODE_SHA256
    if node_id == VOICE_ID:
        return "VRGDG_PythonCodeRunner", VOICE_CODE_SHA256
    if node_id in GUARD_IDS:
        return "IDENode", GUARD_CODE_SHA256[node_id]
    if node_id in RUNNER_NODES:
        return "VRGDG_PythonCodeRunner", RUNNER_NODES[node_id]["sha256"]
    if node_id in TRANCHE5_BY_ID:
        item = TRANCHE5_BY_ID[node_id]
        return item["origin"], item["sha256"]
    raise MigrationError(f"{node_id} is not in the migration set")


def _spec(node_id: int) -> dict[str, Any]:
    if node_id in TRANCHE5_BY_ID:
        item = TRANCHE5_BY_ID[node_id]
        return {
            "class_type": item["class_type"],
            "linked": list(item["linked"]),
            "unlinked": list(item["unlinked"]),
            "outputs": list(item["outputs"]),
        }
    if node_id in RUNNER_NODES:
        item = RUNNER_NODES[node_id]
        return {
            "class_type": item["class_type"],
            "linked": list(item["linked"]),
            "outputs": list(RUNNER_OUTPUTS),
        }
    if node_id in MEDIA_IDS:
        return {
            "class_type": "PPCMediaMissing",
            "linked": [("optional_media", "*")],
            "outputs": [("result", "BOOLEAN")],
        }
    if node_id == VIDEO_ID:
        return {
            "class_type": "PPCVideoInventory",
            "linked": [
                ("video_1_frames", "*"),
                ("video_2_frames", "*"),
                ("video_3_frames", "*"),
            ],
            "outputs": [("result", "STRING")],
        }
    if node_id == ADAPTER_ID:
        return {
            "class_type": "PPCReferenceInputAdapter",
            "linked": [("input_text", "STRING"), ("input_json", "STRING")],
            "outputs": [
                ("result_text", "STRING"),
                ("result_json", "STRING"),
                ("has_error", "BOOLEAN"),
            ],
        }
    if node_id in (PARSER_ID, VOICE_ID):
        class_type = "PPCStoryboardParser" if node_id == PARSER_ID else "PPCVoiceRoute"
        return {
            "class_type": class_type,
            "linked": [("input_text", "STRING")],
            "outputs": [
                ("result_text", "STRING"),
                ("result_json", "STRING"),
                ("has_error", "BOOLEAN"),
            ],
        }
    stage = GUARD_IDS[node_id]
    linked = [("runner_text", "STRING"), ("runner_has_error", "BOOLEAN")]
    if stage == "inventory":
        linked.extend(
            [
                ("storyboard_text", "STRING"),
                ("storyboard_has_error", "BOOLEAN"),
                ("caption_text", "STRING"),
                ("caption_has_error", "BOOLEAN"),
            ]
        )
    return {
        "class_type": "PPCResultGuard",
        "stage": stage,
        "linked_before_widget": linked[:2],
        "linked_after_widget": linked[2:],
        "outputs": [("result", "STRING"), ("rejection", "VIDEO"), ("invalid", "BOOLEAN")],
    }


def _linked_input(old_inputs: list, name: str, new_type: str) -> dict:
    matches = [item for item in old_inputs if item.get("name") == name]
    if len(matches) != 1:
        raise MigrationError(f"expected one input named {name}")
    old = matches[0]
    if old.get("link") is None:
        raise MigrationError(f"input {name} has no link")
    rebuilt = {
        "name": name,
        "type": new_type,
        "link": old.get("link"),
        "label": name,
    }
    if "shape" in old:
        rebuilt["shape"] = old["shape"]
    return rebuilt


def _rebuild_node(node: dict) -> tuple[dict, dict[int, int]]:
    node_id = node["id"]
    expect_type, expect_sha = _expected_code(node_id)
    if node.get("type") != expect_type:
        raise MigrationError(f"node {node_id} type is {node.get('type')}, expected {expect_type}")
    actual = _sha(_code_of(node))
    if actual != expect_sha:
        raise MigrationError(f"node {node_id} code sha256 is {actual}, expected {expect_sha}")
    spec = _spec(node_id)
    old_inputs = list(node.get("inputs") or [])
    slot_map: dict[int, int] = {}
    new_inputs = []
    if "stage" in spec:
        for name, typ in spec["linked_before_widget"]:
            old_index = next(i for i, item in enumerate(old_inputs) if item.get("name") == name)
            slot_map[old_index] = len(new_inputs)
            new_inputs.append(_linked_input(old_inputs, name, typ))
        new_inputs.append(
            {
                "name": "stage",
                "type": "COMBO",
                "widget": {"name": "stage"},
                "link": None,
                "label": "stage",
            }
        )
        for name, typ in spec["linked_after_widget"]:
            old_index = next(i for i, item in enumerate(old_inputs) if item.get("name") == name)
            slot_map[old_index] = len(new_inputs)
            new_inputs.append(_linked_input(old_inputs, name, typ))
        widgets = [spec["stage"]]
        widgets_named = {"stage": spec["stage"]}
    else:
        for name, typ in spec["linked"]:
            old_index = next(i for i, item in enumerate(old_inputs) if item.get("name") == name)
            slot_map[old_index] = len(new_inputs)
            new_inputs.append(_linked_input(old_inputs, name, typ))
        for name, typ in spec.get("unlinked") or []:
            new_inputs.append(
                {"name": name, "type": typ, "link": None, "label": name}
            )
        widgets = []
        widgets_named = {}
    linked_old = {
        index
        for index, item in enumerate(old_inputs)
        if item.get("link") is not None
    }
    if set(slot_map) != linked_old:
        dropped = sorted(linked_old - set(slot_map))
        raise MigrationError(f"node {node_id} would drop linked input slots {dropped}")
    old_outputs = list(node.get("outputs") or [])
    if len(old_outputs) != len(spec["outputs"]):
        raise MigrationError(f"node {node_id} output count does not match")
    new_outputs = []
    for index, (name, typ) in enumerate(spec["outputs"]):
        if old_outputs[index].get("name") != name:
            raise MigrationError(
                f"node {node_id} output {index} is {old_outputs[index].get('name')}, expected {name}"
            )
        updated = dict(old_outputs[index])
        updated["name"] = name
        updated["type"] = typ
        new_outputs.append(updated)
    rebuilt = dict(node)
    rebuilt["type"] = spec["class_type"]
    rebuilt["inputs"] = new_inputs
    rebuilt["outputs"] = new_outputs
    rebuilt["widgets_values"] = widgets
    rebuilt["widgets_values_named"] = widgets_named
    properties = dict(node.get("properties") or {})
    properties["Node name for S&R"] = spec["class_type"]
    rebuilt["properties"] = properties
    return rebuilt, slot_map


def _validate_shape(graph: dict) -> None:
    if not isinstance(graph, dict):
        raise MigrationError("graph must be an object")
    if len(graph.get("nodes") or []) != SOURCE_NODE_COUNT:
        raise MigrationError(f"expected {SOURCE_NODE_COUNT} nodes")
    if len(graph.get("links") or []) != SOURCE_LINK_COUNT:
        raise MigrationError(f"expected {SOURCE_LINK_COUNT} links")
    if len(BUSINESS_INPUT_IDS) != 35:
        raise MigrationError("business input inventory is not 35 ids")


def migrate(graph: dict) -> dict:
    """Return a new graph. ``graph`` is not modified."""
    _validate_shape(graph)
    if (graph.get("extra") or {}).get("ppc_first_batch"):
        raise MigrationError("graph is already marked as a first-batch candidate")
    original_nodes = _index_nodes(graph)
    missing = [node_id for node_id in BATCH_IDS if node_id not in original_nodes]
    if missing:
        raise MigrationError(f"missing batch nodes {missing}")
    slot_maps = {}
    output_types = {}
    rebuilt_nodes = {}
    for node_id in BATCH_IDS:
        rebuilt, slot_map = _rebuild_node(original_nodes[node_id])
        rebuilt_nodes[node_id] = rebuilt
        slot_maps[node_id] = slot_map
        output_types[node_id] = [item["type"] for item in rebuilt["outputs"]]
    migrated = copy.deepcopy(graph)
    for index, node in enumerate(migrated["nodes"]):
        if node["id"] in rebuilt_nodes:
            migrated["nodes"][index] = copy.deepcopy(rebuilt_nodes[node["id"]])
    for link in migrated["links"]:
        if not isinstance(link, list) or len(link) < 6:
            raise MigrationError("a link is not a 6-field list")
        _link_id, source, source_slot, target, target_slot, _typ = link[:6]
        if target in slot_maps:
            if target_slot not in slot_maps[target]:
                raise MigrationError(
                    f"link {link[0]} targets {target} slot {target_slot}, which is not a kept input"
                )
            link[4] = slot_maps[target][target_slot]
        if source in output_types:
            if source_slot >= len(output_types[source]):
                raise MigrationError(f"link {link[0]} source slot is out of range")
            link[5] = output_types[source][source_slot]
    extra = dict(migrated.get("extra") or {})
    extra["ppc_first_batch"] = {
        "status": PARTIAL_STATUS,
        "deployable": False,
        "reason": PARTIAL_REASON,
        "replaced_node_ids": list(BATCH_IDS),
        "remaining_executor_nodes": REMAINING_EXECUTORS,
    }
    migrated["extra"] = extra
    _assert_boundaries(graph, migrated)
    return migrated


def _node_map(graph: dict) -> dict[int, dict]:
    return {node["id"]: node for node in graph["nodes"]}


def _assert_boundaries(original: dict, migrated: dict) -> None:
    if len(migrated["nodes"]) != len(original["nodes"]):
        raise MigrationError("node count changed")
    if len(migrated["links"]) != len(original["links"]):
        raise MigrationError("link count changed")
    before = _node_map(original)
    after = _node_map(migrated)
    if set(before) != set(after):
        raise MigrationError("node ids changed")
    for node_id, node in before.items():
        if node_id in BATCH_IDS:
            continue
        if node != after[node_id]:
            raise MigrationError(f"node {node_id} changed outside the first batch")
    executors = sum(1 for node in migrated["nodes"] if node.get("type") in EXECUTOR_TYPES)
    if executors != REMAINING_EXECUTORS:
        raise MigrationError(f"remaining executors are {executors}, expected {REMAINING_EXECUTORS}")
    for node_id in BUSINESS_INPUT_IDS:
        if before[node_id] != after[node_id]:
            raise MigrationError(f"business input node {node_id} changed")
    label = migrated["extra"]["ppc_first_batch"]["status"]
    if label != PARTIAL_STATUS or migrated["extra"]["ppc_first_batch"]["deployable"] is not False:
        raise MigrationError("candidate is not labeled PARTIAL and not deployable")


def revert(candidate: dict, original: dict) -> dict:
    """Restore the 19 instances from ``original``. Both graphs are not modified."""
    _validate_shape(candidate)
    _validate_shape(original)
    _assert_boundaries(original, candidate)
    restored = copy.deepcopy(candidate)
    original_nodes = _node_map(original)
    for index, node in enumerate(restored["nodes"]):
        if node["id"] in BATCH_IDS:
            restored["nodes"][index] = copy.deepcopy(original_nodes[node["id"]])
    original_links = {link[0]: link for link in original["links"]}
    for index, link in enumerate(restored["links"]):
        if link[1] in BATCH_IDS or link[3] in BATCH_IDS:
            restored["links"][index] = copy.deepcopy(original_links[link[0]])
    extra = dict(restored.get("extra") or {})
    extra.pop("ppc_first_batch", None)
    restored["extra"] = extra
    if restored != original:
        raise MigrationError("revert did not restore the original graph")
    return restored


def boundary_report(original: dict, migrated: dict) -> dict:
    """Slot and type changes only. No widget source and no prompt text."""
    before = _node_map(original)
    after = _node_map(migrated)
    nodes = []
    for node_id in BATCH_IDS:
        old = before[node_id]
        new = after[node_id]
        nodes.append(
            {
                "id": node_id,
                "old_type": old.get("type"),
                "new_type": new.get("type"),
                "old_input_names": [item.get("name") for item in old.get("inputs") or []],
                "new_input_names": [item.get("name") for item in new.get("inputs") or []],
                "old_output_types": [item.get("type") for item in old.get("outputs") or []],
                "new_output_types": [item.get("type") for item in new.get("outputs") or []],
                "title_unchanged": old.get("title") == new.get("title"),
            }
        )
    old_links = {link[0]: link for link in original["links"]}
    changed_links = []
    for link in migrated["links"]:
        previous = old_links[link[0]]
        if previous != link:
            changed_links.append(
                {
                    "id": link[0],
                    "source": link[1],
                    "source_slot": link[2],
                    "target": link[3],
                    "old_target_slot": previous[4],
                    "new_target_slot": link[4],
                    "old_type": previous[5],
                    "new_type": link[5],
                }
            )
    return {
        "status": PARTIAL_STATUS,
        "deployable": False,
        "replaced_instances": len(BATCH_IDS),
        "remaining_executor_nodes": REMAINING_EXECUTORS,
        "nodes": nodes,
        "changed_links": changed_links,
        "business_input_ids_unchanged": list(BUSINESS_INPUT_IDS),
    }

