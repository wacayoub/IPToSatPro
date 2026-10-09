"""Optional r70 mirror of *existing* manual lock persistence.

This NEVER becomes the source of truth: r69 native overrides stay authoritative.
Runs only on user-initiated lock/unlock actions (never on zap or candidate list).
"""
import functools
import os

try:
    from .r70_safety_core import ManualLockGuard
except ImportError:
    try:
        from Plugins.Extensions.SatIPTVBridge.r70_safety_core import ManualLockGuard
    except ImportError:
        from r70_safety_core import ManualLockGuard


def attach_mapping_hooks(namespace):
    """Wrap native functions exactly once while preserving their returns."""
    if namespace.get("_r70_lock_hooks_attached", False):
        return False
    save = namespace.get("_save_override")
    unlock = namespace.get("_remove_override")
    canonical = namespace.get("sat_service_key")
    fingerprint = namespace.get("channel_fingerprint")
    path = namespace.get("OVERRIDE_PATH")
    if not all(callable(x) for x in (save, unlock, canonical, fingerprint)):
        return False
    if not isinstance(path, str) or not path:
        return False
    directory = os.path.dirname(os.path.abspath(path))
    mirror_path = os.path.join(directory, "r70-manual-locks.json")
    backup_path = os.path.join(directory, "r70-manual-overrides.backup.json")

    @functools.wraps(save)
    def protected_save(*args, **kwargs):
        # Native r69 mapping *must* be committed first and remain authoritative.
        result = save(*args, **kwargs)
        try:
            sat_ref = args[0] if args else kwargs.get("sat_ref_string", "")
            candidate = args[1] if len(args) > 1 else kwargs.get("channel")
            if sat_ref and isinstance(candidate, dict):
                mirror = ManualLockGuard(mirror_path)
                mirror.keep(canonical(sat_ref), fingerprint(candidate))
                mirror.snapshot_legacy(path, backup_path)
        except Exception:
            # Auxiliary mirror/backup failure can never break a saved native lock.
            pass
        return result

    @functools.wraps(unlock)
    def protected_unlock(*args, **kwargs):
        result = unlock(*args, **kwargs)
        try:
            sat_ref = args[0] if args else kwargs.get("sat_ref_string", "")
            if sat_ref:
                mirror = ManualLockGuard(mirror_path)
                mirror.drop(canonical(sat_ref))
                mirror.snapshot_legacy(path, backup_path)
        except Exception:
            pass
        return result

    namespace["_save_override"] = protected_save
    namespace["_remove_override"] = protected_unlock
    namespace["_r70_lock_hooks_attached"] = True
    return True
