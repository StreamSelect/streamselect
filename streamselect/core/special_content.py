"""Special content detection and parsing for PPV, Live Events, and Sports"""

import re
from typing import Optional, Dict, Any

from streamselect.core import sports_catalog
from streamselect.core.database import ChannelDB
from streamselect.core.channel_name_utils import parse_platform_event
from streamselect.core.event_datetime import parse_event_window, placeholder_slot_start
from streamselect.core.fixture_titles import fixture_display_title, parse_fixture_opponents


_VS_PATTERN = re.compile(r'\s+(?:vs\.?|v\.?)\s+', re.IGNORECASE)
_TRAILING_JUNK = re.compile(r'[\[\(].*$')  # Strip trailing "[EVENT]", "(HD)", etc.

def parse_sports_channel(channel: ChannelDB) -> Dict[str, Any]:
    """The sport, league, provenance and matchup of one sports listing.

    The sport and league come from the one sports list
    (:func:`sports_catalog.classify`); a channel nothing identifies is stored as
    a network channel, an event slot, or ``'unknown'`` so it stays in the Sports
    view rather than being dropped.

    Returns:
        Dict with keys: sport_type, league_name, sport_from, team_name.
    """
    name = channel.name or ''
    team_name = None
    # Split on " | " to get pipe-delimited segments, then scan from the end for
    # a segment containing a "vs" matchup: "EN | NHL | Panthers vs Bruins".
    for segment in reversed([s.strip() for s in name.split(' | ')]):
        vs_match = _VS_PATTERN.search(segment)
        if vs_match:
            left = segment[:vs_match.start()].strip()
            right = _TRAILING_JUNK.sub('', segment[vs_match.end():]).strip()
            if left and right:
                team_name = f"{left} vs {right}"
            break

    tag = sports_catalog.classify(
        name, channel.category or '',
        # The fixture chokepoint (SPORT-4), not the "vs" split above: that one
        # reads "4k| V SPORT UHD" as a matchup.
        names_a_matchup=parse_fixture_opponents(name)[0] is not None)
    # An empty slot written as a sentinel date ("(Victory+ 002) |  (2098-…)").
    if tag.sport_type == sports_catalog.UNKNOWN and placeholder_slot_start(name) is not None:
        tag = sports_catalog.SportTag(sports_catalog.SLOT)
    return {
        'sport_type': tag.sport_type,
        'league_name': tag.league_name,
        'sport_from': tag.sport_from,
        'team_name': team_name,
    }


def detect_ppv_channel(channel: ChannelDB) -> bool:
    """Detect if channel is a PPV event
    
    PPV Pattern: Contains date/time in channel name + "PPV" keyword
    Example: "End | Rolling Loud | all | 11-05-2026 | 09:37 (GMT) | 8K EXCLUSIVE | US: SOCCER PPV 1"
    """
    name = channel.name.lower()
    
    # Must have "ppv" keyword
    if 'ppv' not in name:
        return False
    
    # Must have date pattern (DD-MM-YYYY or MM-DD-YYYY)
    date_pattern = r'\d{2}-\d{2}-\d{4}'
    if not re.search(date_pattern, channel.name):
        return False
    
    # Filter out organizational headers (no stream_url)
    if not channel.stream_url:
        return False
    
    return True


def detect_live_event_channel(channel: ChannelDB) -> bool:
    """Detect if channel is a live event
    
    Live Event Pattern: [EVENT] or [LIVE-EVENT] tag in channel name
    Example: "4K| SKY SPORTS UHD [EVENT]"
    """
    name = channel.name.lower()
    
    # Check for event tags
    if '[event]' in name or '[live-event]' in name:
        return True
    
    return False


def detect_platform_event_channel(channel: ChannelDB) -> bool:
    """Detect an EPG-embedded event feed: "US (Peacock 01) | Title (timestamp)".

    These encode a scheduled programme (or an always-available network feed) in the
    channel name. Only the *scheduled* form (a real timestamp or the always-available
    sentinel) is a live event; the plain network form ("US (P+) Title", no time) is a
    regular channel and falls through to the keyword-based detectors.
    """
    pe = parse_platform_event(channel.name or "")
    return bool(pe and (pe.start_time is not None or pe.always_available))


def detect_sports_channel(channel: ChannelDB) -> bool:
    """Whether a live channel belongs in Sports: its name or category carries a
    sport word, a gating league word or a network word from the one sports list
    (:func:`sports_catalog.is_sports`)."""
    # The sports population is the LIVE grammar — a series/movie cannot be
    # "on now"; VOD sports content stays findable via search/genres.
    if channel.media_type != 'live':
        return False
    return sports_catalog.is_sports(channel.name or '', channel.category or '')


