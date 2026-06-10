import json
import logging
import re
import traceback
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
        """从 LLM 返回的内容中提取 JSON 字符串"""
        if not content:
            return ""
        # 尝试使用正则匹配第一个 JSON 对象或数组
        match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # 兜底清理 Markdown 标记
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]
        elif cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:]
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]
        return cleaned_content.strip()

    def _parse_requirements_plan(self, content: str):
        cleaned_content = self._clean_content(content)
        try:
            parsed_json = json.loads(cleaned_content)
        except Exception as e:
            logger.error(f"Failed to parse JSON in _parse_requirements_plan: {e}\nContent: {cleaned_content}")
            # 兜底：如果 JSON 解析失败，将原始内容视为 script，并自动分段
            script = content.strip()
            return {
                "script": script,
                "suggestions": ["自动分段处理"],
                "effects": {"highlight": True, "blur": False},
                "segments": []  # 稍后在外层通过 align_script_with_subtitles 补齐
            }

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

    def _split_script_to_narration_segments(self, script: str, max_chars: int = 28) -> List[Dict[str, Any]]:
        normalized = str(script or "").strip()
        if not normalized:
            return []
        parts = re.split(r"(?<=[。！？!?；;])", normalized)
        items: List[Dict[str, Any]] = []
        buffer = ""
        for raw in parts:
            chunk = str(raw or "").strip()
            if not chunk:
                continue
            if not buffer:
                buffer = chunk
                continue
            if len(buffer) + len(chunk) <= max_chars:
                buffer = f"{buffer}{chunk}"
                continue
            items.append({"text": buffer})
            buffer = chunk
        if buffer:
            items.append({"text": buffer})
        return items

    def _parse_redub_outline(self, content: str):
        cleaned_content = self._clean_content(content)
        try:
            parsed_json = json.loads(cleaned_content)
        except Exception as e:
            logger.error(f"Failed to parse JSON in _parse_redub_outline: {e}\nContent: {cleaned_content}")
            # 兜底：如果 JSON 解析失败，将原始内容视为 script，并调用本地分段逻辑
            script = content.strip()
            return {
                "script": script,
                "suggestions": ["自动分段处理"],
                "effects": {"highlight": True, "blur": False},
                "narration_segments": self._split_script_to_narration_segments(script)
            }

        script = ""
        suggestions = []
        effects = {"highlight": True, "blur": False}
        narration_segments: List[Dict[str, Any]] = []
        if isinstance(parsed_json, dict):
            if isinstance(parsed_json.get("script"), str):
                script = parsed_json.get("script", "").strip()
            if isinstance(parsed_json.get("suggestions"), list):
                suggestions = [str(s).strip() for s in parsed_json.get("suggestions") if str(s).strip()]
            if isinstance(parsed_json.get("effects"), dict):
                effects["highlight"] = bool(parsed_json["effects"].get("highlight", effects["highlight"]))
                effects["blur"] = bool(parsed_json["effects"].get("blur", effects["blur"]))
            if isinstance(parsed_json.get("narration_segments"), list):
                for item in parsed_json.get("narration_segments", []):
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text", "")).strip()
                    if not text:
                        continue
                    narration_segments.append(
                        {
                            "text": text,
                            "focus": str(item.get("focus", "")).strip(),
                        }
                    )
        if not narration_segments and script:
            narration_segments = self._split_script_to_narration_segments(script)
        if not script and narration_segments:
            script = "".join(str(item.get("text", "")).strip() for item in narration_segments).strip()
        return {
            "script": script,
            "suggestions": suggestions,
            "effects": effects,
            "narration_segments": narration_segments,
        }

    def _parse_timed_redub_segments(self, content: str):
        cleaned_content = self._clean_content(content)
        try:
            parsed_json = json.loads(cleaned_content)
        except Exception as e:
            logger.error(f"Failed to parse JSON in _parse_timed_redub_segments: {e}\nContent: {cleaned_content}")
            return []

        raw_segments = []
        if isinstance(parsed_json, dict):
            raw_segments = parsed_json.get("segments", [])
        elif isinstance(parsed_json, list):
            raw_segments = parsed_json

        segments: List[Dict[str, Any]] = []
        for seg in raw_segments or []:
            if not isinstance(seg, dict):
                continue
            try:
                start = int(seg.get("start", 0))
                end = int(seg.get("end", 0))
            except (ValueError, TypeError):
                continue
            if end <= start:
                continue
            dubbing = str(seg.get("dubbing", "")).strip()
            if not dubbing:
                continue
            
            # 注意：这里我们尽量保留 LLM 返回的所有字段，但核心字段必须存在
            segments.append(
                {
                    "start": start,
                    "end": end,
                    "content": str(seg.get("content", "") or seg.get("text", "") or "").strip(),
                    "dubbing": dubbing,
                    "segment_index": int(seg.get("segment_index", len(segments)) or len(segments)),
                    # 以下两个字段后端会按需回填，这里解析是为了兼容性
                    "required_duration_ms": int(seg.get("required_duration_ms", 0) or 0),
                    "tts_duration_ms": int(seg.get("tts_duration_ms", 0) or 0),
                }
            )
        segments.sort(key=lambda item: (item["segment_index"], item["start"]))
        return segments

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
            traceback.print_exc()
            return {"script": "", "suggestions": [], "effects": {"highlight": True, "blur": False}}

    def generate_redub_outline(self, requirements: str, subtitles: List[Dict[str, Any]]):
        if not self._ensure_client():
            return {"script": "", "suggestions": [], "effects": {"highlight": True, "blur": False}, "narration_segments": []}
        system_prompt = """你是专业的视频导演与解说文案策划。现在只做第一轮：先根据用户需求和字幕，生成成片解说文案。

# 重要：输出格式
必须仅返回 JSON 对象。绝对不要包含 Markdown 标题、解释或任何 JSON 块之外的文字。
{
  "script": "完整成片文案",
  "narration_segments": [
    {"text": "第1段解说词", "focus": "本段画面重点"},
    {"text": "第2段解说词", "focus": "本段画面重点"}
  ],
  "suggestions": ["建议1", "建议2"],
  "effects": {"highlight": true, "blur": false}
}

# 文案要求
1. script 必须是完整、自然、可朗读的成片文案。
2. narration_segments 必须按最终成片顺序拆分 script，每段都要适合单独配音。
3. narration_segments 的 text 要尽量完整自然，避免太长，一般控制在 1-2 句。
4. 这一轮不要输出 start/end，不要估算时长。
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
                    {"role": "user", "content": user_content},
                ],
                temperature=0.4,
            )
            content = response.choices[0].message.content
            logger.info(f"LLM Redub Outline Raw Response: {content}")
            return self._parse_redub_outline(content)
        except Exception as e:
            logger.error(f"LLM Redub Outline Error: {e}")
            return {"script": "", "suggestions": [], "effects": {"highlight": True, "blur": False}, "narration_segments": []}

    def generate_timed_redub_segments(self, requirements: str, subtitles: List[Dict[str, Any]], narration_segments: List[Dict[str, Any]]):
        if not self._ensure_client():
            return []
        system_prompt = """你是视频剪辑助手。现在做第二轮：根据字幕、逐段配音文案以及每段真实配音时长，选择最终要截取的视频片段。

