import json
import re
import sys
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import KB_CHUNKS_PATH, KB_POLICY_INDEX_PATH, PROJECT_ROOT


MAX_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 120


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw_meta = text[4:end].strip()
    body = text[end + 5 :].lstrip()
    metadata: dict[str, Any] = {}
    for line in raw_meta.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.lower() == "true":
            parsed: Any = True
        elif value.lower() == "false":
            parsed = False
        elif value.lower() in {"null", "none"}:
            parsed = None
        else:
            parsed = value.strip('"').strip("'")
        metadata[key.strip()] = parsed
    return metadata, body


def split_sections(body: str) -> list[dict[str, str]]:
    matches = list(re.finditer(r"^(#{1,4})\s+(.+?)\s*$", body, flags=re.MULTILINE))
    if not matches:
        return [{"section_title": "全文", "text": body.strip()}]

    sections = []
    for idx, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if content:
            sections.append({"section_title": heading, "text": content})
    return sections


def paragraph_units(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    units: list[str] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) > 8 and all(line.lstrip().startswith(("-", "*")) for line in lines if line.strip()):
            units.extend(line.strip() for line in lines if line.strip())
        else:
            units.append(block)
    return units


def split_long_unit(unit: str) -> list[str]:
    if len(unit) <= MAX_CHUNK_CHARS:
        return [unit]
    sentences = re.split(r"(?<=[。！？；])", unit)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + len(sentence) > MAX_CHUNK_CHARS:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current}{sentence}"
    if current:
        chunks.append(current.strip())
    return chunks or [unit]


def chunk_section(text: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for unit in paragraph_units(text):
        for piece in split_long_unit(unit):
            if current and len(current) + len(piece) + 2 > MAX_CHUNK_CHARS:
                chunks.append(current.strip())
                current = piece
            elif current and len(current) < MIN_CHUNK_CHARS:
                current = f"{current}\n\n{piece}"
            elif current:
                chunks.append(current.strip())
                current = piece
            else:
                current = piece
    if current:
        chunks.append(current.strip())
    return chunks


def infer_chunk_flags(chunk: dict[str, Any]) -> None:
    text = chunk["chunk_text"]
    policy_id = chunk["policy_id"]
    section = chunk["section_title"]

    if any(word in text for word in ["人工处理", "升级人工", "待人工确认", "人工确认"]):
        chunk["risk_level"] = "high"
    elif chunk.get("requires_human_review"):
        chunk["risk_level"] = "medium"

    if policy_id in {
        "ticket_change_policy",
        "refund_policy",
        "hotel_policy",
        "car_rental_policy",
        "excursion_policy",
    } and any(word in text for word in ["取消", "改签", "修改", "预订", "退款"]):
        chunk["requires_confirmation"] = True

    allowed_actions = []
    combined = f"{section}\n{text}"
    if "改签" in combined:
        allowed_actions.append("ticket_change")
    if "取消" in combined:
        allowed_actions.append("cancel")
    if "退款" in combined:
        allowed_actions.append("refund")
    if "预订" in combined:
        allowed_actions.append("booking")
    if "发票" in combined:
        allowed_actions.append("invoice")
    if allowed_actions:
        chunk["allowed_action"] = sorted(set(allowed_actions))


def build_chunks(index_path: Path = KB_POLICY_INDEX_PATH) -> list[dict[str, Any]]:
    policies = read_jsonl(index_path)
    chunks: list[dict[str, Any]] = []
    policy_counts: dict[str, int] = {}

    for policy in policies:
        file_path = PROJECT_ROOT / policy["file_path"]
        metadata, body = parse_front_matter(file_path.read_text(encoding="utf-8"))
        merged_meta = {**policy, **metadata}
        policy_id = merged_meta["policy_id"]
        policy_counts.setdefault(policy_id, 0)

        for section in split_sections(body):
            for chunk_text in chunk_section(section["text"]):
                policy_counts[policy_id] += 1
                chunk = {
                    "chunk_id": f"{policy_id}__{policy_counts[policy_id]:03d}",
                    "policy_id": policy_id,
                    "title": merged_meta.get("title", policy.get("title", policy_id)),
                    "service": merged_meta.get("service", policy.get("service")),
                    "policy_type": merged_meta.get("policy_type", policy.get("policy_type")),
                    "source": merged_meta.get("source", policy.get("source")),
                    "review_status": merged_meta.get("review_status", policy.get("review_status")),
                    "requires_human_review": bool(
                        merged_meta.get("requires_human_review", policy.get("requires_human_review", False))
                    ),
                    "file_path": policy["file_path"],
                    "section_title": section["section_title"],
                    "chunk_text": chunk_text,
                }
                infer_chunk_flags(chunk)
                chunks.append(chunk)
    return chunks


def write_chunks(chunks: list[dict[str, Any]], output_path: Path = KB_CHUNKS_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + "\n",
        encoding="utf-8",
    )


def write_stats(chunks: list[dict[str, Any]], output_path: Path) -> None:
    by_policy: dict[str, list[int]] = {}
    for chunk in chunks:
        by_policy.setdefault(chunk["policy_id"], []).append(len(chunk["chunk_text"]))

    all_lengths = [len(chunk["chunk_text"]) for chunk in chunks]
    lines = [
        "# KB Chunk Statistics",
        "",
        f"- total_chunks: {len(chunks)}",
        f"- average_chunk_length: {round(mean(all_lengths), 2) if all_lengths else 0}",
        f"- min_chunk_length: {min(all_lengths) if all_lengths else 0}",
        f"- max_chunk_length: {max(all_lengths) if all_lengths else 0}",
        "",
        "| Policy | Chunks | Avg chars | Min chars | Max chars |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for policy_id, lengths in sorted(by_policy.items()):
        lines.append(
            f"| `{policy_id}` | {len(lengths)} | {round(mean(lengths), 2)} | {min(lengths)} | {max(lengths)} |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    chunks = build_chunks()
    write_chunks(chunks)
    stats_path = KB_CHUNKS_PATH.parent / "chunk_stats.md"
    write_stats(chunks, stats_path)
    print(f"Wrote {len(chunks)} chunks to {KB_CHUNKS_PATH}")
    print(f"Wrote stats to {stats_path}")


if __name__ == "__main__":
    main()
