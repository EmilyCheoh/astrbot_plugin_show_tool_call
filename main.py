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
    "1.2.0",
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
    def _format_value(cls, data: Any) -> str:
        data = cls._to_serializable(data)

        if isinstance(data, str):
            return data.strip("\n")

        if data is None:
            return "null"

        if isinstance(data, bool):
            return "true" if data else "false"

        if isinstance(data, int | float):
            return str(data)

        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @classmethod
    def _format_args(cls, tool_args: dict | None) -> str:
        if not tool_args:
            return "（无参数）"

        parts = []
        for name, value in tool_args.items():
            rendered = cls._format_value(value)
            if name == "code" and isinstance(value, str):
                rendered = f"```\n{rendered}\n```"
            parts.append(f"{name}:\n{rendered}")

        return "\n\n".join(parts)

    @classmethod
    def _format_result_item(cls, item: Any) -> str:
        item = cls._to_serializable(item)

        if not isinstance(item, dict):
            return cls._format_value(item)

        item_type = item.get("type")

        if item_type == "text" and isinstance(item.get("text"), str):
            return item["text"].strip("\n")

        if item_type in ("image", "audio"):
            mime_type = item.get("mimeType") or item.get("mime_type") or "未知格式"
            label = "图片" if item_type == "image" else "音频"
            return f"[{label}结果：{mime_type}]"

        resource = item.get("resource")
        if isinstance(resource, dict):
            if isinstance(resource.get("text"), str):
                return resource["text"].strip("\n")
            if resource.get("blob") is not None:
                mime_type = resource.get("mimeType") or "未知格式"
                return f"[二进制资源：{mime_type}]"

        return cls._format_value(item)

    @classmethod
    def _format_result(cls, tool_result: CallToolResult | None) -> str:
        if tool_result is None:
            return "（无返回结果）"

        result_data = cls._to_serializable(tool_result)

        if not isinstance(result_data, dict):
            return cls._format_value(result_data)

        is_error = bool(
            result_data.get("isError", result_data.get("is_error", False))
        )
        parts = []

        content = result_data.get("content")
        if isinstance(content, list):
            for item in content:
                rendered = cls._format_result_item(item)
                if rendered:
                    parts.append(rendered)
        elif content is not None:
            parts.append(cls._format_value(content))

        structured_content = result_data.get(
            "structuredContent",
            result_data.get("structured_content"),
        )
        if structured_content is not None and not parts:
            parts.append(cls._format_value(structured_content))

        if not parts:
            parts.append("（无返回内容）")

        if is_error:
            parts.insert(0, "❌ 工具执行失败")

        return "\n\n".join(parts)

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
            args_text = self._format_args(tool_args)
            result_text = self._format_result(tool_result)

            content = (
                f"🔧 Tool\n{tool_name}\n\n"
                f"📦 Arguments\n{args_text}\n\n"
                f'📨 Result\n"""\n{result_text}\n"""'
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