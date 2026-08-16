/* ============================================
   星衍AI · 离线语音识别（sherpa-onnx WASM）
   断网时手机浏览器本地识别，无需服务器
   ============================================ */

(function (global) {
  'use strict';

  // sherpa-onnx WASM 资源（首次联网时预下载缓存）
  const WASM_BASE = '/wasm';
  const MODEL_URLS = {
    // 中文流式 Zipformer 小模型（约 15MB）
    encoder: `${WASM_BASE}/encoder.onnx`,
    decoder: `${WASM_BASE}/decoder.onnx`,
    joiner: `${WASM_BASE}/joiner.onnx`,
    tokens: `${WASM_BASE}/tokens.txt`,
  };

  let _offlineAsr = null;
  let _recognizer = null;
  let _stream = null;
  let _modelLoaded = false;

  // ─── sherpa-onnx 加载（动态 import WASM 模块）───
  async function loadSherpaOnnx() {
    if (_offlineAsr) return _offlineAsr;

    // 动态加载 sherpa-onnx 浏览器版（通过 CDN 或本地）
    const script = document.createElement('script');
    script.src = `${WASM_BASE}/sherpa-onnx-wasm.js`;
    script.async = true;
    await new Promise((resolve, reject) => {
      script.onload = resolve;
      script.onerror = () => reject(new Error('sherpa-onnx WASM 加载失败'));
      document.head.appendChild(script);
    });

    _offlineAsr = global.sherpa_onnx;
    return _offlineAsr;
  }

  // ─── 加载模型 ───
  async function loadOfflineModel(progress) {
    if (_modelLoaded) return true;

    try {
      const sherpa = await loadSherpaOnnx();
      if (!sherpa) throw new Error('sherpa-onnx 不可用');

      const config = {
        'feat-config': {
          'sample-rate': 16000,
          'feature-dim': 80,
        },
        'model-config': {
          'encoder-filename': MODEL_URLS.encoder,
          'decoder-filename': MODEL_URLS.decoder,
          'joiner-filename': MODEL_URLS.joiner,
          'tokens-filename': MODEL_URLS.tokens,
          'num-threads': 2,
          'provider': 'wasm',
          'debug': 1,
        },
        'enable-endpoint-detection': true,
        'rule1-min-trailing-silence': 2.4,
        'rule2-min-trailing-silence': 1.2,
        'rule3-min-utterance-length': 300,
      };

      _recognizer = sherpa.createOnlineRecognizer(config);
      _modelLoaded = true;
      console.log('[OfflineASR] 模型加载成功');
      return true;
    } catch (e) {
      console.error('[OfflineASR] 模型加载失败:', e);
      return false;
    }
  }

  // ─── 录音并识别（一次性）───
  async function recognizeOffline(audioData, sampleRate = 16000) {
    if (!_recognizer) {
      const ok = await loadOfflineModel();
      if (!ok) return { ok: false, text: '', error: '离线模型未加载' };
    }

    try {
      _stream = _recognizer.createStream();
      const samples = new Float32Array(audioData);

      // 分块喂入音频
      const chunkSize = 1600; // 100ms
      let text = '';
      for (let i = 0; i < samples.length; i += chunkSize) {
        const chunk = samples.subarray(i, i + chunkSize);
        _stream.acceptWaveform({ sampleRate, samples: chunk });

        // 获取解码结果
        const result = _recognizer.isReady(_stream)
          ? _recognizer.getResult(_stream)
          : '';
        if (result && result.text) {
          text = result.text;
        }

        // 端点检测：静音足够长时结束
        if (_recognizer.isEndpointDetected(_stream)) {
          const final = _recognizer.getResult(_stream);
          if (final && final.text) text = final.text;
          break;
        }
      }

      // 获取最终结果
      const finalResult = _recognizer.getResult(_stream);
      if (finalResult && finalResult.text) text = finalResult.text;

      _stream = null;
      return { ok: true, text };
    } catch (e) {
      console.error('[OfflineASR] 识别失败:', e);
      return { ok: false, text: '', error: e.message };
    }
  }

  // ─── 录音（MediaRecorder → PCM）───
  async function recordOfflineAudio(maxDuration = 30) {
    return new Promise(async (resolve, reject) => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        });

        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtx.createMediaStreamSource(stream);

        // 采样到 16kHz 单声道
        const sampleRate = 16000;
        const bufferSize = 4096;
        const recorder = audioCtx.createScriptProcessor(bufferSize, 1, 1);
        const pcmChunks = [];

        recorder.onaudioprocess = (e) => {
          const input = e.inputBuffer.getChannelData(0);
          // 降采样到 16kHz
          const ratio = audioCtx.sampleRate / sampleRate;
          const out = new Float32Array(Math.floor(input.length / ratio));
          for (let i = 0; i < out.length; i++) {
            out[i] = input[Math.floor(i * ratio)];
          }
          pcmChunks.push(out);
        };

        source.connect(recorder);
        recorder.connect(audioCtx.destination);

        // 自动停止
        setTimeout(() => {
          source.disconnect();
          recorder.disconnect();
          stream.getTracks().forEach((t) => t.stop());
          audioCtx.close();

          // 合并 PCM
          const totalLen = pcmChunks.reduce((sum, c) => sum + c.length, 0);
          const merged = new Float32Array(totalLen);
          let offset = 0;
          for (const chunk of pcmChunks) {
            merged.set(chunk, offset);
            offset += chunk.length;
          }

          resolve({ samples: merged, sampleRate });
        }, maxDuration * 1000);

        // 返回停止函数
        resolve.stop = () => {
          source.disconnect();
          recorder.disconnect();
          stream.getTracks().forEach((t) => t.stop());
          audioCtx.close();
        };
      } catch (e) {
        reject(e);
      }
    });
  }

  // ─── 对外 API ───
  global.XingyanOfflineASR = {
    loadOfflineModel,
    recognizeOffline,
    recordOfflineAudio,
    isModelLoaded: () => _modelLoaded,
  };
})(window);
