import websockets
import json
import asyncio

from config import logger, Config
from app import lag

from lagrange.client.client import Client
from onebot.communications.api import Communication

websocket_connection = None

instance = Communication

async def process(client: Client, data: dict) -> dict:
    echo = data.get("echo")
    action = data.get("action")
    if not hasattr(instance, action):
        logger.onebot.error(f"Client Request Action Failed: `{action}` Not Exists.")
        return {"status": "failed", "retcode": -1, "data": None, "echo": echo}
    logger.onebot.success(f"Client Request Action Successfully: `{action}`.")
    params = data.get("params")
    method = getattr(instance, action)
    resp = await method(client=lag.get_client(), echo=echo, **params)
    return resp

async def connect():
    global websocket_connection
    uri = Config.ws_url
    while True:
        try:
            async with websockets.connect(uri, extra_headers={"X-Self-Id": str(Config.uin)}) as websocket:
                websocket_connection = websocket
                logger.onebot.success("WebSocket Established")
                
                while True:
                    try:
                        rec = await websocket.recv()
                        rec = json.loads(rec)

                        rply = await process(client, rec)
                        await websocket.send(json.dumps(rply, ensure_ascii=False))
                    
                    except websockets.exceptions.ConnectionClosed:
                        logger.onebot.warning("WebSocket Closed")
                        break
                    # except Exception as e:
                    #     logger.onebot.error(f"Unhandled Exception in message handling: {e}")

        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            logger.onebot.warning(f"WebSocket Connection Closed: {e}, retrying...")
        except ConnectionRefusedError:
            logger.onebot.error("Connection Refused, retrying...")
            await asyncio.sleep(2)