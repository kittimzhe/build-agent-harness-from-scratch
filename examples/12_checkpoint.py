"""12_checkpoint.py —— 第 12 章案例：Checkpoint 与状态恢复（断点续跑）

运行方式（仓库任意子目录）：
    python examples/12_checkpoint.py

本章全部 demo **不需要 API Key**：状态序列化 / 断点续跑是纯本地确定的。

演示结构：
    1. 序列化往返：Plan → dict → Plan（状态不丢）
    2. 落盘看内容：checkpoint.json 长什么样
    3. 断点续跑：第 2 步「崩溃」，从盘上恢复、换 executor 接着做完
    4. Durable Execution 思路：状态是真源，执行只推进状态并每步落盘
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (
    Plan, plan_to_dict, plan_from_dict, save_checkpoint, load_checkpoint,
    run_plan_with_checkpoint,
)


# ---------- demo ----------

def demo_roundtrip():
    """① 序列化往返：状态不丢。"""
    print("=" * 60)
    print("① 序列化往返：Plan ↔ dict ↔ Plan")
    print("=" * 60)
    plan = Plan(goal="出周报", steps=["拉订单数据", "算总额", "画图"])
    plan.mark_done(0, "拉了 1200 单")
    plan[1].status = "in_progress"

    d = plan_to_dict(plan)
    back = plan_from_dict(d)
    print("  dict 里的 goal：", d["goal"])
    print("  往返后第 0 步状态：", back[0].status, "| 结果：", back[0].result)
    print("  往返后第 1 步状态：", back[1].status)
    print("  （『状态序列化』就是把对象变成能安全写盘、再还原的字典）\n")


def demo_see_json():
    """② 落盘看内容。"""
    print("=" * 60)
    print("② checkpoint.json 长什么样")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "checkpoint.json")
        plan = Plan(goal="出周报", steps=["拉订单数据", "算总额", "画图"])
        plan.mark_done(0, "拉了 1200 单")
        save_checkpoint(plan, path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            print("  " + line)
        print("  （version 字段给未来格式演进留余地；result 里能塞任何字符串）\n")


def demo_resume():
    """③ 断点续跑：第 2 步崩溃 → 恢复 → 接着做完。"""
    print("=" * 60)
    print("③ 断点续跑：进程崩了，从 checkpoint 恢复接着做")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "checkpoint.json")
        plan = Plan(goal="出周报", steps=["拉订单数据", "算总额", "画图", "发邮件"])

        # 第一次执行：第 0 步成功、第 1 步「崩溃」（抛异常）
        def crashy_executor(desc, idx):
            if idx == 1:
                raise RuntimeError("数据库连接断开（模拟进程崩溃）")
            return f"完成{desc}"

        try:
            run_plan_with_checkpoint(plan, crashy_executor, path)
        except RuntimeError:
            pass
        print("  第一次执行中断。落盘状态：")
        for line in plan.progress().splitlines():
            print("    " + line)

        # 模拟「进程重启」：从盘上读回一个全新的 Plan 对象
        resumed = load_checkpoint(path)
        print("  重启后 load_checkpoint 得到的状态：")
        for line in resumed.progress().splitlines():
            print("    " + line)

        # 修复 executor，从断点接着跑
        def fixed_executor(desc, idx):
            return f"完成{desc}"
        run_plan_with_checkpoint(resumed, fixed_executor, path)
        print("  修复后恢复执行，最终：")
        for line in resumed.progress().splitlines():
            print("    " + line)
        print(f"  全部完成：{resumed.is_complete()}（第 1 步 failed 被重跑成 done）\n")


def demo_durable_idea():
    """④ Durable Execution 思路。"""
    print("=" * 60)
    print("④ Durable Execution：状态是真源，执行只推进状态并每步落盘")
    print("=" * 60)
    print("  三句话：")
    print("    1. SAVE 是常态、不是事后：每步前后都落盘，崩了才不丢")
    print("    2. 只重跑「还没 done」的：done 是唯一稳定边界（at-least-once）")
    print("    3. 恢复 = 加载状态 + 继续推进，代码和第一次跑是同一份")
    print("  对照第 10 章 execute_plan：失败即停、failed 被永久跳过；")
    print("  本章 run_plan_with_checkpoint：失败落盘后停止，恢复时 failed 重跑\n")


def main():
    print()
    demo_roundtrip()
    demo_see_json()
    demo_resume()
    demo_durable_idea()
    print("✅ 本章全部 demo 无需 API Key，确定性输出完成。")


if __name__ == "__main__":
    main()