from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from kechafa_app.repositories.ai_repository import AIConversationRepository
from kechafa_app.repositories.base_repo import BaseRepository


class AIService:
    def __init__(self):
        self.repo = AIConversationRepository()
        self.base_repo = BaseRepository()
        self.openrouter_api_key = self._normalize_openrouter_key(os.environ.get("OPENROUTER_API_KEY", ""))
        self.openrouter_fallback_api_key = self._normalize_openrouter_key(os.environ.get("OPENROUTER_FALLBACK_API_KEY", ""))
        self.openrouter_model = (os.environ.get("OPENROUTER_MODEL", "openrouter/free") or "openrouter/free").strip()
        self.openrouter_max_tokens = self._read_max_tokens()
        self.openrouter_app_url = (os.environ.get("OPENROUTER_APP_URL", "") or "").strip()
        self.openrouter_app_title = (os.environ.get("OPENROUTER_APP_TITLE", "Academic Kechafa") or "Academic Kechafa").strip()
        self.enable_real_ai = os.environ.get("ENABLE_REAL_AI", "false").lower() == "true"

    @staticmethod
    def _normalize_openrouter_key(value: str) -> str:
        key = (value or "").strip()
        if not key:
            return ""
        if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
            key = key[1:-1].strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        return key

    def list_conversations(self, user_id: int) -> list[dict[str, Any]]:
        conversations = self.repo.list_for_user(user_id)
        items = []
        for conversation in conversations:
            history = self._deserialize_history(conversation.get("history_json"))
            title = self._resolve_title(conversation, history)
            preview = self._build_preview(history)
            items.append(
                {
                    "id": conversation["id"],
                    "title": title,
                    "preview": preview,
                    "updated_at": conversation.get("updated_at"),
                    "updated_label": self._format_timestamp(conversation.get("updated_at")),
                    "message_count": len(history),
                    "is_empty": not history,
                }
            )
        return items

    def get_conversation(self, user_id: int, conversation_id: int | None):
        if not conversation_id:
            return None
        return self.repo.get_for_user(user_id, conversation_id)

    def latest_conversation(self, user_id: int):
        return self.repo.latest_for_user(user_id)

    def get_history(self, user_id: int, conversation_id: int | None = None) -> list[dict[str, Any]]:
        conversation = self.get_conversation(user_id, conversation_id) if conversation_id else self.latest_conversation(user_id)
        return self._deserialize_history(conversation["history_json"]) if conversation else []

    def clear_history(self, user_id: int, conversation_id: int | None) -> None:
        conversation = self.get_conversation(user_id, conversation_id)
        if not conversation:
            return
        self.repo.clear_history(conversation["id"], "New chat")

    def rename_conversation(self, user_id: int, conversation_id: int | None, title: str) -> dict[str, Any] | None:
        conversation = self.get_conversation(user_id, conversation_id)
        cleaned_title = " ".join((title or "").split()).strip()
        if not conversation or not cleaned_title:
            return None
        cleaned_title = cleaned_title[:60]
        self.repo.rename_conversation(conversation["id"], cleaned_title)
        return {
            "id": conversation["id"],
            "title": cleaned_title,
        }

    def delete_conversation(self, user_id: int, conversation_id: int | None) -> bool:
        conversation = self.get_conversation(user_id, conversation_id)
        if not conversation:
            return False
        self.repo.delete_conversation(conversation["id"])
        return True

    def edit_user_message(
        self,
        user_id: int,
        conversation_id: int | None,
        message_index: int,
        new_text: str,
    ) -> dict[str, Any]:
        conversation = self.get_conversation(user_id, conversation_id)
        if not conversation:
            return {"ok": False, "reason": "Conversation not found."}

        history = self._deserialize_history(conversation.get("history_json"))
        if message_index < 0 or message_index >= len(history):
            return {"ok": False, "reason": "Message not found."}

        target_message = history[message_index]
        if target_message.get("role") != "user":
            return {"ok": False, "reason": "Only user questions can be edited."}

        cleaned_text = " ".join((new_text or "").split()).strip()
        if not cleaned_text:
            return {"ok": False, "reason": "Question cannot be empty."}

        original_auto_title = self._build_title_from_history(history)
        history = history[: message_index + 1]
        history[message_index]["content"] = cleaned_text

        current_title = conversation.get("title") or ""
        if not current_title or current_title == original_auto_title or current_title == self._legacy_title_from_history(history):
            current_title = self._build_title_from_history(history)

        self.repo.persist_history(conversation["id"], json.dumps(history, ensure_ascii=False), current_title)

        if not self.enable_real_ai:
            return {
                "ok": False,
                "conversation_id": conversation["id"],
                "conversation_title": current_title,
                "reason": "Real AI is disabled in configuration.",
            }

        if not self._openrouter_keys():
            return {
                "ok": False,
                "conversation_id": conversation["id"],
                "conversation_title": current_title,
                "reason": "No OpenRouter API key is configured.",
            }

        user = self.base_repo.fetchone("SELECT * FROM users WHERE id=?", (user_id,)) or {}
        result = self._openrouter_reply(user, history)
        ai_reply = result["content"]
        if ai_reply is None:
            return {
                "ok": False,
                "conversation_id": conversation["id"],
                "conversation_title": current_title,
                "reason": result["error"] or "OpenRouter request failed.",
            }

        history.append({"role": "assistant", "content": ai_reply})
        self.repo.persist_history(conversation["id"], json.dumps(history, ensure_ascii=False), current_title)
        return {
            "ok": True,
            "conversation_id": conversation["id"],
            "conversation_title": current_title,
            "history": history,
            "reply": ai_reply,
            "provider": "openrouter",
            "label": "OpenRouter AI",
            "is_live": True,
            "reason": f"Using OpenRouter model {self.openrouter_model}.",
        }

    def provider_status(self) -> dict[str, Any]:
        if not self.enable_real_ai:
            reason = "Real AI is disabled in configuration."
        elif not self._openrouter_keys():
            reason = "No OpenRouter API key is configured."
        else:
            reason = f"Using OpenRouter model {self.openrouter_model}."
        return {
            "provider": "openrouter",
            "label": "OpenRouter AI",
            "is_live": self.enable_real_ai and bool(self._openrouter_keys()),
            "reason": reason,
        }

    def get_display_title(self, user_id: int, conversation_id: int | None) -> str:
        conversation = self.get_conversation(user_id, conversation_id) if conversation_id else self.latest_conversation(user_id)
        history = self._deserialize_history(conversation["history_json"]) if conversation else []
        return self._resolve_title(conversation, history)

    def reply(self, user_id: int, user_input: str, conversation_id: int | None = None) -> dict[str, Any]:
        user = self.base_repo.fetchone("SELECT * FROM users WHERE id=?", (user_id,)) or {}
        conversation = self.get_conversation(user_id, conversation_id)
        history = self._deserialize_history(conversation["history_json"]) if conversation else []
        history.append({"role": "user", "content": user_input})

        title = self._resolve_title(conversation, history) if conversation else self._build_title_from_history(history)

        if conversation:
            active_conversation_id = conversation["id"]
            self.repo.persist_history(active_conversation_id, json.dumps(history, ensure_ascii=False), title)
        else:
            active_conversation_id = self.repo.create_conversation(
                user_id,
                title,
                json.dumps(history, ensure_ascii=False),
            )

        if not self.enable_real_ai:
            return self._error_result(active_conversation_id, history, "Real AI is disabled in configuration.")

        if not self._openrouter_keys():
            return self._error_result(active_conversation_id, history, "No OpenRouter API key is configured.")

        result = self._openrouter_reply(user, history)
        ai_reply = result["content"]
        if ai_reply is None:
            return self._error_result(active_conversation_id, history, result["error"] or "OpenRouter request failed.")

        history.append({"role": "assistant", "content": ai_reply})
        self.repo.persist_history(active_conversation_id, json.dumps(history, ensure_ascii=False), title)
        return {
            "ok": True,
            "reply": ai_reply,
            "history": history,
            "conversation_id": active_conversation_id,
            "conversation_title": title,
            "provider": "openrouter",
            "label": "OpenRouter AI",
            "is_live": True,
            "reason": f"Using OpenRouter model {self.openrouter_model}.",
        }

    def _openrouter_keys(self) -> list[str]:
        keys = []
        for key in [self.openrouter_api_key, self.openrouter_fallback_api_key]:
            normalized = self._normalize_openrouter_key(key)
            if normalized and normalized not in keys:
                keys.append(normalized)
        return keys

    def _openrouter_reply(self, user: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, str | None]:
        name = user.get("full_name") or user.get("username") or "Scout"
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Academic Kechafa AI coach, a scouting mentor for Moroccan learners. "
                    "Be concise, supportive, and answer in the same language as the user. "
                    "Use scout values: service, discipline, teamwork, and respect. "
                    "Avoid generic motivational slogans or pep-talk intros/outros. "
                    "Do not mention software development environments unless the user asks about software development. "
                    "Use plain text (avoid markdown formatting like **bold**) unless the user explicitly asks for it. "
                    f"The current learner name is {name}."
                ),
            }
        ]
        messages.extend(history[-10:])

        last_error = "OpenRouter request failed."
        for api_key in self._openrouter_keys():
            try:
                payload = json.dumps(
                    {
                        "model": self.openrouter_model,
                        "messages": messages,
                        "temperature": 0.4,
                        "max_tokens": self.openrouter_max_tokens,
                    }
                ).encode("utf-8")
                req = urllib_request.Request(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    data=payload,
                    headers=self._openrouter_headers(api_key),
                    method="POST",
                )
                with urllib_request.urlopen(req, timeout=60) as response:
                    body = json.loads(response.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]
                if isinstance(content, list):
                    content = "\n".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ).strip()
                if content:
                    return {"content": content, "error": None}
                last_error = "OpenRouter returned an empty response."
            except urllib_error.HTTPError as exc:
                last_error = self._read_openrouter_error(exc)
            except urllib_error.URLError as exc:
                last_error = f"OpenRouter connection failed: {exc.reason}"
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = f"Invalid OpenRouter response: {exc}"
            except Exception as exc:
                last_error = f"OpenRouter request failed: {exc}"

        return {"content": None, "error": last_error}

    def _openrouter_headers(self, api_key: str) -> dict[str, str]:
        api_key = self._normalize_openrouter_key(api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter accepts X-Title; some examples/docs also show X-OpenRouter-Title.
            "X-Title": self.openrouter_app_title,
            "X-OpenRouter-Title": self.openrouter_app_title,
        }
        if self.openrouter_app_url:
            # OpenRouter examples commonly use HTTP-Referer; some clients send Referer.
            headers["HTTP-Referer"] = self.openrouter_app_url
            headers["Referer"] = self.openrouter_app_url
        return headers

    def _error_result(self, conversation_id: int, history: list[dict[str, Any]], reason: str) -> dict[str, Any]:
        return {
            "ok": False,
            "reply": None,
            "history": history,
            "conversation_id": conversation_id,
            "provider": "openrouter",
            "label": "OpenRouter AI",
            "is_live": False,
            "reason": reason,
        }

    def _deserialize_history(self, history_json: str | None) -> list[dict[str, Any]]:
        if not history_json:
            return []
        try:
            history = json.loads(history_json)
            if not isinstance(history, list):
                return []
            return [item for item in history if not self._is_unwanted_boilerplate_message(item)]
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _is_unwanted_boilerplate_message(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        if item.get("role") != "assistant":
            return False
        content = item.get("content")
        if not isinstance(content, str):
            return False
        text = content.lower()
        # Specific unwanted canned text users reported; keep the match strict to avoid hiding real replies.
        return ("development environment" in text) and ("scout your progress" in text) and ("remember," in text)

    def _build_title(self, text: str) -> str:
        title = " ".join((text or "").split()).strip()
        if not title:
            return "New chat"

        lowered = title.lower()
        prefixes = [
            "can you help me with ",
            "can you help with ",
            "could you help me with ",
            "could you help with ",
            "please help me with ",
            "please help with ",
            "i want to know about ",
            "i want to learn about ",
            "i want to ask about ",
            "tell me about ",
            "explain ",
            "how do i ",
            "how can i ",
            "what is ",
            "give me ",
        ]
        for prefix in prefixes:
            if lowered.startswith(prefix):
                title = title[len(prefix):].strip()
                break

        title = re.sub(r"^[^A-Za-z0-9\u0600-\u06FF]+", "", title)
        title = re.sub(r"\s+", " ", title).strip(" .,!?:;-_")
        if not title:
            return "New chat"

        words = title.split()
        if len(words) > 7:
            title = " ".join(words[:7])

        small_words = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}
        formatted_words = []
        for index, word in enumerate(title.split()):
            if re.search(r"[\u0600-\u06FF]", word):
                formatted_words.append(word)
                continue
            lowered_word = word.lower()
            if index > 0 and lowered_word in small_words:
                formatted_words.append(lowered_word)
            else:
                formatted_words.append(lowered_word.capitalize())

        title = " ".join(formatted_words).strip()
        if len(title) > 42:
            title = title[:42].rstrip(" ,.!?:;-_") + "..."
        return title or "New chat"

    def _build_title_from_history(self, history: list[dict[str, Any]]) -> str:
        for message in history:
            if message.get("role") == "user" and message.get("content"):
                return self._build_title(message["content"])
        return "New chat"

    def _legacy_title(self, text: str) -> str:
        title = " ".join((text or "").split()).strip()
        if not title:
            return "New chat"
        return title[:60] + ("..." if len(title) > 60 else "")

    def _legacy_title_from_history(self, history: list[dict[str, Any]]) -> str:
        for message in history:
            if message.get("role") == "user" and message.get("content"):
                return self._legacy_title(message["content"])
        return "New chat"

    def _resolve_title(self, conversation: dict[str, Any] | None, history: list[dict[str, Any]]) -> str:
        auto_title = self._build_title_from_history(history)
        if not conversation:
            return auto_title

        stored_title = (conversation.get("title") or "").strip()
        if not stored_title or stored_title == "New chat" or stored_title == self._legacy_title_from_history(history):
            return auto_title
        return stored_title

    def _build_preview(self, history: list[dict[str, Any]]) -> str:
        if not history:
            return "No messages yet"
        latest = history[-1].get("content", "")
        latest = " ".join(str(latest).split()).strip()
        if not latest:
            return "No messages yet"
        return latest[:80] + ("..." if len(latest) > 80 else "")

    def _format_timestamp(self, value: str | None) -> str:
        if not value:
            return ""
        return value.replace("T", " ")[:16]

    def _read_max_tokens(self) -> int:
        raw_value = os.environ.get("OPENROUTER_MAX_TOKENS", "512").strip()
        try:
            value = int(raw_value)
        except ValueError:
            return 512
        return min(max(value, 64), 2048)

    @staticmethod
    def _read_openrouter_error(exc: urllib_error.HTTPError) -> str:
        try:
            raw_body = exc.read().decode("utf-8")
            body = json.loads(raw_body)
            message = body.get("error", {}).get("message") or body.get("message")
            if exc.code == 401:
                details = message or exc.reason
                return (
                    "OpenRouter authentication failed (401). "
                    "Check `OPENROUTER_API_KEY` (use an OpenRouter key; do not include a 'Bearer ' prefix). "
                    f"Details: {details}"
                )
            if message:
                return f"OpenRouter error {exc.code}: {message}"
            if raw_body:
                return f"OpenRouter error {exc.code}: {raw_body}"
        except Exception:
            pass
        if exc.code == 401:
            return (
                "OpenRouter authentication failed (401). "
                "Check `OPENROUTER_API_KEY` (use an OpenRouter key; do not include a 'Bearer ' prefix)."
            )
        return f"OpenRouter error {exc.code}: {exc.reason}"
