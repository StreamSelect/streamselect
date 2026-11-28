"""The right-click menu of a Discover shelf: its row's header or its tile.

Every shelf: Expand or Collapse, Pin or Unpin, See all, Hide. A shelf the user
made also offers its own delete: a saved recipe ("Delete recipe…", plus "Edit
recipe…") and a list ("Delete list…"). Deleting confirms first, because it is the
whole list or recipe, not one title (the app's deletion grammar); a list's titles
stay in the library. The deletes run in the host (MainWindow), which owns the
recipe store and the list writes, through the view's two request signals.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMenu, QMessageBox

from streamselect.gui.discover_workers import _RECIPE_PREFIX, _USER_CAT_PREFIX


def show_shelf_menu(view, shelf_key: str, global_pos) -> None:
    """Pop up *shelf_key*'s menu at *global_pos*."""
    shelf = view._shelf_widgets.get(shelf_key)
    if shelf is None:
        return
    menu = QMenu(view)
    title = shelf._title
    if shelf._collapsed:
        menu.addAction(f"Expand {title}", lambda: view._on_expand_requested(shelf_key))
    else:
        menu.addAction(f"Collapse {title}", lambda: view._on_collapse_requested(shelf_key))
    if view._shelf_zones.get(shelf_key) == "pinned":
        menu.addAction("Unpin", lambda: view._on_unpin_requested(shelf_key))
    else:
        menu.addAction("Pin to top", lambda: view._on_pin_requested(shelf_key))
    menu.addAction("See all", lambda: view._on_see_all(shelf_key))
    if shelf_key.startswith(_RECIPE_PREFIX):
        menu.addAction("Edit recipe…", lambda: view.recipeEditRequested.emit(shelf_key[len(_RECIPE_PREFIX):]))
    menu.addAction("Hide this shelf", lambda: view._on_hide_requested(shelf_key))
    if shelf_key.startswith((_RECIPE_PREFIX, _USER_CAT_PREFIX)):
        menu.addSeparator()
        if shelf_key.startswith(_RECIPE_PREFIX):
            menu.addAction("Delete recipe…", lambda: _delete(view, shelf_key, title))
        else:
            menu.addAction("Delete list…", lambda: _delete(view, shelf_key, title))
    menu.exec(global_pos)


def confirm_delete_text(shelf_key: str, title: str) -> tuple[str, str]:
    """The confirmation's title and question for deleting *shelf_key*."""
    if shelf_key.startswith(_RECIPE_PREFIX):
        name = shelf_key[len(_RECIPE_PREFIX):]
        return "Delete Recipe", f'Delete the saved recipe "{name}"?\n\nIts shelf leaves Discover; no titles are affected.'
    name = shelf_key[len(_USER_CAT_PREFIX):]
    return "Delete List", (f'Delete the list "{name}"?\n\nThe titles in it stay in your library; '
                           "only the list goes.")


def _delete(view, shelf_key: str, title: str) -> None:
    head, question = confirm_delete_text(shelf_key, title)
    reply = QMessageBox.question(view, head, question,
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No)
    if reply != QMessageBox.StandardButton.Yes:
        return
    if shelf_key.startswith(_RECIPE_PREFIX):
        view.recipeDeleteRequested.emit(shelf_key[len(_RECIPE_PREFIX):])
    else:
        view.userListDeleteRequested.emit(shelf_key[len(_USER_CAT_PREFIX):])


def delete_user_list(host, name: str) -> None:
    """Delete a list (user category), already confirmed. *host* is MainWindow.

    One write off the UI thread clears the name from every title; then the name
    leaves Global Exclusions (a deleted list can't be excluded), and the views that
    show lists reload. The titles stay in the library.
    """
    def done(count: int) -> None:
        excluded = list(getattr(host.config, "global_filter_excluded_user_categories", []))
        if name in excluded:
            host.config.global_filter_excluded_user_categories = [c for c in excluded if c != name]
            host.config.save()
        host.status(f'Deleted the list "{name}" ({count:,} title{"s" if count != 1 else ""} kept in your library)')
        host.load_favorites()
        host.load_channels()
        host.discover_view.reload()

    host._run_query(lambda repos: repos.channels.delete_user_category(name), done, commit=True,
                    on_error=lambda e: host.status(f'Could not delete the list "{name}": {e}',
                                                   ms=6000, level="error"))
