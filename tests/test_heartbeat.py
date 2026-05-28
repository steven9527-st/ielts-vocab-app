"""单元测试：心跳机制（fix-app-lifecycle）

覆盖：
  • POST /api/heartbeat 返回 {ok: True}
  • before_request 钩子刷新 _last_heartbeat 时间戳
  • 任何路由请求都隐式刷新心跳（不仅 /api/heartbeat）
"""

import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestHeartbeat(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 用临时 DB 隔离
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
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def test_heartbeat_route_returns_ok(self):
        client = self.app.test_client()
        resp = client.post('/api/heartbeat')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('ok'))

    def test_heartbeat_route_updates_timestamp(self):
        client = self.app.test_client()

        # 手动把时间戳拨回过去 100 秒
        with self.app_module._heartbeat_lock:
            self.app_module._last_heartbeat = time.time() - 100
        old = self.app_module._last_heartbeat

        # 发心跳
        resp = client.post('/api/heartbeat')
        self.assertEqual(resp.status_code, 200)

        # 时间戳应该被刷新
        with self.app_module._heartbeat_lock:
            new = self.app_module._last_heartbeat
        self.assertGreater(new, old, '心跳后时间戳未刷新')

    def test_any_request_refreshes_heartbeat(self):
        """before_request 钩子让任何路由都隐式续命"""
        client = self.app.test_client()

        with self.app_module._heartbeat_lock:
            self.app_module._last_heartbeat = time.time() - 100
        old = self.app_module._last_heartbeat

        # 发一个完全无关的请求（首页）
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)

        with self.app_module._heartbeat_lock:
            new = self.app_module._last_heartbeat
        self.assertGreater(new, old, '普通请求未刷新心跳')

    def test_watchdog_function_exists(self):
        """守护线程函数应存在但未被自动启动（开发模式）"""
        self.assertTrue(hasattr(self.app_module, '_start_heartbeat_watchdog'))
        self.assertTrue(callable(self.app_module._start_heartbeat_watchdog))


if __name__ == '__main__':
    unittest.main(verbosity=2)
