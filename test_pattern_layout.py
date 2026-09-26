import itertools
import random
import unittest
from fractions import Fraction

from pattern_layout import solve_layout


def brute_force(gauge, targets, edge, center, pattern_width, tolerance):
    """暴力枚举所有严格递增重复数组，返回 (最小总宽差, 字典序最小数组) 或 None。"""
    base = 2 * edge + center
    step = 2 * pattern_width
    n = len(targets)

    def width(r):
        return Fraction(10 * (base + step * r), 1) / gauge

    feasible = []
    for t in targets:
        # 可行重复数上界：width(r) ≤ t + tolerance → r ≤ ((t+tol)×gauge/10 − base)/step
        hi = int((t + tolerance) * gauge / 10 - base) // step + 1
        ok = [r for r in range(1, hi + 1)
              if abs(width(r) - t) <= tolerance]
        feasible.append(ok)
    best = None
    for combo in itertools.product(*feasible):
        if any(combo[i] >= combo[i + 1] for i in range(n - 1)):
            continue
        total = sum(abs(width(r) - t) for r, t in zip(combo, targets))
        key = (total, combo)
        if best is None or key < best:
            best = key
    return best


class TestSolveLayout(unittest.TestCase):
    def test_basic_three_sizes(self):
        # 密度 22 针/10cm，固定针 2*2+6=10，每档 16 针
        result = solve_layout(
            Fraction(22), [Fraction(41), Fraction(48), Fraction(55)],
            2, 6, 8, Fraction(1))
        self.assertTrue(result['ok'])
        self.assertEqual(result['base'], 10)
        self.assertEqual(result['step'], 16)
        repeats = [s['repeats'] for s in result['sizes']]
        self.assertEqual(repeats, [5, 6, 7])
        self.assertEqual([s['cast_on'] for s in result['sizes']], [90, 106, 122])
        # 实际片幅 = 起针数 × 10 ÷ 密度
        self.assertEqual(result['sizes'][0]['width'], Fraction(900, 22))
        self.assertAlmostEqual(float(result['sizes'][0]['deviation']), 0.0909, places=3)
        total = sum(s['deviation'] for s in result['sizes'])
        self.assertEqual(result['total_deviation'], total)

    def test_tie_breaks_to_lexicographically_smallest(self):
        # (2,4) 与 (3,4) 总宽差同为 9，应取字典序最小的 (2,4)
        result = solve_layout(
            Fraction(10), [Fraction(25), Fraction(36)],
            0, 0, 5, Fraction(10))
        self.assertTrue(result['ok'])
        self.assertEqual([s['repeats'] for s in result['sizes']], [2, 4])
        self.assertEqual(result['total_deviation'], 9)

    def test_repeats_at_least_one(self):
        # 目标片幅很小，最优会想用 0 次重复，但必须至少 1 次
        result = solve_layout(
            Fraction(10), [Fraction(2)], 0, 0, 5, Fraction(20))
        self.assertTrue(result['ok'])
        self.assertEqual(result['sizes'][0]['repeats'], 1)
        self.assertEqual(result['sizes'][0]['cast_on'], 10)

    def test_infeasible_single_size_empty_range(self):
        # 允许宽差太小，唯一尺码在宽差内没有任何可行重复数
        result = solve_layout(
            Fraction(10), [Fraction(25)], 0, 0, 5, Fraction(1))
        self.assertFalse(result['ok'])
        self.assertEqual(result['fail_index'], 0)
        lo, hi = result['ranges'][0]
        self.assertGreater(lo, hi)  # 空区间

    def test_infeasible_strictly_increasing_chain(self):
        # 各尺码单独可行，但严格递增无法同时满足：
        # 尺码1 只能取 2，尺码2 只能取 2~3，尺码3 只能取 3 → 需要 4
        result = solve_layout(
            Fraction(10), [Fraction(20), Fraction(25), Fraction(30)],
            0, 0, 5, Fraction(5))
        self.assertFalse(result['ok'])
        self.assertEqual(result['ranges'], [(2, 2), (2, 3), (3, 3)])
        self.assertEqual(result['fail_index'], 2)
        self.assertEqual(result['fail_need'], 4)
        self.assertEqual(result['fail_hi'], 3)

    def test_exact_width_match_with_zero_tolerance(self):
        # 宽差为 0：目标必须恰好落在针数网格上（width(r) = 5r 厘米）
        result = solve_layout(
            Fraction(20), [Fraction(10), Fraction(20)],
            0, 0, 5, Fraction(0))
        self.assertTrue(result['ok'])
        self.assertEqual([s['repeats'] for s in result['sizes']], [2, 4])
        self.assertEqual(result['total_deviation'], 0)

    def test_fractional_gauge_and_targets(self):
        # 小数密度与小数目标：全程分数运算，结果与暴力枚举一致
        gauge = Fraction(215, 10)   # 21.5 针/10cm
        targets = [Fraction(43), Fraction(485, 10), Fraction(54)]
        result = solve_layout(gauge, targets, 2, 4, 6, Fraction(15, 10))
        self.assertTrue(result['ok'])
        best = brute_force(gauge, targets, 2, 4, 6, Fraction(15, 10))
        self.assertIsNotNone(best)
        self.assertEqual(result['total_deviation'], best[0])
        self.assertEqual(tuple(s['repeats'] for s in result['sizes']), best[1])

    def test_random_against_brute_force(self):
        # 随机小参数与暴力枚举对照：总宽差与重复数组都必须一致
        rng = random.Random(20260925)
        for _ in range(300):
            n = rng.randint(1, 4)
            gauge = Fraction(rng.randint(10, 30))
            start = rng.randint(10, 40)
            gap = rng.randint(1, 15)
            targets = [Fraction(start + gap * i) for i in range(n)]
            edge = rng.randint(0, 3)
            center = rng.randint(0, 12)
            width = rng.randint(2, 8)
            tolerance = Fraction(rng.randint(0, 6))
            result = solve_layout(
                gauge, targets, edge, center, width, tolerance)
            best = brute_force(
                gauge, targets, edge, center, width, tolerance)
            if best is None:
                self.assertFalse(result['ok'], msg=(
                    '参数 n={} gauge={} targets={} edge={} center={} '
                    'width={} tol={}'.format(
                        n, gauge, targets, edge, center, width, tolerance)))
            else:
                self.assertTrue(result['ok'], msg=(
                    '参数 n={} gauge={} targets={} edge={} center={} '
                    'width={} tol={}'.format(
                        n, gauge, targets, edge, center, width, tolerance)))
                got = tuple(s['repeats'] for s in result['sizes'])
                self.assertEqual(result['total_deviation'], best[0])
                self.assertEqual(got, best[1])
                # 每个尺码都在允许宽差内且严格递增
                for s, t in zip(result['sizes'], targets):
                    self.assertLessEqual(s['deviation'], tolerance)
                self.assertTrue(all(got[i] < got[i + 1]
                                    for i in range(n - 1)))


if __name__ == '__main__':
    unittest.main()
