import asyncio
import json
import socket
import sys
from contextlib import asynccontextmanager

import click
from loguru import logger
from typing import Tuple


@asynccontextmanager
async def init_chat_connection(
    host: str, port: int, connection_timeout: int
) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    logger.debug("trying to connect to server", extra={"host": host, "port": port})
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), connection_timeout
    )
    init_response = (await reader.readline()).decode()

    logger.debug(
        "get init response from server", extra={"init_response": init_response}
    )
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()


async def register(
    user_name: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    logger.debug("start registering user", extra={"user_name": user_name})
    writer.write(b"\n")
    await writer.drain()

    logger.debug("awaiting login", extra={"server_response": await reader.readline()})

    writer.write(f"'{user_name.__repr__()}\n".encode())
    await writer.drain()

    register_response = await reader.readline()

    try:
        return json.loads(register_response)["account_hash"]
    except json.JSONDecodeError:
        logger.error(
            f"Can not parse to JSON the server response",
            extra={"auth_response": register_response},
        )
        raise


class AuthException(Exception):
    pass


async def authorize(
    chat_token: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    writer.write(f"{chat_token}\n".encode())
    await writer.drain()

    auth_response = (await reader.readline()).decode()
    try:
        auth_result = json.loads(auth_response)
    except json.JSONDecodeError:
        logger.error(
            f"Can not parse to JSON the server response",
            extra={"auth_response": auth_response},
        )
        raise

    logger.debug("receives auth response", extra=auth_result)
    if not auth_result:
        raise AuthException

    logger.debug("auth successfully")


async def submit_message(message, writer):
    for line in message.splitlines():
        writer.write(f"{line}\n\n".encode())
    await writer.drain()


async def process_message_sending(
    message: str,
    chat_token: str,
    user_name: str,
    host: str,
    port: int,
    connection_timeout: int,
):

    if not chat_token:
        async with init_chat_connection(host, port, connection_timeout) as (
            reader,
            writer,
        ):
            chat_token = await register(user_name, reader, writer)

    async with init_chat_connection(host, port, connection_timeout) as (reader, writer):
        await authorize(chat_token, reader, writer)
        await submit_message(message, writer)

        logger.bind(name="prod_logger").debug(message)


@click.command()
@click.option(
    "-m", "--message", required=True , help="text to post")
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
@click.option(
    "-to",
    "--connection_timeout",
    envvar="CONNECTION_TIMEOUT",
    default=3,
    help="chat server connection timeout",
)
def main(
    message: str,
    chat_token: str,
    user_name: str,
    host: str,
    port: int,
    log_level: str,
    connection_timeout: int,
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
        asyncio.run(
            process_message_sending(
                message, chat_token, user_name, host, port, connection_timeout
            )
        )
    except AuthException:
        logger.bind(name="prod_logger").error("chat token is not valid. exiting ...")
        return

    except (asyncio.TimeoutError, socket.gaierror):
        logger.bind(name="prod_logger").error("can`t connect to chat server")
        return


if __name__ == "__main__":
    main()
