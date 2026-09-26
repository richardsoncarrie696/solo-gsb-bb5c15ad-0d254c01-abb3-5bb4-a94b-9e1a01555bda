import unittest

from app import app


class TestValidateApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def post(self, cast_on, pattern):
        return self.client.post('/api/validate', json={
            'cast_on': cast_on,
            'pattern': pattern,
        }).get_json()

    def test_all_valid(self):
        data = self.post(12, '(k2tog yo)*6\np*12\n(k2tog)*6\n(yo k2tog)*3\nk*6')
        self.assertTrue(data['ok'])
        self.assertIsNone(data['error'])
        self.assertEqual(len(data['rows']), 5)
        self.assertEqual(data['rows'][0]['in'], 12)
        self.assertEqual(data['rows'][0]['consume'], 12)
        self.assertEqual(data['rows'][0]['out'], 12)
        self.assertEqual(data['rows'][2]['out'], 6)
        self.assertEqual(data['final'], 6)

    def test_count_shortfall(self):
        # 第 2 行需要 13 针，但只有 12 针，缺 1 针
        data = self.post(12, 'k*12\nk*13\nk*12')
        self.assertFalse(data['ok'])
        self.assertEqual(len(data['rows']), 1)  # 错误行及之后不再推算
        err = data['error']
        self.assertEqual(err['type'], 'count')
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['diff'], 1)

    def test_count_leftover(self):
        # 第 2 行只消耗 10 针，剩余 2 针未使用
        data = self.post(12, 'k*12\nk*10')
        self.assertFalse(data['ok'])
        err = data['error']
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['diff'], -2)

    def test_parse_error_stops(self):
        data = self.post(4, 'k*4\nssk\nk*4')
        self.assertFalse(data['ok'])
        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(data['error']['type'], 'parse')
        self.assertEqual(data['error']['line'], 2)

    def test_blank_lines_skipped_but_line_numbers_kept(self):
        data = self.post(2, 'k*2\n\nk*3')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['line'], 3)

    def test_bad_cast_on(self):
        for bad in [0, -3, 'abc', '2.5', None, True]:
            data = self.post(bad, 'k*2')
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'cast_on')

    def test_string_cast_on_accepted(self):
        data = self.post('4', 'k*4')
        self.assertTrue(data['ok'])
        self.assertEqual(data['final'], 4)

    def test_single_size_rejects_multi_size_repeat(self):
        # 单尺码接口下 *{a|b} 项数（2）与尺码数（1）不符
        data = self.post(4, 'k*{2|2}')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'parse')
        self.assertIn('项数不符', data['error']['message'])