def parse_ppv_event(channel: ChannelDB) -> Dict[str, Any]:
    """Parse PPV event details from channel name
    
    Example: "End | Rolling Loud | all | 11-05-2026 | 09:37 (GMT) | 8K EXCLUSIVE | US: SOCCER PPV 1"
    
    Returns:
        dict with keys: event_name, start_time, quality, sport_type, stream_number
    """
    result = {
        'event_name': None,
        'start_time': None,
        'quality': None,
        'sport_type': None,
        'stream_number': None,
        'stop_time': None,
    }
    
    parts = channel.name.split('|')
    
    # Extract event name (usually second part after status)
    if len(parts) >= 2:
        event_name = parts[1].strip()
        if event_name and event_name.lower() not in ['all', 'end', 'live']:
            result['event_name'] = event_name
    
    # Extract date and time — one chokepoint, all three provider date forms.
    # This used to be a local DD-MM-YYYY regex plus `re.search(r'(\d{2}):(\d{2})')`,
    # which (a) knew one of the three shapes, covering 654 of many dated rows,
    # (b) ignored the timezone named in the string, and (c) took the FIRST HH:MM
    # anywhere in the name — including one inside the event title.
    _window = parse_event_window(channel.name)
    result['start_time'] = _window.start
    # The provider's own end, present only on the slot form. Carried alongside
    # the start so "still on" is a fact rather than an assumed duration.
    result['stop_time'] = _window.stop
    
    # Extract quality markers
    name_upper = channel.name.upper()
    if '8K' in name_upper:
        result['quality'] = '8K'
    elif '4K' in name_upper or 'UHD' in name_upper:
        result['quality'] = '4K'
    elif 'FHD' in name_upper or '1080' in name_upper:
        result['quality'] = 'FHD'
    elif 'HD' in name_upper or '720' in name_upper:
        result['quality'] = 'HD'
    
    # The sport comes from the one sports list, as every other row's does; the
    # slot's own name ("US: SOCCER PPV 80") is only a last-resort guess.
    tag = parse_sports_channel(channel)
    result['sport_type'] = tag['sport_type']
    result['league_name'] = tag['league_name']
    result['sport_from'] = tag['sport_from']

    # Extract stream number (e.g., "PPV 1", "PPV 2")
    stream_match = re.search(r'PPV\s+(\d+)', channel.name, re.IGNORECASE)
    if stream_match:
        result['stream_number'] = int(stream_match.group(1))
    
    return result


def detect_and_categorize_channel(channel: ChannelDB) -> Optional[str]:
    """Detect and categorize channel into special views

    Priority:
        1. PPV (has date/time + PPV keyword)
        2. Live Event ([EVENT] tag, or EPG-embedded "REGION (NETWORK) | Title (time)")
        3. Sports (has sports keywords)

    Returns:
        'ppv', 'live_event', 'sports', or None
    """
    # Organizational headers start with '#' — not actual channels
    if channel.name and channel.name.startswith('#'):
        return None

    # Priority 1: PPV
    if detect_ppv_channel(channel):
        return 'ppv'

    # Priority 2: Live Events — [EVENT] tag or EPG-embedded scheduled programme
    if detect_live_event_channel(channel) or detect_platform_event_channel(channel):
        return 'live_event'
    
    # Priority 3: Sports
    if detect_sports_channel(channel):
        return 'sports'

    # Last: a PPV listing dated in a form the DD-MM-YYYY test above does not
    # read ("ENDED | … | Mon 26 Oct 01:00 EDT (US) | … PPV 1", ISO dates) —
    # 483 of them landed in no view and stored no time. Checked after sports
    # so the 381 such rows Sports already lists stay where they are.
    if (channel.stream_url and 'ppv' in channel.name.lower()
            and parse_event_window(channel.name).start is not None):
        return 'ppv'

    return None


def _apply_fixture_title(channel: ChannelDB) -> None:
    """Store a fixture's matchup title (SPORT-8), never blanking an existing one.

    ``fixture_display_title()`` is the ONE chokepoint (``fixture_titles.py``)
    for turning a fixture's raw provider slot string into what the Sports
    list should show. None means "no derivable matchup" — the row's own
    ``detected_title``, usually set by the DIFFERENT ``update_detected_prefixes``
    chokepoint, is left exactly as it is. Shared by the ``ppv`` and ``sports``
    branches below so the rule lives in one place, not two.
    """
    title = fixture_display_title(channel.name or "")
    if title:
        channel.detected_title = title


