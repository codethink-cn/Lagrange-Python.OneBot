from typing import List, Literal, Type, Any
from urllib.parse import urlparse

from lagrange.client.message.elems import Text, Image, At, Quote, MarketFace, Audio
from lagrange.client.message.types import Element
from lagrange.client.client import Client

from onebot.utils.message_segment import MessageSegment
from onebot.utils.audio import mp3_to_silk
from onebot.utils.database import db
from onebot.utils.datamodels import MessageEvent

import io
import httpx
import os
import base64

from config import logger

class MessageConverter:
    def __init__(self, client: Client):
        self.client = client

    async def convert_to_segments(self, elements: List[Element], message_type: Literal["grp", "friend"], group_id: int = 0, uid: str = "") -> List[MessageSegment]:
        """
        将 Lagrange.Element 列表转换为 MessageSegment 列表
        将 Lagrange 传入的消息转换为 OneBot 处理端接受的数据类型
        """
        segments: List[MessageSegment] = []
        for element in elements:
            if isinstance(element, At):
                segments.append(MessageSegment.at(element.uin))
            elif isinstance(element, Quote):
                msg_data: MessageEvent | Any = db.where_one(MessageEvent(), "uin = ? AND seq = ?", element.uin, element.seq, default=None)
                if msg_data is None:
                    continue
                segments.append(MessageSegment.reply(msg_data.msg_id))
            elif isinstance(element, (Image, MarketFace)):
                segments.append(MessageSegment.image(element.url))
            elif isinstance(element, Audio):
                segments.append(MessageSegment.record(element.url))
            elif isinstance(element, Text):
                segments.append(MessageSegment.text(element.text))
            else:
                logger.onebot.error(f"Unknown message type: {element}")
        return segments

    async def convert_to_elements(self, segments: List[MessageSegment], group_id: int = 0, uid: str = "") -> List[Element]:
        """
        将 MessageSegment 列表转换为 Lagrange.Element 列表
        将 OneBot 处理端 收到的消息转换为 Lagrange 接受的数据类型
        """
        elements: List[Element] = []
        for segment in segments:
            if segment.type == "at":
                elements.append(At(uin=int(int(segment.data["qq"])))) # type: ignore
                # Not Support Yet
            elif segment.type == "reply":
                # message_id = segment.data["id"]
                # message_event: MessageEvent | Any = db.where_one(MessageEvent(), "msg_id = ?", message_id, default=None)
                # if not message_event:
                #     continue
                # elements.append(Quote.build(
                #     GroupMessage(
                #         uid=message_event.uid,
                #         seq=message_event.seq,
                #         time=message_event.time,
                #         rand=message_event.rand,
                #         grp_id=message_event.grp_id,
                #         uin=message_event.uin,
                #         grp_name=message_event.grp_name,
                #         nickname=message_event.nickname,
                        
                #     )
                # ))
                continue
                # Not Support Yet 谁爱写谁写吧
            elif segment.type == "image":
                image_content = segment.data["file"]
                image_content = await self._process_image_content(image_content)
                if image_content:
                    if group_id:
                        elements.append(await self.client.upload_grp_image(image_content, group_id))
                    elif uid:
                        elements.append(await self.client.upload_friend_image(image_content, uid=uid))
            elif segment.type == "record":
                voice_content = segment.data["file"]
                voice_content = await self._process_voice_content(voice_content)
                if voice_content:
                    voice_content_silk = await mp3_to_silk(voice_content)
                    if group_id:
                        elements.append(await self.client.upload_grp_audio(voice_content_silk, group_id))
                    elif uid:
                        elements.append(await self.client.upload_friend_audio(voice_content_silk, uid=uid))
            elif segment.type == "text":
                elements.append(Text(text=segment.data["text"]))
            else:
                logger.onebot.error(f"Unknown message type: {segment}")
        return elements

    def parse_message(self, messages: List[dict], target_type: Type[Element] | Type[MessageSegment]) -> List[Element | MessageSegment]:
        parsed_messages = []
        for message in messages:
            if target_type == MessageSegment:
                parsed_messages.append(MessageSegment(**message))
            # elif target_type == Element:
            #     parsed_messages.append(Element(message))
        return parsed_messages

    def convert_to_dict(self, obj):
        if not hasattr(obj, "__dict__"):
            return obj
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = self.convert_to_dict(value) if hasattr(value, "__dict__") else value
        return result

    async def _process_image_content(self, content: str | bytes | io.BytesIO) -> io.BytesIO | None:
        if isinstance(content, bytes):
            return io.BytesIO(content)
        elif isinstance(content, str):
            if content.startswith("http"):
                return await self._download_image_content(content)
            elif content.startswith("file"):
                return self._load_local_image_content(content)
            elif content.startswith("base64"):
                return io.BytesIO(base64.b64decode(content[9:]))
            else:
                raise ValueError(f"Unknown content type for Image {content}!")
        else:
            raise ValueError(f"Unknown file type for Image {content}!")
        
    async def _download_image_content(self, url: str) -> io.BytesIO | None:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as httpx_client:
            try:
                response = await httpx_client.get(url, timeout=600)
                return io.BytesIO(response.content)
            except httpx.TimeoutException:
                logger.onebot.error(f"Image download timed out: {url}")
                return None

    def _load_local_image_content(self, file_path: str) -> io.BytesIO | None:
        local_path = urlparse(file_path).path
        if local_path.startswith("/") and local_path[2] == ":":
            local_path = local_path[1:]
        if os.path.exists(local_path):
            with open(local_path, "rb") as file:
                return io.BytesIO(file.read())
        else:
            logger.onebot.error(f"Local image not found: {local_path}")
            return None

    async def _process_voice_content(self, content: str | bytes | io.BytesIO) -> io.BytesIO | None:
        if isinstance(content, bytes):
            return io.BytesIO(content)
        elif isinstance(content, str):
            if content.startswith("http"):
                return await self._download_voice_content(content)
            elif content.startswith("file"):
                return self._load_local_voice_content(content)
            elif content.startswith("base64"):
                return io.BytesIO(base64.b64decode(content[9:]))
            else:
                raise ValueError(f"Unknown content type for Voice {content}!")
        else:
            raise ValueError(f"Unknown file type for Voice {content}!")

    async def _download_voice_content(self, url: str) -> io.BytesIO | None:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as httpx_client:
            try:
                response = await httpx_client.get(url, timeout=600)
                return io.BytesIO(response.content)
            except httpx.TimeoutException:
                logger.onebot.error(f"Voice download timed out: {url}")
                return None

    def _load_local_voice_content(self, file_path: str) -> io.BytesIO | None:
        local_path = urlparse(file_path).path
        if local_path.startswith("/") and local_path[2] == ":":
            local_path = local_path[1:]
        if os.path.exists(local_path):
            with open(local_path, "rb") as file:
                return io.BytesIO(file.read())
        else:
            logger.onebot.error(f"Local voice not found: {local_path}")
            return None
        
    @staticmethod
    def bytes_serializer(obj):
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="ignore") 
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")