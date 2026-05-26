/**
 * tts.js — 全局 Web Speech API 封装
 * 暴露：
 *   - window.ttsAvailable(): boolean
 *   - window.speakWord(text, opts?): void
 *
 * 浏览器降级：若 speechSynthesis 不可用，speakWord 静默返回；
 * 页面上的 .btn-tts 会在 DOMContentLoaded 时被自动禁用并设置 tooltip。
 */
(function() {
  'use strict';

  function ttsAvailable() {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
           && typeof window.SpeechSynthesisUtterance === 'function';
  }

  function speakWord(text, opts) {
    if (!ttsAvailable()) return;
    if (!text || typeof text !== 'string') return;

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
})();
