"""Main entry point for MKV Audio Extractor."""

import sys


def main() -> None:
    """Main entry point — launches GUI if no arguments, CLI otherwise."""
    # If run with arguments (other than just the script name), use CLI
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--gui"):
        if sys.platform == "win32":
            try:
                import ctypes
                # Attach to parent console if launched from CMD or PowerShell
                ctypes.windll.kernel32.AttachConsole(-1)
            except Exception:
                pass
        from .cli import main as cli_main
        cli_main()
    else:
        # Try to launch GUI
        try:
            from .gui.main_window import run_gui
            sys.exit(run_gui())
        except ImportError as e:
            print(
                f"GUI dependencies not available: {e}\n"
                "Install PyQt6: pip install PyQt6\n"
                "Or use the CLI: mkv-audio-extractor <file.mkv> --all",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
