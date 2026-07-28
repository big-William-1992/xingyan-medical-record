"""
语音命令解析器
在 ASR 识别结果进入填充流程前，拦截命令短语并映射为 UI 动作。
匹配到命令则执行对应动作，不再作为病历文本填充。
"""
import re


class VoiceCommandParser:
    """
    识别语音命令。返回 (command, arg)：
    - command 为 None 表示不是命令（应作为普通文本填充）
    - command 为字符串（如 'switch_template'）时，arg 为参数（模板名等）
    """

    # 命令关键词 → 命令标识
    COMMAND_PATTERNS = {
        "clear": ["清除内容", "清空内容", "清除文本", "清空文本", "全部清除", "清空病历"],
        "export": ["导出病历", "导出文本", "保存文件", "导出文件"],
        "correct": ["开始纠错", "运行纠错", "执行纠错", "纠错"],
        "save": ["保存病历", "存病历", "保存到病历库", "入库"],
        "start_record": ["开始录音", "继续录音"],
        "stop_record": ["停止录音", "结束录音", "停止", "结束录音了"],
        "copy": ["复制全文", "复制病历", "复制内容"],
        "open_library": ["打开病历库", "查看病历库", "病历库"],
    }

    # "换模板XX" / "切换模板XX" / "使用XX模板"
    SWITCH_TEMPLATE_RE = [
        re.compile(r'^(?:换|切换|使用|选择)\s*模板\s*(.+)$'),
        re.compile(r'^(?:换|切换|使用|选择)\s*(.+?)\s*模板$'),
        re.compile(r'^模板\s*(?:切换|换)\s*(?:到|为)?\s*(.+)$'),
    ]

    # "切换科室XX" / "换到XX科"
    SWITCH_DEPT_RE = [
        re.compile(r'^(?:换|切换|使用|选择)\s*科室\s*(.+)$'),
        re.compile(r'^(?:换|切换)\s*(?:到|为)?\s*(.+?科)\s*$'),
    ]

    def parse(self, text):
        """
        解析文本。返回 (command, arg)。
        非命令返回 (None, None)。
        """
        if not text:
            return (None, None)
        # 去掉首尾标点与空白（ASR 常带句号）
        cleaned = text.strip().strip("。，,.！!？?、；; \u3000")
        if not cleaned:
            return (None, None)

        # 命令短语通常很短；过长文本视为病历内容，不拦截
        if len(cleaned) > 12:
            # 仍允许"换模板/切换科室"这类带参数的较长命令通过正则识别
            cmd = self._match_parametric(cleaned)
            return cmd if cmd else (None, None)

        # 精确/包含匹配固定命令
        for command, phrases in self.COMMAND_PATTERNS.items():
            for p in phrases:
                if cleaned == p:
                    return (command, None)

        # 带参数命令（换模板 / 切换科室）
        cmd = self._match_parametric(cleaned)
        if cmd:
            return cmd

        # 短文本但未命中命令，也可能是内容；仅当以命令动词开头才拦截
        return (None, None)

    def _match_parametric(self, text):
        for r in self.SWITCH_TEMPLATE_RE:
            m = r.match(text)
            if m and m.group(1).strip():
                return ("switch_template", m.group(1).strip())
        for r in self.SWITCH_DEPT_RE:
            m = r.match(text)
            if m and m.group(1).strip():
                return ("switch_dept", m.group(1).strip())
        return None


# 命令词（供加入 hotwords.txt / 提示用途）
COMMAND_HOTWORDS = [
    "清除内容", "导出病历", "开始纠错", "保存病历", "停止录音",
    "复制全文", "打开病历库", "换模板", "切换科室",
]
