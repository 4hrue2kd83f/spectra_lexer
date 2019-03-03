from argparse import ArgumentParser, SUPPRESS

from spectra_lexer import Component, on
from spectra_lexer.options import CommandOption

# Default placeholder names and other keywords for argument parsing based on the option's data type.
_TYPE_KWDS = {int:  {"metavar": "#"},
              str:  {"metavar": "FILE"},
              list: {"metavar": ("FILE1", "FILE2"), "nargs": "+"}}


class CmdlineParser(Component):
    """ Command line parser for the Spectra program. """

    ROLE = "cmdline"

    _parser: ArgumentParser = None  # Temporarily holds command line option info from active components.

    @on("new_cmdline_option")
    def add_option(self, role:str, name:str, opt:CommandOption):
        """ Add a single command line option with parameters calculated from the description and data type. """
        if self._parser is not None:
            # All named options handled here must be parsed as long options.
            key = f"--{role}-{name}"
            kwds = _TYPE_KWDS.get(opt.tp) or {}
            self._parser.add_argument(key, help=opt.desc, **kwds)

    @on("cmdline_parse")
    def parse_args(self, **opts) -> None:
        """ Create the parser and suppress defaults for unused arguments so that they don't override any subclasses. """
        self._parser = ArgumentParser(description="Steno rule analyzer", argument_default=SUPPRESS)
        # Send a command to gather all possible command line options and their defaults from all components.
        self.engine_call("cmdline_get_opts")
        # Parse arguments from sys.argv using the gathered info. Options from main() have precedence over these.
        cmd_opts = vars(self._parser.parse_args())
        cmd_opts.update(opts)
        # Update all components with the new options and clean up the parser.
        for opt, val in cmd_opts.items():
            self.engine_call(f"cmdline_set_{opt}", val)
        del self._parser
