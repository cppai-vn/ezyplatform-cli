"""Small, dependency-free status renderer, also copied into standalone skills."""
import os
import sys


def supports_color(stream):
    if os.environ.get('NO_COLOR') or os.environ.get('TERM') == 'dumb' or not stream.isatty():
        return False
    if os.name == 'nt':
        # Older Windows consoles need virtual-terminal processing enabled first.
        import ctypes
        import msvcrt
        try:
            handle = msvcrt.get_osfhandle(stream.fileno())
            mode = ctypes.c_ulong()
            kernel = ctypes.windll.kernel32
            return bool(kernel.GetConsoleMode(ctypes.c_void_p(handle), ctypes.byref(mode))
                        and kernel.SetConsoleMode(ctypes.c_void_p(handle), mode.value | 4))
        except (OSError, ValueError):
            return False
    return True


def print_status(message, ok=None, *, file=None, flush=True):
    """Prefix a result with a green check, red cross, or neutral unknown marker.

    Redirected output keeps readable symbols without ANSI escapes. ASCII-only
    streams get explicit text markers instead of encoding replacement characters.
    """
    stream = sys.stdout if file is None else file
    marker = '?' if ok is None else '✓' if ok else '✗'
    try:
        marker.encode(getattr(stream, 'encoding', None) or 'utf-8')
    except (UnicodeEncodeError, LookupError):
        marker = '[OK]' if ok else '[X]' if ok is not None else '?'
    if ok is not None and supports_color(stream):
        marker = f'\033[{32 if ok else 31}m{marker}\033[0m'
    print(f'{marker} {message}', file=stream, flush=flush)
