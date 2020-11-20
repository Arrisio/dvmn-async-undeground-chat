import asyncio
import sys
import socket

import click
from loguru import logger
from contextlib import asynccontextmanager


def get_chat_logger(history_path: str, log_level: str) -> logger:
    chat_logger = logger.bind(name="chat_logger")
    chat_logger.configure(
        handlers=[
            {
                "sink": history_path,
                "format": "<yellow>[{time:YY-MM-DD HH:mm}] {message}</yellow>",
                "level": "INFO",
                "filter": lambda record: record["extra"].get("name") == "chat_logger",
            },
            {
                "sink": sys.stdout,
                "format": "<yellow>[{time:YY-MM-DD HH:mm}] {message}</yellow>",
                "level": "INFO",
                "filter": lambda record: record["extra"].get("name") == "chat_logger",
            },
            {
                "sink": sys.stdout,
                "format": "<level>{level: <6}</level>:<cyan>{name:<6}</cyan>:<level>{message:>32}</level>:{extra}",
                "level": log_level,
                "filter": lambda record: not record["extra"].get("name"),
            },
        ]
    )
    return chat_logger


@asynccontextmanager
async def chat_connection(
    host: str,
    port: int,
    db: int = 0,
    connection_timeout: int = 5,
) -> (asyncio.StreamReader, asyncio.StreamWriter):

    try:
        logger.debug(
            "trying to connect to chat", extra={"host": host, "port": port, "db": db}
        )
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), connection_timeout
        )
        logger.debug(
            "redis connected successfully",
            extra={"reader": reader.__repr__(), "writer": writer.__repr__()},
        )

    except (ConnectionRefusedError, asyncio.exceptions.TimeoutError, socket.gaierror):
        logger.error(
            "cannot connect to chat server",
            extra={"host": host, "port": port, "db": db},
        )
        raise

    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()


@click.command()
@click.option(
    "-h",
    "--host",
    default="minechat.dvmn.org",
    envvar="CHAT_HOST",
    help="chat hostname",
)
@click.option("--port", envvar="CHAT_INCOME_MSG_PORT", default=5000)
@click.option(
    "--history ",
    "-H",
    "history_path",
    default="minechat.history",
    help="path to write chat history",
    envvar="HISTORY_PATH",
    type=click.Path(exists=False, dir_okay=False, readable=True),
)
@click.option("-l", "--log_level", envvar="LOG_LEVEL", default="INFO")
def main(host, port, history_path, log_level):
    asyncio.run(
        follow_chat(
            host=host,
            port=port,
            chat_logger=get_chat_logger(log_level=log_level, history_path=history_path),
        )
    )


async def follow_chat(host, port, chat_logger, connection_timeout=5):
    async with chat_connection(host, port) as (reader, writer):
        while True:
            # по поводу отказоустойчивасти: выключил сеть , подождал минуту, включил - все само заработало. Т.е. доп. обработки не требуется
            data = await reader.readline()
            # по поводу решения выводить сообщения через логгер я не уверен. Интересно твое мнение
            chat_logger.info(data.decode(encoding="utf8"))


if __name__ == "__main__":
    main()
