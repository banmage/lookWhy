"""Allow ``python -m leleby_ssir`` to invoke the CLI."""

from .cli import main


raise SystemExit(main())
