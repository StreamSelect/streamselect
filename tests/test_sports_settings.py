"""Settings ▸ Sports: predefined defaults, the user's own choices, improved defaults
(design "Sports Settings" rev 1, SS-Q1–Q11; owner 2026-11-18)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from streamselect.core.games import tuning


@pytest.fixture
def moved_default(monkeypatch):
    """The bundled defaults as a later release might ship them: usual length 2 h 50."""
    base = tuning._bundled()
    moved = {**base, "default": {**base["default"], "usual_length": 170}}
    monkeypatch.setattr(tuning, "_bundled", lambda: moved)
    return moved


def test_every_setting_has_a_bundled_default_and_hockey_uses_todays_numbers():
    d = tuning.defaults("hockey")
    assert set(d) == set(tuning.BY_KEY)
    assert d["usual_length"] == 165 and d["long_limit"] == 210 and d["report_days"] == 30


def test_a_value_never_set_follows_a_changed_default_silently(moved_default):
    assert tuning.values("hockey", {})["usual_length"] == 170
    assert tuning.improved({}) == [], "nothing to ask: the user never set it"


def test_a_value_set_back_to_the_old_default_stays_and_is_asked_about(monkeypatch):
    """Owner: "if the user … sets it back to the old default then that breaks that
    auto update" — a value the user set is theirs even when it equals the default."""
    overrides: dict = {}
    tuning.set_choice(overrides, "hockey", "usual_length", 165)          # equal to today's default
    assert overrides == {"hockey": {"usual_length": [165, 165]}}, "stored, not dropped"
    base = tuning._bundled()
    monkeypatch.setattr(tuning, "_bundled", lambda: {**base, "default": {**base["default"], "usual_length": 170}})
    assert tuning.values("hockey", overrides)["usual_length"] == 165, "the user's 2 h 45 stays"
    [item] = tuning.improved(overrides)
    assert (item.yours, item.new, item.was) == (165, 170, 165)


def test_keep_mine_and_take_new_each_answer_once(moved_default):
    overrides = {"hockey": {"usual_length": [180, 165]}}
    [item] = tuning.improved(overrides)
    tuning.keep_mine(overrides, item)
    assert tuning.values("hockey", overrides)["usual_length"] == 180 and tuning.improved(overrides) == []
    overrides = {"hockey": {"usual_length": [180, 165]}}
    tuning.take_new(overrides, tuning.improved(overrides)[0])
    assert overrides == {} and tuning.values("hockey", overrides)["usual_length"] == 170


def test_the_finder_and_view_get_the_users_numbers():
    from streamselect.core.games.store import enabled_leagues, sport_settings
    overrides = {"hockey": {"usual_length": [180, 165], "listed_ahead": [12, 36], "report_days": [7, 30]}}
    nhl = next(s for s in enabled_leagues(overrides) if s.league == "NHL")
    assert nhl.usual_length == timedelta(hours=3) and nhl.window_ahead == timedelta(hours=12)
    assert nhl.report_days == 7 and nhl.long_limit == timedelta(minutes=210), "unset values: defaults"
    hockey = [s for s in enabled_leagues(overrides) if s.sport == "hockey"]
    assert len(hockey) > 1 and all(s.usual_length == timedelta(hours=3) for s in hockey), "every league of the sport"
    assert all(s.usual_length == timedelta(minutes=105) for s in enabled_leagues(overrides) if s.sport == "basketball"), "not another sport's"
    assert sport_settings()["hockey"].usual_length == timedelta(minutes=165)


def test_a_longer_usual_length_keeps_a_game_on_now_longer():
    from streamselect.core.games.read import ON_NOW, ENDING, game_state
    from streamselect.core.games.store import sport_settings
    from tests.test_game_finder import START
    from tests.test_sports_view import GameDTO
    g = GameDTO(1, "hockey", "NHL", "A", "B", START, 1, False, 2, ())
    at = START + timedelta(minutes=170)
    assert game_state(g, at, sport_settings()["hockey"]) == ENDING
    longer = sport_settings({"hockey": {"usual_length": [180, 165]}})["hockey"]
    assert game_state(g, at, longer) == ON_NOW


