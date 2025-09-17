# shared/utils/ts_logger.py
import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.pretty import Pretty
from contextvars import ContextVar
import shutil


class TsLogger:
    """Advanced Logger with RichHandler, ContextVar support, and Pretty Printing."""

    request_id: ContextVar[str] = ContextVar("request_id", default="default")

    def __init__(self, name: str, level: int = logging.INFO, simple: bool = True):
        """Initialize the logger with a RichHandler and ContextVar for request tracking."""
        if simple:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                handlers=[RichHandler(rich_tracebacks=True)]
            )
            self.logger = logging.getLogger(name)
            self.console = Console(force_terminal=True)  # Force color output in all terminal environments

        else:
            self.logger = logging.getLogger(name)
            self.logger.setLevel(level)

            # Setup RichHandler
            self.console = Console(width=self._get_terminal_width(), force_terminal=True)
            rich_handler = RichHandler(console=self.console, rich_tracebacks=True)
            # formatter = logging.Formatter(
            #     "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s",
            #     datefmt="%Y-%m-%d %H:%M:%S",
            # )
            formatter = logging.Formatter(
                "%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            rich_handler.setFormatter(formatter)
            self.logger.addHandler(rich_handler)

    def _get_terminal_width(self, default_width=300) -> int:
        """Get terminal width dynamically, with a fallback default."""
        try:
            size = shutil.get_terminal_size(fallback=(default_width, 24))
            return size.columns
        except Exception:
            return default_width

    def bind_request_id(self, request_id: str):
        """Bind a unique request ID to the context."""
        self.request_id.set(request_id)

    def log(self, level: int, message: str):
        """Log a message at the specified level with request context."""
        extra = {"request_id": self.request_id.get()}
        self.logger.log(level, message, extra=extra)

    def info(self, message: str):
        """Log an info-level message."""
        self.log(logging.INFO, message)

    def debug(self, message: str):
        """Log a debug-level message."""
        self.log(logging.DEBUG, message)

    def warning(self, message: str):
        """Log a debug-level message."""
        self.log(logging.DEBUG, message)

    def error(self, message: str, exception: Exception = None):
        """Log an error-level message with optional exception traceback."""
        self.log(logging.ERROR, message)
        if exception:
            self.logger.error(message, exc_info=True)  # Log the exception traceback
            self.console.print(f"\n[red]Exception:[/red] {exception}")

    def print(self, obj):
        """Pretty print an object to the console."""
        self.console.print(Pretty(obj))

    def exception(self, param):
        pass

    @staticmethod
    def print_by_char_limit_per_chunk(s: str, max_chars: int = 1000):
        lines = s.splitlines()
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > max_chars:
                print('\n'.join(current_chunk))
                print('\n' + '-' * 40 + '\n')  # separator between chunks
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        # Print remaining chunk
        if current_chunk:
            print('\n'.join(current_chunk))
