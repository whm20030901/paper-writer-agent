from __future__ import annotations

from abc import ABC, abstractmethod


class WriterAgentInterface(ABC):
    @abstractmethod
    def write(self, task: str, outline: str, revision_notes: str, previous_review: str = ""):
        raise NotImplementedError


class ReviewerAgentInterface(ABC):
    @abstractmethod
    def review(self, draft: str):
        raise NotImplementedError


class QualityGateInterface(ABC):
    @abstractmethod
    def should_stop(self, score: int, threshold: int = 8) -> bool:
        raise NotImplementedError
