"""模型接入层（DESIGN.md §15）。

适配器模式：OpenAICompatibleAdapter / AnthropicAdapter / GeminiAdapter。
业务代码按角色（judge/advisor/extractor/challenger）取模型，路由表 config/models.yaml。
内置：每 provider 信号量并发控制、令牌桶限速、指数退避+全抖动重试、四档超时。
铁律：每次调用实际使用的模型必须写入 trace。
"""
