from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    purpose: str


class SkillManager:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def install(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def describe(self) -> str:
        if not self._skills:
            return "No skills installed"
        return "\n".join([f"- {s.name}: {s.purpose}" for s in self._skills.values()])


def build_default_skills() -> SkillManager:
    manager = SkillManager()
    manager.install(Skill("citation-formatting", "Format references in academic style"))
    manager.install(Skill("evidence-tracking", "Track claims back to retrieved evidence"))
    manager.install(Skill("argument-structuring", "Improve logical structure of sections"))
    return manager
