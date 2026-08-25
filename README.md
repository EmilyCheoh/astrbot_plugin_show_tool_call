# AstrBot Tool Call Forwarder

以 QQ 合并转发消息的形式，显示 LLM 的完整工具调用信息：

- 工具名称
- 调用参数
- 执行结果

插件会在工具执行完成后发送消息，因此参数和结果会出现在同一条合并转发中。

## 效果

```text
🔧 Tool
web_search

📦 Arguments
{
  "query": "AstrBot"
}

📨 Result
{
  "content": [
    {
      "type": "text",
      "text": "这里是工具返回的内容……"
    }
  ]
}
```

工具调用成功时，插件会隐藏没有实际意义的：

```json
"isError": false
```

如果工具调用失败，`isError: true` 会被保留，方便判断错误来源。