"""Keep the provider-free stream entry point separate from the legacy CLI."""
import sys

if len(sys.argv) > 1 and sys.argv[1] == "stream":
    from .stream import main
    raise SystemExit(main(sys.argv[2:]))

from .cli import main
raise SystemExit(main())
