"""各类对话轮次处理器：斜杠命令、搜索、链接、Agent、天气、OCR。"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.metrics_admin import handle_metrics_command
from src.infra.paths import INSTALL_ROOT
from src.infra.timing import log_timing
from src.memory.search_cache import handle_cache_command
from src.tools.file.search import find_files_impl, grep_files_impl
from src.tools.note import handle_note_command
from src.tools.task import handle_task_command
from src.tools.tool_worker import invoke_tool_in_process
from src.ui.input import (
    InputIntent,
    compose_ocr_message,
    format_ocr_reply,
)
from src.ui.link import run_link_summarize_turn
from src.ui.ocr import ocr_progress_text
from src.ui.search_turn import run_web_search_turn
from src.ui.skill import load_skill_prompt, run_skill


class TurnsMixin:
    """斜杠命令与各类 turn 执行。"""

    def _handle_slash_note(self, intent: InputIntent) -> None:
        args = (intent.slash_args or intent.note_content or "").strip()
        if not args:
            self.chat.append_error(
                "用法：/note add <标题> <内容> | list | <关键字> | rm <id>",
            )
            self.chat.set_status(self._status_text("就绪"))
            return
        try:
            with log_timing("note_command", args=args[:40]):
                result = handle_note_command(args, self._note_store)
            self.chat.append_assistant_complete(result)
            self.chat.set_status(self._status_text("就绪"))
        except ValueError as exc:
            self.chat.append_error(str(exc))
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("笔记命令失败")
            self.chat.append_error(f"笔记命令失败: {exc}")

    def _handle_slash_cache(self, intent: InputIntent) -> None:
        try:
            with log_timing("cache_command", args=(intent.slash_args or "")[:40]):
                result = handle_cache_command(intent.slash_args, self._search_cache)
            self.chat.append_assistant_complete(result)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("缓存命令失败")
            self.chat.append_error(f"缓存命令失败: {exc}")

    def _handle_slash_metrics(self, intent: InputIntent) -> None:
        try:
            with log_timing("metrics_command", args=(intent.slash_args or "")[:40]):
                result = handle_metrics_command(intent.slash_args)
            self.chat.append_assistant_complete(result)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("metrics 命令失败")
            self.chat.append_error(f"metrics 命令失败: {exc}")

    def _handle_slash_task(self, intent: InputIntent) -> None:
        try:
            with log_timing("task_command", args=(intent.slash_args or "")[:40]):
                result = handle_task_command(intent.slash_args, self._task_store)
            self.chat.append_assistant_complete(result, content_format="markdown")
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("任务命令失败")
            self.chat.append_error(f"任务命令失败: {exc}")

    def _handle_slash_file(self, intent: InputIntent) -> None:
        """处理 /file 命令：按关键字搜索文件名或文件内容。"""
        args = (intent.slash_args or "").strip()
        if not args:
            self.chat.append_assistant_complete(
                "📁 **/file 文件搜索命令**\n\n"
                "用法：\n"
                "- `/file <关键字>` - 从当前项目目录搜索文件名\n"
                "- `/file global <关键字>` - 从系统所有目录搜索文件名\n"
                "- `/file grep <内容>` - 从当前项目目录搜索文件内容\n\n"
                "示例：\n"
                "- `/file main.py` - 在项目中搜索 main.py\n"
                "- `/file global config.json` - 在系统中搜索 config.json\n"
                "- `/file grep my_function` - 搜索包含 my_function 的文件",
                content_format="markdown",
            )
            self.chat.set_status(self._status_text("就绪"))
            return

        self.chat.begin_assistant_progress("正在搜索文件…")
        self.chat.set_tool_status("🔍 正在搜索文件…", accent="info")

        def worker() -> None:
            try:
                parts = args.split(maxsplit=1)
                mode = "name"
                pattern = args
                global_search = False

                if len(parts) > 1:
                    first = parts[0].lower()
                    if first == "grep":
                        mode = "grep"
                        pattern = parts[1]
                    elif first == "global":
                        mode = "name"
                        pattern = parts[1]
                        global_search = True

                if mode == "name":
                    if global_search:
                        self.chat.set_tool_status(
                            f"🔍 从系统所有目录搜索文件名「{pattern}」…",
                            accent="info",
                        )
                        import os
                        drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
                        all_results = []
                        for drive in drives[:5]:
                            try:
                                result = find_files_impl(
                                    pattern,
                                    root=drive,
                                    file_type="file",
                                    max_results=10,
                                )
                                if result and "共" in result:
                                    all_results.append(result)
                            except Exception:
                                pass
                        if all_results:
                            result = "\n\n---\n\n".join(all_results)
                        else:
                            result = f"未找到文件名包含「{pattern}」的文件"
                    else:
                        self.chat.set_tool_status(
                            f"🔍 从项目目录搜索文件名「{pattern}」…",
                            accent="info",
                        )
                        result = find_files_impl(
                            pattern,
                            root=str(INSTALL_ROOT),
                            file_type="file",
                            max_results=30,
                        )
                else:
                    self.chat.set_tool_status(
                        f"🔍 从项目目录搜索内容「{pattern}」…",
                        accent="info",
                    )
                    result = grep_files_impl(
                        pattern,
                        root=str(INSTALL_ROOT),
                        max_results=30,
                    )

                self.chat.append_assistant_complete(result, content_format="markdown")
                self.chat.set_status(self._status_text("就绪"))
            except Exception as exc:
                logger.exception("文件搜索失败")
                self.chat.append_error(f"文件搜索失败: {exc}")
                self.chat.set_status(self._status_text("就绪"))
            finally:
                self.chat.clear_tool_status()

        threading.Thread(target=worker, daemon=True, name="file-search").start()

    def _handle_slash_skill(self, intent: InputIntent, text: str) -> None:
        skill_name = intent.skill_name or intent.slash_cmd
        user_part = (intent.slash_args or "").strip()

        self.chat.begin_assistant_progress(f"正在执行 Skill: {skill_name}…")
        self.chat.set_tool_status(
            f"⚙ 正在按 SKILL.md 执行 {skill_name}…",
            accent="info",
        )

        def worker() -> None:
            try:
                self.chat.set_tool_status(
                    f"🧠 正在识别 Skill 意图: {skill_name}…",
                    accent="info",
                )
                result = run_skill(skill_name, user_part, llm=self._llm)
                if result.intent_reason and result.intent_reason not in {
                    "raw_cli",
                    "heuristic",
                }:
                    self.chat.append_tool_call(
                        "parse_skill_intent",
                        {"skill": skill_name, "reason": result.intent_reason},
                    )
                self.chat.set_tool_status(
                    f"⚙ 正在执行 Skill: {skill_name}…",
                    accent="info",
                )
                if result.command:
                    self.chat.append_tool_call(
                        "run_skill",
                        {"skill": skill_name, "cmd": result.command},
                    )
                if result.ok:
                    self.chat.append_assistant_complete(result.output)
                    self.chat.set_status(self._status_text("就绪"))
                    return

                if result.fallback_agent:
                    prompt = load_skill_prompt(skill_name)
                    if not prompt:
                        self.chat.append_error(
                            result.error or f"未找到 Skill：{skill_name}",
                        )
                        self.chat.set_status(self._status_text("就绪"))
                        return
                    self.chat.reset_assistant_for_tool()
                    message = (
                        f"【Skill: {skill_name}】\n\n{prompt}\n\n---\n\n"
                        f"用户请求：{user_part or '请按 Skill 说明执行'}"
                    )
                    self._start_agent_turn(message)
                    return

                detail = result.output or result.error or "Skill 执行失败"
                self.chat.append_assistant_complete(
                    f"Skill 执行失败：{result.error}\n\n{detail}",
                )
                self.chat.set_status(self._status_text("就绪"))
            except Exception as exc:
                logger.exception("Skill 执行异常")
                self.chat.append_error(f"Skill 执行失败: {exc}")
                self.chat.set_status(self._status_text("就绪"))
            finally:
                self.chat.clear_tool_status()

        threading.Thread(target=worker, daemon=True, name="skill-run").start()

    def _handle_weather_intent(self, intent: InputIntent, text: str = "") -> None:
        range_label = "当天" if intent.weather_range == "1d" else "7天"
        self.chat.begin_assistant_progress("正在获取天气预报…")
        self.chat.set_tool_status(
            f"🌤 正在从中国天气网获取{range_label}预报…",
            accent="info",
        )
        try:
            args: dict[str, str] = {
                "range_type": intent.weather_range,
                "query_text": text or "",
            }
            if intent.weather_city_code:
                args["city_code"] = intent.weather_city_code
            result = invoke_tool_in_process("get_weather_forecast", args)
            content_format = "html" if result.lstrip().startswith("<") else "markdown"
            self.chat.append_assistant_complete(result, content_format=content_format)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("获取天气预报失败")
            self.chat.append_error(f"获取天气预报失败: {exc}")
        finally:
            self.chat.clear_tool_status()

    def _handle_ocr_intent(
        self,
        text: str,
        attachments: list[dict[str, Any]],
        intent: InputIntent,
    ) -> None:
        from src.ui.input import INTENT_SLASH_OCR

        if intent.kind == INTENT_SLASH_OCR and not any(
            att.get("type") == "image" for att in attachments
        ):
            self.chat.append_error("请先添加图片，或使用 /ocr 时粘贴/上传图片")
            self.chat.set_status(self._status_text("就绪"))
            return

        self.chat.begin_assistant_progress(ocr_progress_text())
        composed = compose_ocr_message(text, attachments)
        if not composed.get("ok"):
            err = composed.get("error") or "识别失败"
            self.chat.append_assistant_complete(f"识别失败：{err}")
            self.chat.set_status(self._status_text("就绪"))
            return
        for warn in composed.get("errors") or []:
            self.chat.append_system(warn)
        reply = format_ocr_reply(composed.get("ocr_results") or [])
        self.chat.append_assistant_complete(reply)
        self.chat.set_status(self._status_text("就绪"))

    def _start_link_summarize_turn(self, intent: InputIntent) -> None:
        self._compose_busy = False
        self._turn_user_query = intent.link_instruction
        self._running = True
        self.chat.set_running(True)
        self.chat.set_status(self._status_text("获取链接…"))
        threading.Thread(
            target=self._run_link_summarize_turn,
            args=(intent.link_instruction, list(intent.urls)),
            daemon=True,
            name="link-summarize",
        ).start()

    def _run_link_summarize_turn(self, instruction: str, urls: list[str]) -> None:
        try:
            if self._compose_cancel.is_set() or not self._llm:
                if not self._llm:
                    self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
                return

            self.chat.begin_assistant()

            def on_token(token: str) -> None:
                if not self._compose_cancel.is_set():
                    self.chat.append_token(token)

            def on_status(status_text: str, accent: str | None) -> None:
                self.chat.set_tool_status(status_text, accent=accent)

            run_link_summarize_turn(
                self._llm,
                instruction,
                urls,
                on_token=on_token,
                on_status=on_status,
                cancel_check=self._compose_cancel.is_set,
            )

            if self._compose_cancel.is_set():
                return

            self.chat.end_assistant()
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("链接总结失败")
            self.chat.append_error(f"链接处理失败: {exc}")
        finally:
            self._running = False
            self._compose_busy = False
            if not self._compose_cancel.is_set():
                self.chat.set_running(False)
            self.chat.clear_tool_status()
            self._reset_turn_state()
            self._gateway_fail("链接处理未完成，请重试。")

    def _start_agent_turn(self, text: str, *, thread_id: str | None = None) -> None:
        self._compose_busy = False
        self._turn_user_query = text
        self._turn_search_query = ""
        self._turn_tool_calls = []
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False
        self._running = True
        self.chat.set_running(True)
        self.chat.set_status(self._status_text("思考中…"))
        tid = thread_id
        if tid is None and self._gateway_context:
            tid = self._gateway_context.get("thread_id")
        self.runner.run_async(text, tid or self._thread_id)

    def _deliver_cached_search(self, user_query: str, response: str) -> None:
        self.chat.append_assistant_complete(response)
        self.chat.set_status(self._status_text("搜索缓存命中"))

    def _start_search_turn(self, user_query: str) -> None:
        self._compose_busy = False
        self._turn_user_query = user_query
        self._turn_search_query = user_query
        self._turn_used_web_search = True
        self._turn_search_ok = False
        self._collecting_assistant = True
        self._running = True
        self.chat.set_running(True)
        self.chat.set_status(self._status_text("搜索中…"))
        threading.Thread(
            target=self._run_search_turn,
            args=(user_query,),
            daemon=True,
            name="search-turn",
        ).start()

    def _run_search_turn(self, user_query: str) -> None:
        try:
            if self._compose_cancel.is_set():
                return
            if not self._llm:
                self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
                return

            self.chat.reset_assistant_for_tool()
            self.chat.begin_assistant()

            def on_token(token: str) -> None:
                if not self._compose_cancel.is_set():
                    self.chat.append_token(token)

            def on_status(status_text: str, accent: str | None) -> None:
                self.chat.set_tool_status(status_text, accent=accent)

            _response, _raw, ok = run_web_search_turn(
                self._llm,
                user_query,
                on_token=on_token,
                on_search_status=on_status,
                cancel_check=self._compose_cancel.is_set,
            )

            if self._compose_cancel.is_set():
                return

            self._turn_search_ok = ok
            self.chat.end_assistant()
            self._search_cache.save_async(
                user_query,
                user_query,
                self.chat.assistant_stream_buffer,
                search_ok=ok,
                finished=True,
            )
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("搜索流程失败")
            self.chat.append_error(f"搜索失败: {exc}")
        finally:
            self._running = False
            self._compose_busy = False
            if not self._compose_cancel.is_set():
                self.chat.set_running(False)
            self.chat.clear_tool_status()
            self._reset_turn_state()
            self._gateway_fail("搜索未完成，请重试。")
