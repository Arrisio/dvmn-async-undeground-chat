import asyncio
import sys
from datetime import datetime

import aiofiles
import click
from loguru import logger

from utils import chat_connection, ConnectChatException


async def follow_chat(host, port, history_path):

    async with chat_connection(host, port) as (reader, writer):
        while True:
            # по поводу отказоустойчивасти: выключил сеть , подождал минуту, включил - все само заработало. Т.е. доп. обработки не требуется
            income_message_text = (await reader.readline()).decode(encoding="utf8")
            message_info = (
                f"[{datetime.now().strftime('%d.%m.%y %H:%M')}] {income_message_text}"
            )
            print(message_info)
            async with aiofiles.open(history_path, "a") as fh:
                await fh.write(message_info)


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
    logger.configure(
        handlers=[
            dict(
                sink=sys.stdout,
                format="<level>{level: <6}</level>:<cyan>{name:<6}</cyan>:<level>{message:>32}</level>:{extra}",
                level=log_level,
            ),
        ]
    )
    try:
        asyncio.run(
            follow_chat(
                host=host,
                port=port,
                history_path=history_path,
            )
        )
    except ConnectChatException as e:
        logger.error("can`t connect to chat", extra={"host": host, "port": port})

    except FileNotFoundError as e:
        logger.error("con`t add record to history file", extra={"file": history_path})


if __name__ == "__main__":
    main()