# ── the page ──────────────────────────────────────────────────────────────

def _page(qapp, owned_widgets, overrides=None, sport="hockey"):
    from types import SimpleNamespace
    from streamselect.gui.settings_sports_tab import SportsSettingsPage
    page = owned_widgets.own(SportsSettingsPage())
    page.load(SimpleNamespace(sport_settings_overrides=overrides or {}, ask_about_improved_defaults=True))
    page.select_sport(sport)
    page.resize(900, 900)
    page.show()
    qapp.processEvents()
    return page


def test_an_edited_row_shows_its_default_and_a_reset_and_saves_only_that(qapp, owned_widgets):
    from types import SimpleNamespace
    page = _page(qapp, owned_widgets)
    row = page.rows["usual_length"]
    assert row.note.isHidden() and row.reset.isHidden(), "an untouched row shows nothing extra"
    page.edit("usual_length", 180)
    qapp.processEvents()
    assert row.value() == 180 and row.note.text() == "default 2 h 45 min"
    assert row.note.isVisible() and row.reset.isVisible()
    assert row.reset.geometry().left() > row.editor.geometry().right(), "Reset sits after the value"
    assert page.rows["long_limit"].reset.isHidden(), "other rows untouched"
    cfg = SimpleNamespace()
    page.save(cfg)
    assert cfg.sport_settings_overrides == {"hockey": {"usual_length": [180, 165]}}


def test_a_value_set_equal_to_the_default_reads_set_by_you(qapp, owned_widgets):
    page = _page(qapp, owned_widgets)
    page.edit("usual_length", 165)
    row = page.rows["usual_length"]
    assert row.note.text() == "set by you" and row.reset.isVisibleTo(page)


def test_reset_returns_a_row_to_the_default(qapp, owned_widgets):
    page = _page(qapp, owned_widgets, {"hockey": {"usual_length": [180, 165]}})
    row = page.rows["usual_length"]
    assert row.value() == 180 and row.reset.isVisibleTo(page)
    row.reset.click()
    qapp.processEvents()
    assert row.value() == 165 and row.reset.isHidden()


def test_typing_in_a_row_stores_the_choice(qapp, owned_widgets):
    page = _page(qapp, owned_widgets)
    page.rows["report_days"].editor.setValue(14)          # what the user's typing does
    assert page._overrides == {"hockey": {"report_days": [14, 30]}}


def test_advanced_starts_collapsed_and_opens(qapp, owned_widgets):
    page = _page(qapp, owned_widgets)
    assert page.advanced_box.isHidden(), "Advanced starts collapsed (SS-Q5)"
    page.advanced_toggle.click()
    qapp.processEvents()
    assert page.advanced_box.isVisible()
    assert page.rows["same_game"].editor.isVisible()


def test_the_settings_dialog_has_a_sports_page_under_finding_things():
    from streamselect.gui.settings_dialog import SECTION_GROUPS
    groups = {heading: [s[0] for s in sections] for heading, sections in SECTION_GROUPS}
    assert "sports" in groups["Finding things"]


# ── the improved-defaults prompt ─────────────────────────────────────────

