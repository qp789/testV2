"""题型插件注册表：新增题型只需注册一个判分函数。"""

from __future__ import annotations

from typing import Callable

from .models import Question

Scorer = Callable[[Question, object], bool]


def normalize_choice(choice: object) -> list[int]:
    """把前端传来的 int / list[int] / None 统一成去重后的下标列表。"""
    if choice is None:
        return []
    if isinstance(choice, bool):
        return []
    if isinstance(choice, int):
        return [choice]
    if isinstance(choice, (list, tuple)):
        return sorted({int(item) for item in choice if isinstance(item, int) and not isinstance(item, bool)})
    return []


class PluginRegistry:
    def __init__(self) -> None:
        self._scorers: dict[str, Scorer] = {}

    def register(self, kind: str) -> Callable[[Scorer], Scorer]:
        def decorator(scorer: Scorer) -> Scorer:
            self._scorers[kind] = scorer
            return scorer

        return decorator

    def kinds(self) -> list[str]:
        return sorted(self._scorers)

    def score(self, question: Question, choice: object) -> tuple[bool, int]:
        scorer = self._scorers.get(question.kind)
        if scorer is None:
            raise ValueError(f"没有注册题型：{question.kind}")
        correct = scorer(question, choice)
        return correct, (question.max_points if correct else 0)


registry = PluginRegistry()


@registry.register("single")
def _single(question: Question, choice: object) -> bool:
    return normalize_choice(choice) == list(question.answers)


@registry.register("judge")
def _judge(question: Question, choice: object) -> bool:
    return normalize_choice(choice) == list(question.answers)


@registry.register("multi")
def _multi(question: Question, choice: object) -> bool:
    return normalize_choice(choice) == sorted(question.answers)
