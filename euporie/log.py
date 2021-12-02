# -*- coding: utf-8 -*-
"""Initiate logging for euporie."""
from __future__ import annotations

import logging
import logging.config
from bisect import bisect_right
from collections import deque
from typing import IO, Callable, cast

from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.patch_stdout import StdoutProxy
from prompt_toolkit.widgets import SearchToolbar
from rich.console import Console

from euporie.config import config
from euporie.tab import Tab
from euporie.text import FormattedTextArea

LOG_QUEUE: "deque" = deque(maxlen=1000)


def setup_logs() -> "None":
    """Configures the logger for euporie."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain_format": {
                    "format": "{asctime} {levelname:>7} [{name}.{funcName}:{lineno}] {message}",
                    "style": "{",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "rich_format": {
                    "format": "{message}",
                    "style": "{",
                    "datefmt": "%Y%m%d.%H%M%S",
                },
            },
            "handlers": {
                "stdout": {
                    "level": "DEBUG" if config.debug else "ERROR",
                    "class": "rich.logging.RichHandler",
                    "formatter": "rich_format",
                    "console": Console(
                        file=cast("IO[str]", StdoutProxy(raw=True)),
                    ),
                    "markup": False,
                },
                "file": {
                    "level": "DEBUG" if config.debug else "ERROR",
                    "class": "logging.FileHandler",
                    "filename": "/dev/stdout"
                    if config.log_file == "-"
                    else config.log_file,
                    "formatter": "plain_format",
                },
                "internal": {
                    "level": "DEBUG" if config.debug else "INFO",
                    "class": "euporie.log.QueueHandler",
                    "queue": LOG_QUEUE,
                },
            },
            "loggers": {
                "euporie": {
                    "handlers": [
                        "internal",
                        "stdout" if config.log_file == "-" else "file",
                    ],
                    "level": "DEBUG" if config.debug else "INFO",
                    "propagate": False,
                },
            },
            "root": {"handlers": ["internal"]},
        }
    )


class QueueHandler(logging.Handler):
    """This handler store logs events into a queue."""

    hook_id = 0
    hooks: "dict[int, Callable]" = {}

    def __init__(self, queue: "deque") -> "None":
        """Initialize an instance, using the passed queue."""
        logging.Handler.__init__(self)
        self.queue = queue

    def emit(self, record: "logging.LogRecord") -> "None":
        """Queue unformatted records, as they will be formatted when accessed."""
        self.queue.append(record)
        for hook in self.hooks.values():
            if callable(hook):
                hook(record)

    @classmethod
    def hook(cls, hook: "Callable") -> "int":
        """Adds a hook to run after each log entry.

        Args:
            hook: The hook function to add

        Returns:
            The hook id
        """
        hook_id = cls.hook_id
        cls.hook_id += 1
        cls.hooks[hook_id] = hook
        return hook_id

    @classmethod
    def unhook(cls, hook_id: "int") -> "None":
        """Removes a hook function.

        Args:
            hook_id: The ID of the hook function to remove
        """
        if hook_id in cls.hooks:
            del cls.hooks[hook_id]


class LogView(Tab):
    """A tab which allows you to view log entries."""

    levels = [0, 10, 20, 30, 40, 50, 60]
    level_colors = [
        "grey",
        "blue",
        "green",
        "yellow",
        "red",
        "red bold",
    ]

    def __init__(self) -> "None":
        """Builds the tab's contents.

        Also hooks into the queue handeler to update the log.
        """
        self.formatter = logging.Formatter()
        # Build the container
        self.search_field = SearchToolbar(
            text_if_not_searching=[("class:not-searching", "Press '/' to search.")]
        )
        self.text_area = FormattedTextArea(
            formatted_text=[],
            read_only=True,
            scrollbar=True,
            line_numbers=True,
            search_field=self.search_field,
            focus_on_click=True,
            wrap_lines=False,
        )
        self.container = HSplit([self.text_area, self.search_field])
        # Add text to the textarea
        for record in LOG_QUEUE:
            self.add_record(record)
        # Hook the queue handler
        self.hook_id = QueueHandler.hook(self.add_record)

    def add_record(self, record: "logging.LogRecord") -> "None":
        """Adds a single new record to the textarea.

        Args:
            record: The log record to add

        """
        # self.text_area.formatted_text = self.text_area.formatted_tetxt + self.render(record)
        self.text_area.formatted_text += self.render(record)

    def render(self, record: "logging.LogRecord") -> "StyleAndTextTuples":
        """Converts a log record to formatted text.

        Args:
            record: The log record to format

        Returns:
            A list of style and text tuples describing the log record

        """
        date = self.formatter.formatTime(record, "%Y%m%d.%H%M%S")
        record.message = record.getMessage()
        msg = self.formatter.formatMessage(record)
        formatted_record: "StyleAndTextTuples" = [
            ("#00875f", f"{date} "),
            (
                self.level_colors[
                    max(0, bisect_right(self.levels, record.levelno) - 1)
                ],
                f"{record.levelname:>7} ",
            ),
            ("ansidefault", f"{msg} "),
            ("fg:#888888 italic", f"{record.name}.{record.funcName}:{record.lineno} "),
            ("", "\n"),
        ]

        return formatted_record
