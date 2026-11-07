"""Turn a set of failed URL probes into a single machine-readable verdict.

Why this exists
---------------
When every URL of a source fails, the editor used to show one red badge per
URL and nothing else. A user, after an evening lost to it: setting up a new
source failed on every address, and the actual cause was a VPN endpoint whose
IP the provider blocks. Nothing on screen pointed there — and the distinction
matters, because "the server refused you" and "nothing answered" call for
opposite actions.

The probe layer already knows enough to tell them apart; nobody was asking it.
A ``403``/``405`` means the host ANSWERED and declined, so DNS, routing and the
address are all fine and the problem is *who you appear to be*. A timeout means
the opposite. An ``INACTIVE`` account status means the server looked you up and
said the subscription is not live — no amount of address-fiddling helps.

UI-free, deliberately
---------------------
This module returns a :class:`Diagnosis` enum and the counts behind it. It does
NOT return a sentence. ``provider_probe`` opens by promising exactly that — no
user-facing presentation, no English in ``core`` — so a headless backend can
reuse it and a translation can exist later. Rendering lives in the GUI.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import Enum

from streamselect.core.provider_probe import ProbeResult, ProbeStatus

#: HTTP statuses that mean "the host answered and refused you". A provider
#: returns these when the calling IP is blocked (a VPN exit node shared with
#: abusers is the common case) or when the subscription no longer entitles the
#: request. Both are about the CALLER, never about the address being wrong —
#: which is why they must not be read as "this host is unreliable".
REFUSAL_STATUSES: frozenset[str] = frozenset({"403", "405", "401", "429"})

#: HTTP statuses that mean "the host answered, but nothing lives at this path".
#: The server is up and reachable; the address (usually its path or port) is
#: not an Xtream API. Distinct from a refusal: changing the address helps here,
#: and only here.
WRONG_ADDRESS_STATUSES: frozenset[str] = frozenset({"400", "404", "410"})

#: Probe outcomes in which an Xtream server answered as one (whatever it said
#: about the account). Such a host is the right address; if it refuses later,
#: it is refusing the caller, not being the wrong server.
ANSWERED_AS_XTREAM: frozenset[ProbeStatus] = frozenset(
    {ProbeStatus.ACTIVE, ProbeStatus.INACTIVE, ProbeStatus.AUTH_FAILED})


class Diagnosis(str, Enum):
    """Why every URL failed, as a category the UI can phrase."""

    SUBSCRIPTION_INACTIVE = "subscription_inactive"
    CREDENTIALS_REJECTED = "credentials_rejected"
    REFUSED_BY_HOST = "refused_by_host"
    TEMPORARILY_BLOCKED = "temporarily_blocked"
    WRONG_ADDRESS = "wrong_address"
    UNREACHABLE = "unreachable"
    MIXED = "mixed"
    NONE = "none"


@dataclass(frozen=True)
class DiagnosisReport:
    """A verdict plus the evidence for it.

    Attributes:
        diagnosis: The category.
        total: How many URLs were probed.
        refusal_codes: Distinct HTTP refusal codes seen, sorted — evidence the
            UI can quote so the verdict is checkable rather than magic.
        counts: Probe status -> how many URLs ended that way.
        answered: URLs that answered as an Xtream server in this run — the
            caller keeps them, so a later refusal from one of them reads as a
            block rather than a bad address (:attr:`Diagnosis.TEMPORARILY_BLOCKED`).
    """

    diagnosis: Diagnosis
    total: int
    refusal_codes: tuple[str, ...]
    counts: dict[ProbeStatus, int]
    answered: tuple[str, ...] = ()


def _refusal_code(result: ProbeResult) -> str | None:
    """The HTTP refusal code in *result*, if it is one.

    ``detail`` carries the status code for ``HTTP_ERROR`` (documented on
    ``ProbeResult``). It is matched as a substring rather than compared whole
    because callers have historically stored it both bare ("403") and decorated
    ("HTTP 403", "403 Forbidden") — pinning the exact spelling would make this
    silently stop recognising refusals the first time that phrasing changed.
    """
    if result.status is not ProbeStatus.HTTP_ERROR:
        return None
    detail = result.detail or ""
    return next((code for code in sorted(REFUSAL_STATUSES) if code in detail), None)


def _norm(url: str) -> str:
    return url.rstrip("/")


def _wrong_address(result: ProbeResult) -> bool:
    """The host answered, but not as an Xtream API at this address."""
    if result.status is ProbeStatus.NOT_XTREAM:
        return True
    # Substring, like ``_refusal_code``: callers spell the code both bare and
    # decorated.
    detail = result.detail or ""
    return (result.status is ProbeStatus.HTTP_ERROR
            and any(code in detail for code in WRONG_ADDRESS_STATUSES))


def diagnose(results: Sequence[ProbeResult],
             answered_before: Collection[str] = ()) -> DiagnosisReport:
    """Explain why none of *results* succeeded.

    Ordered by how much the evidence actually settles, not by severity. A
    server that names the account state has told us the answer outright; a
    refusal code narrows it to the caller; a timeout only says "nothing came
    back", which is the weakest signal and therefore the last resort.

    Args:
        results: Probe results for every configured URL. A sequence containing
            any success returns :attr:`Diagnosis.NONE` — this only explains a
            total failure, and a partial failure is normal (that is what having
            several addresses is FOR).
        answered_before: URLs known to have answered as an Xtream server
            earlier — a past success, or an earlier test in this session
            (including one that rejected the password). A refusal from one of
            these is a block on the caller, most often the provider locking
            the IP out for a while after failed logins.

    Returns:
        The verdict and its evidence.
    """
    counts = Counter(r.status for r in results)
    total = len(results)
    answered = tuple(r.url for r in results if r.status in ANSWERED_AS_XTREAM)

    def report(d: Diagnosis, codes: tuple[str, ...] = ()) -> DiagnosisReport:
        return DiagnosisReport(d, total, codes, dict(counts), answered)

    if not results or any(r.success for r in results):
        return report(Diagnosis.NONE)

    codes = tuple(sorted({c for c in (_refusal_code(r) for r in results) if c}))

    # The server looked the account up and reported on it. Nothing about the
    # address or the network is in question.
    if counts[ProbeStatus.INACTIVE]:
        return report(Diagnosis.SUBSCRIPTION_INACTIVE, codes)
    if counts[ProbeStatus.AUTH_FAILED]:
        return report(Diagnosis.CREDENTIALS_REJECTED, codes)

    # Every host answered, and every one declined. The addresses work; the
    # caller is the problem — a blocked IP being much the most common reason.
    # If one of them answered as an Xtream server before, it is the right
    # address refusing now: a block, usually temporary after failed logins.
    if codes and counts[ProbeStatus.HTTP_ERROR] == total:
        known = {_norm(u) for u in answered_before}
        if any(_norm(r.url) in known for r in results if _refusal_code(r)):
            return report(Diagnosis.TEMPORARILY_BLOCKED, codes)
        return report(Diagnosis.REFUSED_BY_HOST, codes)

    # Every host answered, and none of them is an Xtream API at that address.
    if all(_wrong_address(r) for r in results):
        return report(Diagnosis.WRONG_ADDRESS, codes)

    # Nothing answered anywhere. DNS, routing, or the connection itself.
    if counts[ProbeStatus.TIMEOUT] + counts[ProbeStatus.ERROR] == total:
        return report(Diagnosis.UNREACHABLE, codes)

    return report(Diagnosis.MIXED, codes)
