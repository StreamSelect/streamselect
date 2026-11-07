"""The diagnostics dialog names the decoder the running player is using.

hwdec=auto-safe hides that choice, and a decoder fault reads as a bad stream.
"""

import pytest

from streamselect.core.stream_diagnostics import ACTIVE_DECODER_PROPS, describe_active_decoder
from streamselect.gui.diagnostics_dialog import StreamDiagnosticsDialog


class _InlineExecutor:
    def submit(self, fn, *args):
        fn(*args)


class _FakeConfig:
    diagnostics_sample_seconds = 1
    diagnostics_baseline_url = ""


def _dialog(qtbot, *, player_active=True, query=None):
    dialog = StreamDiagnosticsDialog(
        channel_name="Test Channel",
        stream_url="http://example.com/live/user/pass/123.ts",
        config=_FakeConfig(),
        executor=_InlineExecutor(),
        player_active=player_active,
        query_player_props=query,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


@pytest.mark.parametrize("hwdec, expected", [
    ("vaapi", "Video decoder in use: vaapi (hardware), h264, 1920x802"),
    ("no", "Video decoder in use: software, h264, 1920x802"),
    ("", "Video decoder in use: software, h264, 1920x802"),
])
def test_describes_hardware_and_software(hwdec, expected):
    props = {"hwdec-current": hwdec, "video-format": "h264", "width": 1920, "height": 802}
    assert describe_active_decoder(props) == expected


def test_no_decoder_means_no_line():
    assert describe_active_decoder(dict.fromkeys(ACTIVE_DECODER_PROPS)) is None


def test_missing_details_are_left_out():
    assert describe_active_decoder({"hwdec-current": "no"}) == "Video decoder in use: software"


def test_line_is_painted_when_a_player_answers(qtbot, qapp):
    asked = []

    def query(names):
        asked.append(names)
        return {"hwdec-current": "vulkan", "video-format": "h264", "width": 1920, "height": 802}

    dialog = _dialog(qtbot, query=query)
    qapp.processEvents()

    assert asked == [list(ACTIVE_DECODER_PROPS)]
    line = dialog._decoder_line
    assert line.isVisible()
    assert "vulkan (hardware)" in line.text()
    assert line.height() > 0
    assert dialog.rect().contains(line.geometry())


@pytest.mark.parametrize("player_active, query", [
    (False, lambda names: {"hwdec-current": "vaapi"}),
    (True, None),
    (True, lambda names: dict.fromkeys(names)),
])
def test_no_line_without_a_decoding_player(qtbot, qapp, player_active, query):
    dialog = _dialog(qtbot, player_active=player_active, query=query)
    qapp.processEvents()
    assert not dialog._decoder_line.isVisible()


def test_a_failed_query_leaves_the_dialog_working(qtbot, qapp):
    def query(names):
        raise OSError("socket gone")

    dialog = _dialog(qtbot, query=query)
    qapp.processEvents()
    assert not dialog._decoder_line.isVisible()
    assert dialog._run_button.isEnabled()
