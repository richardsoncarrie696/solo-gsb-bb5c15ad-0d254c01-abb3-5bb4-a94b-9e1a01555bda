"""对称减针行程：逐行安排左右相同的减针数，使末行余针恰好等于目标针数。

模型（代价与比较全程用 Fraction 精确计算，不用浮点）：
  共需减针 D = 起针数 − 目标针数（双侧合计）。左右对称减针每次共减偶数
  针，故 D 必须为非负偶数。第 i 行单侧减 a_i 针（0 ≤ a_i ≤ 单侧上限），
  a_i = 0 为平织行，a_i ≥ 1 为减针行；减针行之间至少隔一行平织，即任意
  相邻两行不能都是减针行（首行可以是减针行）。末行余针须等于目标针数，
  即单侧累计 Σa_i = D/2。
  第 i 行末的线性目标进度为 D×i/总行数（双侧累计应减针数），优化目标为
  最小化 Σ_i (第 i 行末累计减针数 − D×i/总行数)²；同分取逐行单侧减针
  数组 (a_1, …, a_总行数) 字典序最小的方案。

求解用动态规划：g[i][j][p] 表示安排第 i..N 行时，进入第 i 行前已累计
单侧减针 j、第 i−1 行是减针行当且仅当 p=1，最终单侧累计恰好 D/2 的
最小剩余平方偏差和（不可行为 None）。自末行向首行递推得到最优总代价
后，再从首行正向贪心回溯：每行从小到大尝试 a，取第一个能让“已确定
前缀的代价 + 本行偏差 + g[i+1] 最小剩余”等于最优总代价的值——前缀
逐位最小即保证整个逐行单侧减针数组字典序最小。

可行性：N 行中互不相邻的减针行至多 ⌈N/2⌉ 个（第 1,3,5,… 行），每行
单侧至多减上限针，故单侧至多可减 ⌈N/2⌉×上限 针（双侧 ×2）。D/2 不
超过该值时必有可行方案（把减针行放在第 1,3,5,… 行、每行尽量填满即
可），否则无解；无解时由调用方说明最多可减针数及原因。
"""

from fractions import Fraction


def solve_shaping(cast_on, target, rows, max_decrease):
    """求解对称减针行程。

    参数（调用方已完成校验）：
      cast_on      起针数，int，≥ 1
      target       目标针数（末行余针），int，≥ 1
      rows         总行数，int，≥ 1
      max_decrease 每个减针行单侧最多减针数，int，1 或 2

    可行时返回：
      {"ok": True, "total_decrease", "per_side", "decrease_rows",
       "cost", "plan": [{"row", "left", "right", "decrease",
                          "decreased", "remaining", "progress"}, ...]}
      cost 为最小平方偏差和（精确 Fraction）；plan 逐行给出左右减针数、
      本行共减、截至本行累计减针（双侧）、行末余针与该行末的线性目标
      进度（progress 为精确 Fraction）。
    无解时返回：
      {"ok": False, "reason", "total_decrease", "max_decrease_rows",
       "max_total_decrease"}
      reason ∈ {"target_exceeds", "odd_decrease", "insufficient_rows"}；
      max_total_decrease 为约束下最多可减针数（双侧合计），
      max_decrease_rows 为最多减针行数。
    """
    total = cast_on - target                  # 需减总针数（双侧合计）
    max_rows = (rows + 1) // 2                # 最多减针行数（第 1,3,5,… 行）
    max_total = 2 * max_decrease * max_rows   # 最多可减针数（双侧合计）

    infeasible = {
        "ok": False,
        "total_decrease": total,
        "max_decrease_rows": max_rows,
        "max_total_decrease": max_total,
    }
    if total < 0:
        # 目标针数比起针数多：本模块只安排减针，无法加针
        return dict(infeasible, reason="target_exceeds")
    if total % 2:
        # 左右对称减针每次共减偶数针，奇数差无法恰好达到
        return dict(infeasible, reason="odd_decrease")
    per_side = total // 2
    if per_side > max_decrease * max_rows:
        # 行数不够（或每行减针上限太低）：减满所有可用的减针行也不够
        return dict(infeasible, reason="insufficient_rows")

    # 反向动态规划：table[i][j][p] 即 g[i][j][p]（1 ≤ i ≤ rows+1）。
    # 每行偏差 (2·j − D·i/rows)² 的分母都是 rows²，表内只存分子（整数），
    # 比较与求和完全等价且保持精确，避免逐状态构造 Fraction。
    # 边界：第 rows+1 行（全部行已排完），单侧累计恰为 per_side 时剩余代价 0
    g_next = [[0 if j == per_side else None for _p in (0, 1)]
              for j in range(per_side + 1)]
    table = [None] * (rows + 2)
    table[rows + 1] = g_next
    for i in range(rows, 0, -1):
        base = total * i                      # 目标进度 D·i/rows 的分子部分
        g_i = [[None, None] for _ in range(per_side + 1)]
        for j in range(per_side + 1):
            for p in (0, 1):
                best = None
                for a in range(max_decrease + 1):
                    if a and p:
                        continue              # 减针行之间至少隔一行平织
                    j2 = j + a
                    if j2 > per_side:
                        break                 # 累计减针不能超过总需求
                    tail = g_next[j2][1 if a else 0]
                    if tail is None:
                        continue
                    dev = 2 * j2 * rows - base  # 本行偏差（分子）
                    cost = dev * dev + tail
                    if best is None or cost < best:
                        best = cost
                g_i[j][p] = best
        table[i] = g_i
        g_next = g_i

    optimal_num = table[1][0][0]
    # per_side ≤ max_decrease × max_rows 时必有可行方案，optimal_num 必非 None
    optimal = Fraction(optimal_num, rows * rows)

    # 正向贪心回溯：逐行取最小的 a，使“前缀代价 + 本行偏差 + 最小剩余”
    # 恰等于最优总代价（均按分子比较），得到的逐行单侧减针数组字典序最小
    side = []
    j = 0          # 已排各行的单侧累计减针
    p = 0          # 上一行是否减针行（首行之前视为平织）
    prefix = 0
    for i in range(1, rows + 1):
        base = total * i
        for a in range(max_decrease + 1):
            if a and p:
                continue
            j2 = j + a
            if j2 > per_side:
                break
            tail = table[i + 1][j2][1 if a else 0]
            if tail is None:
                continue
            dev = 2 * j2 * rows - base
            if prefix + dev * dev + tail == optimal_num:
                side.append(a)
                prefix += dev * dev
                j = j2
                p = 1 if a else 0
                break

    plan = []
    decreased = 0   # 截至本行的累计减针（双侧合计）
    for i, a in enumerate(side, 1):
        decreased += 2 * a
        plan.append({
            "row": i,
            "left": a,
            "right": a,
            "decrease": 2 * a,
            "decreased": decreased,
            "remaining": cast_on - decreased,
            "progress": Fraction(total * i, rows),
        })
    return {
        "ok": True,
        "total_decrease": total,
        "per_side": per_side,
        "decrease_rows": sum(1 for a in side if a),
        "cost": optimal,
        "plan": plan,
    }
