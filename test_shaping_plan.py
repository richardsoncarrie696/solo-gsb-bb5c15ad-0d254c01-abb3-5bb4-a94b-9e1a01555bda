import itertools
import random
import unittest
from fractions import Fraction

from shaping_plan import solve_shaping


def brute_force(cast_on, target, rows, max_decrease):
    """暴力枚举所有满足约束的逐行单侧减针数组，返回 (最小代价, 字典序最小数组) 或 None。"""
    total = cast_on - target
    if total < 0 or total % 2:
        return None
    per_side = total // 2
    best = None
    for combo in itertools.product(range(max_decrease + 1), repeat=rows):
        if sum(combo) != per_side:
            continue
        # 减针行之间至少隔一行平织：相邻两行不能都是减针行
        if any(combo[i] and combo[i + 1] for i in range(rows - 1)):
            continue
        cost = Fraction(0)
        cum = 0
        for i, a in enumerate(combo, 1):
            cum += 2 * a
            dev = cum - Fraction(total * i, rows)
            cost += dev * dev
        key = (cost, combo)
        if best is None or key < best:
            best = key
    return best


def side_array(result):
    """从求解结果的 plan 中取出逐行单侧减针数组。"""
    return tuple(row['left'] for row in result['plan'])


class TestSolveShaping(unittest.TestCase):
    def test_basic_tie_breaks_to_lexicographically_smallest(self):
        # 12→8 共减 4 针（单侧 2），4 行、单侧上限 2：
        # [1,0,1,0]、[1,0,0,1]、[0,1,0,1] 代价同为 2，取字典序最小的 [0,1,0,1]
        result = solve_shaping(12, 8, 4, 2)
        self.assertTrue(result['ok'])
        self.assertEqual(result['total_decrease'], 4)
        self.assertEqual(result['per_side'], 2)
        self.assertEqual(side_array(result), (0, 1, 0, 1))
        self.assertEqual(result['cost'], 2)
        self.assertEqual([r['remaining'] for r in result['plan']], [12, 10, 10, 8])
        self.assertEqual(result['decrease_rows'], 2)

    def test_forced_unique_solution(self):
        # 10→4 共减 6 针（单侧 3），5 行、单侧上限 1：最多 3 个减针行，
        # 只能放在第 1、3、5 行，每行单侧减 1
        result = solve_shaping(10, 4, 5, 1)
        self.assertTrue(result['ok'])
        self.assertEqual(side_array(result), (1, 0, 1, 0, 1))
        # 双侧累计 (2,2,4,4,6)，目标进度 (6/5,12/5,18/5,24/5,6)
        self.assertEqual(result['cost'], Fraction(8, 5))
        self.assertEqual([r['remaining'] for r in result['plan']],
                         [8, 8, 6, 6, 4])

    def test_single_decrease_row_tie(self):
        # 6→4 共减 2 针（单侧 1），4 行、单侧上限 1：
        # 减针行在第 2 或第 3 行时代价同为 3/2，取字典序最小的 [0,0,1,0]
        result = solve_shaping(6, 4, 4, 1)
        self.assertTrue(result['ok'])
        self.assertEqual(side_array(result), (0, 0, 1, 0))
        self.assertEqual(result['cost'], Fraction(3, 2))

    def test_no_decrease_needed(self):
        # 目标针数等于起针数：全部平织，代价为 0
        result = solve_shaping(20, 20, 6, 2)
        self.assertTrue(result['ok'])
        self.assertEqual(result['total_decrease'], 0)
        self.assertEqual(side_array(result), (0, 0, 0, 0, 0, 0))
        self.assertEqual(result['cost'], 0)
        self.assertEqual(result['decrease_rows'], 0)
        self.assertEqual(result['plan'][-1]['remaining'], 20)

    def test_single_row(self):
        # 1 行内单侧减 2（左右共 4 针）
        result = solve_shaping(10, 6, 1, 2)
        self.assertTrue(result['ok'])
        self.assertEqual(side_array(result), (2,))
        self.assertEqual(result['plan'][0]['remaining'], 6)

    def test_infeasible_target_exceeds(self):
        result = solve_shaping(10, 12, 5, 2)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'target_exceeds')
        self.assertEqual(result['total_decrease'], -2)

    def test_infeasible_odd_decrease(self):
        # 左右对称减针每次共减偶数针，奇数差无法恰好达到
        result = solve_shaping(10, 5, 5, 2)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'odd_decrease')
        self.assertEqual(result['total_decrease'], 5)

    def test_infeasible_insufficient_rows(self):
        # 20→4 共减 16 针（单侧 8），3 行、单侧上限 1：
        # 最多 2 个减针行、单侧最多减 2 针（双侧 4 针），不够
        result = solve_shaping(20, 4, 3, 1)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'insufficient_rows')
        self.assertEqual(result['max_decrease_rows'], 2)
        self.assertEqual(result['max_total_decrease'], 4)

    def test_max_total_decrease_uses_ceil_half_rows(self):
        # 偶数行：减针行最多 rows/2 个；奇数行：(rows+1)/2 个
        even = solve_shaping(100, 1, 4, 2)
        self.assertEqual(even['max_decrease_rows'], 2)
        self.assertEqual(even['max_total_decrease'], 8)
        odd = solve_shaping(100, 1, 5, 2)
        self.assertEqual(odd['max_decrease_rows'], 3)
        self.assertEqual(odd['max_total_decrease'], 12)

    def test_plan_invariants(self):
        # 一般参数：左右相同、减针行不相邻、末行余针等于目标针数
        result = solve_shaping(70, 40, 15, 2)
        self.assertTrue(result['ok'])
        plan = result['plan']
        self.assertEqual(len(plan), 15)
        for row in plan:
            self.assertEqual(row['left'], row['right'])
            self.assertEqual(row['decrease'], row['left'] + row['right'])
            self.assertIn(row['left'], (0, 1, 2))
        for i in range(len(plan) - 1):
            self.assertFalse(plan[i]['decrease'] and plan[i + 1]['decrease'],
                             msg='第 {}、{} 行相邻却都是减针行'.format(i + 1, i + 2))
        self.assertEqual(plan[-1]['remaining'], 40)
        self.assertEqual(plan[-1]['decreased'], 30)
        # 累计减针与余针自洽
        for row in plan:
            self.assertEqual(row['remaining'], 70 - row['decreased'])

    def test_random_against_brute_force(self):
        # 随机小参数与暴力枚举对照：代价与逐行单侧减针数组都必须一致
        rng = random.Random(20260925)
        for _ in range(300):
            cast_on = rng.randint(1, 24)
            target = rng.randint(1, 24)
            rows = rng.randint(1, 7)
            max_decrease = rng.randint(1, 2)
            result = solve_shaping(cast_on, target, rows, max_decrease)
            best = brute_force(cast_on, target, rows, max_decrease)
            msg = '参数 cast_on={} target={} rows={} max={}'.format(
                cast_on, target, rows, max_decrease)
            if best is None:
                self.assertFalse(result['ok'], msg=msg)
            else:
                self.assertTrue(result['ok'], msg=msg)
                self.assertEqual(result['cost'], best[0], msg=msg)
                self.assertEqual(side_array(result), best[1], msg=msg)


if __name__ == '__main__':
    unittest.main()
