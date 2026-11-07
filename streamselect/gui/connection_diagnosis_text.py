"""User-facing phrasing for a connection diagnosis.

``core.connection_diagnosis`` returns a category and its evidence, and
deliberately no prose — ``provider_probe`` opens by promising no English in
``core`` so a headless backend can reuse it and a translation can exist later.
The sentences live here.

Its own module rather than sitting in ``provider_editor``: that file is the
dialog, and a table of copy is a different concern that would have pushed it
79 lines past its code-health limit. Splitting by what the code IS, not to
satisfy the number.
"""

from __future__ import annotations

from streamselect.core.connection_diagnosis import (
    REFUSAL_STATUSES, WRONG_ADDRESS_STATUSES, Diagnosis,
)
from streamselect.core.provider_probe import ProbeResult, ProbeStatus

#: What to tell the user for each diagnosis, and what to suggest doing.
#:
#: Core returns a category; the sentences are here because ``core`` is
#: deliberately English-free (see ``provider_probe``'s module docstring).
#: Each entry is (headline, what to try) — the second half is the part that was
#: missing, and the reason an evening went into a VPN endpoint nobody suspected.
_DIAGNOSIS_TEXT: dict[Diagnosis, tuple[str, str]] = {
    Diagnosis.REFUSED_BY_HOST: (
        "Every address answered and refused the connection.",
        "The addresses and your network are fine — the provider is rejecting "
        "who you appear to be. This is most often a VPN exit whose IP the "
        "provider blocks: try switching VPN endpoint, or turning the VPN off. "
        "An expired subscription can also do this.",
    ),
    Diagnosis.TEMPORARILY_BLOCKED: (
        "The provider is refusing you now, at an address that answered before.",
        "The address is right. Many providers lock you out for a while after a "
        "few failed logins, or block a VPN's address. Check the username and "
        "password, wait a few minutes, then test again. If it keeps happening, "
        "try with the VPN off or on another endpoint.",
    ),
    Diagnosis.WRONG_ADDRESS: (
        "A server answered, but it isn't an Xtream server at this address.",
        "Check the address your provider gave you, including the port "
        "(e.g. http://example.com:8080). Use the server address on its own, "
        "or paste the whole M3U link and StreamSelect will take the address, "
        "username and password from it.",
    ),
    Diagnosis.SUBSCRIPTION_INACTIVE: (
        "The provider says this subscription is not active.",
        "The addresses work and your credentials were recognised, so changing "
        "them will not help. Check the subscription with the provider.",
    ),
    Diagnosis.CREDENTIALS_REJECTED: (
        "The provider rejected the username or password.",
        "Re-enter the credentials exactly as the provider supplied them, "
        "watching for trailing spaces.",
    ),
    Diagnosis.UNREACHABLE: (
        "Nothing answered at any address.",
        "This looks like a network problem rather than an account one: check "
        "you are online, and if a VPN is connected, try it off or on another "
        "endpoint. A DNS-blocked address also looks like this.",
    ),
    Diagnosis.MIXED: (
        "The addresses failed for different reasons.",
        "See each address's own result above — there is no single cause here.",
    ),
}


def format_probe_message(result: ProbeResult) -> str:
    """One address's test result, in a few words, for its row's badge.

    The cause, not just the code (the code stays as evidence in brackets).
    Short on purpose: the badge is a fixed column, and the full explanation is
    the diagnosis panel's job.
    """
    s = result.status
    if s is ProbeStatus.ACTIVE:
        return f"Active  {result.latency_ms} ms"
    if s is ProbeStatus.INACTIVE:
        return f"Account {result.detail}"
    if s is ProbeStatus.AUTH_FAILED:
        return "Wrong login"
    if s is ProbeStatus.NOT_XTREAM:
        return "Wrong address"
    if s is ProbeStatus.HTTP_ERROR:
        code = (result.detail or "").strip()
        if code in REFUSAL_STATUSES:
            return f"Refused ({code})"
        if code in WRONG_ADDRESS_STATUSES:
            return f"Not found ({code})"
        if code.startswith("5"):
            return f"Server error ({code})"
        return f"HTTP {code}"
    if s is ProbeStatus.TIMEOUT:
        return "No answer"
    return "Can't connect"