class TestValidateSizesApi(unittest.TestCase):
    SIZES = [{'name': 'S', 'cast_on': 12},
             {'name': 'M', 'cast_on': 16},
             {'name': 'L', 'cast_on': 20}]

    def setUp(self):
        self.client = app.test_client()

    def post(self, sizes, pattern, yarn=None):
        payload = {'sizes': sizes, 'pattern': pattern}
        if yarn is not None:
            payload['yarn'] = yarn
        return self.client.post('/api/validate-sizes', json=payload).get_json()

    def test_all_valid(self):
        pattern = '\n'.join([
            '(k2tog yo)*{6|8|10}',
            'p*{12|16|20}',
            '(k2tog)*{6|8|10}',
            '(k2tog)*{3|4|5}',
            'k*{3|4|5}',
        ])
        data = self.post(self.SIZES, pattern)
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['sizes']), 3)
        self.assertEqual([s['name'] for s in data['sizes']], ['S', 'M', 'L'])
        self.assertEqual([s['final'] for s in data['sizes']], [3, 4, 5])
        for s in data['sizes']:
            self.assertTrue(s['ok'])
            self.assertIsNone(s['error'])
            self.assertEqual(len(s['rows']), 5)
        self.assertEqual(data['sizes'][0]['rows'][0]['in'], 12)
        self.assertEqual(data['sizes'][1]['rows'][0]['consume'], 16)
        self.assertEqual(data['sizes'][2]['rows'][2]['out'], 10)

    def test_plain_repeat_applies_to_every_size(self):
        sizes = [{'name': 'A', 'cast_on': 4}, {'name': 'B', 'cast_on': 4}]
        data = self.post(sizes, '(k2tog yo)*2\np*4')
        self.assertTrue(data['ok'])
        self.assertEqual([s['final'] for s in data['sizes']], [4, 4])

    def test_failing_size_stops_independently(self):
        # 第 2 行 M 差 1 针：仅 M 停止，S/L 继续推算到结束
        sizes = [{'name': 'S', 'cast_on': 4},
                 {'name': 'M', 'cast_on': 6},
                 {'name': 'L', 'cast_on': 8}]
        pattern = 'k*{4|6|8}\n(k yo)*{4|5|8}\nk*{8|1|16}'
        data = self.post(sizes, pattern)
        self.assertFalse(data['ok'])
        s, m, l = data['sizes']
        self.assertTrue(s['ok'])
        self.assertEqual(len(s['rows']), 3)
        self.assertEqual(s['final'], 8)
        self.assertFalse(m['ok'])
        self.assertEqual(m['error']['type'], 'count')
        self.assertEqual(m['error']['line'], 2)
        self.assertEqual(m['error']['diff'], -1)
        self.assertEqual(len(m['rows']), 1)  # 错误行及之后不再推算
        self.assertEqual(m['final'], 6)       # 最后有效行之后的针数
        self.assertTrue(l['ok'])
        self.assertEqual(len(l['rows']), 3)
        self.assertEqual(l['final'], 16)

    def test_parse_error_stops_all_sizes(self):
        data = self.post(self.SIZES, 'k*{12|16|20}\nssk\nk*1')
        self.assertFalse(data['ok'])
        for s in data['sizes']:
            self.assertFalse(s['ok'])
            self.assertEqual(s['error']['type'], 'parse')
            self.assertEqual(s['error']['line'], 2)
            self.assertEqual(len(s['rows']), 1)

    def test_size_count_mismatch_reports_line_and_char(self):
        data = self.post(self.SIZES, 'k*{12|16|20}\np*{6|8}')
        self.assertFalse(data['ok'])
        err = data['sizes'][0]['error']
        self.assertEqual(err['type'], 'parse')
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['char'], 2)  # '*' 是第 2 个字符
        self.assertIn('项数不符', err['message'])

    def test_bad_multiplier_reports_line_and_char(self):
        data = self.post(self.SIZES, 'k*{12|16|20}\n(p)*0')
        err = data['sizes'][0]['error']
        self.assertEqual(err['type'], 'parse')
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['char'], 5)  # '0' 是第 5 个字符

    def test_blank_lines_skipped_but_line_numbers_kept(self):
        data = self.post(self.SIZES, 'k*{12|16|20}\n\nssk')
        self.assertFalse(data['ok'])
        self.assertEqual(data['sizes'][0]['error']['line'], 3)

    def test_bad_sizes(self):
        for bad in [None, [], 'S', [{}], [{'name': '', 'cast_on': 4}],
                    [{'name': 'S'}], [{'name': 'S', 'cast_on': 0}],
                    [{'name': 'S', 'cast_on': True}],
                    [{'name': 'S', 'cast_on': 'x'}]]:
            data = self.post(bad, 'k*4')
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'sizes')
            self.assertEqual(data['sizes'], [])

    def test_string_cast_on_accepted(self):
        data = self.post([{'name': 'S', 'cast_on': '4'}], 'k*4')
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['final'], 4)

    YARN = {'k': 0.5, 'p': 0.5, 'yo': 0.2, 'k2tog': 1.0,
            'waste_percent': 10, 'grams_per_ball': 50}

    def test_yarn_weights_per_row_cumulative(self):
        # S(12)：行1 k2tog*6+yo*6 = 6*1.0+6*0.2 = 7.2
        # 行2 p*12 = 6.0，累计 13.2
        # 行3 k2tog*6 = 6.0，累计 19.2
        pattern = '\n'.join([
            '(k2tog yo)*{6|8|10}',
            'p*{12|16|20}',
            '(k2tog)*{6|8|10}',
        ])
        data = self.post(self.SIZES, pattern, self.YARN)
        self.assertTrue(data['ok'])
        s = data['sizes'][0]
        self.assertEqual([r['weight'] for r in s['rows']], [7.2, 13.2, 19.2])
        yarn = s['yarn']
        self.assertFalse(yarn['partial'])
        self.assertTrue(yarn['complete'])
        self.assertEqual(yarn['raw_total'], 19.2)
        self.assertEqual(yarn['with_waste'], 21.12)
        self.assertEqual(yarn['balls'], 1)  # ceil(21.12/50) = 1

    def test_yarn_nested_and_size_repeats(self):
        # 记号次数按尺码分别累计：
        # S: k2tog=6 yo=6 p=12 k2tog=6 -> 6+1.2+6+6 = 19.2
        # M: k2tog=8 yo=8 p=16 k2tog=8 -> 8+1.6+8+8 = 25.6
        # L: k2tog=10 yo=10 p=20 k2tog=10 -> 10+2+10+10 = 32
        pattern = '\n'.join([
            '(k2tog yo)*{6|8|10}',
            'p*{12|16|20}',
            '(k2tog)*{6|8|10}',
        ])
        data = self.post(self.SIZES, pattern, self.YARN)
        raw = [s['yarn']['raw_total'] for s in data['sizes']]
        self.assertEqual(raw, [19.2, 25.6, 32])
        with_waste = [s['yarn']['with_waste'] for s in data['sizes']]
        self.assertEqual(with_waste, [21.12, 28.16, 35.2])
        # 每团 50g：S/M 各 1 团，L 也是 1 团（35.2 < 50）
        self.assertEqual([s['yarn']['balls'] for s in data['sizes']], [1, 1, 1])

    def test_yarn_balls_rounded_up(self):
        # S 含损耗 14.52g，每团 7g -> ceil(2.074) = 3 团
        pattern = '(k2tog yo)*{6|8|10}\np*{12|16|20}'
        yarn = dict(self.YARN, grams_per_ball=7)
        data = self.post(self.SIZES, pattern, yarn)
        s = data['sizes'][0]
        self.assertEqual(s['yarn']['raw_total'], 13.2)
        self.assertEqual(s['yarn']['with_waste'], 14.52)
        self.assertEqual(s['yarn']['balls'], 3)

    def test_yarn_exact_multiple_does_not_round_up_extra(self):
        # 一行 k2tog*10 原始 10g，损耗 0%，每团 5g -> 恰好 2 团而非 3 团
        sizes = [{'name': 'S', 'cast_on': 20}]
        yarn = {'k': 0, 'p': 0, 'yo': 0, 'k2tog': 1.0,
                'waste_percent': 0, 'grams_per_ball': 5}
        data = self.post(sizes, 'k2tog*10', yarn)
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['yarn']['balls'], 2)

    def test_yarn_tiny_excess_still_rounds_up_extra_ball(self):
        # 一行 k：每针 1.0000000001g、每团 1g、损耗 0 -> 用量 1.0000000001g
        # 严格向上取整应为 2 团（逐行与汇总克重显示仍为 1.00g）
        sizes = [{'name': 'S', 'cast_on': 1}]
        yarn = {'k': 1.0000000001, 'p': 0, 'yo': 0, 'k2tog': 0,
                'waste_percent': 0, 'grams_per_ball': 1}
        data = self.post(sizes, 'k*1', yarn)
        self.assertTrue(data['ok'])
        s = data['sizes'][0]
        self.assertEqual(s['rows'][0]['weight'], 1.0)
        self.assertEqual(s['yarn']['raw_total'], 1.0)
        self.assertEqual(s['yarn']['with_waste'], 1.0)
        self.assertEqual(s['yarn']['balls'], 2)

    def test_yarn_tiny_excess_from_numeric_string(self):
        # 高精度小数字符串同样按十进制字面精确处理：1.0001g、每团 1g -> 2 团
        sizes = [{'name': 'S', 'cast_on': 1}]
        yarn = {'k': '1.0001', 'p': '0', 'yo': '0', 'k2tog': '0',
                'waste_percent': '0', 'grams_per_ball': '1'}
        data = self.post(sizes, 'k*1', yarn)
        self.assertTrue(data['ok'])
        s = data['sizes'][0]
        self.assertEqual(s['yarn']['raw_total'], 1.0)
        self.assertEqual(s['yarn']['balls'], 2)

    def test_yarn_waste_tiny_excess_rounds_up(self):
        # 每团 1g、损耗 10%：0.92g ×1.1 = 1.012g -> 2 团
        sizes = [{'name': 'S', 'cast_on': 1}]
        yarn = {'k': 0.92, 'p': 0, 'yo': 0, 'k2tog': 0,
                'waste_percent': 10, 'grams_per_ball': 1}
        data = self.post(sizes, 'k*1', yarn)
        self.assertTrue(data['ok'])
        s = data['sizes'][0]
        self.assertEqual(s['yarn']['raw_total'], 0.92)
        self.assertEqual(s['yarn']['with_waste'], 1.01)
        self.assertEqual(s['yarn']['balls'], 2)

    def test_yarn_accumulation_keeps_full_decimal_precision(self):
        # 3 行各 1 针、每针 0.1g：累计 0.30g，每团 0.3g 恰好 1 团
        # （浮点实现会算成 0.30000000000000004 而多算一团）
        # 起针 1，每行 k 消耗 1 产出 1，三行都平衡
        sizes = [{'name': 'S', 'cast_on': 1}]
        yarn = {'k': 0.1, 'p': 0, 'yo': 0, 'k2tog': 0,
                'waste_percent': 0, 'grams_per_ball': 0.3}
        data = self.post(sizes, 'k\nk\nk', yarn)
        self.assertTrue(data['ok'])
        s = data['sizes'][0]
        self.assertEqual([r['weight'] for r in s['rows']], [0.1, 0.2, 0.3])
        self.assertEqual(s['yarn']['raw_total'], 0.3)
        self.assertEqual(s['yarn']['with_waste'], 0.3)
        self.assertEqual(s['yarn']['balls'], 1)

    def test_yarn_half_cent_rounds_up_only_in_display(self):
        # 原始 0.125g 显示为 0.13g（四舍五入两位小数）；但线团数按未舍入值：
        # 每团 0.125g 恰好 1 团，而非按显示的 0.13g 推算
        sizes = [{'name': 'S', 'cast_on': 1}]
        yarn = {'k': '0.125', 'p': '0', 'yo': '0', 'k2tog': '0',
                'waste_percent': '0', 'grams_per_ball': '0.125'}
        data = self.post(sizes, 'k*1', yarn)
        self.assertTrue(data['ok'])
        s = data['sizes'][0]
        self.assertEqual(s['rows'][0]['weight'], 0.13)
        self.assertEqual(s['yarn']['raw_total'], 0.13)
        self.assertEqual(s['yarn']['balls'], 1)

    def test_yarn_count_error_marks_partial_for_that_size(self):
        # 第 2 行 M 差 1 针：M 停止，用量仅含第 1 行且 partial；S/L 完整
        sizes = [{'name': 'S', 'cast_on': 4},
                 {'name': 'M', 'cast_on': 6},
                 {'name': 'L', 'cast_on': 8}]
        pattern = 'k*{4|6|8}\n(k yo)*{4|5|8}\nk*{8|1|16}'
        data = self.post(sizes, pattern, self.YARN)
        s, m, l = data['sizes']
        # S 完整：行1 k*4=2, 行2 k*4+yo*4=2.8 累计 4.8, 行3 k*8=4 累计 8.8
        self.assertFalse(s['yarn']['partial'])
        self.assertAlmostEqual(s['yarn']['raw_total'], 8.8)
        self.assertEqual(len(s['rows']), 3)
        # M 部分：仅行1 k*6 = 3.0
        self.assertTrue(m['yarn']['partial'])
        self.assertFalse(m['yarn']['complete'])
        self.assertEqual(m['yarn']['raw_total'], 3.0)
        self.assertEqual(len(m['rows']), 1)
        self.assertEqual(m['rows'][0]['weight'], 3.0)
        # L 完整
        self.assertFalse(l['yarn']['partial'])

    def test_yarn_parse_error_marks_all_partial(self):
        data = self.post(self.SIZES, 'k*{12|16|20}\nssk\nk*1', self.YARN)
        self.assertFalse(data['ok'])
        for s in data['sizes']:
            self.assertTrue(s['yarn']['partial'])
            # 行1：S k*12=6.0，M k*16=8.0，L k*20=10.0
        self.assertEqual([s['yarn']['raw_total'] for s in data['sizes']],
                         [6.0, 8.0, 10.0])

    def test_yarn_nested_group_count(self):
        # ((k yo)*2 k2tog)*3 单尺码：k=6, yo=6, k2tog=3
        # 原始 = 6*0.5 + 6*0.2 + 3*1.0 = 7.2
        # 消耗: (k yo)*2 消耗2产出4；k2tog 消耗2产出1 => 每组消耗4产出5
        # 整体 *3：消耗12产出15，故起针12
        sizes = [{'name': 'S', 'cast_on': 12}]
        data = self.post(sizes, '((k yo)*2 k2tog)*3', self.YARN)
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['yarn']['raw_total'], 7.2)

    def test_yarn_invalid_params(self):
        pattern = 'k*4'
        good = {'k': 0.5, 'p': 0.5, 'yo': 0.2, 'k2tog': 1.0,
                'waste_percent': 10, 'grams_per_ball': 50}
        bad_payloads = [
            'not-an-object',
            {},  # 缺字段
            dict(good, k=-1),  # 负克重
            dict(good, k='abc'),
            dict(good, waste_percent=-5),
            dict(good, grams_per_ball=0),  # 每团必须大于 0
            dict(good, grams_per_ball='x'),
            dict(good, k=True),  # 布尔值不接受
        ]
        for yarn in bad_payloads:
            data = self.post([{'name': 'S', 'cast_on': 4}], pattern, yarn)
            self.assertFalse(data['ok'], msg=repr(yarn))
            self.assertEqual(data['error']['type'], 'yarn', msg=repr(yarn))
            self.assertEqual(data['sizes'], [])

    def test_yarn_numeric_strings_accepted(self):
        sizes = [{'name': 'S', 'cast_on': 2}]
        yarn = {'k': '0.5', 'p': '0.5', 'yo': '0.2', 'k2tog': '1',
                'waste_percent': '0', 'grams_per_ball': '10'}
        data = self.post(sizes, 'k2tog*1', yarn)
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['yarn']['raw_total'], 1.0)

    def test_no_yarn_keeps_response_backward_compatible(self):
        data = self.post(self.SIZES, 'k*{12|16|20}')
        self.assertTrue(data['ok'])
        for s in data['sizes']:
            self.assertNotIn('yarn', s)
            self.assertNotIn('weight', s['rows'][0])


