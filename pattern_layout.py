"""多尺码对称花样排针：为全部尺码选择严格递增的单侧花样重复数。

模型（所有输入先换算为精确分数，比较与寻优全程不用浮点）：
  起针数   cast_on(r) = 2×边针 + 中央针 + 2×花样宽度×r     （r 为单侧重复数）
  实际片幅 width(r)    = cast_on(r) × 10 ÷ 每10厘米针数     （厘米）
  每尺码约束 |width(r_i) − 目标片幅_i| ≤ 允许宽差，且 r_i ≥ 1 为整数；
  尺码间约束 r_1 < r_2 < … < r_n（严格递增，每侧使用相同的完整花样重复）。

由于 width(r) 关于 r 严格递增，每个尺码在允许宽差内的可行重复数构成一个
连续区间 [lo_i, hi_i]（可能为空）。在此之上求“宽差绝对值之和最小”的
严格递增序列：逐尺码代价 cost_i(r) = |width(r) − t_i| 是 r 的凸分段线性
函数，其最小值点构成区间 M_i = [m⁻_i, m⁺_i]。可以证明任意最优解必满足
  r_i ≤ max_{j≤i} (m⁺_j + (i−j))，  r_i ≥ min_{j≥i} (m⁻_j − (j−i))
——若 r_i 越过该界，则它属于一段“连续整数链”，把整段向最优点方向平移 1
仍满足全部约束且总宽差严格变小，矛盾。因此每个尺码只需在该窗口内做动态
规划（前缀最小值优化，O(尺码数 × 窗口)），即可得到精确最优解；代价与
并列比较均用 Fraction 精确计算，同分时按 (总宽差, 重复数组) 字典序取
最小，即得到“同分取按尺码顺序字典序最小的重复数组”。
"""

import math
from fractions import Fraction


def solve_layout(gauge, targets, edge, center, pattern_width, tolerance):
    """求解多尺码对称花样排针。

    参数（调用方已完成校验）：
      gauge         每10厘米针数，Fraction，> 0
      targets       各尺码目标片幅（厘米），Fraction 列表，> 0 且单调不减
      edge          单侧边针数，int，≥ 0
      center        中央针数，int，≥ 0
      pattern_width 花样宽度（针），int，≥ 1
      tolerance     允许宽差（厘米），Fraction，≥ 0

    可行时返回：
      {"ok": True, "base", "step", "total_deviation",
       "sizes": [{"repeats", "cast_on", "width", "deviation"}, ...]}
      其中 width/deviation/total_deviation 为精确 Fraction。
    无可行组合时返回：
      {"ok": False, "base", "step", "ranges": [(lo, hi), ...],
       "fail_index", "fail_need", "fail_hi"}
      ranges 为各尺码在允许宽差内的可行重复数区间（lo > hi 表示该尺码
      单独即无可行重复数）；fail_* 描述首个无法满足的尺码：严格递增
      要求它至少取 fail_need，但允许宽差内至多为 fail_hi。
    """
    base = 2 * edge + center          # 固定针数：两侧边针 + 中央针
    step = 2 * pattern_width          # 单侧重复数每 +1，起针数增加 2×花样宽度
    n = len(targets)

    def width(r):
        """单侧重复数为 r 时的实际片幅（厘米，精确分数）。"""
        return Fraction(10 * (base + step * r), 1) / gauge

    # 各尺码在允许宽差内的可行重复数区间 [lo, hi]（含 r ≥ 1）
    ranges = []
    for t in targets:
        target_sts = t * gauge / 10               # 目标片幅换算成针数
        slack = tolerance * gauge / 10            # 允许宽差换算成针数
        lo = max(1, math.ceil((target_sts - slack - base) / step))
        hi = math.floor((target_sts + slack - base) / step)
        ranges.append((lo, hi))

    # 可行性贪心：r_i 取 max(lo_i, r_{i-1}+1)，首个越界处即失败位置
    prev = 0
    for i, (lo, hi) in enumerate(ranges):
        need = max(lo, prev + 1)
        if need > hi:
            return {
                "ok": False,
                "base": base,
                "step": step,
                "ranges": ranges,
                "fail_index": i,
                "fail_need": need,
                "fail_hi": hi,
            }
        prev = need

    # 各尺码代价最小的重复数区间 M_i = [m⁻, m⁺]（凸分段线性代价的极小点集）
    minimizers = []
    for i, t in enumerate(targets):
        lo, hi = ranges[i]
        r_star = (t * gauge / 10 - base) / step   # 实数最优点
        if r_star <= lo:
            minimizers.append((lo, lo))
        elif r_star >= hi:
            minimizers.append((hi, hi))
        else:
            minimizers.append((math.floor(r_star), math.ceil(r_star)))

    # 最优解必落在窗口内：r_i ≤ max_{j≤i}(m⁺_j + (i−j))，r_i ≥ min_{j≥i}(m⁻_j − (j−i))
    upper = []
    best = None
    for i in range(n):
        cand = minimizers[i][1]
        best = cand if best is None else max(best + 1, cand)
        upper.append(best)
    lower = [0] * n
    best = None
    for i in range(n - 1, -1, -1):
        cand = minimizers[i][0]
        best = cand if best is None else min(best - 1, cand)
        lower[i] = best

    candidates = []
    for i in range(n):
        lo = max(ranges[i][0], lower[i])
        hi = min(ranges[i][1], upper[i])
        candidates.append(list(range(lo, hi + 1)))

    def cost(i, r):
        return abs(width(r) - targets[i])

    # 动态规划：dp_i(r) = (前 i 个尺码且 r_i = r 的最小总宽差, 对应重复数组)；
    # 按 (总宽差, 重复数组) 字典序比较，同分自然取字典序最小的重复数组。
    prev_row = {}
    for r in candidates[0]:
        prev_row[r] = (cost(0, r), (r,))
    for i in range(1, n):
        prev_rs = sorted(prev_row)
        cur = {}
        best = None          # r' < r 的 (代价, 数组) 前缀最小值
        pi = 0
        for r in sorted(candidates[i]):
            while pi < len(prev_rs) and prev_rs[pi] < r:
                entry = prev_row[prev_rs[pi]]
                if best is None or entry < best:
                    best = entry
                pi += 1
            if best is None:  # 没有更小的可行前驱（不在任何最优路径上）
                continue
            cur[r] = (cost(i, r) + best[0], best[1] + (r,))
        prev_row = cur

    total, repeats = min(prev_row.values())
    sizes = []
    for i, r in enumerate(repeats):
        w = width(r)
        sizes.append({
            "repeats": r,
            "cast_on": base + step * r,
            "width": w,
            "deviation": abs(w - targets[i]),
        })
    return {
        "ok": True,
        "base": base,
        "step": step,
        "total_deviation": total,
        "sizes": sizes,
    }
