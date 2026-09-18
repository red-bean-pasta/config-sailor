from typing import Iterable

from config_sailor.patch.base.schemas import CombineMode, Combine


def apply_combine(
        combine: Combine,
        left: Iterable[int],
        right: Iterable[int]
) -> list[int]:
    return _logic_operators[combine.mode](left, right)
    
    
def _union(
        left: Iterable[int],
        right: Iterable[int],
) -> list[int]:
    result = list(left)
    left_set = set(left)
    for i in right:
        if i not in left_set:
            result.append(i)
    return result


def _intersect(
        left: Iterable[int],
        right: Iterable[int],
) -> list[int]:
    return _intersect_or_symmetric_difference(left, right, False)


def _difference(
        left: Iterable[int],
        right: Iterable[int],
) -> list[int]:
    result = []
    right_set = set(right)
    for i in left:
        if i not in right_set:
            result.append(i)
    return result


def _append(
        left: Iterable[int],
        right: Iterable[int],
) -> list[int]:
    return list(left) + list(right)


# Not implemented
def _symmetric_difference(
        left: Iterable[int],
        right: Iterable[int],
) -> list[int]:
    return _intersect_or_symmetric_difference(left, right, True)


def _intersect_or_symmetric_difference(
        left: Iterable[int],
        right: Iterable[int],
        is_difference: bool
) -> list[int]:
    intersection = set(left) & set(right)
    result = []
    for i in left:
        if i not in intersection if is_difference else i in intersection:
            result.append(i)
    return result


_logic_operators = {
    CombineMode.UNION: _union,
    CombineMode.INTERSECT: _intersect,
    CombineMode.DIFFERENCE: _difference,
    CombineMode.APPEND: _append,
}