class TestValidateSizesSuggestion(unittest.TestCase):
    SIZES = [{'name': 'S', 'cast_on': 12},
             {'name': 'M', 'cast_on': 16},
             {'name': 'L', 'cast_on': 20}]

    def setUp(self):
        self.client = app.test_client()

    def post(self, sizes, pattern, yarn=None):
        payload = {'sizes': sizes, 'pattern': pattern}
        if yarn is not None:
            payload['yarn'] = yarn
        return self.client.post('/api/validate-sizes', json=payload).get_json()

    def test_count_error_yields_fix_suggestion(self):
        # 第 1 行 L 需要 *10 而非 *9；S/M 原本正确，不能受影响
        pattern = '(k2tog yo)*{6|8|9}\np*{12|16|20}'
        data = self.post(self.SIZES, pattern)
        self.assertFalse(data['ok'])
        sug = data['suggestion']
        self.assertIsNotNone(sug)
        self.assertEqual(sug['line'], 1)
        self.assertEqual(sug['char'], 11)  # '*' 是第 11 个字符
        self.assertEqual(sug['old'], '*{6|8|9}')
        self.assertEqual(sug['new'], '*{6|8|10}')
        self.assertEqual(sug['instruction'], '(k2tog yo)*{6|8|10}')
        self.assertEqual(sug['produces'], [12, 16, 20])
        # 原有结果字段不受影响
        self.assertEqual(data['sizes'][2]['error']['type'], 'count')
        self.assertEqual(data['sizes'][2]['error']['diff'], -2)
        self.assertEqual(len(data['sizes'][0]['rows']), 2)

    def test_applied_suggestion_passes_validation(self):
        pattern = '(k2tog yo)*{6|8|9}\np*{12|16|20}'
        data = self.post(self.SIZES, pattern)
        sug = data['suggestion']
        lines = pattern.split('\n')
        lines[sug['line'] - 1] = sug['instruction']
        fixed = self.post(self.SIZES, '\n'.join(lines))
        self.assertTrue(fixed['ok'])
        self.assertIsNone(fixed['suggestion'])
        self.assertEqual([s['final'] for s in fixed['sizes']], [12, 16, 20])

    def test_no_error_gives_null_suggestion(self):
        data = self.post(self.SIZES, '(k2tog yo)*{6|8|10}\np*{12|16|20}')
        self.assertTrue(data['ok'])
        self.assertIsNone(data['suggestion'])

    def test_unsolvable_row_gives_null_suggestion(self):
        # (k2tog)*n 消耗总是偶数，7 针无法通过改倍数修正
        sizes = [{'name': 'S', 'cast_on': 7}]
        data = self.post(sizes, '(k2tog)*3')
        self.assertFalse(data['ok'])
        self.assertIsNone(data['suggestion'])
        self.assertEqual(data['sizes'][0]['error']['type'], 'count')

    def test_parse_error_gives_null_suggestion(self):
        data = self.post(self.SIZES, 'k*{12|16|20}\nssk')
        self.assertFalse(data['ok'])
        self.assertIsNone(data['suggestion'])

    def test_suggestion_targets_first_error_row(self):
        # 第 2 行 M 差额（首个错误行）；建议只改第 2 行的倍数
        sizes = [{'name': 'S', 'cast_on': 4},
                 {'name': 'M', 'cast_on': 6},
                 {'name': 'L', 'cast_on': 8}]
        pattern = 'k*{4|6|8}\n(k yo)*{4|5|8}\nk*{8|1|16}'
        data = self.post(sizes, pattern)
        sug = data['suggestion']
        self.assertIsNotNone(sug)
        self.assertEqual(sug['line'], 2)
        self.assertEqual(sug['instruction'], '(k yo)*{4|6|8}')
        self.assertEqual(sug['produces'], [8, 12, 16])
        # 应用后 M 推进到第 3 行才出错，并给出新的建议
        lines = pattern.split('\n')
        lines[sug['line'] - 1] = sug['instruction']
        fixed = self.post(sizes, '\n'.join(lines))
        s, m, l = fixed['sizes']
        self.assertTrue(s['ok'])
        self.assertTrue(l['ok'])
        self.assertFalse(m['ok'])
        self.assertEqual(m['error']['line'], 3)
        self.assertEqual(fixed['suggestion']['line'], 3)
        self.assertEqual(fixed['suggestion']['instruction'], 'k*{8|12|16}')

    def test_suggestion_with_yarn_request(self):
        # 线材用量估算与建议互不影响
        yarn = {'k': 0.5, 'p': 0.5, 'yo': 0.2, 'k2tog': 1.0,
                'waste_percent': 10, 'grams_per_ball': 50}
        data = self.post(self.SIZES, '(k2tog yo)*{6|8|9}\np*{12|16|20}', yarn)
        self.assertFalse(data['ok'])
        self.assertEqual(data['suggestion']['instruction'], '(k2tog yo)*{6|8|10}')
        self.assertTrue(data['sizes'][2]['yarn']['partial'])
        self.assertFalse(data['sizes'][0]['yarn']['partial'])

    def test_single_size_api_has_no_suggestion(self):
        data = self.client.post('/api/validate', json={
            'cast_on': 7, 'pattern': '(k2tog)*3',
        }).get_json()
        self.assertFalse(data['ok'])
        self.assertNotIn('suggestion', data)


class TestMoveSizeApi(unittest.TestCase):
    SIZES = [{'name': 'S', 'cast_on': 12},
             {'name': 'M', 'cast_on': 16},
             {'name': 'L', 'cast_on': 20}]
    PATTERN = '\n'.join([
        '(k2tog yo)*{6|8|10}',
        'p*{12|16|20}',
        '(k2tog)*{6|8|10}',
        '(k2tog)*{3|4|5}',
        'k*{3|4|5}',
    ])

    def setUp(self):
        self.client = app.test_client()

    def move(self, sizes, pattern, index, direction):
        return self.client.post('/api/move-size', json={
            'sizes': sizes, 'pattern': pattern,
            'index': index, 'direction': direction,
        }).get_json()

    def validate(self, sizes, pattern):
        return self.client.post('/api/validate-sizes', json={
            'sizes': sizes, 'pattern': pattern,
        }).get_json()

    def _results_by_name(self, data):
        return {s['name']: {
            'ok': s['ok'],
            'final': s['final'],
            'error': None if s['error'] is None else (
                s['error']['type'], s['error'].get('line'), s['error'].get('diff')),
            'rows': [(r['line'], r['consume'], r['produce'], r['out']) for r in s['rows']],
        } for s in data['sizes']}

    def test_move_down_swaps_sizes_and_pattern(self):
        # M 下移：[S,M,L] -> [S,L,M]
        data = self.move(self.SIZES, self.PATTERN, 1, 'down')
        self.assertTrue(data['ok'])
        self.assertEqual([s['name'] for s in data['sizes']], ['S', 'L', 'M'])
        self.assertEqual([s['cast_on'] for s in data['sizes']], [12, 20, 16])
        self.assertEqual(data['pattern'].splitlines(), [
            '(k2tog yo)*{6|10|8}',
            'p*{12|20|16}',
            '(k2tog)*{6|10|8}',
            '(k2tog)*{3|5|4}',
            'k*{3|5|4}',
        ])

    def test_move_up_swaps_sizes_and_pattern(self):
        # L 上移：[S,M,L] -> [S,L,M]
        data = self.move(self.SIZES, self.PATTERN, 2, 'up')
        self.assertTrue(data['ok'])
        self.assertEqual([s['name'] for s in data['sizes']], ['S', 'L', 'M'])
        self.assertEqual(data['pattern'].splitlines()[0], '(k2tog yo)*{6|10|8}')

    def test_plain_repeats_and_text_unchanged(self):
        pattern = '((k yo)*2 k2tog)*3\nk*{3|4|5} tail k*9\n'
        data = self.move(self.SIZES, pattern, 0, 'down')
        self.assertTrue(data['ok'])
        self.assertEqual(data['pattern'].splitlines()[0], '((k yo)*2 k2tog)*3')
        self.assertEqual(data['pattern'].splitlines()[1], 'k*{4|3|5} tail k*9')
        self.assertTrue(data['pattern'].endswith('\n'))

    def test_nested_and_multiple_sites_per_line(self):
        pattern = '(k*{2|3|4} yo)*2 p*{5|6|7}'
        data = self.move(self.SIZES, pattern, 0, 'down')
        self.assertTrue(data['ok'])
        self.assertEqual(data['pattern'], '(k*{3|2|4} yo)*2 p*{6|5|7}')

    def test_crlf_and_blank_lines_preserved(self):
        pattern = 'k*{1|2|3}\r\n\r\np*{4|5|6}'
        data = self.move(self.SIZES, pattern, 2, 'up')
        self.assertTrue(data['ok'])
        self.assertEqual(data['pattern'], 'k*{1|3|2}\r\n\r\np*{4|6|5}')

    def test_validation_results_identical_after_move(self):
        # 重排后各尺码重新校验的针数与移动前一致（按尺码名对照）
        before = self._results_by_name(self.validate(self.SIZES, self.PATTERN))
        moved = self.move(self.SIZES, self.PATTERN, 0, 'down')
        after = self._results_by_name(
            self.validate(moved['sizes'], moved['pattern']))
        self.assertEqual(before, after)

    def test_results_identical_with_count_errors(self):
        # 移动前 M 在第 2 行针数出错；移动后按名字对照结果仍一致
        sizes = [{'name': 'S', 'cast_on': 4},
                 {'name': 'M', 'cast_on': 6},
                 {'name': 'L', 'cast_on': 8}]
        pattern = 'k*{4|6|8}\n(k yo)*{4|5|8}\nk*{8|1|16}'
        before = self._results_by_name(self.validate(sizes, pattern))
        moved = self.move(sizes, pattern, 0, 'down')  # -> [M,S,L]
        after = self._results_by_name(
            self.validate(moved['sizes'], moved['pattern']))
        self.assertEqual(before, after)
        self.assertEqual(moved['pattern'], 'k*{6|4|8}\n(k yo)*{5|4|8}\nk*{1|8|16}')

    def test_count_mismatch_blocks_whole_move(self):
        # 第 2 行倍数只有 2 项：整次移动不生效（无 sizes/pattern 回写）
        pattern = 'k*{6|8|10}\np*{12|16}\n'
        data = self.move(self.SIZES, pattern, 0, 'down')
        self.assertFalse(data['ok'])
        self.assertNotIn('sizes', data)
        self.assertNotIn('pattern', data)
        err = data['error']
        self.assertEqual(err['type'], 'reorder')
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['char'], 2)
        self.assertIn('项数不符', err['message'])

    def test_bad_value_blocks_whole_move(self):
        pattern = 'k*{6|0|10}'
        data = self.move(self.SIZES, pattern, 2, 'up')
        self.assertFalse(data['ok'])
        err = data['error']
        self.assertEqual(err['type'], 'reorder')
        self.assertEqual(err['line'], 1)
        self.assertEqual(err['char'], 6)  # '0' 是第 6 个字符
        self.assertIn('正整数', err['message'])

    def test_invalid_sizes_rejected(self):
        data = self.move([], 'k*1', 0, 'up')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'sizes')

    def test_boundary_and_bad_direction_rejected(self):
        for index, direction in [(0, 'up'), (2, 'down')]:
            data = self.move(self.SIZES, self.PATTERN, index, direction)
            self.assertFalse(data['ok'], msg=(index, direction))
            self.assertEqual(data['error']['type'], 'move')
        data = self.move(self.SIZES, self.PATTERN, 1, 'sideways')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'move')
        data = self.move(self.SIZES, self.PATTERN, 9, 'up')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'move')

    def test_single_size_move_is_boundary_error(self):
        sizes = [{'name': 'S', 'cast_on': 4}]
        data = self.move(sizes, 'k*{4}', 0, 'up')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'move')


