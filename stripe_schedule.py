"""条纹用线排程：把总行数恰好分成连续的异色条纹段，最小化段长与偏好段长的
绝对差之和。

模型（代价与比较全程用整数/分数精确计算，不用浮点）：
  N 行由若干连续条纹段组成，第 i 段记为 (c_i, l_i)：c_i 为颜色（按输入顺序
  用下标 0,1,… 区分，共 2~3 种），l_i 为该段行数且
  最短 ≤ l_i ≤ 最长（均在 1~6 之间）。相邻段必须异色 c_i ≠ c_{i-1}；每种
  颜色各段行数之和不得超过它的库存（可编织行数）。所有段长度之和须恰好等于
  总行数 N。优化目标为最小化 Σ_i |l_i − P|（P 为偏好段长）；同分（绝对差
  之和相同）时按段序列 ((c_1,l_1),(c_2,l_2),…) 的字典序取最小：先比颜色
  输入顺序（颜色下标小者优先），颜色相同再比段长（短者优先）。

求解用记忆化动态规划：状态 (last, usages) 中 last 为上一段颜色（首段之前
为 −1）、usages 为各色截至当前的累计用量元组；已排行数 pos = Σusages 可
直接推出，无需单独成维。best(last, usages) 为从该状态出发恰好排满 N 行的
最小剩余绝对差之和，不可行为 None。偏好段长写作最简分数 P = p/q 后，每段
长度 l 的代价 |l−P| = |l·q−p|/q 与总代价分母恒为 q，故 DP 表内只存分子
（非负整数），比较与求和完全等价且避免逐状态构造 Fraction；最终总代价再
除以 q 得到精确 Fraction。得到最优总代价后自第 1 段正向贪心回溯：颜色按
下标升序、段长由短到长逐一尝试，取第一个让“本段代价 + 下一状态最优剩余”
恰等于当前最优剩余的 (c, l)——前缀逐位最小即保证整条段序列在同分方案中
字典序最小。

无解诊断（均不返回部分安排）：
  length_range    不存在整数段数 k 使 k×最短 ≤ N ≤ k×最长；
  stock_shortage  各色库存合计少于 N；
  no_exact_cover  以上均通过但 DP 无完整方案（相邻异色与各色库存共同限制），
                  另由 cover(...) 求出约束下最多可连续覆盖的行数 max_cover。
"""

from fractions import Fraction
from functools import lru_cache


