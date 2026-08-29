"""Runtime guard for repeatedly invalid Pinterest pins.

Python imports sitecustomize automatically at startup. We patch the downloader's
Pinterest discovery so known-dead pins are skipped before yt-dlp probes them,
and pins that fail repeatedly are promoted to the persistent blacklist.
"""
from pathlib import Path
import re

try:
    from bot import downloader as _d
except Exception:
    _d = None

if _d is not None:
    _orig_discover = _d.discover_from_source
    _blacklist_path = Path("invalid_pins.txt")
    _failures_path = Path("pin_failures.txt")

    def _pin_id(url: str) -> str:
        m = re.search(r"/pin/([0-9]{6,})", url or "", re.I)
        return m.group(1) if m else ""

    def _load_blacklist() -> set[str]:
        if not _blacklist_path.exists():
            return set()
        return {
            line.strip()
            for line in _blacklist_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    def _load_failures() -> dict[str, int]:
        out: dict[str, int] = {}
        if not _failures_path.exists():
            return out
        for line in _failures_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) != 2:
                continue
            try:
                out[parts[0]] = int(parts[1])
            except ValueError:
                pass
        return out

    def _save_failures(data: dict[str, int]) -> None:
        text = "".join(f"{pin_id}\t{count}\n" for pin_id, count in sorted(data.items()))
        _failures_path.write_text(text, encoding="utf-8")

    def _mark_failed(pin_id: str) -> None:
        if not pin_id:
            return
        failures = _load_failures()
        failures[pin_id] = failures.get(pin_id, 0) + 1
        if failures[pin_id] >= 2:
            blocked = _load_blacklist()
            if pin_id not in blocked:
                with _blacklist_path.open("a", encoding="utf-8") as f:
                    f.write(pin_id + "\n")
                print("Pinterest pin permanently blacklisted after repeated failures:", pin_id)
            failures.pop(pin_id, None)
        _save_failures(failures)

    def _clear_failure(pin_id: str) -> None:
        if not pin_id:
            return
        failures = _load_failures()
        if pin_id in failures:
            failures.pop(pin_id, None)
            _save_failures(failures)

    def _probe_pin_guarded(pin_url: str, cfg):
        pin_id = _pin_id(pin_url)
        if pin_id and pin_id in _load_blacklist():
            print("Known invalid Pinterest pin skipped before probe:", pin_id)
            return None
        item = _d._probe_pin(pin_url, cfg)
        if item is None:
            _mark_failed(pin_id)
        else:
            _clear_failure(pin_id)
        return item

    def _discover_guarded(source_url: str, cfg):
        resolved = _d._resolve_short_url(source_url)

        if _d._is_instagram(resolved):
            return _orig_discover(source_url, cfg)

        if cfg.get("discovery", {}).get("exact_pin_sources_only", True) and not _d._is_pin(resolved):
            print("Rejected unsupported/non-individual source:", resolved)
            return []

        if _d._is_pin(resolved):
            item = _probe_pin_guarded(resolved, cfg)
            return [item] if item else []

        pin_urls = _d._get_profile_pin_urls(resolved, cfg)
        candidates = []
        for pin_url in pin_urls:
            item = _probe_pin_guarded(pin_url, cfg)
            if item:
                candidates.append(item)
        return candidates

    _d.discover_from_source = _discover_guarded
