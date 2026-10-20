"""Make a local backlog file show the versions the program has already landed.

The notes stay in ``backlog/`` and are not part of a stage skill. This script
only reads the status block and rewrites it from ``backlog_landed.py``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


START = "<!-- backlog-status:start -->"
END = "<!-- backlog-status:end -->"
FILE_VERSION = re.compile(r"^file_version: (?P<version>\d+)$")
ITEM = re.compile(
    r"^- (?P<id>[a-z0-9-]+) version (?P<version>\d+) — (?P<title>.+)$"
)


def reconcile_text(text: str, landed: dict[str, int]) -> str:
    """Return ``text`` with the status block matched to ``landed`` versions."""
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < start:
        raise ValueError("backlog status block is missing")
    body_start = start + len(START)
    block = text[body_start:end]
    file_version, items = _parse_block(block)
    changed = False
    for item in items:
        done = landed.get(item["id"], 0) >= item["version"]
        status = "done" if done else "open"
        if item["status"] != status:
            item["status"] = status
            changed = True
    if changed:
        file_version += 1
    rendered = _render_block(file_version, items)
    if rendered == block:
        return text
    return text[:body_start] + rendered + text[end:]


def reconcile_workspace(workspace_root: Path) -> list[str]:
    """Rewrite each local backlog file. Return the lines that changed."""
    from backlog_landed import LANDED_VERSIONS

    backlog_root = workspace_root / "backlog"
    if not backlog_root.is_dir():
        return []
    messages: list[str] = []
    for path in sorted(backlog_root.glob("*.md")):
        landed = LANDED_VERSIONS.get(path.name)
        if landed is None:
            messages.append(f"error: {path.name} has no landed versions")
            continue
        original = path.read_text(encoding="utf-8")
        try:
            updated = reconcile_text(original, landed)
        except ValueError as error:
            messages.append(f"error: {path.name} {error}")
            continue
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            messages.append(f"updated {path.name}")
    return messages


def _parse_block(block: str) -> tuple[int, list[dict[str, object]]]:
    file_version: int | None = None
    status: str | None = None
    items: list[dict[str, object]] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        version_match = FILE_VERSION.match(line)
        if version_match:
            file_version = int(version_match.group("version"))
            continue
        if line == "## Open":
            status = "open"
            continue
        if line == "## Done":
            status = "done"
            continue
        item_match = ITEM.match(line)
        if item_match is None or status is None:
            continue
        items.append(
            {
                "id": item_match.group("id"),
                "version": int(item_match.group("version")),
                "title": item_match.group("title"),
                "status": status,
            }
        )
    if file_version is None:
        raise ValueError("file_version is missing")
    if not items:
        raise ValueError("no backlog items")
    return file_version, items


def _render_block(file_version: int, items: list[dict[str, object]]) -> str:
    lines = ["", f"file_version: {file_version}", "", "## Open", ""]
    lines.extend(_section_lines([item for item in items if item["status"] == "open"]))
    lines.extend(["## Done", ""])
    lines.extend(_section_lines([item for item in items if item["status"] == "done"]))
    return "\n".join(lines)


def _section_lines(items: list[dict[str, object]]) -> list[str]:
    if not items:
        return ["- (none)", ""]
    return [_item_line(item) for item in items] + [""]


def _item_line(item: dict[str, object]) -> str:
    return f"- {item['id']} version {item['version']} — {item['title']}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match local backlog status to versions the program has landed."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()
    messages = reconcile_workspace(args.workspace_root)
    errors = [message for message in messages if message.startswith("error:")]
    for message in messages:
        print(message)
    if not messages:
        print("backlog matches landed versions")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
