"""Small, dependency-free statistics helpers.

The pipeline must run on a bare Python (no numpy/scipy) so that the agent stack
is portable; every test used for evidence scoring therefore lives here:
Pearson/Spearman correlation with a Student-t p-value, Kaplan–Meier curves,
the log-rank test, Benjamini–Hochberg FDR and robust z-scores.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# special functions
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-12) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a,b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """P(T > |t|) * 2 for a two-sided Student-t test."""
    if df <= 0:
        return 1.0
    x = df / (df + t * t)
    return betainc(df / 2.0, 0.5, x)


def chi2_sf(x: float, df: int = 1) -> float:
    """Survival function of the chi-square distribution."""
    if x <= 0:
        return 1.0
    if df == 1:
        return math.erfc(math.sqrt(x / 2.0))
    return betainc(df / 2.0, 0.5, 1.0) if df > 1 else 1.0


# ---------------------------------------------------------------------------
# descriptive statistics
# ---------------------------------------------------------------------------
def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def median(xs: Sequence[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def robust_z(value: float, population: Sequence[float]) -> float:
    """Median/MAD z-score, clipped to [-5, 5]."""
    if not population:
        return 0.0
    med = median(population)
    mad = median([abs(x - med) for x in population]) or 1e-9
    z = 0.6745 * (value - med) / mad
    return max(-5.0, min(5.0, z))


def percentile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def minmax(xs: Iterable[float]) -> tuple[float, float]:
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    if not xs:
        return 0.0, 1.0
    return min(xs), max(xs)


def scale01(value: float, lo: float, hi: float) -> float:
    if hi - lo <= 1e-12:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------
def pearson(x: Sequence[float], y: Sequence[float]) -> tuple[float, float, int]:
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    n = len(pairs)
    if n < 4:
        return 0.0, 1.0, n
    xs, ys = zip(*pairs)
    mx, my = mean(xs), mean(ys)
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0, 1.0, n
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    r = sxy / math.sqrt(sxx * syy)
    r = max(-1.0, min(1.0, r))
    if abs(r) >= 1.0:
        return r, 0.0, n
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return r, t_sf(abs(t), n - 2), n


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> tuple[float, float, int]:
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 4:
        return 0.0, 1.0, len(pairs)
    xs, ys = zip(*pairs)
    return pearson(_ranks(list(xs)), _ranks(list(ys)))


# ---------------------------------------------------------------------------
# survival
# ---------------------------------------------------------------------------
def kaplan_meier(times: Sequence[float], events: Sequence[int]) -> list[tuple[float, float, int]]:
    """Return the step curve as (time, survival, at_risk)."""
    data = sorted([(t, e) for t, e in zip(times, events) if t is not None and t > 0])
    n = len(data)
    curve: list[tuple[float, float, int]] = [(0.0, 1.0, n)]
    surv = 1.0
    at_risk = n
    i = 0
    while i < len(data):
        t = data[i][0]
        d = 0
        c = 0
        while i < len(data) and data[i][0] == t:
            if data[i][1]:
                d += 1
            else:
                c += 1
            i += 1
        if at_risk > 0 and d > 0:
            surv *= 1.0 - d / at_risk
        at_risk -= d + c
        curve.append((t, surv, max(at_risk, 0)))
    return curve


def logrank(times: Sequence[float], events: Sequence[int], groups: Sequence[int]) -> tuple[float, float]:
    """Two-group log-rank test -> (chi2, p)."""
    order = sorted(range(len(times)), key=lambda i: times[i])
    n1 = sum(1 for g in groups if g == 1)
    n0 = len(groups) - n1
    if n1 == 0 or n0 == 0:
        return 0.0, 1.0
    at_risk0, at_risk1 = n0, n1
    o1 = e1 = v = 0.0
    i = 0
    while i < len(order):
        t = times[order[i]]
        d1 = d0 = 0
        c1 = c0 = 0
        while i < len(order) and times[order[i]] == t:
            idx = order[i]
            if groups[idx] == 1:
                if events[idx]:
                    d1 += 1
                else:
                    c1 += 1
            else:
                if events[idx]:
                    d0 += 1
                else:
                    c0 += 1
            i += 1
        d = d1 + d0
        n = at_risk0 + at_risk1
        if n > 0 and d > 0:
            frac = at_risk1 / n
            o1 += d1
            e1 += d * frac
            if n > 1:
                v += d * frac * (1 - frac) * (n - d) / (n - 1)
        at_risk0 -= d0 + c0
        at_risk1 -= d1 + c1
    if v <= 0:
        return 0.0, 1.0
    chi2 = (o1 - e1) ** 2 / v
    return chi2, chi2_sf(chi2, 1)


def hazard_ratio(times: Sequence[float], events: Sequence[int], groups: Sequence[int]) -> float:
    """Mantel–Haenszel (log-rank) hazard ratio for group 1 vs 0."""
    order = sorted(range(len(times)), key=lambda i: times[i])
    n1 = sum(1 for g in groups if g == 1)
    n0 = len(groups) - n1
    at_risk0, at_risk1 = n0, n1
    o1 = e1 = 0.0
    i = 0
    while i < len(order):
        t = times[order[i]]
        d1 = d0 = c1 = c0 = 0
        while i < len(order) and times[order[i]] == t:
            idx = order[i]
            if groups[idx] == 1:
                d1 += 1 if events[idx] else 0
                c1 += 0 if events[idx] else 1
            else:
                d0 += 1 if events[idx] else 0
                c0 += 0 if events[idx] else 1
            i += 1
        d = d1 + d0
        n = at_risk0 + at_risk1
        if n > 0 and d > 0:
            o1 += d1
            e1 += d * (at_risk1 / n)
        at_risk0 -= d0 + c0
        at_risk1 -= d1 + c1
    if o1 <= 0 or e1 <= 0:
        return 1.0
    return o1 / e1


# ---------------------------------------------------------------------------
# multiple testing
# ---------------------------------------------------------------------------
def bh_fdr(pvalues: Sequence[float]) -> list[float]:
    """Benjamini–Hochberg adjusted p-values (same order as input)."""
    n = len(pvalues)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvalues[i])
    adj = [1.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        val = min(prev, pvalues[idx] * n / rank)
        adj[idx] = min(1.0, val)
        prev = adj[idx]
    return adj
