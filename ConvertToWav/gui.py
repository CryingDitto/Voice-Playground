"""Small Tkinter front end; conversion stays off the UI thread."""

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from convert_to_wav import convert_file, find_ffmpeg


class ConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.files: list[Path] = []
        self.events = queue.Queue()
        self.busy = False
        self.output = tk.StringVar(value=str(Path(__file__).parent.resolve() / "output"))
        self.rate = tk.StringVar(value="원본 유지")
        self.channels = tk.StringVar(value="원본 유지")
        self.status = tk.StringVar(value="변환할 M4A 파일을 추가하세요.")
        root.title("M4A → WAV 변환기")
        root.geometry("760x620")
        root.minsize(620, 520)
        root.protocol("WM_DELETE_WINDOW", self.close)
        frame = ttk.Frame(root, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        frame.rowconfigure(10, weight=1)
        ttk.Label(frame, text="M4A → WAV", font=("맑은 고딕", 19, "bold")).grid(sticky="w")
        toolbar = ttk.Frame(frame)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(12, 6))
        self.add_button = ttk.Button(toolbar, text="파일 추가…", command=self.add_files)
        self.add_button.pack(side="left")
        self.clear_button = ttk.Button(toolbar, text="목록 비우기", command=self.clear_files)
        self.clear_button.pack(side="left", padx=8)
        list_frame = ttk.Frame(frame)
        list_frame.grid(row=2, column=0, sticky="nsew")
        self.file_list = tk.Listbox(list_frame, height=7, activestyle="none")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.file_list.pack(side="left", fill="both", expand=True)
        ttk.Label(frame, text="저장 폴더").grid(row=3, sticky="w", pady=(12, 4))
        destination = ttk.Frame(frame)
        destination.grid(row=4, sticky="ew")
        self.output_entry = ttk.Entry(destination, textvariable=self.output)
        self.output_entry.pack(side="left", fill="x", expand=True)
        self.folder_button = ttk.Button(destination, text="찾아보기…", command=self.select_folder)
        self.folder_button.pack(side="right", padx=(8, 0))
        options = ttk.Frame(frame)
        options.grid(row=5, sticky="ew", pady=12)
        ttk.Label(options, text="샘플레이트").pack(side="left")
        self.rate_combo = ttk.Combobox(options, textvariable=self.rate, state="readonly", width=12,
                                      values=["원본 유지", "8000", "16000", "22050", "24000", "44100", "48000"])
        self.rate_combo.pack(side="left", padx=(8, 20))
        ttk.Label(options, text="채널").pack(side="left")
        self.channel_combo = ttk.Combobox(options, textvariable=self.channels, state="readonly", width=12,
                                         values=["원본 유지", "모노", "스테레오"])
        self.channel_combo.pack(side="left", padx=8)
        ttk.Label(frame, text="16비트 PCM WAV로 저장 · 기존 파일은 보존하고 이름에 번호를 붙입니다.").grid(row=6, sticky="w")
        self.start_button = ttk.Button(frame, text="WAV로 변환", command=self.start)
        self.start_button.grid(row=7, sticky="ew", pady=12)
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=8, sticky="ew")
        ttk.Label(frame, textvariable=self.status).grid(row=9, sticky="w", pady=6)
        self.log = ScrolledText(frame, height=7, wrap="word", state="disabled")
        self.log.grid(row=10, sticky="nsew")
        self.root.after(100, self.poll)

    def add_files(self):
        selected = filedialog.askopenfilenames(title="M4A 파일 선택", filetypes=[("M4A 오디오", "*.m4a *.M4A")])
        for name in selected:
            path = Path(name).resolve()
            if path not in self.files:
                self.files.append(path)
                self.file_list.insert("end", str(path))
        self.status.set(f"선택한 파일: {len(self.files)}개")

    def clear_files(self):
        self.files.clear()
        self.file_list.delete(0, "end")
        self.status.set("변환할 M4A 파일을 추가하세요.")

    def select_folder(self):
        folder = filedialog.askdirectory(title="WAV 저장 폴더 선택")
        if folder:
            self.output.set(folder)

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.add_button, self.clear_button, self.folder_button,
                       self.output_entry, self.start_button):
            widget.configure(state="disabled" if busy else "normal")
        for widget in (self.rate_combo, self.channel_combo):
            widget.configure(state="disabled" if busy else "readonly")

    def start(self):
        if not self.files:
            messagebox.showinfo("파일 선택", "변환할 M4A 파일을 추가하세요.")
            return
        if not self.output.get().strip():
            messagebox.showerror("저장 폴더", "저장 폴더를 지정하세요.")
            return
        files = tuple(self.files)
        output = Path(self.output.get().strip())
        rate = None if self.rate.get() == "원본 유지" else int(self.rate.get())
        channels = {"원본 유지": None, "모노": 1, "스테레오": 2}[self.channels.get()]
        self.set_busy(True)
        self.progress.configure(maximum=len(files), value=0)
        self.status.set("변환 준비 중…")
        threading.Thread(target=self.convert, args=(files, output, rate, channels), daemon=True).start()

    def convert(self, files, output, rate, channels):
        success = 0
        try:
            executable = find_ffmpeg()
            for index, source in enumerate(files, 1):
                self.events.put(("status", f"변환 중 ({index}/{len(files)}): {source.name}"))
                try:
                    path = convert_file(source, output, sample_rate=rate, channels=channels, ffmpeg=executable)
                    success += 1
                    self.events.put(("log", f"완료: {path}"))
                except Exception as exc:
                    self.events.put(("log", f"실패: {source}\n{exc}"))
                self.events.put(("progress", index))
        except Exception as exc:
            self.events.put(("log", str(exc)))
        finally:
            self.events.put(("done", (success, len(files) - success)))

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", value + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "status":
                    self.status.set(value)
                elif kind == "progress":
                    self.progress.configure(value=value)
                elif kind == "done":
                    self.set_busy(False)
                    success, failed = value
                    self.status.set(f"변환 종료 — 성공 {success}개 / 실패 {failed}개")
                    if failed:
                        messagebox.showwarning("변환 결과", f"성공 {success}개 / 실패 {failed}개\n아래 기록에서 실패 원인을 확인하세요.")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("변환 중", "변환이 끝난 뒤 창을 닫아주세요.")
            return
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
