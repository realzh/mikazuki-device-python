import json
from typing import Optional

import websockets


class WebSocketClient:
    """Python 版 WebSocket 客户端（对应你的 FastAPI 服务器）"""

    def __init__(self, uri: str):
        self.uri = uri
        self.websocket: Optional[websockets.ClientConnection | None] = None
        self.is_connected = False
        self.client_id: Optional[str] = None

    async def connect(self):
        """建立连接并处理握手"""
        try:
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,  # 自动发送 ping
                ping_timeout=10,  # ping 超时时间
                close_timeout=10,
                max_size=2**23,  # 允许大消息
            )
            self.is_connected = True
            print(f"已连接到服务器: {self.uri}")

        except Exception as e:
            print(f"连接失败: {e}")
            self.is_connected = False
            raise

    async def send(self, data: dict):
        """发送 JSON 消息"""
        if not self.is_connected or not self.websocket:
            raise RuntimeError("WebSocket 未连接")

        try:
            await self.websocket.send(json.dumps(data))
            print(f"send: {data}")
        except Exception as e:
            print(f"发送失败: {e}")
            await self.disconnect()

    async def receive(self):
        """接收并解析消息（阻塞）"""
        if not self.is_connected or not self.websocket:
            raise RuntimeError("WebSocket 未连接")
        message = None
        try:
            message = await self.websocket.recv()
            data = json.loads(message)
            return data
        except websockets.exceptions.ConnectionClosed as e:
            print(f"⚠️ 连接已关闭: {e}")
            self.is_connected = False
            raise
        except json.JSONDecodeError:
            print(f"⚠️ 收到非 JSON 消息: {message}")
            return {"type": "error", "payload": "Invalid JSON"}

    async def disconnect(self):
        """主动断开连接"""
        if self.websocket and self.is_connected:
            await self.websocket.close()
            self.is_connected = False
            print("🔌 连接已断开")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
