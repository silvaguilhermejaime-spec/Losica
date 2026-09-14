"""Typed construction grammar over language-neutral semantic identifiers."""
from __future__ import annotations

import copy
import json

from .lexicon_v021 import by_concept
from .reference_system import reference_value, resolve_cell
from .numeral_system import decompose_cardinal, numeral_semantic_id
from .semantic_core import (
    G_ADP_INSTR, G_ADP_LOC, G_ADP_SOURCE, G_COMP, G_COORD_ADD, G_COP, G_DEM_DIST,
    G_DEM_PROX, G_EXIST, G_IMP, G_INT_PERSON, G_NEG, G_NUM_1, G_NUM_2,
    G_MANNER_PROX, G_Q_POLAR, G_REL, G_TIME_ALWAYS,
)

UD_VERSION = "2.18"


def construction_inventory(profile: dict) -> list[dict]:
    specs = [
        ("intransitive", ["nsubj", "root"]), ("transitive", ["nsubj", "obj", "root"]),
        ("ditransitive", ["nsubj", "obj", "iobj", "root"]), ("copular", ["nsubj", "cop", "root"]),
        ("existential", ["expl", "nsubj", "root"]), ("possessive", ["nmod:poss", "case", "root"]),
        ("locative", ["nsubj", "obl", "case", "cop"]), ("modification", ["amod"]),
        ("numeral", ["nummod"]), ("quantification", ["det"]), ("negation", ["advmod", "aux"]),
        ("polar_question", ["discourse"]), ("content_question", ["nsubj", "obj", "obl"]),
        ("imperative", ["root"]), ("coordination", ["conj", "cc"]),
        ("complement", ["ccomp", "mark"]), ("relative", ["acl:relcl", "ref"]),
        ("adverbial", ["advcl", "mark"]),
    ]
    return [{
        "construction_id": f"CX-{name.upper().replace('_', '-')}",
        "name": name,
        "type": "typed_form_meaning_pairing",
        "semantic_input": {"type": "clause_or_phrase", "construction": name},
        "form_constraints": {"profile_keys": ["syntax.clause_order", "syntax.marking_locus"], "executable": True},
        "ud": {"version": UD_VERSION, "relation_ids": rels, "source_treebanks": ["UD fixture: data/ud_templates.example.conllu"]},
        "architecture_reference": ["DELPH-IN Grammar Matrix typed choices", "Babel/Fluid Construction Grammar form-meaning pairing"],
    } for name, rels in specs]


def entity(concept: str | None = None, *, reference: dict | None = None, number="SG", modifiers=None, possessor=None, deixis=None, numeral=None, quantifier=None) -> dict:
    out = {"type": "entity", "number": number, "modifiers": modifiers or [], "possessor": possessor, "deixis": deixis, "numeral": numeral, "quantifier": quantifier}
    if concept is not None:
        out["concept"] = concept
    if reference is not None:
        out["reference"] = reference
    if concept is None and reference is None:
        raise ValueError("entity requires a concept or participant-reference value")
    return out


def participant_reference(*, speaker: str, addressee: str, cardinality: int | None = None, minimum: int | None = None) -> dict:
    return entity(reference=reference_value(speaker=speaker, addressee=addressee, cardinality=cardinality, minimum=minimum))


def clause(predicate: str, arguments: dict, *, construction=None, features=None) -> dict:
    return {"type": "clause", "predicate": predicate, "arguments": arguments, "construction": construction, "features": features or {}}


def validate_semantics(graph: dict) -> None:
    if not isinstance(graph, dict) or graph.get("type") not in {"clause", "coordination", "phrase"}:
        raise ValueError("semantic input must be a typed clause, coordination, or phrase graph")
    if graph["type"] == "clause":
        if not isinstance(graph.get("predicate"), str) or not isinstance(graph.get("arguments", {}), dict):
            raise ValueError("clause semantics requires a predicate and role-indexed arguments")
        for role, value in graph["arguments"].items():
            if role not in {"AGENT", "PATIENT", "THEME", "RECIPIENT", "LOCATION", "SOURCE", "GOAL", "INSTRUMENT", "BENEFICIARY", "POSSESSOR", "POSSESSED", "ATTRIBUTE", "CONTENT", "TIME", "MANNER"}:
                raise ValueError(f"unsupported semantic role {role!r}")
            if not isinstance(value, dict):
                raise ValueError(f"semantic role {role!r} requires a typed value")


