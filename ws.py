import websockets
import json
import asyncio

from config import logger, Config

from lagrange.client.client import Client
from onebot.communications.api import OneBotAPI_V11

websocket_connection = None

async def process(client: Client, data: dict, instance: OneBotAPI_V11) -> dict:
    echo = data.get("echo", "")
    action: str = data.get("action", "")
    if not hasattr(instance, action):
        logger.onebot.error(f"Client Request Action Failed: `{action}` Not Exists.")
        return {"status": "failed", "retcode": -1, "data": None, "echo": echo}
    params: dict = data.get("params", {})
    logger.onebot.debug(
        f"Client Request Action Successfully: `{action}` with echo {echo}, params: " + \
        json.dumps(
            params,
            ensure_ascii=False
        )
    )
    method = getattr(instance, action)
    try:
        resp = await method(echo=echo, **params)
        logger.onebot.debug(f"Send Response: `{resp}`.")
    except Exception as e:
        logger.onebot.error(f"Error when calling `{action}`: {e}")
        return {"status": "failed", "retcode": -1, "data": None, "echo": echo}
    return resp


async def connect(client: Client):
    global websocket_connection
    uri = Config.ws_url
    instance = OneBotAPI_V11(client=client)
    if not Config.ws_url.startswith("ws://") and not Config.ws_url.startswith("wss://"):
        return
    while True:
        try:
            async with websockets.connect(
                uri,
                extra_headers={"X-Self-Id": str(client.uin)}, max_size=10*1024*1024
            ) as websocket:
                websocket_connection = websocket
                logger.onebot.success(f"Reserved WebSocket Connected to {Config.ws_url}!")

                while True:
                    try:
                        rec = await websocket.recv()
                        rec = json.loads(rec)

                        rply = await process(client, rec, instance)
                        await websocket.send(json.dumps(rply, ensure_ascii=False))

                    except websockets.exceptions.ConnectionClosed as e:
                        logger.onebot.warning(f"Reserved WebSocket Closed, status code: {e.code}")
                        break
                    except Exception as e:
                        logger.onebot.error(f"Unhandled Exception in message handling: {e}")

        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            logger.onebot.warning(f"Reserved WebSocket Connection Closed: {e}, retrying...")
        except ConnectionRefusedError:
            logger.onebot.error("Reserved WebSocket Connection Refused, retrying...")
            await asyncio.sleep(5)
