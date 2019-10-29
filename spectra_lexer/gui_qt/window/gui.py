import pkgutil
from typing import Callable

from PyQt5.QtWidgets import QMainWindow

from .display import DisplayController
from .main_window_ui import Ui_MainWindow
from .menu import MenuController
from .search import SearchController
from .window import WindowController


class QtGUI:

    ICON_PATH = __package__, 'icon.svg'  # Package and relative file path for window icon.

    def __init__(self, window:WindowController, menu:MenuController,
                 search:SearchController, display:DisplayController) -> None:
        self._window = window
        self._menu = menu
        self._search = search
        self._display = display
        self._state_vars = {}
        self.show = window.show
        self.close = window.close
        self.menu_add = menu.add
        self.set_status = display.set_status
        self.show_traceback = display.show_traceback

    def connect(self, action_fn:Callable[[str], None]) -> None:
        """ Connect all GUI input signals to the action function. """
        self._search.connect(action_fn)
        self._display.connect(action_fn)

    def get_state(self) -> dict:
        return {**self._state_vars,
                **self._search.get_state(),
                **self._display.get_state()}

    def set_state(self, **state_vars) -> None:
        self._state_vars.update(state_vars)
        self._search.update(state_vars)
        self._display.update(state_vars)

    def enable(self, msg:str=None) -> None:
        """ Enable all widgets when GUI-blocking operations are done. """
        self._set_enabled(True)
        if msg is not None:
            self.set_status(msg)

    def disable(self, msg:str=None) -> None:
        """ Disable all widgets when GUI-blocking operations start. """
        self._set_enabled(False)
        if msg is not None:
            self.set_status(msg)

    def _set_enabled(self, enabled:bool) -> None:
        """ Enable/disable all widgets when GUI-blocking operations are running. """
        self._menu.set_enabled(enabled)
        self._search.set_enabled(enabled)
        self._display.set_enabled(enabled)

    @classmethod
    def from_window(cls, w_window:QMainWindow):
        ui = Ui_MainWindow()
        ui.setupUi(w_window)
        icon_data = pkgutil.get_data(*cls.ICON_PATH)
        window = WindowController(w_window)
        window.load_icon(icon_data)
        menu = MenuController(ui.w_menubar)
        search = SearchController(ui.w_input, ui.w_matches, ui.w_mappings, ui.w_strokes, ui.w_regex)
        display = DisplayController(ui.w_title, ui.w_graph, ui.w_board, ui.w_caption)
        return cls(window, menu, search, display)
