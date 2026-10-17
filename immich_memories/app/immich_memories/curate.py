"""Choosing an event's photos: grouping near-identical shots, picking the best
of each group, scoring and picking a spread of the best."""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

from .analysis import Analysis, similarity
from .immich import Photo
from .labels import LabelIndex


@dataclass
class Group:
    """Near-identical shots of the same moment; `best` is the one to show."""

    photos: list[Photo]
    best: Photo

    @property
    def others(self) -> list[Photo]:
        return [p for p in self.photos if p.id != self.best.id]


@dataclass(frozen=True)
class Strictness:
    """How hard to look for repeats. Similarity is analysis.similarity()."""

    stack_seconds: float  # near-identical shots must be this close in time...
    stack_similarity: float  # ...and at least this alike to be stacked
    scene_seconds: float  # an album won't hold two photos this close in time...
    scene_similarity: float  # ...that are at least this alike


STRICTNESS = {
    "light": Strictness(90, 0.85, 15 * 60, 0.75),
    "normal": Strictness(5 * 60, 0.75, 45 * 60, 0.62),
    "strong": Strictness(15 * 60, 0.68, 2 * 3600, 0.55),
}
BURST_SECONDS = 2


def group_similar(
    photos: list[Photo],
    analyses: dict[str, Analysis],
    strictness: Strictness = STRICTNESS["normal"],
) -> list[list[Photo]]:
    """Group burst shots and near-duplicates: Immich's duplicate detection,
    shots a second or two apart, and photos taken within a few minutes that
    look alike (similar colours and layout, see analysis.similarity)."""
    ordered = sorted(photos, key=lambda p: p.utc_dt)
    parent = {p.id: p.id for p in ordered}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    by_dup: dict[str, str] = {}
    for p in ordered:
        if p.stack_id:
            continue  # already in a stack; leave it alone
        if p.duplicate_id:
            if p.duplicate_id in by_dup:
                union(p.id, by_dup[p.duplicate_id])
            else:
                by_dup[p.duplicate_id] = p.id

    for i, p in enumerate(ordered):
        if p.stack_id:
            continue
        ap = analyses.get(p.id)
        for q in reversed(ordered[max(0, i - 40) : i]):
            if q.stack_id:
                continue
            dt = (p.utc_dt - q.utc_dt).total_seconds()
            if dt > strictness.stack_seconds:
                break
            aq = analyses.get(q.id)
            if not ap or not aq:
                if dt <= BURST_SECONDS:
                    union(p.id, q.id)
                continue
            sim = similarity(ap, aq)
            if (dt <= BURST_SECONDS and sim >= 0.5) or sim >= strictness.stack_similarity:
                union(p.id, q.id)

    groups: dict[str, list[Photo]] = {}
    for p in ordered:
        groups.setdefault(find(p.id), []).append(p)
    return list(groups.values())


def pick_best(photos: list[Photo], analyses: dict[str, Analysis]) -> Photo:
    """The best of near-identical shots.

    With people in them: the shot where the most people are facing the camera
    with their eyes open, then the sharpest faces. Without: the sharpest and
    best exposed. A favourite or higher star rating wins outright.
    """
    if len(photos) == 1:
        return photos[0]
    a = {p.id: analyses.get(p.id) for p in photos}
    max_faces = max((len(x.faces) for x in a.values() if x), default=0)

    def sharp(p):
        x = a[p.id]
        if not x:
            return 0.0
        return (x.face_sharpness if max_faces and x.faces else x.sharpness) or 0.0

    top_sharp = max(sharp(p) for p in photos) or 1.0

    def score(p):
        x = a[p.id]
        s = 0.0
        if x:
            s_sharp = sharp(p) / top_sharp
            if max_faces:
                looking = x.looking_count / max_faces
                smiling = sum(f.smiling for f in x.faces) / max_faces
                s = 0.5 * looking + 0.32 * s_sharp + 0.12 * x.exposure + 0.06 * smiling
            else:
                s = 0.75 * s_sharp + 0.25 * x.exposure
        s += 1.0 if p.is_favorite else 0.0
        s += 0.1 * p.rating
        return s

    return max(photos, key=score)


