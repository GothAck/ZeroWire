from __future__ import annotations
from typing import Optional, Union
from logging import getLogger, Logger


class ClassLogger:
    __cachedLogger: Optional[Logger]
    __loggerName: Optional[str] = None

    def _setLoggerName(
        self,
        name: Optional[Union[str, ClassLogger]] = None,
    ) -> None:
        if isinstance(name, ClassLogger):
            self.__loggerName = name.__loggerName
        else:
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