class TestPreviewRowApi(unittest.TestCase):
    SIZES = [{'name': 'S', 'cast_on': 12},
             {'name': 'M', 'cast_on': 16},
             {'name': 'L', 'cast_on': 20}]
    PATTERN = '\n'.join([
        '(k2tog yo)*{6|8|10}',
        'p*{12|16|20}',
        '',
        'ssk bad',
    ])

    def setUp(self):
        self.client = app.test_client()

    def preview(self, line, size_index=0, start=1, sizes=None, pattern=None):
        return self.client.post('/api/preview-row', json={
            'sizes': sizes or self.SIZES,
            'pattern': self.PATTERN if pattern is None else pattern,
            'line': line,
            'size_index': size_index,
            'start': start,
        }).get_json()

    def test_first_page_s_size(self):
        data = self.preview(1, 0, 1)
        self.assertTrue(data['ok'])
        self.assertEqual(data['line'], 1)
        self.assertEqual(data['instruction'], '(k2tog yo)*{6|8|10}')
        self.assertEqual(data['size'], 'S')
        self.assertEqual(data['size_index'], 0)
        self.assertEqual(data['cast_on'], 12)
        self.assertEqual(data['total'], 12)
        self.assertEqual(data['consume'], 12)
        self.assertEqual(data['produce'], 12)
        self.assertEqual(data['limit'], 50)
        self.assertIsNone(data['next_start'])
        self.assertEqual(len(data['items']), 12)
        self.assertEqual(data['items'][0], {
            'seq': 1, 'stitch': 'k2tog', 'consume_before': 0,
            'in_from': 1, 'in_to': 2, 'out': 1})
        self.assertEqual(data['items'][1], {
            'seq': 2, 'stitch': 'yo', 'consume_before': 2,
            'in_from': None, 'in_to': None, 'out': 2})

    def test_size_index_selects_multiplier(self):
        data = self.preview(1, 2, 1)
        self.assertTrue(data['ok'])
        self.assertEqual(data['size'], 'L')
        self.assertEqual(data['total'], 20)
        self.assertEqual(data['consume'], 20)

    def test_pagination_fields(self):
        pattern = 'k*120'
        first = self.preview(1, 0, 1,
                             sizes=[{'name': 'S', 'cast_on': 120}],
                             pattern=pattern)
        self.assertEqual(len(first['items']), 50)
        self.assertEqual(first['next_start'], 51)
        self.assertEqual(first['prev_start'], 1)
        second = self.preview(1, 0, 51,
                              sizes=[{'name': 'S', 'cast_on': 120}],
                              pattern=pattern)
        self.assertEqual([i['seq'] for i in second['items']],
                         list(range(51, 101)))
        self.assertEqual(second['prev_start'], 1)
        self.assertEqual(second['next_start'], 101)
        third = self.preview(1, 0, 101,
                             sizes=[{'name': 'S', 'cast_on': 120}],
                             pattern=pattern)
        self.assertEqual(len(third['items']), 20)
        self.assertIsNone(third['next_start'])

    def test_huge_repeat_tail(self):
        # 十亿次重复直接查看尾段，不展开
        data = self.preview(1, 0, 1999999997,
                            sizes=[{'name': 'S', 'cast_on': 1}],
                            pattern='(k yo)*1000000000')
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 2000000000)
        self.assertEqual(len(data['items']), 4)
        self.assertEqual(data['items'][0]['seq'], 1999999997)
        self.assertEqual(data['items'][-1]['stitch'], 'yo')

    def test_zero_input_yo_marker(self):
        data = self.preview(1, 0, 1,
                            sizes=[{'name': 'S', 'cast_on': 4}],
                            pattern='yo k yo k2tog')
        self.assertTrue(data['ok'])
        yo1, _k, yo2, _k2tog = data['items']
        self.assertIsNone(yo1['in_from'])
        self.assertIsNone(yo1['in_to'])
        self.assertEqual(yo1['consume_before'], 0)
        self.assertEqual(yo2['consume_before'], 1)
        self.assertEqual(_k2tog['in_from'], 2)
        self.assertEqual(_k2tog['in_to'], 3)

    def test_zero_consume_only_row_preview(self):
        # 整行只有挂线：消耗 0 但每个 yo 都是实际针法
        data = self.preview(1, 0, 1,
                            sizes=[{'name': 'S', 'cast_on': 4}],
                            pattern='(yo)*3')
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['consume'], 0)
        self.assertEqual(data['produce'], 3)
        self.assertEqual([i['seq'] for i in data['items']], [1, 2, 3])
        self.assertTrue(all(i['in_from'] is None for i in data['items']))

    def test_parse_error_returns_existing_error_with_line_and_char(self):
        # 第 4 行非法：返回与校验接口相同的 parse 错误（原文行号与字符位置），
        # 不含 items/部分预览
        data = self.preview(4, 0, 1)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'parse')
        self.assertEqual(data['error']['line'], 4)
        self.assertEqual(data['error']['char'], 1)
        self.assertNotIn('items', data)

    def test_parse_error_size_brace_mismatch_reports_star(self):
        data = self.preview(1, 0, 1,
                            sizes=self.SIZES,
                            pattern='k*{12|16}\n')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'parse')
        self.assertEqual(data['error']['line'], 1)
        self.assertEqual(data['error']['char'], 2)
        self.assertIn('项数不符', data['error']['message'])

    def test_parse_error_consistent_with_validate_sizes(self):
        # 同一非法行在两个接口中的消息与字符位置完全一致
        preview_data = self.preview(1, 0, 1, pattern='(k yo\nk*1')
        validate_data = self.client.post('/api/validate-sizes', json={
            'sizes': self.SIZES, 'pattern': '(k yo\nk*1',
        }).get_json()
        verr = validate_data['sizes'][0]['error']
        perr = preview_data['error']
        self.assertEqual(perr['message'], verr['message'])
        self.assertEqual(perr['char'], verr['char'])
        self.assertEqual(perr['line'], verr['line'])

    def test_blank_line_rejected(self):
        data = self.preview(3, 0, 1)  # 第 3 行为空行
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'line')
        self.assertEqual(data['error']['line'], 3)

    def test_line_number_out_of_range(self):
        for bad in [0, 5, -1, '1', 1.0, True, None]:
            data = self.preview(bad, 0, 1)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'line', msg=repr(bad))

    def test_empty_pattern_rejected(self):
        data = self.preview(1, 0, 1, pattern='')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'line')

    def test_bad_size_index(self):
        for bad in [-1, 3, '0', 1.0, True, None]:
            data = self.preview(1, bad, 1)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'size_index',
                             msg=repr(bad))

    def test_bad_start(self):
        for bad in [0, -3, '1', 1.5, True, None]:
            data = self.preview(1, 0, bad)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'start', msg=repr(bad))

    def test_start_beyond_total_reports_total(self):
        data = self.preview(1, 0, 13)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'start')
        self.assertEqual(data['error']['total'], 12)
        self.assertIn('12', data['error']['message'])

    def test_start_defaults_to_one(self):
        data = self.client.post('/api/preview-row', json={
            'sizes': self.SIZES, 'pattern': 'k*{12|16|20}',
            'line': 1, 'size_index': 0,
        }).get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['start'], 1)

    def test_bad_sizes_rejected(self):
        for bad in [None, [], [{'name': '', 'cast_on': 4}],
                    [{'name': 'S', 'cast_on': 0}],
                    [{'name': 'S', 'cast_on': 'x'}]]:
            data = self.client.post('/api/preview-row', json={
                'sizes': bad, 'pattern': 'k*4', 'line': 1,
                'size_index': 0, 'start': 1,
            }).get_json()
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'sizes', msg=repr(bad))

    def test_preview_works_even_when_row_counts_do_not_balance(self):
        # 预览只按语法定位，不要求该行针数与起针数匹配
        data = self.preview(1, 0, 1,
                            sizes=[{'name': 'S', 'cast_on': 99}],
                            pattern='k*3')
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['consume'], 3)

    def test_nested_size_repeats_resolved_for_selected_size(self):
        pattern = '((k yo)*{2|3} p)*{3|2}'
        # S: 每组 (k yo)*2+p = 5 个，*3 -> 15；M: 每组 3 组 k yo +p = 7，*2 -> 14
        s = self.preview(1, 0, 1,
                         sizes=[{'name': 'S', 'cast_on': 1},
                                {'name': 'M', 'cast_on': 1}],
                         pattern=pattern)
        m = self.preview(1, 1, 1,
                         sizes=[{'name': 'S', 'cast_on': 1},
                                {'name': 'M', 'cast_on': 1}],
                         pattern=pattern)
        self.assertEqual(s['total'], 15)
        self.assertEqual(m['total'], 14)
        self.assertEqual([i['stitch'] for i in m['items']][:5],
                         ['k', 'yo', 'k', 'yo', 'k'])


