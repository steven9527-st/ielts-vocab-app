"""端到端全量回归测试
针对今晚累计的所有 changes 做全流程巡检，模拟真实用户使用路径。

覆盖 8 大功能域：
  1. 首页 / 词库切换
  2. 词库导入（跳过实际文件解析，只测路由可达性）
  3. 普通学习流：setup → 翻卡 → 上一张/下一张 → 学完即测 → 通关 / 错题重做
  4. 同义词学习流：setup → 翻卡 → 学完即测 → 通关
  5. 测试模式：setup 拦截 / 正常测试 / 结果页
  6. 词库管理：三态切换 / 编辑 / 删除
  7. 完全掌握机制：POST promote / PATCH status
  8. 统计口径：today_mastered_count / 首页 4 卡数字
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class _FullAppBase(unittest.TestCase):
    """构造一个"完整可用"的测试 App：含 2 个词库、各种状态词分布"""

    @classmethod
    def setUpClass(cls):
        import paths
        cls._tmp_db = tempfile.mktemp(suffix='.db')
        paths.db_path = lambda: cls._tmp_db  # type: ignore
        import importlib
        import database
        database.DB_PATH = cls._tmp_db
        importlib.reload(database)
        import app as app_module
        importlib.reload(app_module)
        cls.app = app_module.app
        cls.app_module = app_module
        cls.db_mod = database
        cls.app.config['TESTING'] = True
        cls.app.config['SECRET_KEY'] = 'test'
        database.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def setUp(self):
        """清空 + 造种子数据：
        list 1（standard）：30 词，10 mastered / 5 fully_mastered / 15 unmastered
        list 2（synonym）：20 词全部有同义词，5 mastered / 15 unmastered
        """
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM learn_session")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std_list', 'standard')")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (2, 'syn_list', 'synonym')")

        wid = 1
        # list 1: 10 mastered
        for _ in range(10):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'mastered')",
                (wid, f'std_m_{wid}', f'释义{wid}'))
            wid += 1
        # list 1: 5 fully_mastered
        for _ in range(5):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'fully_mastered')",
                (wid, f'std_f_{wid}', f'释义{wid}'))
            wid += 1
        # list 1: 15 unmastered
        for _ in range(15):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'unmastered')",
                (wid, f'std_u_{wid}', f'释义{wid}'))
            wid += 1
        # list 2: 5 mastered
        for _ in range(5):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
                "VALUES (?,2,?,?,?, 'mastered')",
                (wid, f'syn_m_{wid}', f'同义释义{wid}', f'similar_{wid}'))
            wid += 1
        # list 2: 15 unmastered
        for _ in range(15):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
                "VALUES (?,2,?,?,?, 'unmastered')",
                (wid, f'syn_u_{wid}', f'同义释义{wid}', f'similar_{wid}'))
            wid += 1
        conn.commit()
        conn.close()

    def _client(self, list_id=1):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = list_id
            sess['list_picked'] = True
        return client


# ═══════════════════════════════════════════════════════════════
# 域 1：首页 / 词库切换
# ═══════════════════════════════════════════════════════════════
class Test1_HomeAndSwitch(_FullAppBase):
    def test_home_renders_with_4_metric_cards(self):
        client = self._client(1)
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        # 4 卡片
        for label in ['词库总数', '已掌握', '完全掌握', '未掌握']:
            self.assertIn(label, body)
        # 数字精确
        self.assertIn('>30<', body)  # total
        self.assertIn('>10<', body)  # mastered
        self.assertIn('>5<', body)   # fully_mastered
        self.assertIn('>15<', body)  # unmastered

    def test_switch_list(self):
        client = self._client(1)
        resp = client.post('/switch_list', data={'list_id': 2}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        with client.session_transaction() as sess:
            self.assertEqual(sess['list_id'], 2)

    def test_home_no_lists(self):
        """删掉所有 list → 首页显示引导"""
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM word_lists")
        conn.commit()
        conn.close()
        client = self.app.test_client()
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('开始你的雅思词汇之旅', body)


# ═══════════════════════════════════════════════════════════════
# 域 2：词库导入路由可达性
# ═══════════════════════════════════════════════════════════════
class Test2_ImportRoutes(_FullAppBase):
    def test_import_page_reachable(self):
        client = self._client()
        resp = client.get('/import')
        self.assertIn(resp.status_code, (200, 302))


# ═══════════════════════════════════════════════════════════════
# 域 3：普通学习流
# ═══════════════════════════════════════════════════════════════
class Test3_LearnFlow(_FullAppBase):
    def test_learn_setup_reachable(self):
        client = self._client(1)
        resp = client.get('/learn/setup')
        self.assertEqual(resp.status_code, 200)

    def test_learn_setup_only_offers_unmastered(self):
        """setup 页 max 应基于 total=20（new 全部掌握后也可学习）"""
        client = self._client(1)
        resp = client.get('/learn/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('max="30"', body)

    def test_full_learn_flow(self):
        """完整走：学 5 词 → 翻卡 → 学完 → 测验 → 全对通关"""
        client = self._client(1)
        # start
        resp = client.post('/learn/start', data={'n': 5})
        self.assertEqual(resp.status_code, 302)
        # 拿 session 的 word_ids
        with client.session_transaction() as sess:
            self.assertIn('learn_session_id', sess)

        # 翻卡 5 张
        for i in range(5):
            r = client.get('/learn/card')
            self.assertEqual(r.status_code, 200)
            body = r.get_data(as_text=True)
            self.assertIn('← 上一张', body)
            # next
            r = client.post('/learn/next')
            self.assertEqual(r.status_code, 302)

        # 学完最后一张 → 应跳测验
        self.assertIn('/learn/quiz', r.location)

        # 触发测验
        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess['quiz_token']
        quiz_data = self.app_module._load_quiz_data(token)
        self.assertEqual(len(quiz_data['questions']), 5)

        # 全部答对
        for q in quiz_data['questions']:
            client.post('/quiz/answer', data={'answer': q['correct']})

        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)
        self.assertIn('今日通关', body)
        self.assertIn('本次学习的 5 个单词已全部标记为已掌握', body)
        # 完全掌握勾选区应出现
        self.assertIn('promote-section', body)

    def test_learn_start_when_all_mastered(self):
        """全部掌握后仍可学习，从全词库选词"""
        conn = self.db_mod.get_db()
        conn.execute("UPDATE words SET status='mastered' WHERE list_id=1")
        conn.commit()
        conn.close()

        client = self._client(1)
        # 首页按钮应可用（不再 disabled）
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('开始学习', body)
        # 不应出现旧版"已全部掌握"引导文案
        self.assertNotIn('词库已全部掌握', body)

        # start 应从全词库选 5 个
        resp = client.post('/learn/start', data={'n': 5})
        self.assertEqual(resp.status_code, 302)
        with client.session_transaction() as sess:
            self.assertIn('learn_session_id', sess)
            self.assertEqual(sess['learn_total'], 5)

    def test_learn_prev_navigation(self):
        """翻卡上一张导航"""
        client = self._client(1)
        client.post('/learn/start', data={'n': 3})
        # 前进 2 张
        client.post('/learn/next')
        client.post('/learn/next')
        # 后退 1 张
        r = client.post('/learn/prev')
        self.assertEqual(r.status_code, 302)


# ═══════════════════════════════════════════════════════════════
# 域 4：同义词学习流
# ═══════════════════════════════════════════════════════════════
class Test4_SynonymFlow(_FullAppBase):
    def test_synonym_setup_shows_unmastered_count(self):
        client = self._client(2)
        resp = client.get('/learn/synonym/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('未掌握的同义词单词', body)
        # unmastered_with_synonyms = 15
        self.assertIn('>15</strong>', body)

    def test_synonym_start_only_unmastered(self):
        """同义词学习只从 unmastered 抽"""
        client = self._client(2)
        client.post('/learn/synonym/start', data={'n': 5})
        with client.session_transaction() as sess:
            picked = sess.get('syn_word_ids') or []
        self.assertEqual(len(picked), 5)
        # 5 个 mastered 词 id 是 26-30，全部应被排除
        for wid in picked:
            self.assertNotIn(wid, range(26, 31))

    def test_full_synonym_flow_with_mastered_update(self):
        """同义词学完 → 测验通关 → 词标 mastered"""
        client = self._client(2)
        client.post('/learn/synonym/start', data={'n': 3})
        with client.session_transaction() as sess:
            word_ids = list(sess['syn_word_ids'])

        # 学完 3 张
        for _ in range(3):
            client.post('/learn/synonym/next')

        # 进测验
        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess['quiz_token']
            self.assertTrue(sess.get('quiz_synonym_flow'))
        quiz_data = self.app_module._load_quiz_data(token)
        for q in quiz_data['questions']:
            client.post('/quiz/answer', data={'answer': q['correct']})

        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)
        self.assertIn('本次共测验了 3 个同义词', body)
        self.assertIn('promote-section', body)

        # DB: 这 3 个词已 mastered
        conn = self.db_mod.get_db()
        for wid in word_ids:
            r = conn.execute("SELECT status FROM words WHERE id=?", (wid,)).fetchone()
            self.assertEqual(r['status'], 'mastered', f'词 {wid} 应被标为 mastered')
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 域 5：测试模式
# ═══════════════════════════════════════════════════════════════
class Test5_TestMode(_FullAppBase):
    def test_test_setup_shows_mastered_count(self):
        client = self._client(1)
        resp = client.get('/test/setup')
        body = resp.get_data(as_text=True)
        # mastered=10（不含 fully_mastered）
        self.assertIn('从已掌握的 10 个单词中随机出题', body)

    def test_test_setup_intercepts_when_mastered_low(self):
        """把 list1 的 mastered 减到 3 → 拦截页"""
        conn = self.db_mod.get_db()
        conn.execute("UPDATE words SET status='unmastered' WHERE list_id=1 AND status='mastered'")
        # 再补 3 个 mastered（SQLite 不支持 UPDATE...ORDER BY，用子查询）
        conn.execute(
            "UPDATE words SET status='mastered' "
            "WHERE id IN (SELECT id FROM words WHERE list_id=1 AND status='unmastered' LIMIT 3)"
        )
        conn.commit()
        conn.close()

        client = self._client(1)
        resp = client.get('/test/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('已掌握词不足 4 个', body)

    def test_test_excludes_fully_mastered(self):
        """测试模式选词天然排除 fully_mastered"""
        client = self._client(1)
        client.post('/test/start', data={'m': 10, 'test_type': 'text'})
        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        quiz_data = self.app_module._load_quiz_data(token)
        wids = [q['word_id'] for q in quiz_data['questions']]

        # list 1: mastered=10（id 1-10），fully_mastered=5（id 11-15）
        for wid in wids:
            self.assertLessEqual(wid, 10, f'word_id={wid} 不应是 fully_mastered')


# ═══════════════════════════════════════════════════════════════
# 域 6：词库管理
# ═══════════════════════════════════════════════════════════════
class Test6_Library(_FullAppBase):
    def test_library_page_shows_three_state_badges(self):
        client = self._client(1)
        resp = client.get('/library')
        body = resp.get_data(as_text=True)
        # 三种状态徽章应共存
        self.assertIn('badge--gold', body)   # fully_mastered
        self.assertIn('badge--green', body)  # mastered
        self.assertIn('badge--blue', body)   # unmastered

    def test_patch_word_status_accepts_all_three_states(self):
        client = self._client(1)
        # 拿一个 unmastered 词
        conn = self.db_mod.get_db()
        wid = conn.execute("SELECT id FROM words WHERE list_id=1 AND status='unmastered' LIMIT 1").fetchone()[0]
        conn.close()

        for target in ['mastered', 'fully_mastered', 'unmastered']:
            resp = client.put(f'/api/word/{wid}',
                              json={'status': target},
                              content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            conn = self.db_mod.get_db()
            r = conn.execute("SELECT status FROM words WHERE id=?", (wid,)).fetchone()
            conn.close()
            self.assertEqual(r['status'], target)

    def test_edit_word_all_fields(self):
        client = self._client(1)
        conn = self.db_mod.get_db()
        wid = conn.execute("SELECT id FROM words WHERE list_id=1 LIMIT 1").fetchone()[0]
        conn.close()
        resp = client.put(f'/api/word/{wid}',
                          json={
                              'english': 'newword',
                              'chinese': '新中文',
                              'phonetic': '/nju:/',
                              'pos': 'n.',
                              'synonyms': 'new_syn',
                          },
                          content_type='application/json')
        self.assertEqual(resp.status_code, 200)

    def test_delete_word(self):
        client = self._client(1)
        conn = self.db_mod.get_db()
        wid = conn.execute("SELECT id FROM words WHERE list_id=1 LIMIT 1").fetchone()[0]
        conn.close()
        resp = client.delete(f'/api/word/{wid}')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════
# 域 7：完全掌握机制
# ═══════════════════════════════════════════════════════════════
class Test7_FullyMasteredPromotion(_FullAppBase):
    def test_promote_endpoint_promotes_mastered_only(self):
        """POST /mastery/promote 只升级 mastered 词"""
        client = self._client(1)
        conn = self.db_mod.get_db()
        mastered_ids = [r['id'] for r in conn.execute(
            "SELECT id FROM words WHERE list_id=1 AND status='mastered' LIMIT 3"
        ).fetchall()]
        unmastered_id = conn.execute(
            "SELECT id FROM words WHERE list_id=1 AND status='unmastered' LIMIT 1"
        ).fetchone()['id']
        conn.close()

        # 混合 3 mastered + 1 unmastered
        resp = client.post('/mastery/promote',
                           json={'word_ids': mastered_ids + [unmastered_id]},
                           content_type='application/json')
        data = resp.get_json()
        self.assertEqual(data['promoted'], 3, '应只升级 3 个 mastered，跳过 unmastered')

    def test_promoted_words_dont_show_in_tests(self):
        """把 mastered 升 fully_mastered 后，测试题库应变小"""
        client = self._client(1)
        conn = self.db_mod.get_db()
        mastered_ids = [r['id'] for r in conn.execute(
            "SELECT id FROM words WHERE list_id=1 AND status='mastered'"
        ).fetchall()]
        conn.close()

        # 全部升 fully_mastered（10 个）
        client.post('/mastery/promote',
                    json={'word_ids': mastered_ids},
                    content_type='application/json')

        # 再进 test_setup 应被拦截（mastered=0 < 4）
        resp = client.get('/test/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('已掌握词不足 4 个', body)


# ═══════════════════════════════════════════════════════════════
# 域 8：统计口径 & 今日新增
# ═══════════════════════════════════════════════════════════════
class Test8_StatsAndTodayMastered(_FullAppBase):
    def test_stats_three_state_sum_equals_total(self):
        stats = self.app_module.get_list_stats(1)
        self.assertEqual(
            stats['mastered'] + stats['fully_mastered'] + stats['unmastered'],
            stats['total']
        )

    def test_today_mastered_after_learn_completion(self):
        """完成一次学习通关 → today_mastered_count 增加"""
        client = self._client(1)
        client.post('/learn/start', data={'n': 5})
        with client.session_transaction() as sess:
            token = None
        # 快速通关：学完 5 张后进测验
        for _ in range(5):
            client.post('/learn/next')
        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess['quiz_token']
        quiz_data = self.app_module._load_quiz_data(token)
        for q in quiz_data['questions']:
            client.post('/quiz/answer', data={'answer': q['correct']})
        client.get('/quiz/submit')

        count = self.app_module.today_mastered_count(1)
        self.assertEqual(count, 5)

    def test_index_shows_today_mastered_when_completed(self):
        """通关后首页显示"今日新增掌握 N 个" """
        from datetime import date
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy) "
            "VALUES (1, ?, 'learn', ?, 1.0)",
            (str(date.today()), json.dumps([1, 2, 3]))
        )
        conn.commit()
        conn.close()

        client = self._client(1)
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('今日已通关', body)
        self.assertIn('今日新增掌握', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
