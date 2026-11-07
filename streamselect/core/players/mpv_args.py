"""The stream-access rules (:mod:`streamselect.core.stream_access`) as mpv flags.

The player and the stream-details probe both launch mpv on a stream URL, and
both start the command line with :func:`stream_args`.
"""

from __future__ import annotations

from streamselect.core.stream_access import PLAYBACK, StreamAccess, ffmpeg_reconnect_options


def _reconnect_flag(policy: StreamAccess) -> str | None:
    options = ffmpeg_reconnect_options(policy)
    if not options:
        return None
    return "--stream-lavf-o=" + ",".join(f"{k}={v}" for k, v in options.items())


def _read_timeout_flag(policy: StreamAccess) -> str:
    # 0 = FFmpeg's default: no read timeout. mpv's own default is 60s, so
    # "never" has to be said explicitly.
    seconds = policy.read_timeout_s
    return f"--network-timeout={0 if seconds is None else f'{seconds:g}'}"


#: mpv falls back to yt-dlp when ffmpeg cannot open a URL. For a provider
#: stream that fallback just re-requests the same URL from the provider — one
#: more refused hit on a one-connection account (ledger D62). Xtream stream
#: URLs carry /live/, /movie/ or /series/; trailer links (YouTube) never do, so
#: they keep the fallback they need.
NO_YTDL_FOR_PROVIDER_STREAMS = "--script-opts=ytdl_hook-exclude=/live/|/movie/|/series/"

RECONNECT_FLAG = _reconnect_flag(PLAYBACK)
NO_READ_TIMEOUT_FLAG = _read_timeout_flag(PLAYBACK)


def stream_args(policy: StreamAccess = PLAYBACK) -> list[str]:
    """User-Agent, reconnect and read-timeout flags — in that order.

    The order matters: user-supplied args come after these, so mpv's last-value
    rule lets the user override any of them.
    """
    reconnect = _reconnect_flag(policy)
    return [f"--user-agent={policy.user_agent}",
            *([reconnect] if reconnect else []),
            _read_timeout_flag(policy),
            NO_YTDL_FOR_PROVIDER_STREAMS]


#: mpv's label for the normalization filter: it is what lets a running player
#: add or remove this one filter without touching any other, and adding it twice
#: replaces rather than stacks it.
_NORMALIZE_LABEL = "@streamselect-normalize"

#: Lifts quiet passages and leaves loud ones alone; ``m`` caps the gain at 10x.
#: Chosen by measurement in mpv 0.41 for "voices too quiet, explosions fine", on
#: a clip with voice 24 dB under effects: voice -32 -> -15 dB, effects -8 -> -9 dB.
#: ``loudnorm`` was the obvious pick and is wrong for this: it targets overall
#: loudness, so it took the voice DOWN to -35 dB.
_NORMALIZE_FILTER = f"{_NORMALIZE_LABEL}:lavfi=[dynaudnorm=f=150:g=15:p=0.9:m=10]"

#: Settings value -> mpv ``audio-channels``. "auto" is mpv's own default, which
#: passes surround through when the output supports it and adds no launch flag.
_DOWNMIX_CHANNELS = {"auto": "auto-safe", "stereo": "stereo", "mono": "mono"}


def _override_all(config) -> bool:
    return bool(getattr(config, "mpv_args_override_all", False))


def normalize_wanted(config) -> bool:
    """Whether playback should normalize volume.

    "Override all" means mpv receives only the user's own flags, so it turns this
    off too, for a running player as much as for a new one.
    """
    return bool(getattr(config, "normalize_volume", False)) and not _override_all(config)


def downmix_channels(config) -> str:
    """The mpv ``audio-channels`` value for the downmix setting."""
    if _override_all(config):
        return _DOWNMIX_CHANNELS["auto"]
    return _DOWNMIX_CHANNELS.get(getattr(config, "audio_downmix", "auto"),
                                 _DOWNMIX_CHANNELS["auto"])


def software_decoding_wanted(config) -> bool:
    """Whether the Video decoder setting asks for software decoding."""
    return getattr(config, "video_decoder", "auto") == "software" and not _override_all(config)


def decoder_command(software: bool) -> list[str]:
    """The IPC command that switches a running player's decoder."""
    return ["set_property", "hwdec", "no" if software else "auto-safe"]


def player_setting_args(config) -> list[str]:
    """Launch flags for the player settings; empty when they are all off.

    "Automatic" adds no ``--hwdec`` flag, so a choice in the user's own mpv.conf
    still stands.
    """
    args = [f"--af-add={_NORMALIZE_FILTER}"] if normalize_wanted(config) else []
    if software_decoding_wanted(config):
        args.append("--hwdec=no")
    channels = downmix_channels(config)
    if channels != _DOWNMIX_CHANNELS["auto"]:
        args.append(f"--audio-channels={channels}")
    return args


def normalize_active(af_chain: object) -> bool:
    """Whether a player's ``af`` property already holds the normalization filter."""
    label = _NORMALIZE_LABEL.removeprefix("@")
    return isinstance(af_chain, list) and any(
        isinstance(f, dict) and f.get("label") == label for f in af_chain
    )


def normalize_command(enabled: bool) -> list[str]:
    """The IPC command that turns normalization on or off in a running player."""
    return ["af", "add", _NORMALIZE_FILTER] if enabled else ["af", "remove", _NORMALIZE_LABEL]