class TestTrackStitchApi(unittest.TestCase):
    SIZES = [{'name': 'S', 'cast_on': 12},
             {'name': 'M', 'cast_on': 16},
             {'name': 'L', 'cast_on': 20}]
    PATTERN = '\n'.join([
        '(k2tog yo)*{6|8|10}',
        'p*{12|16|20}',
        '(k2tog)*{6|8|10}',
        '(k2tog)*{3|4|5}',
        'k*{3|4|5}',
    ])

    def setUp(self):
        self.client = app.test_client()

    def track(self, needle, size_index=0, sizes=None, pattern=None):
        return self.client.post('/api/track-stitch', json={
            'sizes': sizes or self.SIZES,
            'pattern': self.PATTERN if pattern is None else pattern,
            'size_index': size_index,
            'needle': needle,
        }).get_json()

    def test_tracks_every_valid_row_with_line_numbers(self):
        data = self.track(1)
        self.assertTrue(data['ok'])
        self.assertEqual(data['size'], 'S')
        self.assertEqual(data['cast_on'], 12)
        self.assertEqual(data['needle'], 1)
        self.assertEqual(data['final_needle'], 1)
        self.assertIsNone(data['error'])
        self.assertEqual([t['line'] for t in data['tracks']], [1, 2, 3, 4, 5])
        first = data['tracks'][0]
        self.assertEqual(first, {
            'line': 1,
            'instruction': '(k2tog yo)*{6|8|10}',
            'in': 12,
            'needle_in': 1,
            'stitch': 'k2tog',
            'in_from': 1,
            'in_to': 2,
            'merged_with': 2,
            'yos_before': 0,
            'seq': 1,
            'out_needle': 1,
            'consume': 12,
            'produce': 12,
            'available_out': 12,
        })

    def test_needle_chains_across_rows(self):
        # 第 12 枚针：行1 与第 11 枚合并产出第 11 针；之后随 k2tog 逐级合并
        data = self.track(12)
        chain = [(t['line'], t['needle_in'], t['stitch'],
                  t['in_from'], t['in_to'], t['merged_with'],
                  t['out_needle']) for t in data['tracks']]
        self.assertEqual(chain, [
            (1, 12, 'k2tog', 11, 12, 11, 11),
            (2, 11, 'p', 11, 11, None, 11),
            (3, 11, 'k2tog', 11, 12, 12, 6),
            (4, 6, 'k2tog', 5, 6, 5, 3),
            (5, 3, 'k', 3, 3, None, 3),
        ])
        self.assertEqual(data['final_needle'], 3)

    def test_size_index_selects_multiplier(self):
        # L 尺码第 19 枚针
        data = self.track(19, size_index=2)
        self.assertTrue(data['ok'])
        self.assertEqual(data['size'], 'L')
        self.assertEqual(
            [(t['needle_in'], t['stitch'], t['in_from'], t['in_to'])
             for t in data['tracks']],
            [(19, 'k2tog', 19, 20), (19, 'p', 19, 19),
             (19, 'k2tog', 19, 20), (10, 'k2tog', 9, 10),
             (5, 'k', 5, 5)])

    def test_k_and_p_have_no_merge(self):
        # 两行都平衡：行1 k p k p（4->4），行2 p k2tog k（4->3）；
        # 追踪第 1 枚针：行1 被 k 消耗、行2 被 p 消耗，均无合并
        data = self.track(1, sizes=[{'name': 'S', 'cast_on': 4}],
                         pattern='k p k p\np k2tog k')
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['tracks']), 2)
        self.assertTrue(all(t['merged_with'] is None for t in data['tracks']))
        self.assertEqual([t['stitch'] for t in data['tracks']], ['k', 'p'])
        self.assertEqual([t['out_needle'] for t in data['tracks']], [1, 1])

    def test_yo_only_shifts_later_output_positions(self):
        # 行1 k2tog yo：两枚入针合并产出第 1 针，yo 产出第 2 针（不消耗入针）；
        # 行2 p p：追踪第 2 枚入针，行1 合并后是第 1 针，故行2 被第 1 个 p 消耗
        data = self.track(2, sizes=[{'name': 'S', 'cast_on': 2}],
                         pattern='k2tog yo\np p')
        self.assertTrue(data['ok'])
        r1, r2 = data['tracks']
        self.assertEqual(r1['stitch'], 'k2tog')
        self.assertEqual(r1['merged_with'], 1)
        self.assertEqual(r1['out_needle'], 1)
        self.assertEqual(r2['needle_in'], 1)
        self.assertEqual((r2['stitch'], r2['in_from'], r2['in_to'],
                          r2['out_needle']), ('p', 1, 1, 1))
        self.assertEqual(data['final_needle'], 1)

    def test_needle_through_yo_position_shift(self):
        # 第 1 枚针穿过 'yo k' 行：yo 不消耗，k 消耗第 1 枚但产出在第 2 针位
        data = self.track(1, sizes=[{'name': 'S', 'cast_on': 1}],
                         pattern='yo k')
        self.assertTrue(data['ok'])
        t = data['tracks'][0]
        self.assertEqual((t['stitch'], t['in_from'], t['seq'],
                          t['yos_before'], t['out_needle']),
                         ('k', 1, 2, 1, 2))
        self.assertEqual(data['final_needle'], 2)

    def test_nested_repeats_tracked_arithmetically(self):
        # ((k yo)*2 k2tog)*3 消耗12产出15；起针12 平衡，追踪第 12 枚
        data = self.track(12, sizes=[{'name': 'S', 'cast_on': 12}],
                         pattern='((k yo)*2 k2tog)*3')
        self.assertTrue(data['ok'])
        t = data['tracks'][0]
        self.assertEqual((t['stitch'], t['in_from'], t['in_to']),
                         ('k2tog', 11, 12))

    def test_needle_out_of_range_is_clear_error_before_rows(self):
        data = self.track(13)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'needle')
        self.assertEqual(data['error']['cast_on'], 12)
        self.assertEqual(data['error']['needle'], 13)
        self.assertNotIn('tracks', data)
        self.assertIn('1~12', data['error']['message'])

    def test_bad_needle_value(self):
        for bad in [0, -3, 'x', 1.5, True, None, '']:
            data = self.track(bad)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'needle', msg=repr(bad))

    def test_numeric_string_accepted(self):
        data = self.track('12')
        self.assertTrue(data['ok'])
        self.assertEqual(data['needle'], 12)

    def test_count_leftover_stops_and_keeps_prior_track(self):
        data = self.track(12, sizes=[{'name': 'S', 'cast_on': 12}],
                         pattern='k*12\nk*11')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'count')
        self.assertEqual(data['error']['line'], 2)
        self.assertEqual(data['error']['diff'], -1)
        self.assertEqual([t['line'] for t in data['tracks']], [1])
        self.assertNotIn('final_needle', data)

    def test_count_shortfall_stops_at_first_bad_row(self):
        data = self.track(1, sizes=[{'name': 'S', 'cast_on': 12}],
                         pattern='k*12\nk2tog*7')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'count')
        self.assertEqual(data['error']['line'], 2)
        self.assertEqual(data['error']['diff'], 2)
        self.assertEqual([t['line'] for t in data['tracks']], [1])

    def test_parse_error_stops_with_line_and_char(self):
        data = self.track(3, sizes=[{'name': 'S', 'cast_on': 4}],
                         pattern='k*4\np*4\nssk')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'parse')
        self.assertEqual(data['error']['line'], 3)
        self.assertEqual(data['error']['char'], 1)
        # 此前两行有效轨迹保留
        self.assertEqual([t['line'] for t in data['tracks']], [1, 2])

    def test_parse_error_consistent_with_validate_sizes(self):
        pattern = '(k yo\nk*1'
        track_data = self.track(1, sizes=[{'name': 'S', 'cast_on': 2}],
                                pattern=pattern)
        validate_data = self.client.post('/api/validate-sizes', json={
            'sizes': [{'name': 'S', 'cast_on': 2}], 'pattern': pattern,
        }).get_json()
        verr = validate_data['sizes'][0]['error']
        terr = track_data['error']
        self.assertEqual(terr['type'], 'parse')
        self.assertEqual((terr['line'], terr['char'], terr['message']),
                         (verr['line'], verr['char'], verr['message']))

    def test_size_brace_mismatch_is_parse_error_at_star(self):
        data = self.track(1, pattern='k*{12|16}')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'parse')
        self.assertEqual(data['error']['line'], 1)
        self.assertEqual(data['error']['char'], 2)

    def test_blank_lines_count_in_line_numbers(self):
        data = self.track(4, sizes=[{'name': 'S', 'cast_on': 4}],
                         pattern='k*4\n\np*4')
        self.assertTrue(data['ok'])
        self.assertEqual([t['line'] for t in data['tracks']], [1, 3])

    def test_bad_size_index(self):
        for bad in [3, -1, '0', 1.0, True, None]:
            data = self.track(1, size_index=bad)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'size_index',
                             msg=repr(bad))

    def test_bad_sizes_rejected(self):
        for bad in [None, [], [{'name': '', 'cast_on': 4}],
                    [{'name': 'S', 'cast_on': 0}],
                    [{'name': 'S', 'cast_on': 'x'}]]:
            data = self.client.post('/api/track-stitch', json={
                'sizes': bad, 'pattern': 'k*4', 'size_index': 0,
                'needle': 1,
            }).get_json()
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'sizes', msg=repr(bad))

    def test_size_index_defaults_to_zero(self):
        data = self.client.post('/api/track-stitch', json={
            'sizes': [{'name': 'S', 'cast_on': 4}], 'pattern': 'k*4',
            'needle': 1,
        }).get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['size_index'], 0)

    def test_huge_repeats_without_expansion(self):
        # 十亿次重复直接定位，不能超时/展开
        data = self.track(1000000000,
                          sizes=[{'name': 'S', 'cast_on': 1000000000}],
                          pattern='(k yo)*1000000000')
        self.assertTrue(data['ok'])
        t = data['tracks'][0]
        self.assertEqual((t['stitch'], t['in_from'], t['out_needle']),
                         ('k', 1000000000, 1999999999))
        self.assertEqual(data['final_needle'], 1999999999)


