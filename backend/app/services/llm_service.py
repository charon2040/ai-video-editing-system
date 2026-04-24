import json
import logging
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = None
        # 懒加载 client，避免启动时因缺少 key 而报错
        if settings.LLM_API_KEY:
            self._init_client()
            
    def _init_client(self):
        try:
            self.client = OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL
            )
            # 打印掩码后的 key 用于调试
            masked_key = f"{settings.LLM_API_KEY[:4]}****{settings.LLM_API_KEY[-4:]}" if settings.LLM_API_KEY else "None"
            logger.info(f"LLM Client initialized with base_url: {settings.LLM_BASE_URL}, key: {masked_key}, model: {settings.LLM_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")

    def _ensure_client(self) -> bool:
        if not self.client:
            if settings.LLM_API_KEY:
                self._init_client()
            else:
                logger.warning("LLM_API_KEY is not set. Returning mock data.")
                return False
        return True

    def _clean_content(self, content: str) -> str:
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]
        elif cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:]
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]
        return cleaned_content.strip()

    def _split_script_by_segments(self, script: str, segments: List[Dict[str, Any]]) -> List[str]:
        normalized_script = script.strip()
        if not normalized_script or not segments:
            return []

        total_duration = sum(max(int(seg.get("end", 0)) - int(seg.get("start", 0)), 1) for seg in segments)
        if total_duration <= 0:
            return [normalized_script]

        punctuation = "，。！？；：,.!?;、"
        text_length = len(normalized_script)
        chunks = []
        cursor = 0
        consumed_duration = 0
        segment_count = len(segments)

        for index, seg in enumerate(segments):
            duration = max(int(seg.get("end", 0)) - int(seg.get("start", 0)), 1)
            if index == segment_count - 1:
                chunk = normalized_script[cursor:].strip()
                chunks.append(chunk)
                break

            consumed_duration += duration
            target = round(text_length * consumed_duration / total_duration)
            min_split = cursor + 1
            max_split = text_length - (segment_count - index - 1)
            target = max(min_split, min(target, max_split))

            split_index = target
            best_distance = None
            search_start = max(min_split, target - 8)
            search_end = min(max_split, target + 8)
            for candidate in range(search_start, search_end + 1):
                if normalized_script[candidate - 1] in punctuation:
                    distance = abs(candidate - target)
                    if best_distance is None or distance < best_distance:
                        split_index = candidate
                        best_distance = distance

            chunk = normalized_script[cursor:split_index].strip()
            if not chunk:
                split_index = min_split
                chunk = normalized_script[cursor:split_index].strip()
            chunks.append(chunk)
            cursor = split_index

        return chunks

    def project_script_to_segments(self, script: str, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunks = self._split_script_by_segments(script, segments)
        if not chunks:
            return segments

        updated_segments = []
        for index, seg in enumerate(segments):
            item = dict(seg)
            item["dubbing"] = chunks[index] if index < len(chunks) else ""
            updated_segments.append(item)
        return updated_segments

    def _parse_requirements_plan(self, content: str):
        cleaned_content = self._clean_content(content)
        parsed_json = json.loads(cleaned_content)
        script = ""
        suggestions = []
        effects = {"highlight": True, "blur": False}
        segments = []
        if isinstance(parsed_json, dict):
            if isinstance(parsed_json.get("script"), str):
                script = parsed_json.get("script", "").strip()
            if isinstance(parsed_json.get("suggestions"), list):
                suggestions = [str(s).strip() for s in parsed_json.get("suggestions") if str(s).strip()]
            if isinstance(parsed_json.get("effects"), dict):
                effects["highlight"] = bool(parsed_json["effects"].get("highlight", effects["highlight"]))
                effects["blur"] = bool(parsed_json["effects"].get("blur", effects["blur"]))
            if isinstance(parsed_json.get("segments"), list):
                segments = self._postprocess_segments(parsed_json.get("segments"))
            if not script and segments:
                script = " ".join(
                    str(seg.get("dubbing", "")).strip()
                    for seg in segments
                    if str(seg.get("dubbing", "")).strip()
                ).strip()
        return {"script": script, "suggestions": suggestions, "effects": effects, "segments": segments}

    def _postprocess_segments(self, segments: List[Dict[str, Any]], min_ms: int = 1, merge_gap_ms: int = 0):
        if not segments:
            return []
        normalized = []
        for seg in segments:
            try:
                start = int(seg.get("start", 0))
                end = int(seg.get("end", 0))
            except Exception:
                continue
            if end <= start:
                continue
            content = seg.get("content", seg.get("text", ""))
            dubbing = seg.get("dubbing", "")
            normalized.append({"start": start, "end": end, "content": content, "dubbing": dubbing})
        if not normalized:
            return []
        normalized.sort(key=lambda x: x["start"])
        merged = [normalized[0]]
        for seg in normalized[1:]:
            last = merged[-1]
            if seg["start"] < last["end"] + merge_gap_ms:
                last["end"] = max(last["end"], seg["end"])
                if seg.get("content") and last.get("content") and seg["content"] not in last["content"]:
                    last["content"] = f"{last['content']} {seg['content']}".strip()
                elif seg.get("content"):
                    last["content"] = seg["content"]

                if seg.get("dubbing") and last.get("dubbing") and seg["dubbing"] not in last["dubbing"]:
                    last["dubbing"] = f"{last['dubbing']}，{seg['dubbing']}".strip()
                elif seg.get("dubbing"):
                    last["dubbing"] = seg["dubbing"]
            else:
                merged.append(seg)
        final_segments = []
        for seg in merged:
            if seg["end"] - seg["start"] >= min_ms:
                final_segments.append(seg)
        return final_segments

    def align_script_with_subtitles(self, target_script: str, asr_subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._ensure_client():
            return []
        
        system_prompt = """你是视频剪辑助手。根据提供的文案和字幕，找出字幕中最匹配文案的片段。
必须仅返回 JSON 数组，格式如：[{"start": 0, "end": 1000, "content": "内容"}]
允许模糊匹配，不要编造时间。"""
        
        user_content = f"【文案】\n{target_script}\n\n【字幕】\n{json.dumps(asr_subtitles, ensure_ascii=False)}"
        
        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                temperature=0.1
            )
            content = response.choices[0].message.content
            parsed = json.loads(self._clean_content(content))
            return self._postprocess_segments(parsed if isinstance(parsed, list) else [])
        except Exception as e:
            logger.error(f"LLM API Call Error: {e}")
            return []

    def generate_requirements_plan(self, requirements: str, subtitles: List[Dict[str, Any]]):
        if not self._ensure_client():
            return {"script": "", "suggestions": [], "effects": {"highlight": True, "blur": False}}
        system_prompt = """你是专业的视频剪辑导演。请根据用户的详细需求和字幕内容，产出可执行的剪辑方案。

# 输出
必须仅返回 JSON 对象，不要包含任何解释或 Markdown。
格式示例：
{
  "script": "可直接用于配音/字幕的成片总文案",
  "segments": [
    {
      "start": 0, 
      "end": 1000, 
      "content": "提取的原字幕片段1",
      "dubbing": "本段画面的解说词，每句解说词尽量简短，控制在15字以内以便于字幕显示"
    },
    {
      "start": 1500, 
      "end": 3000, 
      "content": "提取的原字幕片段2",
      "dubbing": "关键转折点解说（切忌长篇大论）"
    }
  ],
  "suggestions": [
    "片头用一句总述快速引入主题",
    "关键转折前加0.3秒停顿以增强冲击"
  ],
  "effects": {"highlight": true, "blur": false}
}

# 要求
1. segments: 必须从原字幕中挑选出符合需求的片段，保留原始的 start 和 end 时间戳。这是后台剪辑的唯一依据！
2. segments 要尽量保证叙事完整，优先选择信息完整的片段，不要只截取“狼人来了”“龙掉了”这种过短口号。单段尽量控制在 3-10 秒，整片通常选择 6-12 段。
3. script: 必须是一篇完整、能讲清楚故事的导演总文案。不要只写结果摘要，要讲清楚背景、前期局势、中期转折、关键决策、结局和人物表现。整体信息量要明显高于一句赛果播报。
4. dubbing: 必须是 script 按 segments 顺序拆分后的逐段配音稿，不能再次简缩或改写。所有 segment 的 dubbing 按顺序拼接后，应尽量还原 script 原文，只是按画面节奏分段朗读。
5. suggestions: 给出可执行剪辑建议（节奏、转场、强调点等）。
6. effects: 指示是否启用字幕高亮或蒙版模糊。
"""
        user_content = f"""
【需求】：
{requirements}

【字幕】：
{json.dumps(subtitles, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content
            logger.info(f"LLM Raw Response: {content}")
            return self._parse_requirements_plan(content)
        except Exception as e:
            logger.error(f"LLM API Call Error: {e}")
            import traceback
            traceback.print_exc()
            return {"script": "", "suggestions": [], "effects": {"highlight": True, "blur": False}}

llm_service = LLMService()
