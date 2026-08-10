/**
 * tts.js — 全局 Web Speech API 封装
 * 暴露：
 *   - window.ttsAvailable(): boolean
 *   - window.speakWord(text, opts?): void
 *   - window.pickBestVoice(): SpeechSynthesisVoice|null  (调试用)
 *
 * 浏览器降级：
 *   • 完全不支持 speechSynthesis  → speakWord 静默返回，按钮被禁用
 *   • 支持但无英文语音包          → 用户点 🔊 时弹出引导 Toast（同会话仅一次）
 *
 * 音质优化：
 *   不同浏览器默认挑的 voice 质量差异巨大（Chrome on macOS 默认 Google US English
 *   音质很差）。本脚本主动按优先级挑选高品质本地神经网络音色：
 *     1. macOS Siri 系列：Samantha / Alex / Daniel / Karen / Moira / Tessa / Fiona
 *     2. Windows / 微软 Neural：name 含 "Natural" 或 "Neural"
 *     3. 任意 localService=true 的 en-* voice
 *     4. 兜底：第一个 en-* voice
 */
(function() {
  'use strict';

  var _hasEnglishVoice = null;  // null = 还在检测；true/false = 检测完成
  var _bestVoice = null;        // 缓存挑选结果，voiceschanged 时刷新

  // macOS 系统高品质音色名单（按主观音质排序，Samantha 最佳）
  var MACOS_PREMIUM_VOICES = [
    'Samantha', 'Alex', 'Daniel', 'Karen', 'Moira', 'Tessa', 'Fiona',
    'Veena', 'Rishi', 'Aaron', 'Nicky'
  ];

  function ttsAvailable() {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
           && typeof window.SpeechSynthesisUtterance === 'function';
  }

  function _isEnglishVoice(v) {
    return v && v.lang && v.lang.toLowerCase().indexOf('en') === 0;
  }

  function pickBestVoice() {
    if (!ttsAvailable()) return null;
    var voices;
    try {
      voices = window.speechSynthesis.getVoices() || [];
    } catch (e) {
      return null;
    }
    var enVoices = voices.filter(_isEnglishVoice);
    if (enVoices.length === 0) return null;

    // 第一档：macOS Siri 高品质音色（按名单顺序优先）
    for (var i = 0; i < MACOS_PREMIUM_VOICES.length; i++) {
      var target = MACOS_PREMIUM_VOICES[i];
      var found = enVoices.find(function(v) {
        return v.name && v.name.indexOf(target) !== -1;
      });
      if (found) return found;
    }

    // 第二档：Windows / 微软神经网络音色（含 Natural / Neural 关键字）
    var neural = enVoices.find(function(v) {
      var n = (v.name || '').toLowerCase();
      return n.indexOf('natural') !== -1 || n.indexOf('neural') !== -1;
    });
    if (neural) return neural;

    // 第三档：任意本地音色（避开云端 Google US English 这类低质音色）
    var local = enVoices.find(function(v) { return v.localService === true; });
    if (local) return local;

    // 兜底：第一个英文 voice
    return enVoices[0];
  }

  function _detectEnglishVoice() {
    if (!ttsAvailable()) {
      _hasEnglishVoice = false;
      _bestVoice = null;
      return;
    }
    try {
      var voices = window.speechSynthesis.getVoices() || [];
      _hasEnglishVoice = voices.some(_isEnglishVoice);
      _bestVoice = pickBestVoice();
      if (_bestVoice && window.console && console.debug) {
        console.debug('[tts] picked voice:', _bestVoice.name, '|', _bestVoice.lang,
                      '|', _bestVoice.localService ? 'local' : 'remote');
      }
    } catch (e) {
      _hasEnglishVoice = false;
      _bestVoice = null;
    }
  }

  function _showTtsToast() {
    // 同会话仅弹一次
    try {
      if (sessionStorage.getItem('tts_warning_shown') === '1') return;
      sessionStorage.setItem('tts_warning_shown', '1');
    } catch (e) { /* sessionStorage 不可用就让它弹 */ }

    var toast = document.getElementById('ttsToast');
    if (!toast) return;
    toast.hidden = false;
    // 触发渐显动画
    requestAnimationFrame(function() {
      toast.classList.add('tts-toast--visible');
    });

    var closeBtn = document.getElementById('ttsToastClose');
    function close() {
      toast.classList.remove('tts-toast--visible');
      setTimeout(function() { toast.hidden = true; }, 200);
    }
    if (closeBtn) {
      closeBtn.addEventListener('click', close, { once: true });
    }
    // 点击 backdrop 也能关
    toast.addEventListener('click', function(e) {
      if (e.target === toast) close();
    }, { once: true });
  }

  function speakWord(text, opts) {
    if (!ttsAvailable()) return;
    if (!text || typeof text !== 'string') return;

    // 没英文语音包 → 引导用户而不是静默失败
    if (_hasEnglishVoice === false) {
      _showTtsToast();
      return;
    }

    try {
      window.speechSynthesis.cancel();
    } catch (e) { /* noop */ }

    // 加 50ms 缓冲，避免 cancel() 与 speak() 抢占导致首声丢失
    setTimeout(function() {
      try {
        var u = new SpeechSynthesisUtterance(text);
        u.lang = (opts && opts.lang) || 'en-US';
        u.rate = (opts && typeof opts.rate === 'number') ? opts.rate : 0.9;
        u.pitch = (opts && typeof opts.pitch === 'number') ? opts.pitch : 1.0;
        u.volume = 1.0;
        // 优先使用挑选出来的高品质音色（避免 Chrome 默认那个刺耳的 Google US English）
        var v = _bestVoice || pickBestVoice();
        if (v) {
          u.voice = v;
          u.lang = v.lang || u.lang;  // 强制语言与 voice 对齐，避免 Chrome 偷换 voice
        }
        window.speechSynthesis.speak(u);
      } catch (e) {
        console.warn('[tts] speak failed:', e);
      }
    }, 50);
  }

  // 浏览器不支持时：禁用所有 .btn-tts 并加 tooltip
  function decoratePageButtons() {
    if (ttsAvailable()) return;
    document.querySelectorAll('.btn-tts').forEach(function(btn) {
      btn.disabled = true;
      btn.setAttribute('title', '当前浏览器不支持发音功能');
    });
  }

  // 同步检测一次（部分浏览器同步返回）+ 异步事件再检测一次
  _detectEnglishVoice();
  if (ttsAvailable()) {
    try {
      window.speechSynthesis.onvoiceschanged = _detectEnglishVoice;
    } catch (e) { /* noop */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', decoratePageButtons);
  } else {
    decoratePageButtons();
  }

  // 页面卸载时停止播放
  window.addEventListener('beforeunload', function() {
    try { window.speechSynthesis.cancel(); } catch (e) {}
  });

  window.ttsAvailable = ttsAvailable;
  window.speakWord = speakWord;
  window.pickBestVoice = pickBestVoice;
})();