# 输出
必须仅返回 JSON 对象，不要包含解释或 Markdown：
{
  "segments": [
    {
      "segment_index": 0,
      "start": 0,
      "end": 3200,
      "content": "该时间范围对应的原字幕内容摘要",
      "dubbing": "本段配音文案原文"
    }
  ]
}

# 严格要求
1. 每个 narration segment 必须对应一个最终视频片段，按顺序输出。
2. start/end 必须来自原字幕时间线，不得编造。
3. 每个片段的时长 end-start 必须 >= 当前 narration segment 中给出的 tts_duration_ms，最好额外留出 150-300ms 缓冲。
4. 如单条字幕不够长，可以合并相邻字幕形成更长片段，但只能做“刚好够用”的最小合并，禁止动辄返回几十秒或几分钟的超长片段。
5. dubbing 必须原样返回，不要改写。
6. content 用对应时间范围内的原字幕内容概述即可。
7. 所有 segments 必须时间顺序递增，尽量不要重叠。
8. 不要重新估算或改写时长，不要返回 required_duration_ms 或 tts_duration_ms，后端会按 segment_index 回填真实测时结果。
9. 如果某段配音只需要 3-8 秒，就只选择接近这个长度的画面区间，不要选择覆盖整局比赛的大段视频。
"""
        user_content = f"""
【需求】：
{requirements}

【逐段配音与真实时长】：
{json.dumps(narration_segments, ensure_ascii=False)}

【原字幕】：
{json.dumps(subtitles, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
            )
            content = response.choices[0].message.content
            logger.info(f"LLM Timed Redub Raw Response: {content}")
            return self._parse_timed_redub_segments(content)
        except Exception as e:
            logger.error(f"LLM Timed Redub Error: {e}")
            return []

llm_service = LLMService()
