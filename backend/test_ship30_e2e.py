"""
Real end-to-end Ship 30 test using Ollama.
Requires Ollama running locally with qwen3:1.7b model and backend running on port 8000.
"""
import httpx
import sys

BASE_URL = "http://127.0.0.1:8000/api/sessions"
TIMEOUT = 660.0  # 11 minutes: backend needs up to 10 min on CPU for long-form generation

def check(label, condition, note=""):
    icon = "PASS" if condition else "FAIL"
    suffix = f"  ({note})" if note else ""
    print(f"   [{icon}] {label}{suffix}")
    return condition

def test_ship30_e2e():
    print("=== Ship 30 for 30 — Real Ollama E2E Test ===\n")
    
    # 1. Create session
    print("1. Creating session...")
    res = httpx.post(f"{BASE_URL}/", json={"title": "Ship30 E2E Test"}, timeout=10.0)
    if res.status_code != 201:
        print(f"   FAILED: {res.text}")
        sys.exit(1)
    session_id = res.json()["id"]
    print(f"   Session: {session_id}")

    # 2. Send Ship30 request
    topic = "how product teams should prioritize what to build, grounded in Lenny's podcast"
    prompt = f"Write a Ship 30 for 30 style article about {topic}."
    print(f"\n2. Sending Ship30 request:\n   '{prompt}'\n   (This may take 2-5 minutes on CPU...)\n")

    res = httpx.post(
        f"{BASE_URL}/{session_id}/messages",
        json={"role": "user", "content": prompt},
        timeout=TIMEOUT
    )
    if res.status_code != 200:
        print(f"   FAILED ({res.status_code}): {res.text}")
        sys.exit(1)

    data = res.json()
    msg = data.get("message", {})
    meta = msg.get("meta") or {}
    content = msg.get("content", "")
    sources = data.get("sources", [])

    print(f"3. Provider: {data.get('provider', 'unknown')}\n")

    # 4. Meta checks
    print("4. Meta / Skill output:")
    meta_type = meta.get("type", "N/A")
    meta_title = meta.get("title", "N/A")
    meta_wc = meta.get("word_count", "N/A")
    print(f"   type:       {meta_type}")
    print(f"   title:      {meta_title}")
    print(f"   word_count: {meta_wc}")

    # 5. Word count cross-check
    actual_wc = len(content.split())
    print(f"\n5. Word count cross-check:")
    print(f"   meta word_count : {meta_wc}")
    print(f"   actual wc       : {actual_wc}")
    if meta_wc != "N/A":
        check("meta word_count matches actual content", meta_wc == actual_wc)

    # 6. Sources
    print(f"\n6. Sources ({len(sources)}):")
    for s in sources:
        url = s.get("youtube_url") or "no URL"
        print(f"   - {s.get('title')} | {s.get('guest')} | sim={s.get('similarity', 0):.4f}")

    # 7. Structural checks
    print("\n7. Structural checks:")
    lines = content.splitlines()
    has_h1 = any(l.strip().startswith("# ") for l in lines)
    has_h2 = any(l.strip().startswith("## ") for l in lines)
    has_bullets = "- " in content or "* " in content
    has_bold = "**" in content
    has_content = actual_wc >= 200

    check("Ship30 skill invoked (meta.type == ship30)", meta_type == "ship30",
          note="if N/A, tool routing failed" if meta_type != "ship30" else "")
    check("H1 title present", has_h1)
    check("H2 subheadings present", has_h2)
    check("Bullet points present", has_bullets)
    check("Bold emphasis present", has_bold)
    check("Content length >= 200 words", has_content, note=f"actual={actual_wc}")
    check("Word count >= 600 (target ~1250)", actual_wc >= 600,
          note="local model may produce shorter output")
    check("Sources returned", len(sources) > 0)

    # 8. Article excerpt
    print(f"\n8. Article excerpt (first 500 chars):")
    print("-" * 60)
    print(content[:500])
    print("...")
    print("-" * 60)

    all_passed = has_h1 and has_content and len(sources) > 0
    print(f"\n=== {'PASSED' if all_passed else 'PARTIAL — see checks above'} ===")

if __name__ == "__main__":
    test_ship30_e2e()
