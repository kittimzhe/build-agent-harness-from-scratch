"""第 18 章离线冒烟：起 app → /health → /research → 断言无状态与续跑。

CI（.github/workflows/ci.yml）与本地通用：
    DEEP_RESEARCH_OFFLINE=1 python deploy/smoke_test.py
无需任何 API Key。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from deploy.app import app  # noqa: E402


def main() -> int:
    c = TestClient(app)

    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok", r.text
    print("✅ /health →", r.json())

    r1 = c.post("/research", json={"question": "LangGraph 和 MCP 有什么关系？"})
    b1 = r1.json()
    assert r1.status_code == 200 and b1["final_state"] == "done", b1
    print(f"✅ /research → final_state={b1['final_state']} rounds={b1['rounds']} "
          f"checkpoint_id={b1['checkpoint_id']}")

    # 无状态：两个请求的 workdir 必须不同（文件层不串味）
    r2 = c.post("/research", json={"question": "第二单"})
    b2 = r2.json()
    assert b1["checkpoint_id"] != b2["checkpoint_id"], "两请求共用了 workdir！"
    print(f"✅ 两请求 workdir 不同：{b1['checkpoint_id']} vs {b2['checkpoint_id']}")

    # 断点续跑：带 checkpoint_id 复用同一目录
    r3 = c.post("/research", json={"question": "续跑", "checkpoint_id": b1["checkpoint_id"]})
    b3 = r3.json()
    assert b3["checkpoint_id"] == b1["checkpoint_id"], "续跑没复用目录！"
    print(f"✅ checkpoint_id 续跑复用目录：{b3['checkpoint_id']}")

    # 超时路径：RESEARCH_TIMEOUT 极小 → 504（且 checkpoint 已落盘可续跑）
    os.environ["RESEARCH_TIMEOUT"] = "0.0001"
    r = c.post("/research", json={"question": "x"})
    assert r.status_code == 504, f"超时应 504，实际 {r.status_code}"
    assert "checkpoint_id" in r.json()["detail"] or "续跑" in r.json()["detail"]
    print("✅ /research 超时 → 504（detail 提示可续跑）")
    del os.environ["RESEARCH_TIMEOUT"]

    # 路径穿越/格式非法：一律 400（basename('..') 仍是 '..'，白名单才挡得住）
    for bad in ["..", ".", "../etc", "req-ZZZZabcdefgh", "req-abc", "/etc/passwd"]:
        r = c.post("/research", json={"question": "x", "checkpoint_id": bad})
        assert r.status_code == 400, f"{bad!r} 应被拒绝，实际 {r.status_code}"
    print("✅ 非法 checkpoint_id（.. / . / 穿越 / 格式错）全部 400")

    print("\n离线冒烟全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
