"""
聊天工作线程
"""

import json
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from api import chat, chat_with_document


class ChatWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, user_id, message, file_path=None):
        super().__init__()
        self.user_id = user_id
        self.message = message
        self.file_path = file_path

    def run(self):
        try:
            if self.file_path:
                result = chat_with_document(self.user_id, self.message, self.file_path)
            else:
                result = chat(self.user_id, self.message)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class StreamChatWorker(QObject):
    """SSE 流式聊天线程——实时推送事件"""

    event_reasoning = pyqtSignal(str)
    event_answer_chunk = pyqtSignal(str)
    event_tool_call = pyqtSignal(str, str)
    event_tool_result = pyqtSignal(str, str)
    event_command_rewritten = pyqtSignal(str, str)  # original, rewritten
    event_done = pyqtSignal()
    event_error = pyqtSignal(str)

    def __init__(self, user_id, message):
        super().__init__()
        self.user_id = user_id
        self.message = message

    def run(self):
        import requests
        try:
            url = "http://127.0.0.1:8000/chat/stream"
            params = {"user_id": self.user_id, "message": self.message}
            resp = requests.get(url, params=params, stream=True, timeout=300)
            resp.raise_for_status()

            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type", "")
                if etype == "reasoning":
                    self.event_reasoning.emit(event.get("content", ""))
                elif etype == "command_rewritten":
                    self.event_command_rewritten.emit(
                        event.get("original", ""),
                        event.get("rewritten", ""),
                    )
                elif etype == "answer_chunk":
                    self.event_answer_chunk.emit(event.get("content", ""))
                elif etype == "tool_call":
                    self.event_tool_call.emit(event.get("tool", "?"), event.get("command", ""))
                elif etype == "tool_result":
                    self.event_tool_result.emit(event.get("tool", "?"), event.get("result", ""))
                elif etype == "done":
                    self.event_done.emit()
                    return
                elif etype == "error":
                    self.event_error.emit(event.get("content", "未知错误"))
                    return
        except Exception as e:
            self.event_error.emit(str(e))


class VoiceWorker(QObject):
    """语音录制工作线程（支持停止）"""
    result_ready = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            import speech_recognition as sr

            r = sr.Recognizer()
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = None
                while not self._stop_event.is_set():
                    try:
                        audio = r.listen(
                            source,
                            timeout=0.5,
                            phrase_time_limit=10,
                        )
                        break
                    except sr.WaitTimeoutError:
                        continue

            if self._stop_event.is_set():
                self.result_ready.emit(None)
                return

            text = r.recognize_google(audio, language="zh-CN")
            self.result_ready.emit(text)
        except sr.RequestError:
            self.result_ready.emit("[ERROR] 语音识别服务网络不通，请检查网络")
        except sr.UnknownValueError:
            self.result_ready.emit(None)
        except Exception as e:
            self.result_ready.emit(f"[ERROR] {e}")
