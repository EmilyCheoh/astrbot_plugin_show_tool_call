import json
from typing import Any

from mcp.types import CallToolResult

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Node, Plain
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.tool import FunctionTool


@register(
    "astrbot_plugin_show_tool_call",
    "Felis Abyssalis",
    "以合并转发消息的形式发送 LLM 工具名称、参数和执行结果",
    "1.0.0",
)
class ShowToolCallPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @staticmethod
    def _to_serializable(data: Any) -> Any:
        """把 Pydantic/MCP 对象转换成可序列化的数据。"""
        if not hasattr(data, "model_dump"):
            return data

        try:
            return data.model_dump(mode="json", exclude_none=True)
        except TypeError:
            return data.model_dump(exclude_none=True)

    @classmethod
    def _format_json(cls, data: Any) -> str:
        data = cls._to_serializable(data)
        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @classmethod
    def _format_result(cls, tool_result: CallToolResult | None) -> str:
        if tool_result is None:
            return "（无返回结果）"

        result_data = cls._to_serializable(tool_result)

        # 成功时不显示无意义的 isError: false；失败时保留 true。
        if isinstance(result_data, dict):
            for key in ("isError", "is_error"):
                if result_data.get(key) is False:
                    result_data.pop(key)

        return cls._format_json(result_data)

    @filter.on_llm_tool_respond()
    async def show_tool_call(
        self,
        event: AstrMessageEvent,
        tool: FunctionTool,
        tool_args: dict | None,
        tool_result: CallToolResult | None,
    ):
        """在工具执行完成后发送工具名称、参数和结果。"""
        try:
            tool_name = getattr(tool, "name", "unknown_tool")
            args_text = self._format_json(tool_args or {})
            result_text = self._format_result(tool_result)

            content = (
                f"🔧 Tool\n{tool_name}\n\n"
                f"📦 Arguments\n{args_text}\n\n"
                f"📨 Result\n{result_text}"
            )

            nodes = [
                Node(
                    uin=0,
                    name="🤖🛠️ The tool call",
                    content=[Plain(content)],
                )
            ]

            await event.send(event.chain_result(nodes))

        except Exception as exc:
            logger.error(f"发送工具调用信息失败: {exc}")

