"""Project folder: one game being translated.

    project.json   source ISO, plugin id, disc info
    state.json     hashes of unpacked files, to find what the user changed
    ...            the rest is up to the plugin
"""
import hashlib
import json
import os
from typing import Dict


def file_hash(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Project:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.meta: Dict = self._load("project.json")
        self.state: Dict[str, str] = self._load("state.json")

    @classmethod
    def create(cls, root: str, iso_path: str, plugin_id: str, info: Dict) -> "Project":
        os.makedirs(root, exist_ok=True)
        meta = {"iso": os.path.abspath(iso_path), "plugin": plugin_id, **info}
        with open(os.path.join(root, "project.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return cls(root)

    def _load(self, name: str) -> Dict:
        p = os.path.join(self.root, name)
        if not os.path.exists(p):
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def save_meta(self):
        with open(self.path("project.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=2)

    def save_state(self):
        with open(self.path("state.json"), "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=0, sort_keys=True)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    @property
    def iso_path(self) -> str:
        return self.meta["iso"]

    def remember(self, rel: str):
        """Mark a just-unpacked file as pristine."""
        self.state[rel] = file_hash(self.path(rel))

    def changed(self, prefix: str = ""):
        """Unpacked files whose content differs from when they were unpacked."""
        for rel, h in sorted(self.state.items()):
            if rel.startswith(prefix) and os.path.exists(self.path(rel)) and file_hash(self.path(rel)) != h:
                yield rel
