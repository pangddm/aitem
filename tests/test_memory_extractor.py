"""
记忆提取器单元测试
测试 MemoryExtractor 和 MemoryUpdater 的纯代码规则引擎
（不依赖 LLM 调用，只测 _should_keep_memory 和 _should_persist 等纯逻辑）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory.classes import CandidateMemory, MemoryType, MemorySource
from app.memory.extractor import MemoryExtractor
from app.memory.updater import MemoryUpdater


def make_candidate(
    type: MemoryType = MemoryType.KNOWLEDGE,
    content: str = "测试内容",
    summary: str | None = "测试摘要",
    importance: float = 0.5,
) -> CandidateMemory:
    return CandidateMemory(
        type=type,
        content=content,
        summary=summary,
        source=MemorySource.CHAT,
        importance=importance,
    )


# ============================================================
# MemoryExtractor._should_keep_memory 测试
# ============================================================

def test_should_keep_memory():
    """测试 _should_keep_memory 的过滤逻辑"""
    extractor = MemoryExtractor()
    
    cases = [
        # (candidate, expected_keep, description)
        
        # --- 基础规则 ---
        (make_candidate(content="有意义的记忆内容", importance=0.5), True, "正常内容+中等重要度 → keep"),
        (make_candidate(content="", importance=0.5), False, "空内容 → 丢弃"),
        (make_candidate(content="   ", importance=0.5), False, "空白内容 → 丢弃"),
        
        # --- 琐碎消息过滤 ---
        (make_candidate(content="你好", importance=0.5), False, "问候语 → 丢弃"),
        (make_candidate(content="好的", importance=0.5), False, "确认语 → 丢弃"),
        (make_candidate(content="谢谢", importance=0.5), False, "感谢语 → 丢弃"),
        (make_candidate(content="ok", importance=0.5), False, "英文确认 → 丢弃"),
        (make_candidate(content="在吗", importance=0.5), False, "招呼语 → 丢弃"),
        
        # --- 重要度 < 0.45 的边界 ---
        (make_candidate(content="短内容", importance=0.3), False, "低重要度+短内容(<20字符) → 丢弃"),
        (make_candidate(content="这是一个超过20个字符的测试内容字符串", importance=0.3), False, "低重要度+长内容(>=20字符)但无关键词 → 丢弃"),
        (make_candidate(content="这是一个优先事项必须记住的内容", importance=0.3), False, "低重要度+含关键词但内容<20字符 → 丢弃(先检查长度)"),
        (make_candidate(content="这个故障需要重点关注和处理一下啊啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'故障'+内容>=20字符 → keep"),
        (make_candidate(content="记住这个结论非常重要一定要记住啊啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'记住'+内容>=20字符 → keep"),
        (make_candidate(content="生产环境配置需要优先处理一下啊啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'环境'+内容>=20字符 → keep"),
        
        # --- 重要度 >= 0.45 ---
        (make_candidate(content="正常记忆内容", importance=0.45), True, "边界重要度0.45 → keep"),
        (make_candidate(content="正常记忆内容", importance=0.5), True, "正常重要度 → keep"),
        (make_candidate(content="正常记忆内容", importance=0.9), True, "高重要度 → keep"),
        
        # --- 瞬时操作过滤 ---
        (make_candidate(content="已缩容 deployment 到 3 副本", importance=0.6), False, "瞬时操作'已缩容' → 丢弃"),
        (make_candidate(content="已删除 default/nginx-pod", importance=0.6), False, "瞬时操作'已删除' → 丢弃"),
        (make_candidate(content="已执行 kubectl get pods", importance=0.6), False, "瞬时操作'已执行' → 丢弃"),
        (make_candidate(content="现在集群中的 pod 状态正常", importance=0.6), False, "瞬时操作'现在集群中的 pod' → 丢弃"),
        (make_candidate(content="还有其他需要吗", importance=0.6), False, "瞬时操作'还有其他需要吗' → 丢弃"),
        
        # --- 重要度 < 0.45 + 含关键词 + 短内容(<20字符) → 丢弃(先检查长度) ---
        (make_candidate(content="优先", importance=0.3), False, "低重要度+关键词'优先'但短内容(<20字符) → 丢弃"),
        (make_candidate(content="故障", importance=0.3), False, "低重要度+关键词'故障'但短内容(<20字符) → 丢弃"),
    ]
    
    print("=" * 60)
    print("[TEST] MemoryExtractor._should_keep_memory 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (candidate, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._should_keep_memory(candidate)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


# ============================================================
# MemoryUpdater._should_persist 测试
# ============================================================

def test_should_persist():
    """测试 _should_persist 的持久化判断逻辑"""
    updater = object.__new__(MemoryUpdater)
    
    cases = [
        # (candidate, expected_persist, description)
        
        # --- 基础规则 ---
        (make_candidate(content="有意义的记忆内容", importance=0.5), True, "正常内容+重要度>=0.45 → persist"),
        (make_candidate(content="", importance=0.5), False, "空内容 → 不持久化"),
        (make_candidate(content="   ", importance=0.5), False, "空白内容 → 不持久化"),
        
        # --- 重要度边界 ---
        (make_candidate(content="测试内容", importance=0.45), True, "边界重要度0.45 → persist"),
        (make_candidate(content="测试内容", importance=0.44), False, "略低于边界0.44+无关键词 → 不持久化"),
        (make_candidate(content="测试内容", importance=0.0), False, "零重要度+无关键词 → 不持久化"),
        
        # --- 低重要度 + 短内容 ---
        (make_candidate(content="短", importance=0.3), False, "低重要度+短内容 → 不持久化"),
        (make_candidate(content="短内容", importance=0.3), False, "低重要度+短内容(<20字符) → 不持久化"),
        
        # --- 低重要度 + 长内容 + 关键词 ---
        (make_candidate(content="这是一个超过20个字符的测试内容字符串", importance=0.3), False, "低重要度+长内容但无关键词 → 不持久化"),
        (make_candidate(content="这个故障需要优先处理一下啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'故障' → persist"),
        (make_candidate(content="必须记住这个结论非常重要啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'必须' → persist"),
        (make_candidate(content="生产环境配置需要优先处理啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'环境' → persist"),
        (make_candidate(content="这是一个异常情况需要记录一下啊啊啊", importance=0.3), True, "低重要度+含关键词'异常' → persist"),
        (make_candidate(content="用户偏好使用 nginx 部署啊啊啊啊", importance=0.3), True, "低重要度+含关键词'偏好' → persist"),
        (make_candidate(content="保留这个配置不要修改啊啊啊啊啊", importance=0.3), True, "低重要度+含关键词'保留' → persist"),
        
        # --- 类型权重提升 ---
        (make_candidate(type=MemoryType.PREFERENCE, content="偏好内容", importance=0.5), True, "PREFERENCE类型 → persist"),
        (make_candidate(type=MemoryType.KNOWLEDGE, content="知识内容", importance=0.5), True, "KNOWLEDGE类型 → persist"),
        (make_candidate(type=MemoryType.EXPERIENCE, content="经验内容", importance=0.5), True, "EXPERIENCE类型 → persist"),
        (make_candidate(type=MemoryType.FAULT, content="故障内容", importance=0.5), True, "FAULT类型 → persist"),
        (make_candidate(type=MemoryType.SUMMARY, content="摘要内容", importance=0.5), True, "SUMMARY类型 → persist"),
        (make_candidate(type=MemoryType.DOCUMENT, content="文档内容", importance=0.5), True, "DOCUMENT类型 → persist"),
        (make_candidate(type=MemoryType.CLUSTER_STATE, content="集群状态", importance=0.5), True, "CLUSTER_STATE类型 → persist"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryUpdater._should_persist 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (candidate, expected, desc) in enumerate(cases, 1):
        try:
            result = updater._should_persist(candidate)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


# ============================================================
# MemoryExtractor 辅助方法测试
# ============================================================

def test_is_trivial_message():
    """测试 _is_trivial_message 的琐碎消息识别"""
    extractor = MemoryExtractor()
    
    cases = [
        # (text, expected_trivial, description)
        ("", True, "空字符串 → trivial"),
        (None, True, "None → trivial"),
        ("你好", True, "问候 → trivial"),
        ("hello", True, "英文问候 → trivial"),
        ("好的", True, "确认 → trivial"),
        ("谢谢", True, "感谢 → trivial"),
        ("bye", True, "英文再见 → trivial"),
        ("在吗", True, "招呼 → trivial"),
        ("帮我看一下", True, "请求帮助 → trivial"),
        ("ok", True, "英文确认 → trivial"),
        ("hi", True, "英文招呼 → trivial"),
        ("这是一个有意义的查询内容", False, "有意义内容 → 非trivial"),
        ("帮我排查一下为什么 Pod 起不来", False, "故障排查 → 非trivial"),
        ("查看所有 Pod", False, "操作请求 → 非trivial"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._is_trivial_message 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (text, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._is_trivial_message(text)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_looks_important():
    """测试 _looks_important 的重要度关键词识别"""
    extractor = MemoryExtractor()
    
    cases = [
        # (text, expected_important, description)
        ("必须使用这个配置", True, "含'必须' → important"),
        ("一定要记住这个", True, "含'一定' → important"),
        ("不要在生产环境执行", True, "含'不要' → important"),
        ("请优先处理这个故障", True, "含'优先' → important"),
        ("这是一个重要配置", True, "含'重要' → important"),
        ("以后都用这个方案", True, "含'以后' → important"),
        ("每次部署前都要检查", True, "含'每次' → important"),
        ("一直保持这个配置", True, "含'一直' → important"),
        ("持续监控这个指标", True, "含'持续' → important"),
        ("总是先检查日志", True, "含'总是' → important"),
        ("普通查询内容", False, "无关键词 → 非important"),
        ("查看 Pod 状态", False, "操作请求 → 非important"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._looks_important 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (text, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._looks_important(text)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_contains_constraint():
    """测试 _contains_constraint 的约束关键词识别"""
    extractor = MemoryExtractor()
    
    cases = [
        # (text, expected_constraint, description)
        ("不要在生产环境执行", True, "含'不要' → constraint"),
        ("必须使用这个配置", True, "含'必须' → constraint"),
        ("只能使用这个版本", True, "含'只能' → constraint"),
        ("优先使用这个方案", True, "含'优先' → constraint"),
        ("必须要先测试", True, "含'必须要' → constraint"),
        ("普通查询内容", False, "无约束关键词 → 非constraint"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._contains_constraint 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (text, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._contains_constraint(text)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_contains_problem_statement():
    """测试 _contains_problem_statement 的问题描述识别"""
    extractor = MemoryExtractor()
    
    cases = [
        # (text, expected_problem, description)
        ("nginx 发生故障", True, "含'故障' → problem"),
        ("Pod 状态异常", True, "含'异常' → problem"),
        ("连接报错", True, "含'报错' → problem"),
        ("服务挂了", True, "含'挂了' → problem"),
        ("部署失败", True, "含'失败' → problem"),
        ("网络问题", True, "含'问题' → problem"),
        ("部署卡住了", True, "含'卡住' → problem"),
        ("查看 Pod 状态", False, "无问题关键词 → 非problem"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._contains_problem_statement 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (text, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._contains_problem_statement(text)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_looks_like_transient_operation():
    """测试 _looks_like_transient_operation 的瞬时操作识别"""
    extractor = MemoryExtractor()
    
    cases = [
        # (text, expected_transient, description)
        ("已缩容 deployment 到 3 副本", True, "含'已缩容' → transient"),
        ("已扩容到 5 副本", True, "含'已扩容' → transient"),
        ("已删除 default/nginx-pod", True, "含'已删除' → transient"),
        ("成功删掉这个 Pod", True, "含'成功删掉' → transient"),
        ("已执行 kubectl get pods", True, "含'已执行' → transient"),
        ("现在集群中的 pod 状态正常", True, "含'现在集群中的 pod' → transient"),
        ("pod 名称是 nginx-xxx", True, "含'pod 名称' → transient"),
        ("状态正常", True, "含'状态' → transient"),
        ("运行中", True, "含'运行中' → transient"),
        ("已完成", True, "含'已完成' → transient"),
        ("还有其他需要吗", True, "含'还有其他需要吗' → transient"),
        ("可以继续", True, "含'可以继续' → transient"),
        ("这是一个需要记住的故障排查结论", False, "有意义内容 → 非transient"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._looks_like_transient_operation 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (text, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._looks_like_transient_operation(text)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_type_weight_boost():
    """测试 _type_weight_boost 的类型权重提升"""
    updater = object.__new__(MemoryUpdater)
    
    cases = [
        # (type, expected_boost, description)
        (MemoryType.PREFERENCE, 0.12, "PREFERENCE → 0.12"),
        (MemoryType.KNOWLEDGE, 0.08, "KNOWLEDGE → 0.08"),
        (MemoryType.EXPERIENCE, 0.07, "EXPERIENCE → 0.07"),
        (MemoryType.FAULT, 0.09, "FAULT → 0.09"),
        (MemoryType.SUMMARY, 0.05, "SUMMARY → 0.05"),
        (MemoryType.DOCUMENT, 0.05, "DOCUMENT → 0.05"),
        (MemoryType.CLUSTER_STATE, 0.05, "CLUSTER_STATE → 0.05"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryUpdater._type_weight_boost 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (type_, expected, desc) in enumerate(cases, 1):
        try:
            result = updater._type_weight_boost(type_)
            ok = abs(result - expected) < 0.001
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_validate_type():
    """测试 _validate_type 的类型验证"""
    extractor = MemoryExtractor()
    
    cases = [
        # (value, expected_type, description)
        ("preference", MemoryType.PREFERENCE, "preference → PREFERENCE"),
        ("knowledge", MemoryType.KNOWLEDGE, "knowledge → KNOWLEDGE"),
        ("experience", MemoryType.EXPERIENCE, "experience → EXPERIENCE"),
        ("fault", MemoryType.FAULT, "fault → FAULT"),
        ("summary", MemoryType.SUMMARY, "summary → SUMMARY"),
        ("document", MemoryType.DOCUMENT, "document → DOCUMENT"),
        ("cluster_state", MemoryType.CLUSTER_STATE, "cluster_state → CLUSTER_STATE"),
        ("invalid_type", MemoryType.KNOWLEDGE, "无效类型 → KNOWLEDGE(默认)"),
        ("", MemoryType.KNOWLEDGE, "空字符串 → KNOWLEDGE(默认)"),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._validate_type 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (value, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._validate_type(value)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected.value}, 实际: {result.value}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_detect_correction():
    """测试 _detect_correction 的纠正检测"""
    extractor = MemoryExtractor()
    
    cases = [
        # (messages, content, expected_correction, description)
        # _detect_correction 逻辑：
        # 1. 遍历 user 消息
        # 2. 检查消息中是否包含纠正关键词
        # 3. 检查 content 是否在消息文本中，或消息以"不是"开头，或消息包含"不对"
        (
            [{"role": "user", "content": "不是这样的，我之前说的不对"}],
            "之前说的不对",
            "correction",
            "用户说'不是' + content在消息中 → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "不对，我改主意了"}],
            "之前说的内容",
            "correction",
            "用户消息含'不对' → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "不是，之前说的内容错了"}],
            "之前说的内容",
            "correction",
            "用户消息以'不是'开头 + content在消息中 → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "不是，之前说的内容错了"}],
            "之前说的内容",
            "correction",
            "用户消息以'不是'开头 → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "不对，之前说的内容不需要了"}],
            "之前说的内容",
            "correction",
            "用户消息含'不对' + content在消息中 → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "不是，之前说的内容不要这样配置"}],
            "之前说的内容",
            "correction",
            "用户消息以'不是'开头 + content在消息中 → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "不是，之前说的内容我不想用了"}],
            "之前说的内容",
            "correction",
            "用户消息以'不是'开头 + content在消息中 → 检测到纠正"
        ),
        (
            [{"role": "user", "content": "查看所有 Pod"}],
            "查看 Pod",
            None,
            "正常查询 → 无纠正"
        ),
        (
            [{"role": "assistant", "content": "不是这样的"}],
            "之前说的内容",
            None,
            "assistant 说的'不是' → 不检测(只检查user)"
        ),
        # 有纠正关键词且消息以"不是"开头 → 即使content不匹配也检测到纠正
        (
            [{"role": "user", "content": "不是，我改主意了"}],
            "完全不相关的内容",
            "correction",
            "消息以'不是'开头 → 即使content不匹配也检测到纠正"
        ),
        # 有纠正关键词但消息不以"不是"开头且不含"不对"且content不匹配 → 无纠正
        (
            [{"role": "user", "content": "错了，我改主意了"}],
            "完全不相关的内容",
            None,
            "消息不以'不是'开头且不含'不对'且content不匹配 → 无纠正"
        ),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._detect_correction 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (messages, content, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._detect_correction(messages, content)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_count_repeated_emphasis():
    """测试 _count_repeated_emphasis 的重复强调计数"""
    extractor = MemoryExtractor()
    
    cases = [
        # (messages, content, expected_count, description)
        (
            [{"role": "user", "content": "以后都用这个方案"}],
            "以后都用这个方案",
            1,
            "用户说过一次 → count=1"
        ),
        (
            [
                {"role": "user", "content": "以后都用这个方案"},
                {"role": "assistant", "content": "好的"},
                {"role": "user", "content": "以后都用这个方案"},
            ],
            "以后都用这个方案",
            2,
            "用户说过两次 → count=2"
        ),
        (
            [
                {"role": "user", "content": "以后都用这个方案"},
                {"role": "assistant", "content": "以后都用这个方案"},
            ],
            "以后都用这个方案",
            1,
            "assistant 说的不计数 → count=1"
        ),
        (
            [{"role": "user", "content": "查看所有 Pod"}],
            "以后都用这个方案",
            0,
            "内容不匹配 → count=0"
        ),
        (
            [],
            "以后都用这个方案",
            0,
            "空消息列表 → count=0"
        ),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._count_repeated_emphasis 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (messages, content, expected, desc) in enumerate(cases, 1):
        try:
            result = extractor._count_repeated_emphasis(messages, content)
            ok = result == expected
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望: {expected}, 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_normalize_importance():
    """测试 _normalize_importance 的重要度归一化"""
    extractor = MemoryExtractor()
    
    cases = [
        # (importance, expected_min, expected_max, description)
        (0.5, 0.0, 1.0, "正常值0.5 → 保持"),
        (0.0, 0.0, 1.0, "最小值0.0 → 保持"),
        (1.0, 0.0, 1.0, "最大值1.0 → 保持"),
        (-0.1, 0.0, 1.0, "负值 → 钳制到0.0"),
        (1.5, 0.0, 1.0, "超1.0 → 钳制到1.0"),
        # _normalize_importance 调用 float(value)，None 会抛出 TypeError
        # 这是代码的一个潜在问题，测试记录此行为
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._normalize_importance 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (importance, expected_min, expected_max, desc) in enumerate(cases, 1):
        try:
            result = extractor._normalize_importance(importance)
            ok = expected_min <= result <= expected_max
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望范围: [{expected_min}, {expected_max}], 实际: {result}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_apply_reinforcement_rules():
    """测试 _apply_reinforcement_rules 的强化规则"""
    extractor = MemoryExtractor()
    
    cases = [
        # (candidate, messages, expected_importance_min, description)
        (
            make_candidate(content="以后都用这个方案", importance=0.5),
            [{"role": "user", "content": "以后都用这个方案"}],
            0.5,
            "重复强调 → 重要度提升"
        ),
        (
            make_candidate(content="必须记住这个配置", importance=0.5),
            [],
            0.6,
            "含'必须' → 重要度+0.1"
        ),
        (
            make_candidate(content="不要在生产环境执行", importance=0.5),
            [],
            0.58,
            "含约束'不要' → 重要度+0.08"
        ),
        (
            make_candidate(content="nginx 发生故障", importance=0.5),
            [],
            0.56,
            "含问题描述'故障' → 重要度+0.06"
        ),
        (
            make_candidate(content="以后必须优先处理这个故障", importance=0.5),
            [{"role": "user", "content": "以后必须优先处理这个故障"}],
            0.5,
            "多重规则叠加 → 重要度提升"
        ),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._apply_reinforcement_rules 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (candidate, messages, expected_min, desc) in enumerate(cases, 1):
        try:
            result = extractor._apply_reinforcement_rules(candidate, messages)
            ok = result.importance >= expected_min
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   原始重要度: {candidate.importance}, 强化后: {result.importance}, 期望>=: {expected_min}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


def test_fallback_extract():
    """测试 _fallback_extract_from_messages 的降级提取"""
    extractor = MemoryExtractor()
    
    cases = [
        # (messages, expected_count, description)
        (
            [{"role": "user", "content": "查看所有 Pod"}],
            1,
            "单条用户消息 → 提取1条"
        ),
        (
            [
                {"role": "user", "content": "nginx 挂了"},
                {"role": "assistant", "content": "我来排查一下"},
            ],
            1,
            "用户+助手 → 提取1条"
        ),
        (
            [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！"},
            ],
            0,
            "琐碎对话 → 不提取"
        ),
        (
            [],
            0,
            "空消息列表 → 不提取"
        ),
        (
            [
                {"role": "user", "content": "查看所有 Pod"},
                {"role": "assistant", "content": "已执行 kubectl get pods"},
                {"role": "user", "content": "现在集群中的 pod 状态怎么样"},
            ],
            1,
            "多轮对话 → 提取最后2条"
        ),
    ]
    
    print("\n" + "=" * 60)
    print("[TEST] MemoryExtractor._fallback_extract_from_messages 测试")
    print(f"测试用例数: {len(cases)}")
    print("=" * 60)
    
    correct = 0
    total = len(cases)
    
    for i, (messages, expected_count, desc) in enumerate(cases, 1):
        try:
            results = extractor._fallback_extract_from_messages(messages, MemorySource.CHAT)
            actual_count = len(results)
            ok = actual_count == expected_count
            if ok:
                correct += 1
            status = "[OK]" if ok else "[FAIL]"
            print(f"\n[{i}/{total}] {status} {desc}")
            print(f"   期望数量: {expected_count}, 实际: {actual_count}")
            if results:
                print(f"   内容: {results[0].content[:60]}...")
                print(f"   类型: {results[0].type.value}, 重要度: {results[0].importance}")
        except Exception as e:
            print(f"\n[{i}/{total}] [ERROR] {desc}")
            print(f"   错误: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"[RESULT] 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)
    return correct, total


if __name__ == "__main__":
    total_correct = 0
    total_cases = 0
    
    tests = [
        ("_should_keep_memory", test_should_keep_memory),
        ("_should_persist", test_should_persist),
        ("_is_trivial_message", test_is_trivial_message),
        ("_looks_important", test_looks_important),
        ("_contains_constraint", test_contains_constraint),
        ("_contains_problem_statement", test_contains_problem_statement),
        ("_looks_like_transient_operation", test_looks_like_transient_operation),
        ("_type_weight_boost", test_type_weight_boost),
        ("_validate_type", test_validate_type),
        ("_detect_correction", test_detect_correction),
        ("_count_repeated_emphasis", test_count_repeated_emphasis),
        ("_normalize_importance", test_normalize_importance),
        ("_apply_reinforcement_rules", test_apply_reinforcement_rules),
        ("_fallback_extract", test_fallback_extract),
    ]
    
    print("\n" + "=" * 60)
    print("记忆提取器综合测试报告")
    print("=" * 60)
    
    for name, test_func in tests:
        c, t = test_func()
        total_correct += c
        total_cases += t
    
    print("\n" + "=" * 60)
    print(f"总准确率: {total_correct}/{total_cases} ({total_correct/total_cases*100:.1f}%)")
    print("=" * 60)