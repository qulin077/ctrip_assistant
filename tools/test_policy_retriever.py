import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.retriever_vector import lookup_policy_structured


TEST_CASES = [
    ("我可以在起飞前多久在线改签？", "ticket_change_policy"),
    ("如果我取消机票，退款用什么货币？", "refund_policy"),
    ("电子机票可以当发票吗？", "invoice_policy"),
    ("酒店入住后还能取消吗？", "hotel_policy"),
    ("租车开始后还能修改吗？", "car_rental_policy"),
]


def summarize(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else f"{text[:limit]}..."


def main() -> None:
    for query, expected_policy in TEST_CASES:
        result = lookup_policy_structured(query=query, top_k=3)
        matches = result["matches"]
        top = matches[0] if matches else {}
        status = "PASS" if top.get("policy_id") == expected_policy else "CHECK"
        print("=" * 80)
        print(f"Query: {query}")
        print(f"Expected: {expected_policy}")
        print(f"Status: {status}")
        if not top:
            print("No match")
            continue
        print(f"Top policy_id: {top.get('policy_id')}")
        print(f"Section: {top.get('section_title')}")
        print(f"Requires human review: {top.get('requires_human_review')}")
        print(f"Similarity: {top.get('similarity')}")
        print(f"Chunk: {summarize(top.get('chunk_text', ''))}")
        print("Top 3:")
        for idx, match in enumerate(matches, start=1):
            print(
                f"  {idx}. {match.get('policy_id')} | "
                f"{match.get('section_title')} | "
                f"review={match.get('requires_human_review')} | "
                f"score={match.get('similarity')}"
            )


if __name__ == "__main__":
    main()
