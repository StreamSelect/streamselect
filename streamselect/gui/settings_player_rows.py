"""Settings → Playback: the rows for how the player handles a stream's sound and buffer.

Its own module because the tabs module is at its size pin.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QComboBox, QFormLayout


#: Labels shared with the header's playback menu, so the two read as one setting.
NORMALIZE_LABEL = "Normalize volume"
NORMALIZE_TIP = ("Lifts quiet voices without making explosions louder, "
                 "and evens out the level between channels.")
DOWNMIX_OPTIONS = (("auto", "Off"), ("stereo", "To stereo"), ("mono", "To mono"))
DOWNMIX_TIP = ("Mixes 5.1 and other surround audio down to two channels or one. "
               "Off keeps the stream's own channels.")
DECODER_OPTIONS = (("auto", "Automatic"), ("software", "Software"))
DECODER_TIP = ("Software can clear up colour faults and glitches caused by a hardware decoder, "
               "but uses more CPU. Switching skips the picture ahead to the next keyframe.")


def add_player_rows(dlg, form: QFormLayout) -> None:
    """Add the audio, decoder and Buffering rows, setting controls on *dlg*."""
    live = "\nApplies straight away, including to a player window that is already open."
    dlg._normalize_volume_check = QCheckBox(NORMALIZE_LABEL)
    dlg._normalize_volume_check.setToolTip(NORMALIZE_TIP + live)
    form.addRow(dlg._normalize_volume_check)

    dlg._audio_downmix_combo = QComboBox()
    for value, label in DOWNMIX_OPTIONS:
        dlg._audio_downmix_combo.addItem(label, userData=value)
    dlg._audio_downmix_combo.setToolTip(DOWNMIX_TIP + live)
    form.addRow("Downmix audio:", dlg._audio_downmix_combo)

    dlg._video_decoder_combo = QComboBox()
    for value, label in DECODER_OPTIONS:
        dlg._video_decoder_combo.addItem(label, userData=value)
    dlg._video_decoder_combo.setToolTip(DECODER_TIP + live)
    form.addRow("Video decoder:", dlg._video_decoder_combo)

    dlg._buffer_combo = QComboBox()
    dlg._buffer_combo.addItem("Reconnect only (no extra buffer)", userData="reconnect_only")
    dlg._buffer_combo.addItem("Modest (~10s buffer)", userData="modest")
    dlg._buffer_combo.addItem("Large (~30s buffer)", userData="large")
    dlg._buffer_combo.addItem("Open-ended (disk-backed, max buffer)", userData="open_ended")
    dlg._buffer_combo.setToolTip(
        "Controls how much media mpv buffers ahead while playing.\n"
        "\n"
        "• Reconnect only — no extra buffer; lowest memory use.\n"
        "• Modest (~10s) — default; absorbs brief network hiccups.\n"
        "• Large (~30s) — useful on congested or high-latency links.\n"
        "• Open-ended — buffers as far ahead as the stream allows\n"
        "  (disk-backed, up to 2 GiB / 1 hour); best for unstable\n"
        "  streams or when you want the maximum lead time. Uses more\n"
        "  disk space while playing.\n"
        "\n"
        "Auto-reconnect is always on regardless of this setting."
    )
    form.addRow("Buffering:", dlg._buffer_combo)
