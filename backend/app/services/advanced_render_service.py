import os
import subprocess
from typing import List, Dict, Any

class AdvancedRenderService:
    def __init__(self):
        pass
        
    def _split_text(self, text: str, max_chars: int = 15) -> str:
        """
        长字幕分行处理
        """
        if len(text) <= max_chars:
            return text
        
        words = text.replace('，', ' ').replace('。', ' ').replace(',', ' ').replace('.', ' ').split()
        if len(words) > 1:
            # 如果有空格/标点分割的词，按词截断
            lines = []
            current_line = ""
            for word in words:
                if len(current_line) + len(word) > max_chars:
                    if current_line:
                        lines.append(current_line.strip())
                    current_line = word
                else:
                    current_line += " " + word if current_line else word
            if current_line:
                lines.append(current_line.strip())
            return "\\N".join(lines)
        else:
            # 如果是纯中文字符串没有空格，直接按字数硬截断
            return text[:max_chars] + "\\N" + text[max_chars:]

    def generate_ass_subtitle(self, subtitles: List[Dict[str, Any]], output_path: str, style_config: Dict[str, Any] = None):
        """
        根据 LLM 的决策，生成带特效的 ASS 字幕文件。
        ASS 格式支持复杂的颜色、字体大小、甚至动画特效。
        """
        # 默认样式
        font_size = style_config.get("font_size", 24) if style_config else 24
        primary_color = style_config.get("primary_color", "&H00FFFFFF") if style_config else "&H00FFFFFF" # BGR 格式
        
        ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{primary_color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        events = []
        for seg in subtitles:
            # 将毫秒转为 ASS 时间格式: H:MM:SS.cs
            start_s = seg["start"] / 1000.0
            end_s = seg["end"] / 1000.0
            
            def format_ass_time(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                cs = int((seconds - int(seconds)) * 100)
                return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
                
            start_time = format_ass_time(start_s)
            end_time = format_ass_time(end_s)
            text = seg.get("text", "")
            
            # 动态调整字体大小避免溢出
            style_prefix = ""
            if len(text) > 30:
                style_prefix += r"{\fs" + str(int(font_size * 0.8)) + r"}"
                
            # 处理换行
            text = self._split_text(text, max_chars=18)
            
            # 高亮特效
            if seg.get("is_highlight"):
                # 放大 + 变色 + 边框加粗
                style_prefix += r"{\fs" + str(int(font_size * 1.2)) + r"\c&H00FFFF&\3c&HFFFFFF&\bord4}"
                effect_text = f"{style_prefix}{text}"
            else:
                effect_text = f"{style_prefix}{text}"
                
            events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{effect_text}")
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(events))
            
        return output_path

    def apply_advanced_effects(self, input_video: str, output_video: str, render_commands: Dict[str, Any]) -> bool:
        """
        基于 LLM 决策出的复杂特效参数（蒙版、滤镜），调用 FFmpeg 进行高级重渲染。
        render_commands: 包含滤镜图（Filter Graph）参数或 ASS 路径。
        """
        try:
            # 这是一个示例 Filter Graph，实际可由大模型生成
            # 比如应用高斯模糊蒙版，或者烧录刚刚生成的 ASS 字幕
            ass_file = render_commands.get("ass_file_path")
            
            # 注意：在 Windows 环境下 FFmpeg 烧录字幕需要处理路径转义
            ass_path_escaped = ass_file.replace("\\", "/").replace(":", "\\:") if ass_file else ""
            
            vf_filters = []
            if ass_path_escaped:
                vf_filters.append(f"ass='{ass_path_escaped}'")
                
            if render_commands.get("apply_blur"):
                # 在特定时间段应用模糊
                blur_start = render_commands["blur_start"]
                blur_end = render_commands["blur_end"]
                vf_filters.append(f"boxblur=10:enable='between(t,{blur_start},{blur_end})'")
                
            filter_graph = ",".join(vf_filters) if vf_filters else "copy"
            
            cmd = [
                "ffmpeg", "-y", "-i", input_video
            ]
            
            if filter_graph != "copy":
                cmd.extend(["-vf", filter_graph, "-c:a", "copy"])
            else:
                cmd.extend(["-c", "copy"])
                
            cmd.append(output_video)
            
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Advanced Render Error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False

advanced_render_service = AdvancedRenderService()
