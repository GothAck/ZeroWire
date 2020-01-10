from __future__ import annotations
from typing import Optional
from logging import getLogger, Logger


class ClassLogger:
    __cachedLogger: Optional[Logger] = None
    __loggerName: Optional[str] = None

    def _setLoggerName(
        self,
        name: Optional[str] = None,
        parent: Optional[ClassLogger] = None,
    ) -> None:
        if parent is not None:
            if name is None:
                name = parent.__loggerName
            else:
                name = f'{parent.__loggerName}.{name}'

        self.__loggerName = name
        self.__cachedLogger = None

    @property
    def logger(self) -> Logger:
        if self.__cachedLogger is None:
            clslogger = getLogger(self.__class__.__name__)
            name = self.__loggerName
            if name is None:
                self.__cachedLogger = clslogger
            else:
                self.__cachedLogger = clslogger.getChild(name)
        return self.__cachedLogger
