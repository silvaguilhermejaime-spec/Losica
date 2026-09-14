"""Disk-indexed diagnostics with bounded examples."""
import sqlite3
from collections import Counter

EXAMPLE_LIMIT = 20
ROOT_EXAMPLE_LIMIT = 20

class StreamingDiagnostics:
    def __init__(self, path, categories, relation_ids):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA temp_store=FILE")
        self.conn.execute("PRAGMA cache_size=-2048")
        self.conn.execute("CREATE TABLE proto_map(category TEXT, candidate TEXT, root TEXT, proto TEXT)")
        self.conn.execute("CREATE INDEX collision_roots ON proto_map(category,proto,root)")
        self.conn.execute("CREATE INDEX collision_candidates ON proto_map(category,proto,candidate)")
        self.total = Counter({c["id"]: 0 for c in categories})
        self.sources = Counter({"primitive": 0, "lexical_process": 0})
        self.branches = Counter()
        self.matches = Counter({r: 0 for r in relation_ids})
        self.ambiguous = Counter()
        self.derivation_ambiguous = Counter()

    def add(self, category, candidate_id, root, protos, branches, source, matches):
        self.total[category] += 1
        self.sources[source] += 1
        self.branches[category] += branches
        self.ambiguous[category] += len(protos) > 1
        self.derivation_ambiguous[category] += branches > 1
        self.matches.update(m.relation_id for m in matches)
        self.conn.executemany("INSERT INTO proto_map VALUES(?,?,?,?)",
                              ((category, candidate_id, root, p) for p in protos))

    def summarize(self):
        self.conn.commit()
        result = []
        for cat in sorted(self.total):
            query = """SELECT proto, COUNT(DISTINCT root), COUNT(DISTINCT candidate)
                       FROM proto_map WHERE category=? GROUP BY proto
                       HAVING COUNT(DISTINCT root)>1 ORDER BY proto"""
            count, examples = 0, []
            for proto, root_count, candidate_count in self.conn.execute(query, (cat,)):
                count += 1
                if len(examples) < EXAMPLE_LIMIT:
                    roots = [r[0] for r in self.conn.execute(
                        "SELECT DISTINCT root FROM proto_map WHERE category=? AND proto=? ORDER BY root LIMIT ?",
                        (cat, proto, ROOT_EXAMPLE_LIMIT))]
                    examples.append({"proto": proto, "distinct_root_count": root_count,
                                     "distinct_candidate_count": candidate_count, "roots": roots,
                                     "roots_truncated": root_count > len(roots)})
            candidate_collisions = self.conn.execute("""
                SELECT COUNT(*) FROM (SELECT proto FROM proto_map WHERE category=?
                GROUP BY proto HAVING COUNT(DISTINCT candidate)>1)""", (cat,)).fetchone()[0]
            result.append({"category_id": cat, "emitted_candidate_count": self.total[cat],
                           "historical_branch_count": self.branches[cat],
                           "historically_ambiguous_count": self.ambiguous[cat],
                           "derivationally_ambiguous_count": self.derivation_ambiguous[cat],
                           "proto_collision_group_count": count,
                           "candidate_collision_group_count": candidate_collisions,
                           "proto_collision_examples": examples,
                           "collision_examples_truncated": count > len(examples)})
        return result

    def close(self):
        self.conn.close()
