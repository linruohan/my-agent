from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from loguru import logger

from src.memory.rag import get_knowledge_stats, ingest_files


class KnowledgeDialog(ctk.CTkToplevel):
    """知识库文档导入对话框。"""

    def __init__(self, master, provider, on_done: Callable[[str], None] | None = None):
        super().__init__(master)
        self.title("知识库管理")
        self.geometry("480x360")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._provider = provider
        self._on_done = on_done

        stats = get_knowledge_stats()
        backend_label = "本地" if stats["embedding_backend"] == "local" else "API"
        info = (
            f"已索引文档: {stats['document_count']} 个\n"
            f"向量块数: {stats['chunk_count']}\n"
            f"索引状态: {'已建立' if stats['has_index'] else '未建立'}\n"
            f"Embedding: {backend_label} ({stats['embedding_model']})"
        )
        ctk.CTkLabel(self, text="知识库状态", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 4)
        )
        self.status_label = ctk.CTkLabel(self, text=info, justify="left")
        self.status_label.pack(anchor="w", padx=20, pady=4)

        ctk.CTkLabel(
            self,
            text="支持 .txt / .md / .pdf / .docx",
            text_color="gray60",
        ).pack(anchor="w", padx=20, pady=(12, 4))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=8)
        ctk.CTkButton(btn_frame, text="选择文件", command=self._pick_files).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(btn_frame, text="选择文件夹", command=self._pick_folder).pack(side="left")

        self.log_box = ctk.CTkTextbox(self, height=120)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=8)

        ctk.CTkButton(self, text="关闭", width=100, command=self.destroy).pack(pady=16)

    def _log(self, msg: str) -> None:
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")

    def _import_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._log(f"开始导入 {len(paths)} 项...")
        try:
            file_count, chunk_count = ingest_files(paths, self._provider)
            self._log(f"完成：{file_count} 个文件，{chunk_count} 个文本块")
            stats = get_knowledge_stats()
            backend_label = "本地" if stats["embedding_backend"] == "local" else "API"
            self.status_label.configure(
                text=(
                    f"已索引文档: {stats['document_count']} 个\n"
                    f"向量块数: {stats['chunk_count']}\n"
                    f"索引状态: {'已建立' if stats['has_index'] else '未建立'}\n"
                    f"Embedding: {backend_label} ({stats['embedding_model']})"
                )
            )
            if self._on_done:
                self._on_done(f"知识库已更新：+{file_count} 文件，+{chunk_count} 块")
        except Exception as exc:
            logger.exception("知识库导入失败")
            msg = str(exc)
            if "embedding" in msg.lower() or "404" in msg or "model" in msg.lower():
                msg += "\n提示: 请在 config/search.yaml 中将 embedding_mode 设为 local（默认已启用本地模型）。"
            self._log(f"导入失败: {msg}")

    def _pick_files(self) -> None:
        files = filedialog.askopenfilenames(
            parent=self,
            title="选择文档",
            filetypes=[
                ("文档", "*.txt *.md *.pdf *.docx"),
                ("所有文件", "*.*"),
            ],
        )
        self._import_paths([Path(f) for f in files])

    def _pick_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="选择文件夹")
        if folder:
            self._import_paths([Path(folder)])
