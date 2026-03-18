from typing import Any, Sequence

class Machine:
    def __init__(
        self,
        model: object,
        states: Sequence[str],
        initial: str,
        auto_transitions: bool = ...,
        *args: Any,
        **kwargs: Any,
    ) -> None: ...
    def add_transition(
        self,
        trigger: str,
        source: str,
        dest: str,
        *args: Any,
        **kwargs: Any,
    ) -> None: ...
