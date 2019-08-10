""" Base module for a Qt dialog framework with callbacks. """

import sys

from PyQt5.QtWidgets import QMainWindow

from .config import ConfigDialog
from .console import ConsoleDialog
from .dialog import FileDialog
from .index import default_index_dialog, SliderIndexDialog
from .menu import MainMenu, MenuItem
from .objtree import ObjectTreeDialog
from ..window import QtGUI
from spectra_lexer.steno import StenoEngine
from spectra_lexer.steno.view import ConfigDictionary
from spectra_lexer.system import SystemLayer


class QtGUIExtension:
    """ GUI Qt extended operations class with a menu and dialog tools. """

    _steno: StenoEngine
    _system: SystemLayer
    _gui: QtGUI
    _window: QMainWindow  # All GUI menus and dialogs must be children of the main window.
    _menu: MainMenu

    def __init__(self, gui:QtGUI, steno:StenoEngine, system:SystemLayer) -> None:
        self._steno = steno
        self._system = system
        self._gui = gui
        self._window = gui.window
        self._menu = MainMenu(self._window, self)
        self._menu.show()

    @MenuItem("File", "Load Translations...")
    def FileOpenTranslations(self) -> None:
        """ Present a dialog for the user to select translation files and attempt to load them all unless cancelled. """
        filenames = FileDialog.open_all(self._window, "Load Translations", ".json")
        if filenames:
            self._steno.RSTranslationsLoad(*filenames)
            self._show_message("Loaded translations from file dialog.")

    @MenuItem("File", "Load Index...")
    def FileOpenIndex(self) -> None:
        """ Present a dialog for the user to select an index file and attempt to load it unless cancelled. """
        filename = FileDialog.open(self._window, "Load Index", ".json")
        if filename:
            self._steno.RSIndexLoad(filename)
            self._show_message("Loaded index from file dialog.")

    @MenuItem("File", "Close", after_separator=True)
    def FileExit(self) -> None:
        """ Exit the application. Must not be called by a worker thread (or it won't kill the main program). """
        sys.exit()

    @MenuItem("Tools", "Edit Configuration...")
    def ConfigOpen(self) -> None:
        """ Create and show the GUI configuration manager dialog. """
        self._steno.VIEWConfigInfo(qt_callback=self._on_config_info)

    def _on_config_info(self, config:ConfigDictionary) -> None:
        ConfigDialog(self._window, self._config_update, config).show()

    def _config_update(self, options:dict) -> None:
        """ Update and save all config options to disk. """
        self._steno.RSConfigSave(options)
        self._steno.RSConfigReady(options)

    def index_missing(self) -> None:
        """ If there is no index file on first start, present a dialog for the user to make a default-sized index.
            Make the index on accept; otherwise save an empty one so the message doesn't appear again. """
        index_size = default_index_dialog(self._window)
        if index_size:
            self._make_index(index_size)
        else:
            self._steno.RSIndexSave({})
            self._show_message("Skipped index creation.")

    @MenuItem("Tools", "Make Index...")
    def IndexOpen(self) -> None:
        """ Create and show a dialog for the index size slider that submits a positive number on accept. """
        SliderIndexDialog(self._window, self._make_index).show()

    def _make_index(self, index_size:int) -> None:
        """ Disable the GUI while the thread is busy. Re-enable the GUI once the thread is clear. """
        self._set_enabled(False)
        self._show_message("Making new index...")
        self._steno.LXAnalyzerMakeIndex(index_size, qt_callback=self._on_index_done)

    def _on_index_done(self, index:dict) -> None:
        self._steno.RSIndexSave(index)
        self._steno.RSIndexReady(index)
        self._show_message("Successfully created index!")
        self._set_enabled(True)

    @MenuItem("Debug", "Open Console...")
    def ConsoleOpen(self) -> None:
        """ Open a new console dialog and connect it to a new interpreter console instance. """
        dialog = ConsoleDialog(self._window)
        console = self._system.open_console(write_to=dialog.add_text)
        dialog.connect(console)
        dialog.show()

    @MenuItem("Debug", "View Object Tree...")
    def TreeOpen(self) -> None:
        """ Create and show the debug tree dialog. """
        ObjectTreeDialog(self._window, self._system.debug_tree()).show()

    def _show_message(self, s:str):
        """ Show a status message on the main GUI. """
        self._gui.status(s)

    def _set_enabled(self, enabled:bool):
        """ Enable/disable the menu as well as the main GUI. """
        self._menu.setEnabled(enabled)
        self._gui.set_enabled(enabled)