/* ============================================
   星衍AI · 离线语音识别（sherpa-onnx WASM）
   断网时手机浏览器本地识别，无需服务器
   引擎：sherpa-onnx-wasm（Zipformer 中文流式模型）
   模型位置：/wasm/model-1pass/（由 download_offline_asr.py 下载）
   ============================================ */

(function (global) {
  'use strict';

  // WASM 引擎资源目录（模型包，含引擎 + 模型 .data）
  const ENGINE_DIR = '/wasm/model-1pass';
  const ENGINE_SCRIPTS = [
    'sherpa-onnx-asr.js',
    'sherpa-onnx-vad.js',
    'sherpa-onnx-wasm-main-asr.js',
  ];

  let _recognizer = null;
  let _stream = null;
  let _modelLoaded = false;
  let _loadPromise = null;

  // ─── 加载引擎脚本 ───
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`脚本加载失败: ${src}`));
      document.head.appendChild(script);
    });
  }

  // ─── 等待 WASM 运行时就绪 ───
  function waitForRuntime(timeoutMs = 60000) {
    const start = Date.now();
    return new Promise((resolve, reject) => {
      const check = () => {
        // 就绪标志：Module 已初始化且 createOnlineRecognizer 可用
        if (global.Module && typeof global.createOnlineRecognizer === 'function' &&
            global.Module.calledRun !== false) {
          resolve(global.Module);
          return;
        }
        if (Date.now() - start > timeoutMs) {
          reject(new Error('WASM 运行时加载超时'));
          return;
        }
        setTimeout(check, 300);
      };
      check();
    });
  }

  // ─── 加载模型与引擎（幂等，可重入）───
  async function loadOfflineModel() {
    if (_modelLoaded) return true;
    if (_loadPromise) return _loadPromise;

    _loadPromise = (async () => {
      try {
        // 按官方顺序加载：asr → vad → wasm 主引擎
        for (const name of ENGINE_SCRIPTS) {
          await loadScript(`${ENGINE_DIR}/${name}`);
        }
        // 等待运行时就绪
        const Module = await waitForRuntime();
        if (!Module) throw new Error('WASM 模块初始化失败');

        // 创建在线识别器（Zipformer transducer）
        const config = {
          featConfig: {
            sampleRate: 16000,
            featureDim: 80,
          },
          modelConfig: {
            transducer: {
              encoder: './encoder.onnx',
              decoder: './decoder.onnx',
              joiner: './joiner.onnx',
            },
            paraformer: { encoder: '', decoder: '' },
            tokens: './tokens.txt',
            numThreads: 2,
            provider: 'wasm',
            debug: 0,
            modelType: 'transducer',
            modelingUnit: 'cjkchar',
            bpeVocab: '',
          },
          decodingMethod: 'greedy_search',
          maxActivePaths: 4,
          enableEndpoint: 1,
          rule1MinTrailingSilence: 1.4,
          rule2MinTrailingSilence: 0.5,
          rule3MinUtteranceLength: 10,
          hotwordsFile: '',
          hotwordsScore: 1.5,
        };

        _recognizer = global.createOnlineRecognizer(Module, config);
        _modelLoaded = true;
        console.log('[OfflineASR] ✅ 模型加载成功');
        return true;
      } catch (e) {
        console.error('[OfflineASR] 模型加载失败:', e);
        _loadPromise = null; // 允许重试
        return false;
      }
    })();

    return _loadPromise;
  }

  // ─── 音频转文本（一次性识别）───
  async function recognizeOffline(audioData, sampleRate = 16000) {
    if (!_recognizer) {
      const ok = await loadOfflineModel();
      if (!ok) return { ok: false, text: '', error: '离线模型未加载' };
    }

    try {
      _stream = _recognizer.createStream();
      const samples = new Float32Array(audioData);

      // 分块喂入音频（每块 400ms = 6400 采样点）
      const chunkSize = 6400;
      let text = '';
      for (let i = 0; i < samples.length; i += chunkSize) {
        const chunk = samples.subarray(i, i + chunkSize);
        _stream.acceptWaveform({ sampleRate, samples: chunk });

        // 流式解码结果
        if (_recognizer.isReady(_stream)) {
          const result = _recognizer.getResult(_stream);
          if (result && result.text) text = result.text;
        }

        // 端点检测：静音足够长时提前结束
        if (_recognizer.isEndpointDetected(_stream)) {
          const final = _recognizer.getResult(_stream);
          if (final && final.text) text = final.text;
          break;
        }
      }

      // 获取最终结果
      const finalResult = _recognizer.getResult(_stream);
      if (finalResult && finalResult.text) text = finalResult.text;

      // 释放流
      try { _stream.free(); } catch (e) { /* ignore */ }
      _stream = null;

      return { ok: true, text: text.trim() };
    } catch (e) {
      console.error('[OfflineASR] 识别失败:', e);
      return { ok: false, text: '', error: e.message };
    }
  }

  // ─── 录音（getUserMedia → PCM 16kHz 单声道）───
  async function recordOfflineAudio(maxDuration = 30) {
    return new Promise((resolve, reject) => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          reject(new Error('浏览器不支持麦克风访问（需 HTTPS 或 localhost）'));
          return;
        }

        navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        }).then((stream) => {
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const source = audioCtx.createMediaStreamSource(stream);

          const sampleRate = 16000;
          const bufferSize = 4096;
          const recorder = audioCtx.createScriptProcessor(bufferSize, 1, 1);
          const pcmChunks = [];
          let stopped = false;

          recorder.onaudioprocess = (e) => {
            if (stopped) return;
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

          const finish = () => {
            if (stopped) return;
            stopped = true;
            try { source.disconnect(); } catch (e) { /* ignore */ }
            try { recorder.disconnect(); } catch (e) { /* ignore */ }
            stream.getTracks().forEach((t) => t.stop());
            try { audioCtx.close(); } catch (e) { /* ignore */ }

            // 合并 PCM
            const totalLen = pcmChunks.reduce((sum, c) => sum + c.length, 0);
            const merged = new Float32Array(totalLen);
            let offset = 0;
            for (const chunk of pcmChunks) {
              merged.set(chunk, offset);
              offset += chunk.length;
            }
            resolve({ samples: merged, sampleRate, stop: finish });
          };

          // 自动停止
          setTimeout(finish, maxDuration * 1000);
        }).catch(reject);
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
