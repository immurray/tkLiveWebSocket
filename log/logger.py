import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


class LogManager:

    def __init__(self, log_name="douyin-webcast"):
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(logging.INFO)
        self.log_dir = None
        self._initialized = True

    def setup_logging(
        self,
        level=logging.INFO,
        log_to_console=False,
        log_path=None,
    ):
        self.logger.handlers.clear()
        self.logger.setLevel(level)

        if log_to_console:
            ch = RichHandler(
                show_time=False,
                show_level=True,
                show_path=False,
                markup=True,
                keywords=(RichHandler.KEYWORDS or []) + ["STREAM"],
                rich_tracebacks=True,
            )
            ch.setFormatter(logging.Formatter("{message}", style="{", datefmt="[%X]"))
            self.logger.addHandler(ch)

        # 文件日志输出
        if log_path:
            self.log_dir = Path(log_path)
            self.ensure_log_dir_exists(self.log_dir)

            # 根据 log_name 动态设置文件名
            log_file_name = (
                f"{self.logger.name}-{datetime.datetime.now():%Y-%m-%d-%H-%M-%S}.log"
            )
            log_file = self.log_dir.joinpath(log_file_name)

            # 根据日期切割日志文件
            fh = TimedRotatingFileHandler(
                log_file,
                when="midnight",
                interval=1,
                backupCount=99,
                encoding="utf-8",
            )
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self.logger.addHandler(fh)

    @staticmethod
    def ensure_log_dir_exists(log_path: Path):
        log_path.mkdir(parents=True, exist_ok=True)


def log_setup(
    log_to_console=True,
    log_name="douyin-webcast",
) -> logging.Logger:
    """
    配置日志记录器。
    """
    logger = logging.getLogger(log_name)
    if logger.hasHandlers():
        # logger已经被设置，不做任何操作
        return logger

    # 创建日志目录
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    # 初始化日志管理器
    log_manager = LogManager(log_name)
    log_manager.setup_logging(
        level=logging.INFO,
        log_to_console=log_to_console,
        log_path=log_dir,
    )

    return logger


# 主日志记录器（包含所有日志级别）
logger = log_setup(log_to_console=True, log_name="douyin-webcast")
