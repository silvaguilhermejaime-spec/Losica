"""Surface analysis for generated Losica states.

The analyzer consumes only the written Losica sentence plus the generated
language snapshot.  It reconstructs lexical, inflectional, referential and
construction structure from the snapshot's own paradigms.
"""
from __future__ import annotations

import copy
from collections import defaultdict

from .grammar_v021 import clause, entity
from .reference_system import condition_matches
from .numeral_system import compose_cardinal
from .semantic_core import (
    G_ADP_INSTR, G_ADP_LOC, G_ADP_SOURCE, G_COMP, G_COORD_ADD, G_COP,
    G_DEM_DIST, G_DEM_PROX, G_EXIST, G_IMP, G_INT_PERSON, G_INT_PLACE,
    G_INT_THING, G_NEG, G_Q_POLAR, G_QUANT_EXIST,
    G_QUANT_UNIV, G_REL,
)

DEFAULTS = {
    "polarity": "POS", "aspect": "IPFV", "tense": "NPST",
    "mood": "IND", "voice": "ACT", "evidentiality": None,
}


class SurfaceAnalyzer:
    def __init__(self, state: dict):
        self.state = state
        self.profile = state["profile"]
        self.morphology = state["morphology"]
        self.lexemes = {x["lexeme_id"]: x for x in state["lexicon"]}
        self.by_concept = {}
        self.static = defaultdict(list)
        self.inflected = defaultdict(list)
        for lex in state["lexicon"]:
            self.by_concept[lex["concept"]] = lex
            for mapping in lex.get("concept_mappings", []):
                self.by_concept[mapping["concept"]] = lex
            self.static[lex.get("orthographic", lex["form"].replace(".", ""))].append(lex)
        for lid, rows in state["paradigms"].items():
            if lid in {"sample_noun", "sample_verb"} or lid not in self.lexemes:
                continue
            for row in rows:
                self.inflected[row["orthographic"]].append((self.lexemes[lid], row))
        self.function_forms = {
            concept: lex.get("orthographic", lex["form"].replace(".", ""))
            for concept, lex in self.by_concept.items() if concept.startswith("g:")
        }
        self.form_to_function = {v: k for k, v in self.function_forms.items()}
        self.form_to_numeral = {}
        for lex in state["lexicon"]:
            if lex.get("class") == "numeral":
                value = lex.get("grammatical_features", {}).get("numeral_value")
                if value is not None:
                    self.form_to_numeral[lex.get("orthographic", lex["form"].replace(".", ""))] = int(value)

    def _verb_candidates(self, word: str):
        return [(lex, row) for lex, row in self.inflected.get(word, []) if lex["class"] in {"verb", "auxiliary"}]

    def _noun_candidates(self, word: str):
        return [(lex, row) for lex, row in self.inflected.get(word, []) if lex["class"] == "noun"]

    def _static_candidates(self, word: str, classes=None):
        rows = self.static.get(word, [])
        if classes is None:
            return rows
        return [x for x in rows if x["class"] in classes]

    def _minimal_features(self, bundle: dict) -> dict:
        out = {}
        for key, default in DEFAULTS.items():
            value = bundle.get(key, default)
            if value != default:
                out[key] = value
        return out

    def _entity_at(self, words: list[str], i: int):
        word = words[i]
        noun = self._noun_candidates(word)
        if noun:
            lex, row = noun[0]
            obj = entity(lex["concept"], number=row["feature_bundle"].get("number", "SG"))
            return obj, row["feature_bundle"].get("case"), lex
        for lex in self._static_candidates(word, {"pronoun"}):
            return entity(reference=copy.deepcopy(lex["grammatical_features"])), None, lex
        for lex in self._static_candidates(word, {"interrogative"}):
            return entity(lex["concept"]), None, lex
        return None

    def _decorate_entities(self, words: list[str], heads: list[dict], blocked: set[int]):
        """Attach generated nominal modifiers to their nearest nominal head."""
        if not heads:
            return
        head_indices = [h["index"] for h in heads]
        numeral_groups = defaultdict(list)
        for i, word in enumerate(words):
            if i in blocked or i in head_indices:
                continue
            numeral_value = self.form_to_numeral.get(word)
            if numeral_value is not None:
                nearest = min(heads, key=lambda h: abs(h["index"] - i))
                numeral_groups[nearest["index"]].append((i, numeral_value))
                blocked.add(i)
                continue
            concept = self.form_to_function.get(word)
            if concept not in {G_DEM_PROX, G_DEM_DIST, G_QUANT_UNIV, G_QUANT_EXIST}:
                continue
            nearest = min(heads, key=lambda h: abs(h["index"] - i))
            obj = nearest["entity"]
            if concept == G_DEM_PROX:
                obj["deixis"] = "PROX"
            elif concept == G_DEM_DIST:
                obj["deixis"] = "DIST"
            else:
                obj["quantifier"] = concept
            blocked.add(i)
        for head in heads:
            rows = sorted(numeral_groups.get(head["index"], []))
            if rows:
                atoms = [value for _, value in rows]
                head["entity"]["numeral"] = compose_cardinal(atoms, self.profile["numeral_system"])

    def _phrase(self, words: list[str]) -> list[dict]:
        heads = []
        for i in range(len(words)):
            found = self._entity_at(words, i)
            if found:
                obj, case, lex = found
                heads.append({"index": i, "entity": obj, "case": case, "lexeme": lex})
        if len(heads) != 1:
            return []
        head = heads[0]
        blocked = {head["index"]}
        self._decorate_entities(words, heads, blocked)
        for i, word in enumerate(words):
            if i == head["index"]:
                continue
            props = self._static_candidates(word, {"property"})
            if props:
                head["entity"]["modifiers"].append(props[0]["concept"])
        obj = head["entity"]
        if obj.get("numeral") is not None:
            construction = "numeral"
        elif obj.get("quantifier") is not None:
            construction = "quantification"
        else:
            construction = "modification"
        return [{"type": "phrase", "head": obj, "construction": construction}]

    def _basic_clause(self, words: list[str], forced_construction: str | None = None) -> list[dict]:
        if not words:
            return []
        words = list(words)
        features = {}
        # Surface construction markers carry information independently of token annotations.
        for concept, feature in ((G_Q_POLAR, ("question", "polar")), (G_IMP, ("mood", "IMP"))):
            form = self.function_forms.get(concept)
            if form in words:
                words.remove(form)
                features[feature[0]] = feature[1]
        neg_form = self.function_forms.get(G_NEG)
        if neg_form in words:
            words.remove(neg_form)
            features["polarity"] = "NEG"
        rel_form = self.function_forms.get(G_REL)
        if rel_form in words:
            words.remove(rel_form)
            forced_construction = "relative"

        verb_positions = [(i, self._verb_candidates(w)) for i, w in enumerate(words) if self._verb_candidates(w)]
        if not verb_positions:
            return self._phrase(words)
        # Simple clauses contain one finite predicate.  When homophony creates more
        # candidates, clause order determines the finite-predicate position.
        if len(verb_positions) > 1:
            pos, candidates = (verb_positions[0] if self.profile["syntax"]["clause_order"].startswith("V") else verb_positions[-1])
        else:
            pos, candidates = verb_positions[0]
        verb_lex, verb_row = candidates[0]
        features = {**self._minimal_features(verb_row["feature_bundle"]), **features}
        predicate = verb_lex["concept"]
        blocked = {pos}

        heads = []
        for i in range(len(words)):
            if i == pos:
                continue
            found = self._entity_at(words, i)
            if found:
                obj, case, lex = found
                heads.append({"index": i, "entity": obj, "case": case, "lexeme": lex})
                blocked.add(i)
        self._decorate_entities(words, heads, blocked)

        # Associate each overt adposition with its host according to the generated
        # adposition order.  Its semantic role is resolved together with valency below.
        explicit_markers = {}
        for i, word in enumerate(words):
            concept = self.form_to_function.get(word)
            if concept in {G_ADP_LOC, G_ADP_SOURCE, G_ADP_INSTR} and heads:
                order = self.profile["syntax"]["adposition_order"]
                if order == "preposition":
                    eligible = [h for h in heads if h["index"] > i]
                    nearest = min(eligible, key=lambda h: h["index"] - i) if eligible else min(heads, key=lambda h: abs(h["index"] - i))
                elif order == "postposition":
                    eligible = [h for h in heads if h["index"] < i]
                    nearest = min(eligible, key=lambda h: i - h["index"]) if eligible else min(heads, key=lambda h: abs(h["index"] - i))
                else:
                    nearest = min(heads, key=lambda h: abs(h["index"] - i))
                explicit_markers[nearest["index"]] = concept
                blocked.add(i)

        # Copular clauses are identified by the generated copular lexeme.
        if predicate == G_COP:
            loc_heads = [h for h in heads if h["case"] == "LOC" or explicit_markers.get(h["index"]) == G_ADP_LOC]
            if loc_heads:
                loc = loc_heads[0]
                theme = next((h for h in heads if h is not loc), None)
                if theme:
                    return [clause(G_COP, {"THEME": theme["entity"], "LOCATION": loc["entity"]}, construction="locative", features=features)]
            props = []
            for i, word in enumerate(words):
                if i == pos:
                    continue
                props.extend(self._static_candidates(word, {"property"}))
            theme = next((h for h in heads if h["case"] in {None, "NOM"}), None)
            if theme and props:
                return [clause(G_COP, {"THEME": theme["entity"], "ATTRIBUTE": entity(props[0]["concept"])}, construction="copular", features=features)]

        if predicate == G_EXIST:
            gen = next((h for h in heads if h["case"] == "GEN"), None)
            nom = next((h for h in heads if h["case"] in {None, "NOM"}), None)
            if gen and nom:
                return [clause(G_EXIST, {"POSSESSOR": gen["entity"], "POSSESSED": nom["entity"]}, construction="possessive", features=features)]
            if nom:
                args = {"THEME": nom["entity"]}
                loc = next((h for h in heads if h["case"] == "LOC" or explicit_markers.get(h["index"]) == G_ADP_LOC), None)
                if loc:
                    args["LOCATION"] = loc["entity"]
                return [clause(G_EXIST, args, construction="existential", features=features)]

        frame = verb_lex.get("argument_structure") or {}
        required = frame.get("required_roles", [])
        arguments = {}
        unused = []
        for h in heads:
            case = h["case"]
            marker = explicit_markers.get(h["index"])
            role = None
            if marker == G_ADP_SOURCE:
                role = "SOURCE"
            elif marker == G_ADP_INSTR:
                role = "RECIPIENT" if "RECIPIENT" in required and "RECIPIENT" not in arguments else "INSTRUMENT"
            elif marker == G_ADP_LOC:
                role = "GOAL" if "GOAL" in required and "GOAL" not in arguments else "LOCATION"
            if role is None:
                role = {
                    "ACC": "PATIENT", "DAT": "RECIPIENT", "LOC": "LOCATION",
                    "ABL": "SOURCE", "INS": "INSTRUMENT", "GEN": "POSSESSOR",
                }.get(case)
            if role is None:
                unused.append(h)
            else:
                arguments[role] = h["entity"]
        subject_roles = []
        primary_subject_role = "THEME" if "THEME" in required and "AGENT" not in required else "AGENT"
        subject_roles.append(primary_subject_role)
        for alt in frame.get("role_alternatives", []):
            if len(alt) == 1 and alt[0] in {"AGENT", "THEME"} and alt[0] not in subject_roles:
                subject_roles.append(alt[0])

        explicit_subject = None
        if unused:
            explicit_subject = min(unused, key=lambda h: h["index"]) if not self.profile["syntax"]["clause_order"].startswith("V") else min(unused, key=lambda h: abs(h["index"] - pos))
            unused.remove(explicit_subject)
        if unused and "PATIENT" not in arguments:
            arguments["PATIENT"] = unused.pop(0)["entity"]
        if unused and "RECIPIENT" not in arguments:
            arguments["RECIPIENT"] = unused.pop(0)["entity"]

        implicit_subjects = []
        if explicit_subject is None and features.get("mood") == "IMP":
            index_id = verb_row["feature_bundle"].get("subject_index")
            agr = next((c for c in self.profile["agreement_system"]["cells"] if c["cell_id"] == index_id), None)
            if agr:
                for ref_cell in self.profile["reference_system"]["cells"]:
                    if condition_matches(ref_cell["condition"], agr["condition"]):
                        implicit_subjects.append(entity(reference=copy.deepcopy(ref_cell["condition"])))
        subject_entities = [explicit_subject["entity"]] if explicit_subject else implicit_subjects or [None]

        construction = forced_construction
        if construction == "content_question":
            features["question"] = "content"
        results = []
        for subj in subject_entities:
            for subject_role in subject_roles:
                out_args = copy.deepcopy(arguments)
                if subj is not None:
                    out_args[subject_role] = copy.deepcopy(subj)
                results.append(clause(predicate, out_args, construction=construction, features=copy.deepcopy(features)))
        return results

    def _content_parse(self, words: list[str], marker_index: int) -> list[dict]:
        """Parse a finite CONTENT complement around the generated complementizer."""
        order = self.profile["syntax"]["clause_order"]
        comp_pos = self.profile["syntax"]["complementizer_position"]
        main_verbs = []
        for i, word in enumerate(words):
            for lex, row in self._verb_candidates(word):
                roles = set((lex.get("argument_structure") or {}).get("required_roles", []))
                if "CONTENT" in roles:
                    main_verbs.append((i, lex, row))
        if not main_verbs:
            return []
        main_i, main_lex, main_row = main_verbs[-1]
        marker = words[marker_index]
        results = []
        if comp_pos == "clause_final":
            # SOV profile: OUTER-SUBJECT EMBEDDED-CLAUSE COMP MAIN-VERB.
            before = words[:marker_index]
            after = words[marker_index + 1:]
            for split in range(1, len(before) + 1):
                outer_prefix, embedded_words = before[:split], before[split:]
                if not embedded_words:
                    continue
                embedded = self._parse_words(embedded_words)
                outer = self._parse_words(outer_prefix + after)
                for e in embedded:
                    for o in outer:
                        if o.get("predicate") == main_lex["concept"]:
                            g = copy.deepcopy(o)
                            g["arguments"]["CONTENT"] = copy.deepcopy(e)
                            g["construction"] = "complement"
                            results.append(g)
        else:
            # SVO/VSO profiles: complementizer precedes the embedded clause. Try
            # every split and retain structures whose outer predicate licenses CONTENT.
            before = words[:marker_index]
            after = words[marker_index + 1:]
            for split in range(1, len(after)):
                embedded_words, outer_suffix = after[:split], after[split:]
                embedded = self._parse_words(embedded_words)
                outer = self._parse_words(before + outer_suffix)
                for e in embedded:
                    for o in outer:
                        if o.get("predicate") == main_lex["concept"]:
                            g = copy.deepcopy(o)
                            g["arguments"]["CONTENT"] = copy.deepcopy(e)
                            g["construction"] = "complement"
                            results.append(g)
        return results

    def _adverbial_parse(self, words: list[str], marker_index: int) -> list[dict]:
        comp_pos = self.profile["syntax"]["complementizer_position"]
        order = self.profile["syntax"]["clause_order"]
        if comp_pos == "clause_final":
            subordinate_words = words[:marker_index]
            main_words = words[marker_index + 1:]
        else:
            # Current non-final profiles linearize main clause before subordinate.
            before = words[:marker_index]
            after = words[marker_index + 1:]
            subordinate_words = after
            main_words = before
        sub = self._parse_words(subordinate_words)
        main = self._parse_words(main_words)
        results = []
        for s in sub:
            if s.get("type") != "clause":
                continue
            for m in main:
                if m.get("type") != "clause":
                    continue
                for role in ("TIME", "MANNER"):
                    g = copy.deepcopy(m)
                    g["arguments"][role] = copy.deepcopy(s)
                    g["construction"] = "adverbial"
                    results.append(g)
        return results

    def _parse_words(self, words: list[str]) -> list[dict]:
        if not words:
            return []
        coord = self.function_forms.get(G_COORD_ADD)
        if coord in words:
            i = words.index(coord)
            left = self._parse_words(words[:i])
            right = self._parse_words(words[i + 1:])
            return [{"type": "coordination", "members": [copy.deepcopy(a), copy.deepcopy(b)]} for a in left for b in right]

        analyses = []
        comp = self.function_forms.get(G_COMP)
        if comp in words:
            for i, word in enumerate(words):
                if word != comp:
                    continue
                analyses.extend(self._content_parse(words, i))
                analyses.extend(self._adverbial_parse(words, i))
        if not analyses:
            analyses = self._basic_clause(words)
            for candidate in self._phrase(words):
                if candidate not in analyses:
                    analyses.append(candidate)
        return analyses

    def analyze(self, sentence: str) -> dict:
        words = [w for w in sentence.strip().split() if w]
        if not words:
            raise ValueError("analysis input requires a written Losica expression")
        analyses = self._parse_words(words)
        # Content questions are identified from the generated interrogative forms.
        for g in analyses:
            if g.get("type") == "clause" and any(
                isinstance(v, dict) and v.get("concept") in {G_INT_PERSON, G_INT_THING, G_INT_PLACE}
                for v in g.get("arguments", {}).values()
            ):
                g["construction"] = "content_question"
                g.setdefault("features", {})["question"] = "content"
        return self._pack(sentence, analyses)

    @staticmethod
    def _pack(sentence: str, analyses: list[dict]) -> dict:
        # Deduplicate structurally identical analyses while retaining genuine surface ambiguity.
        import json
        unique = {}
        for graph in analyses:
            unique[json.dumps(graph, sort_keys=True, separators=(",", ":"))] = graph
        values = list(unique.values())
        return {
            "surface": sentence,
            "status": "single_reading" if len(values) == 1 else "multiple_readings" if values else "empty_reading_set",
            "analyses": values,
            "analysis_count": len(values),
            "method": "generated lexicon + generated paradigms + construction constraints",
        }


def analyze_surface(state: dict, sentence: str) -> dict:
    return SurfaceAnalyzer(state).analyze(sentence)
