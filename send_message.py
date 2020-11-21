import asyncio
import json
import socket
import sys

import click
from loguru import logger

from utils import chat_connection, ConnectChatException


class ParseServerResponseException(Exception):
    pass


async def register(
    user_name: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    init_response = (await reader.readline()).decode()
    logger.debug(
        "get init response from server",
        extra={"init_response": init_response},
    )

    logger.debug("start registering user", extra={"user_name": user_name})
    writer.write(b"\n")
    await writer.drain()

    logger.debug("awaiting login", extra={"server_response": await reader.readline()})

    writer.write(f"'{user_name.__repr__()}\n".encode())
    await writer.drain()

    register_response = await reader.readline()

    try:
        return json.loads(register_response)["account_hash"]

    # по поводу " ¬ысушите код " и "¬ loguru есть декоратор на этот случай."
    # думаю, такой вариант наиболее зрелый
    except json.JSONDecodeError:
        raise ParseServerResponseException("error while registration")


class AuthException(Exception):
    pass


async def authorize(
    chat_token: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    init_response = (await reader.readline()).decode()
    logger.debug(
        "get init response from server",
        extra={"init_response": init_response},
    )

    writer.write(f"{chat_token}\n".encode())
    await writer.drain()

    auth_response = (await reader.readline()).decode()

    try:
        auth_result = json.loads(auth_response)

    except json.JSONDecodeError:
        raise ParseServerResponseException("error while auth")

    logger.debug("receives auth response", extra=auth_result)
    if not auth_result:
        raise AuthException

    logger.debug("auth successfully")


async def submit_message(message, writer):
    for line in message.splitlines():
        writer.write(f"{line}\n\n".encode())
    await writer.drain()


async def process_message_sending(
    message: str, chat_token: str, user_name: str, host: str, port: int,
):

    if not chat_token:
        async with chat_connection(host, port) as (
            reader,
            writer,
        ):
            chat_token = await register(user_name, reader, writer)

    async with chat_connection(host, port) as (reader, writer):
        await authorize(chat_token, reader, writer)
        await submit_message(message, writer)

        logger.bind(name="prod_logger").debug(message)


@click.command()
@click.option("-m", "--message", required=True, help="text to post")
@click.option("-t", "--chat_token", envvar="CHAT_TOKEN", help="chat authenticate token")
@click.option(
    "-u",
    "--user_name",
    envvar="USER_NAME",
    default="anonymous",
    help="if auth token is not provided, new user will be registered with this  username",
)
@click.option(
    "-h", "--host", default="minechat.dvmn.org", envvar="HOST", help="chat hostname"
)
@click.option("--port", envvar="CHAT_PUBLISH_MSG_PORT", default=5050)
@click.option("-l", "--log_level", envvar="LOG_LEVEL", default="INFO")
def main(
    message: str, chat_token: str, user_name: str, host: str, port: int, log_level: str,
):
    logger.configure(
        handlers=[
            {
                "sink": sys.stdout,
                "format": "<level>{level: <6}</level>:<cyan>{extra[name]:<6}</cyan>:<level>{message}</level>",
                "level": "DEBUG",
                "filter": lambda record: record["extra"].get("name") == "prod_logger",
            },
            {
                "sink": sys.stdout,
                "format": "<level>{level: <8}</level>|<cyan>{name:<12}</cyan>:<cyan>{function:<24}</cyan>:<cyan>{line}</cyan> - <level>{message:>32}</level> |{extra}",
                "level": log_level,
                "filter": lambda record: not record["extra"].get("name"),
            },
        ],
    )

    try:
        asyncio.run(process_message_sending(message, chat_token, user_name, host, port))

    except ConnectChatException as e:
        logger.error("can`t connect to chat", extra={"host": host, "port": port})

    except AuthException:
        logger.bind(name="prod_logger").error("chat token is not valid. exiting ...")
        return

    except ParseServerResponseException as e:
        logger.error(e.__repr__(), extra={"host": host, "port": port})


if __name__ == "__main__":
    main()
