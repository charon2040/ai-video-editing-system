import os
from typing import List, Dict, Any

class ExportService:
    def __init__(self):
        pass

    def _ms_to_smpte_timecode(self, ms: float, fps: float = 25.0) -> str:
        """
        将毫秒转换为 SMPTE 时间码格式 HH:MM:SS:FF (小时:分钟:秒:帧)
        """
        total_seconds = ms / 1000.0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        frames = int((total_seconds - int(total_seconds)) * fps)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    def export_to_edl(self, segments: List[Dict[str, Any]], original_video_name: str, output_path: str, fps: float = 25.0) -> bool:
        """
        将剪辑片段导出为 CMX 3600 EDL (Edit Decision List) 格式
        可以被 Premiere Pro, DaVinci Resolve 等专业软件导入
        """
        try:
            edl_lines = [
                "TITLE: AI_CUT_PROJECT",
                "FCM: NON-DROP FRAME",
                ""
            ]
            
            # 记录在最终时间轴上的累计时长
            timeline_current_ms = 0.0
            
            for i, seg in enumerate(segments):
                start_ms = seg.get("start", 0)
                end_ms = seg.get("end", 0)
                duration_ms = end_ms - start_ms
                
                # 源素材的入点和出点
                src_in = self._ms_to_smpte_timecode(start_ms, fps)
                src_out = self._ms_to_smpte_timecode(end_ms, fps)
                
                # 目标时间轴的入点和出点
                rec_in = self._ms_to_smpte_timecode(timeline_current_ms, fps)
                timeline_current_ms += duration_ms
                rec_out = self._ms_to_smpte_timecode(timeline_current_ms, fps)
                
                # CMX3600 标准格式:
                # 001  AX       V     C        00:00:00:00 00:00:05:00 00:00:00:00 00:00:05:00
                # * FROM CLIP NAME: video.mp4
                event_num = f"{i+1:03d}"
                reel_name = "AX" # 辅助卷名
                
                edl_lines.append(f"{event_num}  {reel_name}       V     C        {src_in} {src_out} {rec_in} {rec_out}")
                edl_lines.append(f"* FROM CLIP NAME: {original_video_name}")
                edl_lines.append("")
                
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(edl_lines))
                
            return True
        except Exception as e:
            print(f"Failed to export EDL: {e}")
            return False

export_service = ExportService()
