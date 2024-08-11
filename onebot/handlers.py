from lagrange.client.client import Client
from lagrange.client.events.group import (
    GroupMessage
)

from onebot.event.MessageEvent import (
    GroupMessageEvent
)
from onebot.utils.message_chain import ms_format, ctd

from config import Config

import json
import ws

async def GroupMessageEventHandler(client: Client, event: GroupMessage):
    if ws.websocket_connection:
        content = ms_format(event.msg_chain)
        formated_event = GroupMessageEvent(
            message_id=event.seq,
            time=event.time, 
            group_id=event.grp_id, 
            user_id=event.uin, 
            self_id=Config.uin, 
            raw_message=event.msg, 
            message="".join(str(i) for i in content)
        )
        await ws.websocket_connection.send(
            json.dumps(
                ctd(formated_event),
                ensure_ascii=False)
            )