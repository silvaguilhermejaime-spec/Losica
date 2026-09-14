"""POSIX publication with immutable run directories and one atomic current-pointer commit."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import shutil
import tempfile

@contextmanager
def transaction(out: Path, run_id: str):
    out = out.absolute()
    out.parent.mkdir(parents=True, exist_ok=True)
    store = out.parent / ("." + out.name + ".runs")
    store.mkdir(exist_ok=True)
    # The persistent lock inode serializes publishers.
    with (store / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=store))
        try:
            yield stage
            publish(out, store, stage, run_id)
        finally:
            shutil.rmtree(stage, ignore_errors=True)

def publish(out, store, stage, run_id):
    """Prepare immutable artifacts and commit by atomically advancing `current`."""
    final = store / run_id
    pointer = store / ".next"
    aliases = ((out, "candidates.tsv"), (Path(str(out) + ".diagnostics.json"), "diagnostics.json"))
    changed = []
    new_final = False
    try:
        for name in ("candidates.tsv", "diagnostics.json"):
            with (stage / name).open("rb") as f:
                os.fsync(f.fileno())
        if final.exists():
            # A run_id identifies one artifact byte set.
            import hashlib
            for name in ("candidates.tsv", "diagnostics.json"):
                with (stage / name).open("rb") as a, (final / name).open("rb") as b:
                    if hashlib.file_digest(a, "sha256").digest() != hashlib.file_digest(b, "sha256").digest():
                        raise ValueError("run identity conflict: completed artifacts differ")
        else:
            os.replace(stage, final)
            new_final = True
        for i, (alias, name) in enumerate(aliases):
            target = str(Path(store.name) / "current" / name)
            if alias.is_symlink() and os.readlink(alias) == target:
                continue
            backup = store / f".legacy-{i}"
            if alias.exists() or alias.is_symlink():
                os.replace(alias, backup)
            changed.append((alias, backup))
            alias.symlink_to(target)
        pointer.symlink_to(run_id)
        os.replace(pointer, store / "current")  # Transaction commit point.
    except BaseException:
        pointer.unlink(missing_ok=True)
        for alias, backup in reversed(changed):
            alias.unlink(missing_ok=True)
            if backup.exists() or backup.is_symlink():
                os.replace(backup, alias)
        if new_final:
            shutil.rmtree(final)
        raise
    # Commit status is fixed when `current` advances; backup cleanup is best-effort.
    for _, backup in changed:
        try:
            backup.unlink(missing_ok=True)
        except OSError:
            pass
