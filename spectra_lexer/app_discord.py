""" EXPERIMENTAL DISCORD BOT MODULE (dependency on discord.py not declared in setup). """

import io
import sys
from traceback import format_exc
from typing import Callable, Iterable, List, Optional

import discord

from spectra_lexer import Spectra
from spectra_lexer.engine import StenoEngine
from spectra_lexer.qt.svg import SVGConverter
from spectra_lexer.resource.rules import StenoRule
from spectra_lexer.search import MatchDict
from spectra_lexer.util.cmdline import CmdlineOptions


class BotMessage:
    """ Contains all data that makes up a Discord bot's response. """

    def __init__(self, content:str) -> None:
        self._content = content
        self._file = None

    def __str__(self) -> str:
        return self._content

    def attach_as_file(self, data:bytes, filename:str) -> None:
        """ Attach an arbitrary string of bytes to this message as a file. """
        fstream = io.BytesIO(data)
        self._file = discord.File(fstream, filename)

    async def send(self, channel:discord.TextChannel) -> None:
        """ Send the message to a Discord text channel. """
        await channel.send(self._content, file=self._file)


class DiscordBot:
    """ Basic Discord bot that accepts commands from users in the form of '!command args' """

    def __init__(self, token:str, logger=print) -> None:
        self._token = token  # Discord bot token.
        self._log = logger   # String callable to log all bot activity.
        self._cmds = {}      # Dict of command callables. Must accept a string and return a bot message.
        self._client = discord.Client()
        self._client.event(self.on_ready)
        self._client.event(self.on_message)

    def add_command(self, name:str, func:Callable[[str], Optional[BotMessage]]) -> None:
        """ Add a named ! command with a callable that will be executed with the remainder of the user's input. """
        self._cmds[name] = func

    def run(self) -> int:
        """ Attempt to connect to Discord with the provided token. """
        self._log('Connecting to Discord...')
        return self._client.run(self._token)

    async def on_ready(self) -> None:
        """ When logged in, just print a success message and wait for user input. """
        self._log(f'Logged in as {self._client.user}.')

    async def on_message(self, message:discord.Message) -> None:
        """ Parse user input and execute a command if it isn't our own message, it starts with a "!",
            and the characters after the "!" but before whitespace match a registered command. """
        if message.author == self._client.user:
            return
        content = message.content
        if not content.startswith("!"):
            return
        cmd_name, *cmd_body = content[1:].split(None, 1)
        cmd_func = self._cmds.get(cmd_name)
        if cmd_func is None:
            return
        arg_string = cmd_body[0].strip() if cmd_body else ""
        self._log(f"Command: {cmd_name} {arg_string}")
        try:
            reply = cmd_func(arg_string)
            self._log(f"Reply: {reply}")
        except Exception:
            reply = BotMessage('Command parse error.')
            self._log(format_exc())
        if reply is None:
            return
        await reply.send(message.channel)


class DiscordApplication:
    """ Spectra engine application that accepts string input from Discord users. """

    BOARD_ASPECT_RATIO = 1.5  # Fixed aspect ratio to make board images look best on Discord.
    QUERY_MAX_CHARS = 100     # Maximum number of characters allowed in a user query string.
    EXCLUDED_CHARS = ",.?!"   # Characters that should be removed before searching for words.
    SEARCH_LIMIT = 3          # Maximum number of search results to analyze at once.

    def __init__(self, engine:StenoEngine, space_rule:StenoRule, svg_converter:SVGConverter) -> None:
        self._engine = engine          # Main query engine.
        self._space_rule = space_rule  # Stroke separator rule corresponding to space.
        self._svg_converter = svg_converter

    def _new_rule(self, word:str, matches:MatchDict) -> StenoRule:
        """ Make a new rule from a word and its possible stroke matches. """
        if not matches:
            return StenoRule.analysis("?", "-" * len(word), "Skipped word.")
        if word in matches:
            pairs = [(s, word) for s in matches[word]]
        elif word.lower() in matches:
            pairs = [(s, word) for s in matches[word.lower()]]
        else:
            pairs = [(s, match) for match, strokes_list in matches.items() for s in strokes_list]
        translation = self._engine.best_translation(*pairs)
        return self._engine.analyze(*translation)

    @staticmethod
    def _join_rules(rules:Iterable[StenoRule]) -> StenoRule:
        """ Join several rules into one for display purposes. """
        analysis = StenoRule.analysis("", "", "Compound analysis.")
        offset = 0
        for r in rules:
            analysis.keys += r.keys
            analysis.letters += r.letters
            length = len(r.letters)
            analysis.add_connection(r, offset, length)
            offset += length
        return analysis

    def _split_to_words(self, letters:str) -> List[str]:
        """ Return a list of strings suitable for piece-by-piece word analysis. """
        for c in self.EXCLUDED_CHARS:
            letters = letters.replace(c, "")
        return letters.split()

    def _analyze_words(self, query:str) -> Optional[StenoRule]:
        """ Do an advanced lookup to put together rules containing strokes for multiple words. """
        words = self._split_to_words(query)
        search_list = [self._engine.search(word, self.SEARCH_LIMIT) for word in words]
        if not any(search_list):
            return None
        rules = []
        for word, matches in zip(words, search_list):
            rule = self._new_rule(word, matches)
            rules += [rule, self._space_rule]
        rules.pop()
        return self._join_rules(rules)

    # XXX This type of analysis is rarely used and is a potential DoS avenue.
    # def _analyze_translation(self, query:str) -> Optional[StenoRule]:
    #     """ Do a standard lexical analysis and return the result (unless one or both inputs was empty). """
    #     for delim in ["->", "→"]:  # Tokens that indicate (and delimit) a strokes -> words analysis.
    #         if delim in query:
    #             keys, letters = query.split(delim, 1)
    #             keys = keys.strip()
    #             letters = letters.strip()
    #             if keys and letters:
    #                 return self._engine.analyze(keys, letters)

    def _board_png(self, rule:StenoRule) -> bytes:
        """ Generate a board diagram in PNG raster format with good dimensions. """
        board = self._engine.generate_board(rule, aspect_ratio=self.BOARD_ASPECT_RATIO)
        svg_data = board.encode('utf-8')
        return self._svg_converter.to_png(svg_data)

    def exec(self, query:str) -> BotMessage:
        """ Parse a user query string and return a Discord bot message, possibly with a board PNG attached. """
        if len(query) > self.QUERY_MAX_CHARS:
            return BotMessage('Query is too long.')
        analysis = self._analyze_words(query)
        if analysis is None:
            return BotMessage('No suggestions.')
        msg = BotMessage(f'``{analysis}``')
        png_data = self._board_png(analysis)
        msg.attach_as_file(png_data, "board.png")
        return msg


def main() -> int:
    opts = CmdlineOptions("Run Spectra as a Discord bot.")
    opts.add("token", "", "Discord bot token (REQUIRED).")
    spectra = Spectra(opts)
    spectra.log("Loading...")
    engine = spectra.build_engine()
    translations_files = spectra.translations_paths()
    engine.load_translations(*translations_files)
    space_rule = engine.analyze("/", " ")
    svg_converter = SVGConverter(background_rgba=(0, 0, 0, 0))
    app = DiscordApplication(engine, space_rule, svg_converter)
    bot = DiscordBot(opts.token, spectra.log)
    bot.add_command("spectra", app.exec)
    return bot.run()


if __name__ == '__main__':
    sys.exit(main())