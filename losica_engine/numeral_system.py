"""Generated cardinal-numeral architecture and arithmetic realization."""
from __future__ import annotations

import random


NUMERAL_BASES = (5, 10, 20)
NUMERAL_BASE_WEIGHTS = (0.15, 0.70, 0.15)
NUMERAL_ORDERS = ("coefficient_power", "power_coefficient")


def sample_numeral_system(rng: random.Random, seed: int) -> tuple[dict, dict]:
    base = rng.choices(NUMERAL_BASES, weights=NUMERAL_BASE_WEIGHTS, k=1)[0]
    order = rng.choice(NUMERAL_ORDERS)
    max_exponent = 5
    atoms = list(range(1, base)) + [base ** exponent for exponent in range(1, max_exponent + 1)]
    system = {
        "system_id": f"NUM-{base}-{order.upper()}",
        "base": base,
        "composition_order": order,
        "max_exponent": max_exponent,
        "atoms": atoms,
        "range": {"minimum": 1, "maximum": base ** (max_exponent + 1) - 1},
    }
    decision = {
        "feature": "cardinal_numeral_architecture",
        "value": system["system_id"],
        "source": "Losica numeral typological prior",
        "source_ids": ["LOSICA-NUMERAL-PARTITION-01"],
        "candidate_values": [f"NUM-{b}-{o.upper()}" for b in NUMERAL_BASES for o in NUMERAL_ORDERS],
        "weights": [w / len(NUMERAL_ORDERS) for w in NUMERAL_BASE_WEIGHTS for _ in NUMERAL_ORDERS],
        "sampling_method": "radix prior plus coefficient/power order sampling",
        "seed": seed,
        "evidence_kind": "typological_prior",
        "inference_kind": "statistical_inference",
        "choice_kind": "generated_choice",
    }
    return system, decision


def numeral_semantic_id(value: int) -> str:
    return f"n:{int(value)}"


def decompose_cardinal(value: int, system: dict) -> list[int]:
    value = int(value)
    minimum = int(system["range"]["minimum"])
    maximum = int(system["range"]["maximum"])
    if value < minimum or value > maximum:
        raise ValueError(f"cardinal value {value} is outside generated numeral range {minimum}..{maximum}")
    base = int(system["base"])
    order = system["composition_order"]
    parts: list[int] = []
    remaining = value
    for exponent in range(int(system["max_exponent"]), -1, -1):
        power = base ** exponent
        coefficient, remaining = divmod(remaining, power)
        if coefficient == 0:
            continue
        if exponent == 0:
            parts.append(coefficient)
            continue
        if order == "coefficient_power":
            if coefficient == 1:
                parts.append(power)
            else:
                parts.extend([coefficient, power])
        else:
            parts.extend([power, coefficient])
    return parts


def compose_cardinal(atoms: list[int], system: dict) -> int:
    if not atoms:
        raise ValueError("cardinal composition requires at least one numeral atom")
    base = int(system["base"])
    order = system["composition_order"]
    total = 0
    if order == "coefficient_power":
        pending = None
        for atom in atoms:
            atom = int(atom)
            if atom >= base:
                coefficient = pending if pending is not None else 1
                total += coefficient * atom
                pending = None
            else:
                if pending is not None:
                    total += pending
                pending = atom
        if pending is not None:
            total += pending
    else:
        i = 0
        while i < len(atoms):
            atom = int(atoms[i])
            if atom >= base:
                if i + 1 >= len(atoms) or int(atoms[i + 1]) >= base:
                    raise ValueError("power-first numeral requires a following coefficient atom")
                total += atom * int(atoms[i + 1])
                i += 2
            else:
                total += atom
                i += 1
    return total
