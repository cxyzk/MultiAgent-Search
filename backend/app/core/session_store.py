class SessionStore:
    """内存版会话历史：每个 session 只存一问一答。

    存的格式就是 OpenAI 的 messages 格式，塞回请求零转换。
    """

    MAX_MESSAGES = 20  # 超出丢最老的，防止上下文无限膨胀
    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}

    def get_history(self, session_id: str) -> list[dict]:
        # 返回一个拷贝，防止被修改 对外接口
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str)-> None:
        history = self._sessions.setdefault(session_id,[])
        history.append({"role": role, "content": content})
        if(len(history) > self.MAX_MESSAGES):
            #这里先从内存删除 等有数据库再全部存储
            del history[: len(history) - self.MAX_MESSAGES]
store=SessionStore()