def test_the_prompt_applies_take_and_keep_and_never(qapp, owned_widgets, moved_default):
    from streamselect.gui.improved_defaults_dialog import ImprovedDefaultsDialog
    stored = {"hockey": {"usual_length": [180, 165], "report_days": [7, 30]}}
    moved_default["default"]["report_days"] = 21
    items = tuning.improved(stored)
    assert {i.key for i in items} == {"usual_length", "report_days"}
    dlg = owned_widgets.own(ImprovedDefaultsDialog(items))
    assert all(not r.isChecked() for r in dlg.take), "every row starts on keep yours"
    dlg.take[[i.key for i in items].index("report_days")].setChecked(True)
    overrides = {k: dict(v) for k, v in stored.items()}
    dlg.apply_to(overrides, accepted=True)
    assert overrides == {"hockey": {"usual_length": [180, 170]}}, "taken: follows defaults; kept: noted"
    assert tuning.improved(overrides) == [], "nothing asked twice"

    dlg2 = owned_widgets.own(ImprovedDefaultsDialog(tuning.improved(stored)))
    for r in dlg2.take:
        r.setChecked(True)
    dlg2.never.setChecked(True)
    again = {k: dict(v) for k, v in stored.items()}
    dlg2.apply_to(again, accepted=True)
    assert tuning.values("hockey", again)["usual_length"] == 180, "never ask again keeps the user's values"


def test_settings_changed_gives_the_view_the_new_numbers(db, qapp, owned_widgets):
    from streamselect.core.config import Config
    from streamselect.gui.sports_view import SportsView
    cfg = Config()
    view = owned_widgets.own(SportsView(db, cfg, lambda fn, cb, **_: None))
    assert view.sports["hockey"].usual_length == timedelta(minutes=165)
    cfg.sport_settings_overrides = {"hockey": {"usual_length": [180, 165]}}
    view.settings_changed()
    assert view.sports["hockey"].usual_length == timedelta(hours=3)


def test_the_apply_hook_is_registered():
    from streamselect.gui import settings_apply
    assert "_apply_sports_settings" in settings_apply.HANDLERS


def test_basketball_is_a_second_sport_with_its_own_defaults_on_the_page(qapp, owned_widgets):
    """Owner 2026-11-18: NBA is the second trial league; basketball gets its own
    Settings values (its games are shorter than hockey's)."""
    from streamselect.core.games.store import sport_settings
    sports = sport_settings()
    assert list(sports)[:2] == ["hockey", "basketball"]
    assert sports["basketball"].league == "NBA"
    assert sports["basketball"].usual_length == timedelta(minutes=105)
    assert sports["hockey"].usual_length == timedelta(minutes=165), "hockey keeps its own"
    page = _page(qapp, owned_widgets)
    combo = page.sport_combo
    assert [combo.itemText(i) for i in range(combo.count())][:3] == ["All sports", "Hockey", "Basketball"]
    page.select_sport("basketball")
    qapp.processEvents()
    assert page.rows["usual_length"].value() == 105 and page.reset_all.text() == "Reset Basketball to defaults"
    page.edit("usual_length", 140)
    page.select_sport("hockey")
    qapp.processEvents()
    assert page.rows["usual_length"].value() == 165, "a basketball edit leaves hockey alone"
    assert page._overrides == {"basketball": {"usual_length": [140, 105]}}


# ── All sports (owner 2026-11-18) ────────────────────────────────────────

def test_an_all_sports_value_reaches_every_sport_that_sets_none_of_its_own():
    overrides: dict = {}
    tuning.set_choice(overrides, tuning.ALL, "listed_ahead", 24)
    tuning.set_choice(overrides, "basketball", "listed_ahead", 12)
    assert tuning.values("hockey", overrides)["listed_ahead"] == 24, "follows All sports"
    assert tuning.values("basketball", overrides)["listed_ahead"] == 12, "its own wins"
    assert tuning.inherited("hockey", overrides) == {"listed_ahead": 24}
    assert tuning.inherited("basketball", overrides) == {}
    from streamselect.core.games.store import sport_settings
    s = sport_settings(overrides)
    assert s["hockey"].window_ahead == timedelta(hours=24) and s["basketball"].window_ahead == timedelta(hours=12)


