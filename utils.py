import asyncio
import socket
from contextlib import asynccontextmanager
from typing import Tuple

from anyio import fail_after
from loguru import logger


class ConnectChatException(Exception):
    pass


@asynccontextmanager
async def chat_connection(
    host: str, port: int, connection_timeout: int = 3
) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    logger.debug("trying to connect to server", extra={"host": host, "port": port})

    try:
        async with fail_after(connection_timeout):
            reader, writer = await asyncio.open_connection(host, port)

    except (
        ConnectionRefusedError,
        socket.gaierror,
        asyncio.exceptions.CancelledError,
        TimeoutError,
    ):
        raise ConnectChatException()

    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()


