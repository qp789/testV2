"""抽题策略：按分类/难度过滤，再按题量抽取。"""

from __future__ import annotations

import random
from typing import Iterable, Sequence

from .models import Question


class QuizError(Exception):
    """可预期的业务错误（例如筛选后没有题目）。"""


def select_questions(
    bank: Sequence[Question],
    count: int,
    categories: Iterable[str] | None = None,
    difficulties: Iterable[int] | None = None,
    seed: int | None = None,
) -> list[Question]:
    if count <= 0:
        raise QuizError("题目数量必须大于 0")

    pool = list(bank)
    if categories:
        wanted = {name.strip().lower() for name in categories if name.strip()}
        if wanted:
            pool = [q for q in pool if q.category.lower() in wanted]
    if difficulties:
        levels = set(difficulties)
        pool = [q for q in pool if q.difficulty in levels]
    if not pool:
        raise QuizError("没有符合筛选条件的题目")

    picked = min(count, len(pool))
    return random.Random(seed).sample(pool, picked)