def update_channel_special_content(channel: ChannelDB) -> bool:
    """Update channel with special content categorization.

    Args:
        channel: Channel to categorize and enrich.

    Returns:
        True if channel was categorized, False otherwise.
    """
    special_view = detect_and_categorize_channel(channel)

    if not special_view:
        # A dated slot no event rule recognises — "(Apple) (MLS) 005 | Miami vs.
        # Cincinnati (Spanish) (20)", VICTORY+/VIX/FANATIZ/SN+
        # PPV: 339 rows — still has a schedule. Without it nothing can tell a
        # finished game (a black placeholder slot) from an upcoming one, and
        # "Hide finished events" cannot hide it.
        _window = parse_event_window(channel.name or "") if channel.media_type == "live" else None
        channel.event_start_time = (_window.start or placeholder_slot_start(channel.name)) if _window else None
        channel.event_stop_time = _window.stop if _window else None
        return False

    channel.special_view = special_view

    if special_view == 'ppv':
        ppv_data = parse_ppv_event(channel)
        channel.event_start_time = ppv_data['start_time']
        channel.event_stop_time = ppv_data['stop_time']
        channel.sport_type = ppv_data['sport_type']
        channel.league_name = ppv_data['league_name']
        channel.sport_from = ppv_data['sport_from']
        # PPV fixtures (the day-name matchup form) carry opponents same as
        # the sports branch below — same chokepoint (SPORT-4).
        channel.event_team_a, channel.event_team_b = parse_fixture_opponents(channel.name or "")
        _apply_fixture_title(channel)

        metadata = ppv_data.copy()
        for _key in ('start_time', 'stop_time'):
            if metadata.get(_key):
                metadata[_key] = metadata[_key].isoformat()
        channel.event_metadata = metadata

    elif special_view == 'live_event':
        # EPG-embedded event feeds carry a network/time in the name; enrich from them.
        pe = parse_platform_event(channel.name or "")
        if pe is None or pe.start_time is None:
            # The platform grammar did not read a time (75 rows): the generic
            # date forms still may — same chokepoint as every other branch.
            _window = parse_event_window(channel.name or "")
            channel.event_start_time = _window.start or placeholder_slot_start(channel.name)
            channel.event_stop_time = _window.stop
        if pe is not None:
            if pe.start_time is not None:
                channel.event_start_time = pe.start_time
                # This grammar names a start and nothing else; "still on" falls
                # back to DEFAULT_EVENT_DURATION. Assigned rather than left alone
                # so a row that changes shape cannot keep a stop from its old form.
                channel.event_stop_time = None

            metadata: Dict[str, Any] = {
                'event_name': pe.title or None,
                'network': pe.network,            # browseable broadcaster/brand
                'channel_num': pe.channel_num or None,
                'region': pe.region,
                'availability': 'always' if pe.always_available else 'scheduled',
            }
            if pe.start_time:
                metadata['start_time'] = pe.start_time.isoformat()
            channel.event_metadata = metadata

        # A platform event is a sports event; any other live event ("SKY SPORTS UHD
        # [EVENT]", 59 rows had no sport at all) is tagged when its name or
        # collection says Sports, and left alone otherwise (a concert stays untagged).
        if pe is not None or sports_catalog.is_sports(channel.name or "", channel.category or ""):
            sports_data = parse_sports_channel(channel)
            channel.sport_type = sports_data['sport_type']
            channel.league_name = sports_data['league_name']
            channel.sport_from = sports_data['sport_from']
            channel.team_name = sports_data['team_name']

    elif special_view == 'sports':
        sports_data = parse_sports_channel(channel)
        channel.sport_type = sports_data['sport_type']
        channel.league_name = sports_data['league_name']
        channel.sport_from = sports_data['sport_from']
        channel.team_name = sports_data['team_name']
        # A dated fixture can classify as 'sports' rather than 'ppv' — 927 of them
        # do — and this branch extracted no time at all, so the schedule column and
        # the Q19 staleness cross-check had nothing to read. Same chokepoint as the
        # ppv branch; None for the 24/7 racks, which is correct rather than a miss.
        _window = parse_event_window(channel.name or "")
        channel.event_start_time = _window.start
        channel.event_stop_time = _window.stop
        # Fixture opponents (SPORT-4) — same chokepoint as the ppv branch;
        # None for the 24/7 racks and racing "at venue" listings, which is
        # correct rather than a miss.
        channel.event_team_a, channel.event_team_b = parse_fixture_opponents(channel.name or "")
        _apply_fixture_title(channel)

    return True