def make_groups(photos: list[Photo], analyses: dict[str, Analysis], strictness: Strictness = STRICTNESS["normal"]) -> list[Group]:
    return [Group(g, pick_best(g, analyses)) for g in group_similar(photos, analyses, strictness)]


def score_photos(groups: list[Group], analyses: dict[str, Analysis], labels: LabelIndex) -> dict[str, float]:
    """How much each group's best photo deserves a place in the memory."""
    reps = [g.best for g in groups]
    sharp_values = sorted(analyses[p.id].sharpness for p in reps if p.id in analyses)

    def percentile(v: float) -> float:
        if not sharp_values:
            return 0.5
        return bisect.bisect_left(sharp_values, v) / len(sharp_values)

    scores = {}
    for g in groups:
        p = g.best
        x = analyses.get(p.id)
        s = 0.0
        sharp_pct = percentile(x.sharpness) if x else 0.5
        s += 0.25 * sharp_pct
        if x:
            s += 0.1 * x.exposure
            if x.faces:
                s += 0.05 + 0.15 * x.looking_fraction
        s += 0.12 * min(3, len(p.named_people))
        if labels.kinds(p.id, "highlight"):
            s += 0.25
        if p.is_favorite:
            s += 0.6
        s += 0.06 * p.rating
        # Moments someone photographed over and over were probably special.
        s += 0.05 * math.log2(len(g.photos))
        if x and sharp_pct < 0.1 and not p.is_favorite:
            s -= 0.3
        scores[p.id] = s
    return scores


def target_size(candidates: int, max_photos: int, min_photos: int = 8) -> int:
    return max(min(candidates, min_photos), min(max_photos, round(3 * math.sqrt(candidates))))


def select(
    groups: list[Group],
    scores: dict[str, float],
    max_photos: int,
    analyses: dict[str, Analysis] | None = None,
    strictness: Strictness = STRICTNESS["normal"],
) -> list[Photo]:
    """A spread of the best photos across the event, without repeats.

    Most picks come from splitting the event into equal slices by time and
    taking the best of each, so a long day isn't all one hour; the rest go to
    the highest scores overall. A photo is skipped if the album already has
    one taken around the same time that looks like it (the same scene from a
    slightly different angle, say), so a run of similar shots gives one photo.
    """
    analyses = analyses or {}
    reps = sorted((g.best for g in groups), key=lambda p: p.local_dt)
    n = target_size(len(reps), max_photos)
    chosen: dict[str, Photo] = {}

    def repeats(p: Photo) -> bool:
        a = analyses.get(p.id)
        if not a:
            return False
        for c in chosen.values():
            b = analyses.get(c.id)
            if not b or abs((p.utc_dt - c.utc_dt).total_seconds()) > strictness.scene_seconds:
                continue
            if similarity(a, b) >= strictness.scene_similarity:
                return True
        return False

    def best_first(ps):
        return sorted(ps, key=lambda p: scores.get(p.id, 0), reverse=True)

    buckets = max(1, round(n * 0.7))
    size = len(reps) / buckets
    for b in range(buckets):
        for p in best_first(reps[int(b * size) : int((b + 1) * size)]):
            if not repeats(p):
                chosen[p.id] = p
                break
    for p in best_first(reps):
        if len(chosen) >= n:
            break
        if p.id not in chosen and not repeats(p):
            chosen[p.id] = p
    return sorted(chosen.values(), key=lambda p: p.local_dt)


def pick_cover(photos: list[Photo], scores: dict[str, float], analyses: dict[str, Analysis], labels: LabelIndex) -> Photo:
    def cover_score(p):
        x = analyses.get(p.id)
        s = scores.get(p.id, 0)
        if x and x.faces and x.looking_fraction > 0.6:
            s += 0.2
        if labels.kinds(p.id, "highlight"):
            s += 0.2
        return s

    return max(photos, key=cover_score)