def test_each_setting_is_set_only_where_it_makes_sense():
    overrides: dict = {}
    with pytest.raises(ValueError):
        tuning.set_choice(overrides, tuning.ALL, "usual_length", 120)     # game length: per sport
    with pytest.raises(ValueError):
        tuning.set_choice(overrides, "hockey", "most_watched_days", 7)    # ranks sports: all only
    tuning.set_choice(overrides, tuning.ALL, "most_watched_days", 7)
    assert tuning.values("hockey", overrides)["most_watched_days"] == 7
    assert tuning.values("basketball", overrides)["most_watched_days"] == 7
    stale = {"hockey": {"most_watched_days": [90, 30]}, tuning.ALL: {"usual_length": [100, 165]}}
    assert tuning.values("hockey", stale)["most_watched_days"] == 30, "a value stored where it can't be set is ignored"
    assert tuning.values("hockey", stale)["usual_length"] == 165


def test_an_improved_default_under_all_sports_is_asked_about(moved_default):
    moved_default["default"]["listed_ahead"] = 48
    overrides = {tuning.ALL: {"listed_ahead": [24, 36]}}
    [item] = tuning.improved(overrides)
    assert (item.sport, item.key, item.yours, item.new) == (tuning.ALL, "listed_ahead", 24, 48)
    assert tuning.sport_label(item.sport) == "All sports"


def test_the_page_opens_on_all_sports_and_shows_each_setting_where_it_is_set(qapp, owned_widgets):
    from streamselect.gui.settings_sports_tab import SportsSettingsPage
    from types import SimpleNamespace
    page = owned_widgets.own(SportsSettingsPage())
    page.load(SimpleNamespace(sport_settings_overrides={tuning.ALL: {"listed_ahead": [24, 36]}},
                              ask_about_improved_defaults=True))
    page.resize(900, 900)
    page.show()
    qapp.processEvents()
    assert page.sport_combo.currentText() == "All sports"
    assert not page._boxes[tuning.GAME].isVisible(), "game length is per sport"
    assert page.rows["most_watched_days"].editor.isVisible()
    assert page.rows["listed_ahead"].value() == 24 and page.rows["listed_ahead"].reset.isVisible()
    page.select_sport("hockey")
    qapp.processEvents()
    assert page._boxes[tuning.GAME].isVisible() and page.rows["usual_length"].editor.isVisible()
    assert not page.rows["most_watched_days"].editor.isVisible(), "ranks sports: All sports only"
    row = page.rows["listed_ahead"]
    assert row.value() == 24 and row.note.text() == "from All sports" and row.note.isVisible()
    assert not row.reset.isVisible(), "nothing of hockey's own to reset"
    # The note sits under the value, aligned with it (side by side, a row was ~620 px:
    # wider than the page has; owner, 2026-11-22).
    note, editor = row.note.mapTo(page, row.note.rect().topLeft()), row.editor.mapTo(page, row.editor.rect().bottomLeft())
    assert note.y() > editor.y() and abs(note.x() - editor.x()) <= 2, "the note sits under the value"
    page.edit("listed_ahead", 12)
    assert row.note.text() == "default 36 h ahead" and row.reset.isVisible(), "now hockey's own"


def test_the_hint_beside_the_sport_picker_is_not_cut_off(qapp, owned_widgets, tmp_path):
    """Rendered 2026-11-18 in the 1100 px Settings dialog: "…leagues use thei"."""
    from PyQt6.QtWidgets import QLabel
    from streamselect.core.config import Config
    from streamselect.gui.settings_dialog import SettingsDialog
    dlg = owned_widgets.own(SettingsDialog(Config(config_dir=tmp_path)))
    dlg._nav.select_by_label("Sports")
    dlg.resize(1100, 860)
    dlg.show()
    for _ in range(4):
        qapp.processEvents()
    page = dlg._sports_page
    hint = next(lb for lb in page.findChildren(QLabel) if lb.text().startswith("A sport's own value"))
    assert hint.isVisible() and hint.width() >= hint.sizeHint().width(), (
        f"the whole hint fits: {hint.width()} < {hint.sizeHint().width()}")
