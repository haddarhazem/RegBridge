"""Constrained typed V1 roadmap generation from a verified assessment."""

from __future__ import annotations


def generate_typed_items(result: dict) -> list[dict]:
    """Map only typed assessment conclusions to roadmap items.

    No generic action is invented and each item carries its assessment conclusion ID.
    """
    items: list[dict] = []
    order = 1
    for field, item_type in (("obligations", "obligation"), ("recommendations", "recommendation"), ("uncertainties", "uncertainty")):
        for index, conclusion in enumerate(result.get(field, []), 1):
            conclusion_id = str(conclusion.get("conclusion_id") or f"{item_type}-{index}")
            statement = str(conclusion.get("statement") or "").strip()
            if not statement:
                continue
            items.append({
                "item_type": item_type,
                "title": statement,
                "justification": f"Dérivé de la conclusion {conclusion_id} de l'évaluation réglementaire vérifiée.",
                "priority_order": order,
                "source_conclusion_refs": [conclusion_id],
                "dependency_item_refs": [],
            })
            order += 1
    return items