class TestPatternLayoutApi(unittest.TestCase):
    PAYLOAD = {
        'gauge': 22,
        'sizes': [{'name': 'S', 'target': 41},
                  {'name': 'M', 'target': 48},
                  {'name': 'L', 'target': 55}],
        'edge': 2,
        'center': 6,
        'pattern_width': 8,
        'tolerance': 1,
    }

    def setUp(self):
        self.client = app.test_client()

    def post(self, **overrides):
        payload = dict(self.PAYLOAD)
        payload.update(overrides)
        return self.client.post('/api/pattern-layout', json=payload).get_json()

    def test_basic_layout(self):
        data = self.post()
        self.assertTrue(data['ok'])
        self.assertEqual(data['base'], 10)   # 2×边针 + 中央针
        self.assertEqual(data['step'], 16)   # 2×花样宽度
        self.assertEqual([s['repeats'] for s in data['sizes']], [5, 6, 7])
        self.assertEqual([s['cast_on'] for s in data['sizes']], [90, 106, 122])
        # 实际片幅 = 起针数 × 10 ÷ 每10厘米针数
        self.assertAlmostEqual(data['sizes'][0]['width'], 90 * 10 / 22, places=2)
        self.assertAlmostEqual(data['sizes'][2]['width'], 122 * 10 / 22, places=2)
        # 各尺码偏差不超过允许宽差，总宽差为偏差之和（精确分数 8/11）
        for s in data['sizes']:
            self.assertLessEqual(s['deviation'], 1 + 1e-9)
            self.assertAlmostEqual(s['deviation'],
                                   abs(s['width'] - s['target']), places=1)
        self.assertAlmostEqual(data['total_deviation'], 8 / 11, places=2)

    def test_tie_breaks_to_lexicographically_smallest(self):
        # (2,4) 与 (3,4) 总宽差同为 9，应取字典序最小的 (2,4)
        data = self.post(gauge=10, edge=0, center=0, pattern_width=5,
                         tolerance=10,
                         sizes=[{'name': 'A', 'target': 25},
                                {'name': 'B', 'target': 36}])
        self.assertTrue(data['ok'])
        self.assertEqual([s['repeats'] for s in data['sizes']], [2, 4])
        self.assertEqual(data['total_deviation'], 9)

    def test_infeasible_chain_reports_ranges(self):
        # 尺码1 只能取 2、尺码2 只能取 2~3、尺码3 只能取 3：严格递增不可行
        data = self.post(gauge=10, edge=0, center=0, pattern_width=5,
                         tolerance=5,
                         sizes=[{'name': 'S', 'target': 20},
                                {'name': 'M', 'target': 25},
                                {'name': 'L', 'target': 30}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertIn('无法同时满足约束', data['error']['message'])
        self.assertEqual(data['fail_index'], 2)
        ranges = [(s['min_repeats'], s['max_repeats']) for s in data['sizes']]
        self.assertEqual(ranges, [(2, 2), (2, 3), (3, 3)])

    def test_infeasible_empty_range(self):
        # 允许宽差太小，唯一尺码没有任何可行重复数
        data = self.post(gauge=10, edge=0, center=0, pattern_width=5,
                         tolerance=1, sizes=[{'name': 'S', 'target': 25}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertIn('无法同时满足约束', data['error']['message'])
        s = data['sizes'][0]
        self.assertGreater(s['min_repeats'], s['max_repeats'])

    def test_repeats_at_least_one(self):
        data = self.post(gauge=10, edge=0, center=0, pattern_width=5,
                         tolerance=20, sizes=[{'name': 'S', 'target': 2}])
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['repeats'], 1)

    def test_string_numbers_accepted(self):
        data = self.post(gauge='22', edge='2', center='6',
                         pattern_width='8', tolerance='1',
                         sizes=[{'name': 'S', 'target': '41'}])
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['repeats'], 5)

    def test_bad_scalar_params(self):
        cases = [
            ('gauge', [0, -1, 'x', True, None, '1e2']),
            ('edge', [-1, 'x', True, None, 1.5]),
            ('center', [-1, 'x', True, None, 1.5]),
            ('pattern_width', [0, -1, 'x', True, None, 1.5]),
            ('tolerance', [-1, 'x', True, None]),
        ]
        for field, bad_values in cases:
            for bad in bad_values:
                data = self.post(**{field: bad})
                self.assertFalse(data['ok'], msg='{}={!r}'.format(field, bad))
                self.assertEqual(data['error']['type'], 'params',
                                 msg='{}={!r}'.format(field, bad))

    def test_bad_sizes_rejected(self):
        for bad in [None, [],
                    [{'name': '', 'target': 40}],
                    [{'name': 'S', 'target': 0}],
                    [{'name': 'S', 'target': -3}],
                    [{'name': 'S', 'target': 'x'}],
                    [{'name': 'S'}],
                    ['S']]:
            data = self.post(sizes=bad)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'sizes', msg=repr(bad))

    def test_targets_must_be_ascending(self):
        data = self.post(sizes=[{'name': 'S', 'target': 50},
                                {'name': 'M', 'target': 40}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'sizes')
        self.assertIn('从小到大', data['error']['message'])

    def test_equal_targets_allowed(self):
        # 目标片幅相同（不减）合法，重复数仍须严格递增
        data = self.post(gauge=10, edge=0, center=0, pattern_width=5,
                         tolerance=10,
                         sizes=[{'name': 'A', 'target': 20},
                                {'name': 'B', 'target': 20}])
        self.assertTrue(data['ok'])
        repeats = [s['repeats'] for s in data['sizes']]
        # (1,2) 与 (2,3) 总宽差同为 10，取字典序最小的 (1,2)
        self.assertEqual(repeats, [1, 2])
        self.assertLess(repeats[0], repeats[1])


class TestShapingPlanApi(unittest.TestCase):
    PAYLOAD = {
        'cast_on': 70,
        'target': 40,
        'rows': 15,
        'max_decrease': 2,
    }

    def setUp(self):
        self.client = app.test_client()

    def post(self, **overrides):
        payload = dict(self.PAYLOAD)
        payload.update(overrides)
        return self.client.post('/api/shaping-plan', json=payload).get_json()

    def test_basic_plan(self):
        data = self.post()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total_decrease'], 30)
        self.assertEqual(data['per_side'], 15)
        self.assertEqual(len(data['plan']), 15)
        plan = data['plan']
        # 逐行字段：行号连续、左右相同、本行共减 = 左 + 右
        for i, row in enumerate(plan, 1):
            self.assertEqual(row['row'], i)
            self.assertEqual(row['left'], row['right'])
            self.assertEqual(row['decrease'], row['left'] + row['right'])
            self.assertIn(row['left'], (0, 1, 2))
            self.assertEqual(row['remaining'], 70 - row['decreased'])
        # 减针行之间至少隔一行平织
        for i in range(len(plan) - 1):
            self.assertFalse(plan[i]['decrease'] and plan[i + 1]['decrease'])
        # 末行余针恰好等于目标针数
        self.assertEqual(plan[-1]['remaining'], 40)
        self.assertEqual(plan[-1]['decreased'], 30)
        self.assertEqual(data['decrease_rows'],
                         sum(1 for r in plan if r['decrease']))

    def test_tie_breaks_to_lexicographically_smallest(self):
        # [1,0,1,0]、[1,0,0,1]、[0,1,0,1] 代价同为 2，取字典序最小的 [0,1,0,1]
        data = self.post(cast_on=12, target=8, rows=4, max_decrease=2)
        self.assertTrue(data['ok'])
        self.assertEqual([r['left'] for r in data['plan']], [0, 1, 0, 1])
        self.assertEqual(data['cost'], 2)
        self.assertEqual([r['remaining'] for r in data['plan']],
                         [12, 10, 10, 8])

    def test_progress_is_linear(self):
        # 目标进度 = 总减针数 × 行号 ÷ 总行数（保留两位小数）
        data = self.post(cast_on=10, target=4, rows=5, max_decrease=1)
        self.assertTrue(data['ok'])
        self.assertEqual([r['progress'] for r in data['plan']],
                         [1.2, 2.4, 3.6, 4.8, 6.0])

    def test_string_numbers_accepted(self):
        data = self.post(cast_on='70', target='40', rows='15',
                         max_decrease='2')
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['plan']), 15)

    def test_no_decrease_needed(self):
        data = self.post(cast_on=20, target=20, rows=6, max_decrease=2)
        self.assertTrue(data['ok'])
        self.assertEqual(data['cost'], 0)
        self.assertEqual(data['decrease_rows'], 0)
        self.assertTrue(all(r['decrease'] == 0 for r in data['plan']))

    def test_bad_scalar_params(self):
        cases = [
            ('cast_on', [0, -1, 'x', True, None, 1.5]),
            ('target', [0, -1, 'x', True, None, 1.5]),
            ('rows', [0, -1, 'x', True, None, 1.5]),
            ('max_decrease', [0, 3, -1, 'x', True, None, 1.5]),
        ]
        for field, bad_values in cases:
            for bad in bad_values:
                data = self.post(**{field: bad})
                self.assertFalse(data['ok'], msg='{}={!r}'.format(field, bad))
                self.assertEqual(data['error']['type'], 'params',
                                 msg='{}={!r}'.format(field, bad))

    def test_max_decrease_must_be_1_or_2(self):
        # 12→8（单侧 2）、4 行：单侧上限 1 或 2 都可行
        for good in (1, 2):
            data = self.post(cast_on=12, target=8, rows=4, max_decrease=good)
            self.assertTrue(data['ok'], msg='max_decrease={!r}'.format(good))
        for bad in (0, 3, 4):
            data = self.post(max_decrease=bad)
            self.assertFalse(data['ok'], msg='max_decrease={!r}'.format(bad))
            self.assertEqual(data['error']['type'], 'params')
            self.assertIn('1 或 2', data['error']['message'])

    def test_infeasible_target_exceeds(self):
        data = self.post(cast_on=10, target=12)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertIn('大于起针数', data['error']['message'])
        self.assertIn('最多可减', data['error']['message'])
        self.assertEqual(data['total_decrease'], -2)
        # 15 行、单侧上限 2：最多 8 个减针行，双侧最多可减 32 针
        self.assertEqual(data['max_decrease_rows'], 8)
        self.assertEqual(data['max_total_decrease'], 32)

    def test_infeasible_odd_decrease(self):
        data = self.post(cast_on=10, target=5, rows=5, max_decrease=2)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertIn('奇数', data['error']['message'])
        self.assertIn('最多可减', data['error']['message'])
        self.assertEqual(data['max_total_decrease'], 12)

    def test_infeasible_insufficient_rows(self):
        # 20→4 共减 16 针，3 行、单侧上限 1：最多 2 个减针行、共减 4 针
        data = self.post(cast_on=20, target=4, rows=3, max_decrease=1)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertIn('最多可减 4 针', data['error']['message'])
        self.assertIn('还差 12 针', data['error']['message'])
        self.assertEqual(data['max_decrease_rows'], 2)
        self.assertEqual(data['max_total_decrease'], 4)


