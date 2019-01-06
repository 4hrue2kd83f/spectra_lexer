""" Contains decorators for component engine command flow. """

from functools import partial
from typing import Any, Hashable, Mapping

from spectra_lexer.utils import nop


def control_decorator(dispatch_fn:callable, **dec_kwargs) -> callable:
    """ Create a new control decorator, with additional arguments for the dispatcher in dec_kwargs. """
    def command_decorator(cmd_key:Hashable, *cmd_args, **cmd_kwargs) -> callable:
        def base_decorator(func:callable) -> callable:
            func.cmd = (cmd_key, partial(dispatch_fn, *cmd_args, **dec_kwargs, **cmd_kwargs))
            return func
        return base_decorator
    return command_decorator


on = control_decorator(nop)                        # Most basic decorator: call the command and do nothing else.
respond_to = control_decorator(lambda *args, **kwargs: True)  # Call the command and return its value to caller.


def _dispatch(next_key:Hashable, stack:list, value:Any, ret:bool=False, unpack:bool=False, **cmd_kwargs) -> bool:
    """ If a command is marked to pipe its output to another command (and it isn't None), add that command
        to the stack. Return True if that last command must (also) return the output to its caller.
        If the return value is unpacked, the correct star unpacking operator is chosen based on its type. """
    if value is not None:
        if unpack:
            if isinstance(value, Mapping):
                arg_tuple = (next_key, (), {**value, **cmd_kwargs})
            else:
                arg_tuple = (next_key, value, cmd_kwargs)
        else:
            arg_tuple = (next_key, (value,), cmd_kwargs)
        stack.append(arg_tuple)
    return ret


pipe = control_decorator(_dispatch)            # Call the command and pipe its return value to another command.
fork = control_decorator(_dispatch, ret=True)  # Combination of @pipe and @respond_to.
