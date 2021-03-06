""" Main module for the Discord bot application. """

import sys
from typing import Optional, Sequence, Type

from spectra_lexer import Spectra, SpectraOptions
from spectra_lexer.console.system import SystemConsole
from spectra_lexer.qt.svg import SVGRasterEngine
from spectra_lexer.spc_board import BoardDiagram, BoardEngine
from spectra_lexer.spc_lexer import StenoAnalyzer, TranslationPairs
from spectra_lexer.spc_search import SearchEngine
from spectra_lexer.util.discord import DiscordBot, DiscordMessage


class MessageFactory:
    """ Factory for Discord messages containing content from Spectra. """

    def __init__(self, *, msg_cls:Type[DiscordMessage]=None, svg_engine:SVGRasterEngine=None) -> None:
        self._msg_cls = msg_cls or DiscordMessage
        self._svg_engine = svg_engine or SVGRasterEngine()

    def text_message(self, message:str) -> DiscordMessage:
        """ Generate a Discord message consisting only of text. """
        return self._msg_cls(message)

    def board_message(self, caption:str, board_data:BoardDiagram) -> DiscordMessage:
        """ Generate a Discord message with a board diagram in PNG raster format with good dimensions.
            Discord will not embed SVGs directly. """
        msg = self._msg_cls(f'``{caption}``')
        self._svg_engine.loads(board_data)
        png_data = self._svg_engine.encode_image(fmt="PNG")
        msg.attach_as_file(png_data, "board.png")
        return msg


class DiscordApplication:
    """ Spectra engine application that accepts string input from Discord users. """

    def __init__(self, search_engine:SearchEngine, analyzer:StenoAnalyzer,
                 board_engine:BoardEngine, msg_factory:MessageFactory, *,
                 query_max_chars:int=None, query_trans:dict=None, search_depth=1, board_AR:float=None) -> None:
        self._search_engine = search_engine
        self._analyzer = analyzer
        self._board_engine = board_engine
        self._text_message = msg_factory.text_message
        self._board_message = msg_factory.board_message
        self._query_max_chars = query_max_chars  # Optional limit for # of characters allowed in a user query string.
        self._query_trans = query_trans or {}    # Translation table to remove characters before searching for words.
        self._search_depth = search_depth        # Maximum number of search results to analyze at once.
        self._board_AR = board_AR                # Optional fixed aspect ratio for board images.

    def _find_matches(self, word:str) -> Sequence[str]:
        """ Search for possible stroke matches for a <word>. """
        matches = self._search_engine.search(word, self._search_depth)
        if not matches:
            return ()
        if word in matches:
            return matches[word]
        key = word.lower()
        if key in matches:
            return matches[key]
        for m in matches:
            if key == m.lower():
                return matches[m]
        return ()

    def _best_translation(self, word:str) -> str:
        """ Find the best pairing between a word and its possible stroke matches. """
        matches = self._find_matches(word)
        if not matches:
            keys = ""
        elif len(matches) == 1:
            keys = matches[0]
        else:
            keys = self._analyzer.best_translation(matches, word)
        return keys

    def _search_words(self, letters:str) -> TranslationPairs:
        """ Do an advanced lookup to yield the best strokes for each word in <letters>. """
        for word in letters.split():
            keys = self._best_translation(word)
            if not keys:
                word = "-" * len(word)
            yield keys, word + " "

    def _query_text(self, text:str) -> DiscordMessage:
        """ Parse a user query string as English text and make diagrams from each strokes/word pair we find. """
        show_letters = not text.startswith('+')
        letters = text.translate(self._query_trans)
        translations = list(self._search_words(letters))
        if not any([k for k, w in translations]):
            return self._text_message('No suggestions.')
        analysis = self._analyzer.compound_query(translations)
        caption = str(analysis)
        board_data = self._board_engine.draw_rule(analysis, aspect_ratio=self._board_AR, show_letters=show_letters)
        return self._board_message(caption, board_data)

    def _query_keys(self, keys:str) -> DiscordMessage:
        """ Parse a user query string as a set of RTFCRE steno keys. """
        keys = self._analyzer.normalize_keys(keys)
        if not keys:
            return self._text_message('Invalid key sequence.')
        board_data = self._board_engine.draw_keys(keys, aspect_ratio=self._board_AR)
        return self._board_message(keys, board_data)

    def query(self, query:str) -> Optional[DiscordMessage]:
        """ Parse a user query string and return a Discord bot message, possibly with a board PNG attached. """
        query = query.strip()
        if not query:
            return None
        if self._query_max_chars is not None and len(query) > self._query_max_chars:
            return self._text_message('Query is too long.')
        first, *others = query.split(None, 1)
        if not others and first == first.upper():
            return self._query_keys(first)
        return self._query_text(query)

    def run_console(self) -> int:
        """ Run the application in a debug console. """
        namespace = {k: getattr(self, k) for k in dir(self) if not k.startswith('__')}
        console = SystemConsole.open(namespace)
        console.repl()
        return 0


def build_app(spectra:Spectra) -> DiscordApplication:
    io = spectra.resource_io
    search_engine = spectra.search_engine
    analyzer = spectra.analyzer
    board_engine = spectra.board_engine
    svg_engine = SVGRasterEngine(background_rgba=(0, 0, 0, 0))
    msg_factory = MessageFactory(svg_engine=svg_engine)
    excluded_chars = r'''#$%&()*+-,.?!/:;<=>@[\]^_`"{|}~'''
    map_to_space = dict.fromkeys(map(ord, excluded_chars), ' ')
    translations = io.load_json_translations(*spectra.translations_paths)
    # Strip Plover glue and case metacharacters so our search engine has a chance to find the actual text.
    stripped_values = [v.strip(' {<&>}') for v in translations.values()]
    translations = {k: v for k, v in zip(translations, stripped_values) if v}
    search_engine.set_translations(translations)
    return DiscordApplication(search_engine, analyzer, board_engine, msg_factory,
                              query_max_chars=100, query_trans=map_to_space, search_depth=3, board_AR=1.5)


def main() -> int:
    """ Run the application as a Discord bot. """
    opts = SpectraOptions("Run Spectra as a Discord bot.")
    opts.add("token", "", "Discord bot token (REQUIRED).")
    opts.add("command", "spectra", "!command string for Discord users.")
    spectra = Spectra(opts)
    log = spectra.logger.log
    log("Loading Discord bot...")
    app = build_app(spectra)
    if not opts.token:
        log("No token given. Opening test console...")
        return app.run_console()
    bot = DiscordBot(opts.token, log)
    bot.add_command(opts.command, app.query)
    log("Discord bot started.")
    return bot.run()


if __name__ == '__main__':
    sys.exit(main())
