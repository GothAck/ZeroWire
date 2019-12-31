from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
)


def docopt(
    doc: str,
    argv: Optional[Iterable[str]] = None,
    help: bool = True,
    version: Optional[str] = None,
    options_first: bool = False,
) -> Dict[str, Any]: ...
