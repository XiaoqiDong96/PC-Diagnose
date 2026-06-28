from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from diagnosis_model import (
    APP_DIR,
    FIELD_DEFINITIONS,
    MODEL_FEATURES,
    PancreaticCancerDiagnosisModel,
    create_import_template,
    load_patient_file,
)


class ScrollFrame(ttk.Frame):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.inner.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_width)

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)


class DiagnosisApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("胰腺癌辅助诊断软件")
        self.geometry("1220x780")
        self.minsize(1040, 680)

        self.model: PancreaticCancerDiagnosisModel | None = None
        self.manual_vars: dict[str, tk.StringVar] = {}
        self.manual_report = ""
        self.batch_source: pd.DataFrame | None = None
        self.batch_results: pd.DataFrame | None = None
        self.batch_reports: dict[str, str] = {}

        self._configure_style()
        self._build_shell()
        self.after(80, self._load_model)

    def _configure_style(self) -> None:
        self.configure(bg="#f6f7f9")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f6f7f9", foreground="#1f2933", font=("PingFang SC", 12))
        style.configure("Panel.TLabel", background="#ffffff", foreground="#1f2933", font=("PingFang SC", 12))
        style.configure("Muted.TLabel", background="#f6f7f9", foreground="#657384", font=("PingFang SC", 11))
        style.configure("Title.TLabel", background="#f6f7f9", foreground="#17202a", font=("PingFang SC", 22, "bold"))
        style.configure("Subtitle.TLabel", background="#f6f7f9", foreground="#56616f", font=("PingFang SC", 12))
        style.configure("TButton", font=("PingFang SC", 12), padding=(12, 8))
        style.configure("Accent.TButton", font=("PingFang SC", 12, "bold"), padding=(14, 9))
        style.configure("Treeview", font=("PingFang SC", 11), rowheight=30)
        style.configure("Treeview.Heading", font=("PingFang SC", 11, "bold"))
        style.configure("TNotebook", background="#f6f7f9", borderwidth=0)
        style.configure("TNotebook.Tab", font=("PingFang SC", 12), padding=(18, 10))

    def _build_shell(self) -> None:
        header = ttk.Frame(self, padding=(24, 18, 24, 8))
        header.pack(fill="x")
        ttk.Label(header, text="胰腺癌辅助诊断软件", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="支持手动录入或导入 Excel、CSV、TXT，输出诊断报告、依据和模型可信度。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        self.status_var = tk.StringVar(value="正在加载模型，请稍候...")
        ttk.Label(header, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(6, 18))
        self.manual_tab = ttk.Frame(self.notebook, padding=12)
        self.batch_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.manual_tab, text="手动录入")
        self.notebook.add(self.batch_tab, text="批量导入")

        self._build_manual_tab()
        self._build_batch_tab()

    def _build_manual_tab(self) -> None:
        self.manual_tab.columnconfigure(0, weight=0, minsize=470)
        self.manual_tab.columnconfigure(1, weight=1)
        self.manual_tab.rowconfigure(0, weight=1)

        form_panel = ttk.Frame(self.manual_tab, style="Panel.TFrame", padding=16)
        form_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        form_panel.rowconfigure(1, weight=1)
        form_panel.columnconfigure(0, weight=1)

        ttk.Label(form_panel, text="患者信息", style="Panel.TLabel", font=("PingFang SC", 15, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        scroll = ScrollFrame(form_panel)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.inner.columnconfigure(1, weight=1)
        scroll.inner.columnconfigure(3, weight=1)

        for key in ["姓名", "ID号"]:
            self.manual_vars[key] = tk.StringVar()

        row = 0
        self._add_entry(scroll.inner, row, 0, "姓名", "姓名")
        self._add_entry(scroll.inner, row, 2, "ID号", "ID号")
        row += 1

        for index, field in enumerate(FIELD_DEFINITIONS):
            col = 0 if index % 2 == 0 else 2
            if index % 2 == 0 and index:
                row += 1
            self._add_field(scroll.inner, row, col, field)

        actions = ttk.Frame(form_panel, style="Panel.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="生成报告", style="Accent.TButton", command=self._generate_manual_report).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(actions, text="清空", command=self._clear_manual).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="导出报告", command=self._export_manual_report).grid(row=0, column=2, padx=(4, 0))

        report_panel = ttk.Frame(self.manual_tab, style="Panel.TFrame", padding=16)
        report_panel.grid(row=0, column=1, sticky="nsew")
        report_panel.rowconfigure(1, weight=1)
        report_panel.columnconfigure(0, weight=1)
        ttk.Label(report_panel, text="诊断报告", style="Panel.TLabel", font=("PingFang SC", 15, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        self.manual_text = tk.Text(
            report_panel,
            wrap="word",
            font=("PingFang SC", 12),
            background="#fbfcfd",
            foreground="#17202a",
            relief="flat",
            padx=12,
            pady=12,
        )
        self.manual_text.grid(row=1, column=0, sticky="nsew")
        manual_scrollbar = ttk.Scrollbar(report_panel, orient="vertical", command=self.manual_text.yview)
        manual_scrollbar.grid(row=1, column=1, sticky="ns")
        self.manual_text.configure(yscrollcommand=manual_scrollbar.set)
        self._set_text(self.manual_text, "模型加载完成后，可在左侧录入患者信息并生成报告。")

    def _build_batch_tab(self) -> None:
        self.batch_tab.columnconfigure(0, weight=1)
        self.batch_tab.rowconfigure(2, weight=1)
        self.batch_tab.rowconfigure(4, weight=1)

        toolbar = ttk.Frame(self.batch_tab, padding=(0, 0, 0, 10))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(4, weight=1)
        ttk.Button(toolbar, text="选择文件", style="Accent.TButton", command=self._choose_batch_file).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(toolbar, text="导出结果", command=self._export_batch_results).grid(row=0, column=1, padx=4)
        ttk.Button(toolbar, text="生成导入模板", command=self._save_template).grid(row=0, column=2, padx=4)
        ttk.Button(toolbar, text="清空批量结果", command=self._clear_batch).grid(row=0, column=3, padx=4)

        self.batch_file_var = tk.StringVar(value="未选择文件")
        ttk.Label(toolbar, textvariable=self.batch_file_var, style="Muted.TLabel").grid(row=0, column=4, sticky="e")

        columns = (
            "序号",
            "姓名",
            "ID号",
            "胰腺癌概率(%)",
            "判定可信度(%)",
            "诊断结论",
            "风险等级",
            "高敏感度筛查",
            "子模型一致性",
        )
        self.batch_tree = ttk.Treeview(self.batch_tab, columns=columns, show="headings", selectmode="browse")
        widths = {
            "序号": 70,
            "姓名": 110,
            "ID号": 120,
            "胰腺癌概率(%)": 120,
            "判定可信度(%)": 120,
            "诊断结论": 270,
            "风险等级": 110,
            "高敏感度筛查": 120,
            "子模型一致性": 210,
        }
        for column in columns:
            self.batch_tree.heading(column, text=column)
            self.batch_tree.column(column, width=widths[column], anchor="center")
        self.batch_tree.grid(row=2, column=0, sticky="nsew")
        self.batch_tree.bind("<<TreeviewSelect>>", self._show_selected_batch_report)

        tree_scrollbar = ttk.Scrollbar(self.batch_tab, orient="vertical", command=self.batch_tree.yview)
        tree_scrollbar.grid(row=2, column=1, sticky="ns")
        self.batch_tree.configure(yscrollcommand=tree_scrollbar.set)

        ttk.Label(self.batch_tab, text="选中患者报告", font=("PingFang SC", 14, "bold")).grid(
            row=3, column=0, sticky="w", pady=(14, 8)
        )
        self.batch_text = tk.Text(
            self.batch_tab,
            wrap="word",
            font=("PingFang SC", 12),
            background="#fbfcfd",
            foreground="#17202a",
            relief="flat",
            padx=12,
            pady=12,
            height=12,
        )
        self.batch_text.grid(row=4, column=0, sticky="nsew")
        batch_text_scrollbar = ttk.Scrollbar(self.batch_tab, orient="vertical", command=self.batch_text.yview)
        batch_text_scrollbar.grid(row=4, column=1, sticky="ns")
        self.batch_text.configure(yscrollcommand=batch_text_scrollbar.set)
        self._set_text(self.batch_text, "导入文件后，点击表格中的患者即可查看完整报告。")

    def _add_entry(self, parent: ttk.Frame, row: int, col: int, key: str, label: str) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=col, sticky="w", padx=(0, 8), pady=5)
        entry = ttk.Entry(parent, textvariable=self.manual_vars[key], font=("PingFang SC", 12))
        entry.grid(row=row, column=col + 1, sticky="ew", padx=(0, 16), pady=5)

    def _add_field(self, parent: ttk.Frame, row: int, col: int, field: dict) -> None:
        key = field["key"]
        label = field["label"]
        unit = field.get("unit", "")
        label_text = f"{label}({unit})" if unit else label
        self.manual_vars[key] = tk.StringVar()
        ttk.Label(parent, text=label_text, style="Panel.TLabel").grid(
            row=row, column=col, sticky="w", padx=(0, 8), pady=5
        )
        if field["type"] == "category":
            choices = [""] + [f"{code} - {text}" for code, text in field["options"]]
            widget = ttk.Combobox(
                parent,
                values=choices,
                textvariable=self.manual_vars[key],
                font=("PingFang SC", 12),
                state="readonly",
            )
        else:
            widget = ttk.Entry(parent, textvariable=self.manual_vars[key], font=("PingFang SC", 12))
        widget.grid(row=row, column=col + 1, sticky="ew", padx=(0, 16), pady=5)

    def _load_model(self) -> None:
        try:
            self.model = PancreaticCancerDiagnosisModel()
        except Exception as exc:
            messagebox.showerror("模型加载失败", str(exc))
            self.status_var.set("模型加载失败，请检查训练数据文件。")
            return
        self.status_var.set(self.model.summary_text)
        self._set_text(self.manual_text, "模型已加载。请在左侧录入患者信息，然后点击“生成报告”。")

    def _manual_record(self) -> dict[str, str]:
        record: dict[str, str] = {}
        for key, var in self.manual_vars.items():
            value = var.get().strip()
            if " - " in value:
                value = value.split(" - ", 1)[0].strip()
            record[key] = value
        return record

    def _generate_manual_report(self) -> None:
        if self.model is None:
            messagebox.showinfo("请稍候", "模型仍在加载，请稍后再试。")
            return
        try:
            result = self.model.predict_one(self._manual_record())
        except Exception as exc:
            messagebox.showerror("生成失败", str(exc))
            return
        self.manual_report = result.report
        self._set_text(self.manual_text, result.report)

    def _clear_manual(self) -> None:
        for var in self.manual_vars.values():
            var.set("")
        self.manual_report = ""
        self._set_text(self.manual_text, "已清空。请重新录入患者信息。")

    def _export_manual_report(self) -> None:
        if not self.manual_report:
            messagebox.showinfo("没有报告", "请先生成报告。")
            return
        path = filedialog.asksaveasfilename(
            title="保存诊断报告",
            defaultextension=".txt",
            initialdir=str(APP_DIR),
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(self.manual_report, encoding="utf-8")
        messagebox.showinfo("已保存", f"报告已保存到：\n{path}")

    def _choose_batch_file(self) -> None:
        if self.model is None:
            messagebox.showinfo("请稍候", "模型仍在加载，请稍后再试。")
            return
        path = filedialog.askopenfilename(
            title="选择患者信息文件",
            initialdir=str(APP_DIR.parent),
            filetypes=[
                ("支持的文件", "*.xlsx *.xls *.csv *.txt"),
                ("Excel", "*.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("TXT", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        try:
            source = load_patient_file(path)
            results = self.model.predict_dataframe(source)
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))
            return
        self.batch_source = source
        self.batch_results = results
        self.batch_file_var.set(path)
        self._populate_batch_tree(results)
        if not results.empty:
            first = self.batch_tree.get_children()[0]
            self.batch_tree.selection_set(first)
            self.batch_tree.focus(first)
            self._show_selected_batch_report()

    def _populate_batch_tree(self, results: pd.DataFrame) -> None:
        self.batch_tree.delete(*self.batch_tree.get_children())
        self.batch_reports.clear()
        columns = (
            "序号",
            "姓名",
            "ID号",
            "胰腺癌概率(%)",
            "判定可信度(%)",
            "诊断结论",
            "风险等级",
            "高敏感度筛查",
            "子模型一致性",
        )
        for _, row in results.iterrows():
            item_id = str(row["序号"])
            values = [row.get(column, "") for column in columns]
            self.batch_tree.insert("", "end", iid=item_id, values=values)
            self.batch_reports[item_id] = str(row.get("诊断报告", ""))
        self._set_text(self.batch_text, f"已完成 {len(results)} 条记录预测。请选择患者查看报告。")

    def _show_selected_batch_report(self, _event: tk.Event | None = None) -> None:
        selection = self.batch_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        report = self.batch_reports.get(item_id, "")
        self._set_text(self.batch_text, report)

    def _export_batch_results(self) -> None:
        if self.batch_results is None or self.batch_results.empty:
            messagebox.showinfo("没有结果", "请先导入文件并完成预测。")
            return
        path = filedialog.asksaveasfilename(
            title="保存批量预测结果",
            defaultextension=".xlsx",
            initialdir=str(APP_DIR),
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            if Path(path).suffix.lower() == ".csv":
                self.batch_results.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                self.batch_results.to_excel(path, index=False)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        messagebox.showinfo("已保存", f"批量结果已保存到：\n{path}")

    def _save_template(self) -> None:
        path = filedialog.asksaveasfilename(
            title="保存导入模板",
            defaultextension=".csv",
            initialdir=str(APP_DIR),
            filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            create_import_template(path)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        messagebox.showinfo("已保存", f"导入模板已保存到：\n{path}")

    def _clear_batch(self) -> None:
        self.batch_source = None
        self.batch_results = None
        self.batch_reports.clear()
        self.batch_tree.delete(*self.batch_tree.get_children())
        self.batch_file_var.set("未选择文件")
        self._set_text(self.batch_text, "已清空批量结果。")

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


def main() -> int:
    app = DiagnosisApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