class LanguageExecutor:
    def __init__(self, *, lexicon: list[dict], paradigms: dict[str, list[dict]], morphology: dict, profile: dict):
        self.lexicon = lexicon
        self.by_concept = by_concept(lexicon)
        self.paradigms = paradigms
        self.morphology = morphology
        self.profile = profile

    def _lex(self, semantic_id: str) -> dict:
        if semantic_id not in self.by_concept:
            raise KeyError(f"lexical resolution=unmapped semantic_id={semantic_id!r}")
        return self.by_concept[semantic_id]

    @staticmethod
    def _display(lexeme: dict) -> str:
        return lexeme.get("display", {}).get("en") or lexeme["lemma"]

    @classmethod
    def _token(cls, lexeme: dict, *, deprel: str, role: str | None = None, cell: dict | None = None) -> dict:
        label = cls._display(lexeme)
        return {
            "lexeme_id": lexeme["lexeme_id"], "lemma": lexeme["lemma"], "concept": lexeme["concept"],
            "phonemic": (cell or lexeme)["form"], "orthographic": (cell or lexeme).get("orthographic", (cell or lexeme)["form"].replace(".", "")),
            "morphemes": (cell or {}).get("morpheme_sequence", [{"morpheme_id": lexeme["lexeme_id"], "form": lexeme["form"], "gloss": label}]),
            "gloss": ".".join(str(v) for v in (cell or {}).get("feature_bundle", {}).values() if v is not None) or label,
            "features": (cell or {}).get("feature_bundle", {}), "deprel": deprel, "semantic_role": role,
        }

    def _cell(self, lexeme: dict, wanted: dict) -> dict:
        rows = self.paradigms.get(lexeme["lexeme_id"], [])
        for row in rows:
            bundle = row["feature_bundle"]
            if all(bundle.get(k) == v for k, v in wanted.items()):
                return row
        if rows:
            return rows[0]
        return {"form": lexeme["form"], "orthographic": lexeme.get("orthographic", lexeme["form"].replace(".", "")), "feature_bundle": {}, "morpheme_sequence": []}

    def _case(self, role: str) -> str:
        values = list(self.morphology["noun"]["case"])
        preferred = {"AGENT": "NOM", "THEME": "NOM", "PATIENT": "ACC", "RECIPIENT": "DAT", "BENEFICIARY": "DAT", "GOAL": "DAT", "POSSESSOR": "GEN", "LOCATION": "LOC", "SOURCE": "ABL", "INSTRUMENT": "INS", "TIME": "LOC", "MANNER": "INS"}.get(role, "NOM")
        return preferred if preferred in values else ("ACC" if role == "PATIENT" and "ACC" in values else "NOM")

    def _reference_lexeme(self, value: dict) -> dict:
        cell_id = resolve_cell(value, self.profile["reference_system"]["cells"])
        return self._lex(cell_id)

    def _np(self, obj: dict, role: str, deprel: str) -> list[dict]:
        if "reference" in obj:
            return [self._token(self._reference_lexeme(obj["reference"]), deprel=deprel, role=role)]
        concept = obj["concept"]
        lexical = self._lex(concept)
        if lexical["class"] in {"pronoun", "interrogative"}:
            return [self._token(lexical, deprel=deprel, role=role)]
        noun = lexical
        number = obj.get("number", "SG")
        cell = self._cell(noun, {"number": number, "case": self._case(role)})
        head = self._token(noun, deprel=deprel, role=role, cell=cell)
        pre, post = [], []
        if obj.get("deixis"):
            dem_id = G_DEM_PROX if obj["deixis"] == "PROX" else G_DEM_DIST
            dem = self._token(self._lex(dem_id), deprel="det")
            (pre if self.profile["syntax"]["demonstrative_order"] == "DEM-N" else post).append(dem)
        if obj.get("numeral") is not None:
            numeral_tokens = self._numeral_tokens(int(obj["numeral"]))
            if self.profile["syntax"]["numeral_order"] == "NUM-N":
                pre.extend(numeral_tokens)
            else:
                post.extend(numeral_tokens)
        if obj.get("quantifier"):
            quantifier = self._token(self._lex(obj["quantifier"]), deprel="det")
            (pre if self.profile["syntax"]["demonstrative_order"] == "DEM-N" else post).append(quantifier)
        for modifier in obj.get("modifiers", []):
            mod = self._token(self._lex(modifier), deprel="amod")
            (pre if self.profile["syntax"]["property_order"] == "ADJ-N" else post).append(mod)
        if obj.get("possessor"):
            poss = self._np(obj["possessor"], "POSSESSOR", "nmod:poss")
            if self.profile["syntax"]["genitive_order"] == "GEN-N":
                pre = poss + pre
            else:
                post.extend(poss)
        return pre + [head] + post

    def _numeral_tokens(self, value: int) -> list[dict]:
        atoms = decompose_cardinal(value, self.profile["numeral_system"])
        return [self._token(self._lex(numeral_semantic_id(atom)), deprel="nummod") for atom in atoms]

    def _oblique(self, obj: dict, role: str, deprel: str, adposition=G_ADP_LOC) -> list[dict]:
        phrase = self._np(obj, role, deprel)
        order = self.profile["syntax"]["adposition_order"]
        if order == "case_only":
            return phrase
        marker = self._token(self._lex(adposition), deprel="case")
        if order == "preposition":
            return [marker] + phrase
        if order == "inposition" and len(phrase) > 1:
            return phrase[:1] + [marker] + phrase[1:]
        return phrase + [marker]

    def _adjunct(self, obj: dict, role: str, adposition: str) -> list[dict]:
        if "concept" in obj:
            lexical = self._lex(obj["concept"])
            if lexical.get("class") == "adverb":
                return [self._token(lexical, deprel="advmod", role=role)]
        return self._oblique(obj, role, "obl", adposition)

    def _subject_index(self, obj: dict) -> str:
        if "reference" in obj:
            ref = obj["reference"]
        else:
            ref = reference_value(
                speaker="forbidden", addressee="forbidden",
                cardinality=1 if obj.get("number", "SG") == "SG" else None,
                minimum=2 if obj.get("number") == "PL" else None,
            )
        return resolve_cell(ref, self.profile["agreement_system"]["cells"])

    def _verb(self, predicate: str, subject: dict, features: dict) -> dict:
        verb = self._lex(predicate)
        wanted = {
            "polarity": features.get("polarity", "POS"), "aspect": features.get("aspect", "IPFV"),
            "tense": features.get("tense", "NPST"), "mood": features.get("mood", "IND"),
            "voice": features.get("voice", "ACT"),
            "evidentiality": features.get("evidentiality", next(iter(self.morphology["verb"]["evidentiality"]), None)),
            "subject_index": self._subject_index(subject),
        }
        return self._token(verb, deprel="root", cell=self._cell(verb, wanted))

    def _linearize_core(self, subject: list[dict], objects: list[list[dict]], verb: dict) -> list[dict]:
        slots = {"S": subject, "O": [x for group in objects for x in group], "V": [verb]}
        return [token for symbol in self.profile["syntax"]["clause_order"] for token in slots[symbol]]

    def realize(self, graph: dict) -> dict:
        validate_semantics(graph)
        if graph["type"] == "coordination":
            left, right = self.realize(graph["members"][0]), self.realize(graph["members"][1])
            for token in right["token_details"]:
                if token["deprel"] == "root": token["deprel"] = "conj"
            tokens = left["token_details"] + [self._token(self._lex(G_COORD_ADD), deprel="cc")] + right["token_details"]
            return self._result("coordination", graph, tokens)
        if graph["type"] == "phrase":
            tokens = self._np(graph["head"], graph.get("role", "THEME"), "root")
            return self._result(graph.get("construction", "modification"), graph, tokens)

        args, features = graph.get("arguments", {}), graph.get("features", {})
        construction = graph.get("construction")
        pred = graph["predicate"]
        self._validate_valency(pred, args, construction)
        subject_obj = args.get("AGENT") or args.get("THEME") or args.get("POSSESSED") or participant_reference(speaker="forbidden", addressee="forbidden", cardinality=1)

        if construction == "copular" or "ATTRIBUTE" in args:
            subject = self._np(args.get("THEME") or args.get("POSSESSED"), "THEME", "nsubj")
            attr = self._token(self._lex(args["ATTRIBUTE"]["concept"]), deprel="root", role="ATTRIBUTE")
            cop = self._verb(G_COP, subject_obj, features); cop["deprel"] = "cop"
            adjuncts = []
            for role, marker in (("TIME", G_ADP_LOC), ("MANNER", G_ADP_INSTR)):
                value = args.get(role)
                if isinstance(value, dict) and value.get("type") == "entity":
                    adjuncts.extend(self._adjunct(value, role, marker))
            tokens = subject + adjuncts + [attr, cop] if self.profile["syntax"]["clause_order"].endswith("V") else [cop] + subject + adjuncts + [attr]
            return self._result("copular", graph, tokens)
        if construction == "possessive" or {"POSSESSOR", "POSSESSED"} <= set(args):
            possessed = copy.deepcopy(args["POSSESSED"]); possessed["possessor"] = args["POSSESSOR"]
            subject = self._np(possessed, "THEME", "nsubj")
            verb = self._verb(G_EXIST, possessed, features)
            return self._result("possessive", graph, self._linearize_core(subject, [], verb))
        if construction == "locative" and "LOCATION" in args:
            subject = self._np(args.get("THEME") or args.get("AGENT"), "THEME", "nsubj")
            loc = self._oblique(args["LOCATION"], "LOCATION", "obl")
            verb = self._verb(G_COP, subject_obj, features)
            return self._result("locative", graph, self._linearize_core(subject, [loc], verb))
        if construction == "existential":
            theme = self._np(args["THEME"], "THEME", "nsubj")
            objects = [self._oblique(args["LOCATION"], "LOCATION", "obl")] if "LOCATION" in args else []
            verb = self._verb(G_EXIST, args["THEME"], features)
            return self._result("existential", graph, self._linearize_core(theme, objects, verb))

        subject_role = "AGENT" if "AGENT" in args else "THEME"
        subject = self._np(args[subject_role], subject_role, "nsubj") if subject_role in args and features.get("mood") != "IMP" else []
        objects = []
        if "PATIENT" in args:
            objects.append(self._np(args["PATIENT"], "PATIENT", "obj"))
        if "RECIPIENT" in args:
            recipient = self._np(args["RECIPIENT"], "RECIPIENT", "iobj")
            if "DAT" not in self.morphology["noun"]["case"]:
                recipient = self._oblique(args["RECIPIENT"], "RECIPIENT", "iobj", G_ADP_INSTR)
            objects.append(recipient)
        adjunct_specs = (
            ("LOCATION", G_ADP_LOC), ("SOURCE", G_ADP_SOURCE), ("GOAL", G_ADP_LOC),
            ("INSTRUMENT", G_ADP_INSTR), ("BENEFICIARY", G_ADP_INSTR),
            ("TIME", G_ADP_LOC), ("MANNER", G_ADP_INSTR),
        )
        for role, marker in adjunct_specs:
            value = args.get(role)
            if isinstance(value, dict) and value.get("type") == "entity":
                objects.append(self._adjunct(value, role, marker))
        verb = self._verb(pred, subject_obj, features)
        tokens = self._linearize_core(subject, objects, verb)
        if features.get("polarity") == "NEG":
            neg = self._token(self._lex(G_NEG), deprel="advmod")
            vi = tokens.index(verb); tokens.insert(vi, neg)
            construction = construction or "negation"
        if features.get("mood") == "IMP":
            imp = self._token(self._lex(G_IMP), deprel="discourse")
            tokens.append(imp)
            construction = construction or "imperative"
        if features.get("question") == "polar":
            q = self._token(self._lex(G_Q_POLAR), deprel="discourse")
            if self.profile["syntax"]["question_particle_position"] == "clause_initial": tokens.insert(0, q)
            else: tokens.append(q)
            construction = construction or "polar_question"
        if "CONTENT" in args:
            comp = self.realize(args["CONTENT"])
            for token in comp["token_details"]:
                if token["deprel"] == "root": token["deprel"] = "ccomp"
            marker = self._token(self._lex(G_COMP), deprel="mark")
            embedded = comp["token_details"] + [marker] if self.profile["syntax"]["complementizer_position"] == "clause_final" else [marker] + comp["token_details"]
            vi = tokens.index(verb); tokens[vi:vi] = embedded
            construction = "complement"
        if construction == "relative":
            rel = self._token(self._lex(G_REL), deprel="ref")
            if self.profile["syntax"]["relative_clause_order"] == "REL-N": tokens.insert(0, rel)
            else: tokens.append(rel)
        if construction == "adverbial":
            for adjunct_role in ("TIME", "MANNER"):
                value = args.get(adjunct_role)
                if isinstance(value, dict) and value.get("type") in {"clause", "coordination"}:
                    subordinate = self.realize(value)["token_details"]
                    for token in subordinate:
                        if token["deprel"] == "root": token["deprel"] = "advcl"
                    marker = self._token(self._lex(G_COMP), deprel="mark")
                    subordinate = subordinate + [marker] if self.profile["syntax"]["complementizer_position"] == "clause_final" else [marker] + subordinate
                    tokens = subordinate + tokens if self.profile["syntax"]["clause_order"].endswith("V") else tokens + subordinate
        return self._result(construction or ("ditransitive" if len(objects) == 2 else "transitive" if objects else "intransitive"), graph, tokens)

    def _validate_valency(self, predicate: str, arguments: dict, construction: str | None) -> None:
        if construction in {"copular", "possessive", "locative"}:
            return
        frame = self._lex(predicate).get("argument_structure")
        if not frame:
            raise ValueError(f"predicate {predicate!r} requires an explicit argument-structure frame")
        supplied = {x for x in arguments if x not in {"TIME", "MANNER", "LOCATION", "SOURCE", "GOAL", "INSTRUMENT", "BENEFICIARY"}}
        candidates = [set(frame["required_roles"])] + [set(x) for x in frame.get("role_alternatives", [])]
        if construction == "existential":
            candidates.append({"THEME"})
        if not any(required <= supplied and len(required) == len(supplied) for required in candidates):
            raise ValueError(f"predicate {predicate!r} licenses role sets {sorted(map(sorted, candidates))}; received {sorted(supplied)}")

    def _label(self, semantic_id: str) -> str:
        if semantic_id in self.by_concept:
            return self._display(self.by_concept[semantic_id])
        return semantic_id

    def _result(self, construction: str, graph: dict, tokens: list[dict]) -> dict:
        for i, token in enumerate(tokens, 1):
            token["id"] = i
            token["head"] = 0 if token["deprel"] == "root" else next((j for j, t in enumerate(tokens, 1) if t["deprel"] == "root"), 0)
        phonemic = [x["phonemic"] for x in tokens]
        orthographic = [x["orthographic"] for x in tokens]
        glosses = [x["gloss"] for x in tokens]
        content_indices = [i for i, x in enumerate(tokens) if x["deprel"] not in {"case", "cc", "mark", "discourse", "advmod", "cop"}]
        prominent = content_indices[-1] if content_indices else len(tokens) - 1
        for i, token in enumerate(tokens):
            token["phrase_prominent"] = i == prominent
        translation = semantic_translation(graph, self._label)
        return {
            "construction": construction, "construction_id": f"CX-{construction.upper().replace('_', '-')}",
            "semantic_graph": copy.deepcopy(graph), "tokens": phonemic, "orthographic_tokens": orthographic,
            "token_details": tokens, "phonemic_sentence": " ".join(phonemic), "orthographic_sentence": " ".join(orthographic),
            "meaning": translation, "translation": translation,
            "phrase_prosody": {"rule": self.profile["prosody"]["phrase_rule"], "prominent_token_id": prominent + 1},
            "dependencies": [{"id": x["id"], "head": x["head"], "deprel": x["deprel"]} for x in tokens],
            "interlinear": {"phonemic": " ".join(phonemic), "morphemes": " ".join("-".join(m["form"] for m in x["morphemes"] if m.get("form")) for x in tokens), "gloss": " ".join(glosses), "translation": translation},
            "provenance": {"entity": "sentence", "representation": "UD-like dependency tokens plus typed semantics", "inputs": [graph], "transformation": f"CX-{construction.upper()}", "outputs": orthographic, "source": f"UD {UD_VERSION} relation inventory"},
        }