class TestStripeScheduleApi(unittest.TestCase):
    PAYLOAD = {
        'total_rows': 20,
        'colors': [{'name': '米白', 'rows': 12},
                  {'name': '藏青', 'rows': 8}],
        'min_len': 2,
        'max_len': 4,
        'preferred': 3,
    }

    def setUp(self):
        self.client = app.test_client()

    def post(self, **overrides):
        payload = {
            'total_rows': self.PAYLOAD['total_rows'],
            'colors': [dict(c) for c in self.PAYLOAD['colors']],
            'min_len': self.PAYLOAD['min_len'],
            'max_len': self.PAYLOAD['max_len'],
            'preferred': self.PAYLOAD['preferred'],
        }
        payload.update(overrides)
        return self.client.post('/api/stripe-schedule', json=payload).get_json()

    def test_basic_schedule(self):
        data = self.post()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total_rows'], 20)
        self.assertEqual(data['min_len'], 2)
        self.assertEqual(data['max_len'], 4)
        self.assertEqual(data['preferred'], 3)
        self.assertEqual(data['segment_count'], 7)
        self.assertEqual(data['cost'], 1)
        # 段序列：缩短的 2 行段落在最靠前的可行颜色（藏青，第 2 段）
        self.assertEqual(
            [(s['color_index'], s['length']) for s in data['segments']],
            [(0, 3), (1, 2), (0, 3), (1, 3), (0, 3), (1, 3), (0, 3)])

    def test_segment_fields_cover_all_rows(self):
        data = self.post()
        self.assertTrue(data['ok'])
        segments = data['segments']
        self.assertEqual(segments[0]['start'], 1)
        self.assertEqual(segments[0]['end'], 3)
        self.assertEqual(segments[0]['color'], '米白')
        for prev, seg in zip(segments, segments[1:]):
            self.assertEqual(seg['start'], prev['end'] + 1)
            self.assertNotEqual(seg['color_index'], prev['color_index'])
            self.assertTrue(2 <= seg['length'] <= 4)
        self.assertEqual(segments[-1]['end'], 20)
        self.assertEqual([s['index'] for s in segments],
                         list(range(1, len(segments) + 1)))

    def test_color_summary_usage_and_remaining(self):
        data = self.post()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total_stock'], 20)
        by_index = {c['index']: c for c in data['colors']}
        self.assertEqual(by_index[0]['name'], '米白')
        self.assertEqual((by_index[0]['stock'], by_index[0]['used'],
                          by_index[0]['remaining']), (12, 12, 0))
        self.assertEqual((by_index[1]['stock'], by_index[1]['used'],
                          by_index[1]['remaining']), (8, 8, 0))
        # 各色用量与逐段长度一致
        for color in data['colors']:
            used = sum(s['length'] for s in data['segments']
                       if s['color_index'] == color['index'])
            self.assertEqual(color['used'], used)
            self.assertEqual(color['remaining'], color['stock'] - used)

    def test_three_colors_accepted(self):
        data = self.post(colors=[
            {'name': 'A', 'rows': 5},
            {'name': 'B', 'rows': 5},
            {'name': 'C', 'rows': 5},
        ], total_rows=12, min_len=2, max_len=3, preferred=3)
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['colors']), 3)
        self.assertEqual(data['segments'][-1]['end'], 12)

    def test_string_numbers_accepted(self):
        data = self.post(total_rows='20', min_len='2', max_len='4',
                         preferred='3',
                         colors=[{'name': '米白', 'rows': '12'},
                                 {'name': '藏青', 'rows': '8'}])
        self.assertTrue(data['ok'])
        self.assertEqual(data['segment_count'], 7)

    def test_preferred_decimal_accepted(self):
        data = self.post(preferred='2.5')
        self.assertTrue(data['ok'])
        self.assertEqual(data['preferred'], 2.5)

    def test_tie_break_color_input_order(self):
        # 8 行、段长 1~4、库存充足、偏好 2.5：以颜色 0 开头与以颜色 1 开头
        # 的最优序列同分，按颜色输入顺序取颜色 0 开头
        data = self.post(total_rows=8, min_len=1, max_len=4, preferred=2.5,
                         colors=[{'name': '甲', 'rows': 8},
                                 {'name': '乙', 'rows': 8}])
        self.assertTrue(data['ok'])
        self.assertEqual(data['segments'][0]['color_index'], 0)
        self.assertEqual(data['segments'][0]['color'], '甲')

    def test_bad_total_rows(self):
        for bad in (0, 41, -1, 'x', 1.5, True, None):
            data = self.post(total_rows=bad)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'params', msg=repr(bad))
            self.assertNotIn('segments', data)

    def test_bad_length_bounds(self):
        for field in ('min_len', 'max_len'):
            for bad in (0, 7, -1, 'x', True, None, 1.5):
                data = self.post(**{field: bad})
                self.assertFalse(data['ok'], msg='{}={!r}'.format(field, bad))
                self.assertEqual(data['error']['type'], 'params')

    def test_min_greater_than_max(self):
        data = self.post(min_len=4, max_len=2)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'params')
        self.assertIn('不能大于', data['error']['message'])

    def test_bad_preferred(self):
        for bad in (0, -1, 'x', True, None):
            data = self.post(preferred=bad)
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'params')

    def test_colors_must_be_two_or_three(self):
        one = self.post(colors=[{'name': 'A', 'rows': 20}])
        self.assertFalse(one['ok'])
        self.assertEqual(one['error']['type'], 'colors')
        four = self.post(colors=[{'name': c, 'rows': 10}
                                 for c in ('A', 'B', 'C', 'D')])
        self.assertFalse(four['ok'])
        self.assertEqual(four['error']['type'], 'colors')
        empty = self.post(colors=[])
        self.assertFalse(empty['ok'])
        self.assertEqual(empty['error']['type'], 'colors')

    def test_colors_validation(self):
        missing_name = self.post(
            colors=[{'rows': 10}, {'name': 'B', 'rows': 10}])
        self.assertFalse(missing_name['ok'])
        self.assertEqual(missing_name['error']['type'], 'colors')

        duplicate = self.post(
            colors=[{'name': '红', 'rows': 10}, {'name': '红', 'rows': 10}])
        self.assertFalse(duplicate['ok'])
        self.assertEqual(duplicate['error']['type'], 'colors')
        self.assertIn('重复', duplicate['error']['message'])

        bad_rows = self.post(
            colors=[{'name': 'A', 'rows': -1}, {'name': 'B', 'rows': 10}])
        self.assertFalse(bad_rows['ok'])
        self.assertEqual(bad_rows['error']['type'], 'colors')

        not_list = self.post(colors={'name': 'A', 'rows': 10})
        self.assertFalse(not_list['ok'])
        self.assertEqual(not_list['error']['type'], 'colors')

    def test_infeasible_length_range(self):
        # 段长 4~6：7 行既放不下 1 段也至少需要 8 行才能排 2 段
        data = self.post(total_rows=7, min_len=4, max_len=6,
                         colors=[{'name': 'A', 'rows': 7},
                                 {'name': 'B', 'rows': 7}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['segment_count_min'], 2)
        self.assertEqual(data['segment_count_max'], 1)
        self.assertNotIn('segments', data)

    def test_infeasible_stock_shortage(self):
        data = self.post(
            colors=[{'name': '米白', 'rows': 8}, {'name': '藏青', 'rows': 7}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['total_stock'], 15)
        self.assertIn('还差 5 行', data['error']['message'])
        self.assertNotIn('segments', data)

    def test_infeasible_no_exact_cover(self):
        # 6 行、段长 3~5：需两段异色各 3 行，颜色 0 库存仅 2
        data = self.post(total_rows=6, min_len=3, max_len=5, preferred=3,
                         colors=[{'name': 'A', 'rows': 2},
                                 {'name': 'B', 'rows': 6}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['max_cover'], 5)
        self.assertIn('最多可连续覆盖 5 行', data['error']['message'])
        self.assertIn('不返回部分安排', data['error']['message'])
        self.assertNotIn('segments', data)


class TestSeamAlignApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def post(self, **overrides):
        payload = {'rows_a': 8, 'rows_b': 7}
        payload.update(overrides)
        return self.client.post('/api/seam-align', json=payload).get_json()

    def test_basic_alignment(self):
        data = self.post()
        self.assertTrue(data['ok'])
        self.assertEqual(data['rows_a'], 8)
        self.assertEqual(data['rows_b'], 7)
        self.assertEqual(data['step_count'], 7)
        self.assertEqual(data['cost'], 0.0089)  # 1/112
        moves = [(s['move_a'], s['move_b']) for s in data['steps']]
        self.assertEqual(moves,
                         [(1, 1), (1, 1), (1, 1), (2, 1),
                          (1, 1), (1, 1), (1, 1)])
        # move_label 供页面直接展示
        self.assertEqual(data['steps'][3]['move_label'], '(2,1)')

    def test_markers_chain_and_ranges(self):
        data = self.post(rows_a=10, rows_b=8, markers=[{'a': 3, 'b': 2}])
        self.assertTrue(data['ok'])
        # 完整标记链含起终点
        self.assertEqual(
            [(m['a'], m['b'], m['type']) for m in data['markers']],
            [(0, 0, 'start'), (3, 2, 'mark'), (10, 8, 'end')])
        self.assertEqual(len(data['intervals']), 2)
        self.assertEqual((data['intervals'][0]['a_rows'],
                          data['intervals'][0]['b_rows']), (3, 2))
        # 行号范围连续且恰好覆盖两侧全部行
        self.assertEqual(data['steps'][0]['a_from'], 1)
        self.assertEqual(data['steps'][-1]['a_to'], 10)
        self.assertEqual(data['steps'][-1]['b_to'], 8)
        covered_a = sum(s['a_to'] - s['a_from'] + 1 for s in data['steps'])
        covered_b = sum(s['b_to'] - s['b_from'] + 1 for s in data['steps'])
        self.assertEqual(covered_a, 10)
        self.assertEqual(covered_b, 8)
        # 路径在标记 (3,2) 落脚，且该步记录了经过的标记
        landing = [s for s in data['steps']
                   if any(m['a'] == 3 and m['b'] == 2 for m in s['markers'])]
        self.assertEqual(len(landing), 1)
        self.assertEqual((landing[0]['a_pos'], landing[0]['b_pos']), (3, 2))
        # 末步记录终点
        self.assertEqual(data['steps'][-1]['markers'],
                         [{'index': 2, 'a': 10, 'b': 8, 'type': 'end'}])

    def test_list_form_markers_and_string_numbers(self):
        data = self.post(rows_a='10', rows_b='8', markers=[['3', '2']])
        self.assertTrue(data['ok'])
        self.assertEqual(data['step_count'], 8)

    def test_missing_markers_defaults_to_none(self):
        data = self.post(rows_a=3, rows_b=3)
        self.assertTrue(data['ok'])
        self.assertEqual(
            [(m['a'], m['b'], m['type']) for m in data['markers']],
            [(0, 0, 'start'), (3, 3, 'end')])
        self.assertEqual([s['move_label'] for s in data['steps']],
                         ['(1,1)', '(1,1)', '(1,1)'])

    def test_bad_row_counts(self):
        for field in ('rows_a', 'rows_b'):
            for bad in (0, 61, -1, 'x', 1.5, True, None):
                data = self.post(**{field: bad})
                self.assertFalse(data['ok'], msg='{}={!r}'.format(field, bad))
                self.assertEqual(data['error']['type'], 'params',
                                 msg='{}={!r}'.format(field, bad))
                self.assertNotIn('steps', data)

    def test_bad_marker_form(self):
        data = self.post(markers=[{'a': 3}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')

        data = self.post(markers='3,2')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')

        data = self.post(markers=[[1, 2, 3]])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')

    def test_marker_must_be_strictly_interior(self):
        data = self.post(rows_a=10, rows_b=10, markers=[{'a': 10, 'b': 10}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')
        self.assertIn('内部点', data['error']['message'])

        data = self.post(rows_a=10, rows_b=10, markers=[{'a': 0, 'b': 1}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')

    def test_markers_must_strictly_increase_on_both_sides(self):
        # A 侧未严格递增
        data = self.post(rows_a=10, rows_b=10,
                         markers=[{'a': 5, 'b': 4}, {'a': 5, 'b': 6}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')
        self.assertIn('严格递增', data['error']['message'])
        # B 侧未严格递增
        data = self.post(rows_a=10, rows_b=10,
                         markers=[{'a': 4, 'b': 5}, {'a': 6, 'b': 5}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'markers')

    def test_infeasible_interval_reported_with_no_partial_route(self):
        data = self.post(rows_a=10, rows_b=3)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['interval_index'], 1)
        self.assertEqual((data['a_rows'], data['b_rows']), (10, 3))
        self.assertIn('无法衔接', data['error']['message'])
        self.assertIn('不返回部分路线', data['error']['message'])
        self.assertNotIn('steps', data)
        self.assertNotIn('intervals', data)

    def test_infeasible_interval_between_markers(self):
        # (1,5) 使第 1 区间为 (1,5)，比例 5:1 无法衔接
        data = self.post(rows_a=10, rows_b=10, markers=[{'a': 1, 'b': 5}])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['interval_index'], 1)
        self.assertEqual((data['a_from'], data['b_from']), (0, 0))
        self.assertEqual((data['a_to'], data['b_to']), (1, 5))
        self.assertNotIn('steps', data)

    def test_boundary_ratio_two_is_feasible(self):
        data = self.post(rows_a=10, rows_b=5)
        self.assertTrue(data['ok'])
        self.assertEqual(data['step_count'], 5)
        self.assertTrue(all(s['move_label'] == '(2,1)' for s in data['steps']))
        self.assertEqual(data['cost'], 0.0)

    def test_even_sides_cost_zero(self):
        data = self.post(rows_a=6, rows_b=6)
        self.assertTrue(data['ok'])
        self.assertEqual(data['cost'], 0.0)
        self.assertTrue(all(s['move_label'] == '(1,1)' for s in data['steps']))


class TestBoardLayoutApi(unittest.TestCase):
    PIECES = [
        {'name': '后片', 'width': 40, 'height': 32, 'rotate': False},
        {'name': '左前片', 'width': 20, 'height': 32, 'rotate': True},
        {'name': '右前片', 'width': 20, 'height': 32, 'rotate': True},
        {'name': '袖子A', 'width': 34, 'height': 14, 'rotate': True},
        {'name': '袖子B', 'width': 34, 'height': 14, 'rotate': True},
    ]

    def setUp(self):
        self.client = app.test_client()

    def post(self, **overrides):
        payload = {
            'board_width': 90,
            'board_height': 60,
            'gap': 3,
            'pieces': [dict(p) for p in self.PIECES],
        }
        payload.update(overrides)
        return self.client.post('/api/board-layout', json=payload).get_json()

    def test_basic_layout(self):
        data = self.post()
        self.assertTrue(data['ok'])
        self.assertEqual(data['used_height'], 49)
        self.assertEqual(data['layer_count'], 2)
        self.assertEqual(len(data['layers']), 2)
        self.assertEqual([l['height'] for l in data['layers']], [32, 14])
        self.assertEqual([l['width'] for l in data['layers']], [86, 71])
        # 各片左上角坐标与最终朝向
        expected = [
            ('后片', 1, 0, 0, 40, 32, False),
            ('左前片', 1, 43, 0, 20, 32, False),
            ('右前片', 1, 66, 0, 20, 32, False),
            ('袖子A', 2, 0, 35, 34, 14, False),
            ('袖子B', 2, 37, 35, 34, 14, False),
        ]
        for piece, (name, layer, x, y, w, h, rotated) in zip(
                data['pieces'], expected):
            self.assertEqual(piece['name'], name)
            self.assertEqual(piece['layer'], layer)
            self.assertEqual((piece['x'], piece['y']), (x, y))
            self.assertEqual((piece['width'], piece['height']), (w, h))
            self.assertEqual(piece['rotated'], rotated)

    def test_rotation_used_when_beneficial(self):
        # 两片 20×10 可旋转：都旋转后同层宽 20≤25，占用高度 20
        data = self.post(board_width=25, board_height=25, gap=0, pieces=[
            {'name': 'A', 'width': 20, 'height': 10, 'rotate': True},
            {'name': 'B', 'width': 20, 'height': 10, 'rotate': True},
        ])
        self.assertTrue(data['ok'])
        self.assertEqual(data['used_height'], 20)
        self.assertEqual(data['layer_count'], 1)
        self.assertTrue(all(p['rotated'] for p in data['pieces']))

    def test_height_insufficient_no_partial_layout(self):
        data = self.post(board_height=45)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['reason'], 'height')
        self.assertEqual(data['min_height'], 49)
        self.assertIn('板高不足', data['error']['message'])
        self.assertIn('不返回部分摆放', data['error']['message'])
        self.assertNotIn('pieces', data)
        self.assertNotIn('layers', data)

    def test_width_insufficient_reports_piece(self):
        data = self.post(pieces=[
            {'name': '超宽片', 'width': 95, 'height': 10, 'rotate': False},
            {'name': '小片', 'width': 10, 'height': 10, 'rotate': True},
        ])
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'infeasible')
        self.assertEqual(data['reason'], 'width')
        self.assertIn('板宽不足', data['error']['message'])
        self.assertIn('超宽片', data['error']['message'])
        self.assertIn('不返回部分摆放', data['error']['message'])
        self.assertEqual(len(data['unfit_pieces']), 1)
        unfit = data['unfit_pieces'][0]
        self.assertEqual(unfit['name'], '超宽片')
        self.assertFalse(unfit['width_ok'])
        self.assertTrue(unfit['height_ok'])
        self.assertNotIn('pieces', data)

    def test_jointly_unfit_piece_reports_both(self):
        # 6×12 可旋转、板 10×10：不旋转超高、旋转后超宽
        data = self.post(board_width=10, board_height=10, gap=0, pieces=[
            {'name': '尴尬片', 'width': 6, 'height': 12, 'rotate': True},
            {'name': '小片', 'width': 3, 'height': 3, 'rotate': False},
        ])
        self.assertFalse(data['ok'])
        self.assertEqual(data['reason'], 'both')
        self.assertIn('板宽与板高不足', data['error']['message'])
        self.assertNotIn('pieces', data)

    def test_bad_board_params(self):
        for overrides in [
            {'board_width': 0}, {'board_width': -5}, {'board_width': 'abc'},
            {'board_width': True}, {'board_height': 0}, {'board_height': 2.5},
            {'gap': -1}, {'gap': 'x'},
        ]:
            data = self.post(**overrides)
            self.assertFalse(data['ok'], msg=repr(overrides))
            self.assertEqual(data['error']['type'], 'params', msg=repr(overrides))

    def test_string_numbers_accepted(self):
        data = self.post(board_width='90', board_height='60', gap='3')
        self.assertTrue(data['ok'])
        self.assertEqual(data['used_height'], 49)

    def test_bad_pieces(self):
        too_many = [dict(p) for p in self.PIECES] + [
            {'name': '额外1', 'width': 5, 'height': 5, 'rotate': True},
            {'name': '额外2', 'width': 5, 'height': 5, 'rotate': True}]
        for pieces in [
            [], [{'name': '独片', 'width': 5, 'height': 5, 'rotate': True}],
            too_many,
            [{'name': '', 'width': 5, 'height': 5, 'rotate': True}] * 2,
            [{'name': 'A', 'width': 0, 'height': 5, 'rotate': True},
             {'name': 'B', 'width': 5, 'height': 5, 'rotate': True}],
            [{'name': 'A', 'width': 5, 'height': 5},
             {'name': 'B', 'width': 5, 'height': 5, 'rotate': True}],
            [{'name': 'A', 'width': 5, 'height': 5, 'rotate': 'yes'},
             {'name': 'B', 'width': 5, 'height': 5, 'rotate': True}],
            'not-a-list',
        ]:
            data = self.post(pieces=pieces)
            self.assertFalse(data['ok'], msg=repr(pieces))
            self.assertEqual(data['error']['type'], 'pieces', msg=repr(pieces))


if __name__ == '__main__':
    unittest.main()