def solve_stripes(total_rows, stocks, min_len, max_len, preferred):
    """求解条纹用线排程。

    参数（调用方已完成校验）：
      total_rows 总行数，int，1~40
      stocks     各色可编织行数（库存），list[int]（按颜色输入顺序，长度 2~3）
      min_len    最短条纹行数，int，1~6
      max_len    最长条纹行数，int，min_len ≤ max_len ≤ 6
      preferred  偏好段长，Fraction，大于 0

    可行时返回：
      {"ok": True, "cost", "segment_count", "total_stock",
       "segments": [{"index", "color_index", "length", "start", "end"}, ...],
       "used": [各色已用行数], "remaining": [各色余量]}
      cost 为最小绝对差之和（精确 Fraction）；segments 按编织顺序给出每段
      颜色下标、段长与起止行（行号 1 起，两端都包含）。
    无解时返回：
      {"ok": False, "reason", "total_stock", ...诊断字段}
      reason ∈ {"length_range", "stock_shortage", "no_exact_cover"}；
      length_range 另带 segment_count_min/segment_count_max，
      no_exact_cover 另带 max_cover（约束下最多可连续覆盖的行数）。
    """
    num_colors = len(stocks)
    total_stock = sum(stocks)
    infeasible = {"ok": False, "total_stock": total_stock}

    # 不考虑颜色与库存：k 段能覆盖的总行数区间为 [k×min_len, k×max_len]
    count_min = -(-total_rows // max_len)   # ceil(N / max_len)
    count_max = total_rows // min_len       # floor(N / min_len)
    if count_min > count_max:
        return dict(infeasible, reason="length_range",
                    segment_count_min=count_min,
                    segment_count_max=count_max)
    if total_stock < total_rows:
        return dict(infeasible, reason="stock_shortage")

    zeros = tuple(0 for _ in range(num_colors))
    # P = p/q（最简分数）：单段代价 |l - P| = |l·q - p|/q，分母恒为 q，
    # DP 表内只存分子 num_costs[l] = |l·q - p|（整数）
    pref_num, pref_den = preferred.numerator, preferred.denominator
    num_costs = [abs(length * pref_den - pref_num)
                 for length in range(max_len + 1)]

    def _next_usages(usages, color, used_after):
        """把 usages 中第 color 种颜色的累计用量改为 used_after，返回新元组。"""
        return usages[:color] + (used_after,) + usages[color + 1:]

    @lru_cache(maxsize=None)
    def best(last_color, usages):
        """状态 (last_color, usages) 出发恰好排满 N 行的最小剩余代价分子。

        pos = 各色累计用量之和，不必再作为一维状态；不可行返回 None。
        """
        pos = sum(usages)
        if pos == total_rows:
            return 0
        best_num = None
        for color in range(num_colors):
            if color == last_color:
                continue                  # 相邻段必须异色
            used = usages[color]
            for length in range(min_len, max_len + 1):
                next_pos = pos + length
                if next_pos > total_rows:
                    break                 # length 递增，更长的段更放不下
                used_after = used + length
                if used_after > stocks[color]:
                    break                 # 库存只会更超，无需试更长的段
                tail_num = best(color, _next_usages(usages, color, used_after))
                if tail_num is None:
                    continue
                num = num_costs[length] + tail_num
                if best_num is None or num < best_num:
                    best_num = num
        return best_num

    optimal_num = best(-1, zeros)
    if optimal_num is None:
        @lru_cache(maxsize=None)
        def cover(last_color, usages):
            """该状态出发能到达的最大已排行数（不要求恰好等于 N）。"""
            pos = sum(usages)
            farthest = pos
            for color in range(num_colors):
                if color == last_color:
                    continue
                used = usages[color]
                for length in range(min_len, max_len + 1):
                    next_pos = pos + length
                    used_after = used + length
                    if next_pos > total_rows or used_after > stocks[color]:
                        break
                    reached = cover(color, _next_usages(usages, color, used_after))
                    if reached > farthest:
                        farthest = reached
            return farthest

        return dict(infeasible, reason="no_exact_cover",
                    max_cover=cover(-1, zeros))

    # 正向贪心回溯：颜色下标升序、段长升序，逐位取能达成最优代价的最小组合
    segments = []
    pos = 0
    last_color = -1
    usages = zeros
    remaining_num = optimal_num
    while pos < total_rows:
        picked = False
        for color in range(num_colors):
            if color == last_color:
                continue
            used = usages[color]
            for length in range(min_len, max_len + 1):
                next_pos = pos + length
                used_after = used + length
                if next_pos > total_rows or used_after > stocks[color]:
                    break
                next_usages = _next_usages(usages, color, used_after)
                tail_num = best(color, next_usages)
                if tail_num is not None and num_costs[length] + tail_num == remaining_num:
                    segments.append({"color_index": color, "length": length})
                    pos, last_color, usages = next_pos, color, next_usages
                    remaining_num -= num_costs[length]
                    picked = True
                    break
            if picked:
                break
        if not picked:  # pragma: no cover - 最优解存在时理论上不可能发生
            raise RuntimeError("条纹排程回溯失败")

    used_counts = [0] * num_colors
    cursor = 0
    for index, segment in enumerate(segments, 1):
        start = cursor + 1
        end = cursor + segment["length"]
        segment["index"] = index
        segment["start"] = start
        segment["end"] = end
        cursor = end
        used_counts[segment["color_index"]] += segment["length"]

    return {
        "ok": True,
        "cost": Fraction(optimal_num, pref_den),
        "segment_count": len(segments),
        "total_stock": total_stock,
        "segments": segments,
        "used": used_counts,
        "remaining": [stocks[i] - used_counts[i] for i in range(num_colors)],
    }