def _reference_display(ref: dict) -> str:
    s = ref.get("speaker_membership")
    a = ref.get("addressee_membership")
    card = ref.get("cardinality", {})
    if s == "required" and a == "forbidden" and card.get("exact") == 1:
        return "I"
    if s == "forbidden" and a == "required" and card.get("exact") == 1:
        return "you"
    if s == "required" and card.get("minimum", 0) >= 2:
        return "we"
    if s == "forbidden" and a == "forbidden" and card.get("exact") == 1:
        return "it"
    return "they"


def _entity_translation(obj: dict, label) -> str:
    if "reference" in obj:
        return _reference_display(obj["reference"])
    parts = []
    if obj.get("deixis"):
        parts.append(obj["deixis"].lower())
    if obj.get("quantifier"):
        parts.append(label(obj["quantifier"]))
    if obj.get("numeral") is not None:
        parts.append(str(obj["numeral"]))
    parts.extend(label(x) for x in obj.get("modifiers", []))
    if obj.get("possessor"):
        parts.append(_entity_translation(obj["possessor"], label) + "'s")
    parts.append(label(obj.get("concept", "")))
    if obj.get("number") == "PL":
        parts.append("[plural]")
    return " ".join(x for x in parts if x)


def semantic_translation(graph: dict, label=None) -> str:
    """Render a complete human-readable semantic summary for display/export."""
    label = label or (lambda x: x)
    if graph["type"] == "coordination":
        return " and ".join(semantic_translation(x, label) for x in graph["members"])
    if graph["type"] == "phrase":
        return _entity_translation(graph["head"], label)
    args = graph.get("arguments", {})
    features = graph.get("features", {})
    subject = args.get("AGENT") or args.get("THEME") or args.get("POSSESSED")
    if (
        graph.get("predicate") == G_COP
        and (args.get("ATTRIBUTE") or {}).get("concept") == G_MANNER_PROX
        and (args.get("TIME") or {}).get("concept") == G_TIME_ALWAYS
    ):
        subject_text = _entity_translation(subject, label)
        auxiliary = "have" if subject_text in {"I", "you", "we", "they"} else "has"
        return f"{subject_text} {auxiliary} always been like this"
    words = [] if features.get("mood") == "IMP" else ([_entity_translation(subject, label)] if subject else [])
    if features.get("polarity") == "NEG":
        words.append("NEG")
    words.append(label(graph["predicate"]))
    role_prefix = {
        "PATIENT": "patient", "RECIPIENT": "recipient", "ATTRIBUTE": "attribute",
        "LOCATION": "location", "SOURCE": "source", "GOAL": "goal",
        "INSTRUMENT": "instrument", "BENEFICIARY": "beneficiary", "POSSESSOR": "possessor",
    }
    for role in ("PATIENT", "RECIPIENT", "ATTRIBUTE", "LOCATION", "SOURCE", "GOAL", "INSTRUMENT", "BENEFICIARY", "POSSESSOR"):
        value = args.get(role)
        if isinstance(value, dict) and value.get("type") == "entity":
            words.append(f"{role_prefix[role]}={_entity_translation(value, label)}")
    if "CONTENT" in args:
        words.append("content={" + semantic_translation(args["CONTENT"], label) + "}")
    if "TIME" in args:
        value = args["TIME"]
        rendered = semantic_translation(value, label) if value.get("type") in {"clause", "coordination", "phrase"} else _entity_translation(value, label)
        words.append("time={" + rendered + "}")
    if "MANNER" in args:
        value = args["MANNER"]
        rendered = semantic_translation(value, label) if value.get("type") in {"clause", "coordination", "phrase"} else _entity_translation(value, label)
        words.append("manner={" + rendered + "}")
    text = " ".join(x for x in words if x)
    marked = []
    for key in ("tense", "aspect", "voice", "evidentiality"):
        if key in features:
            marked.append(f"{key}={features[key]}")
    if marked:
        text += " [" + ", ".join(marked) + "]"
    if features.get("question"):
        text += " ?"
    return text



def semantic_equivalent(a: dict, b: dict) -> bool:
    return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(b, sort_keys=True, separators=(",", ":"))
