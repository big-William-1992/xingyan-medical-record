// audio-processor.js — AudioWorklet 处理器（独立线程，不阻塞UI）
class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this._targetRate = options.processorOptions?.targetRate || 16000;
    this._nativeRate = sampleRate; // AudioWorklet 全局变量
    this._ratio = this._nativeRate / this._targetRate;
    this._buffer = [];
    this._bufferSize = 0;
    // 每 4096*4 样本（约1秒@16kHz）发送一次
    this._chunkSize = Math.round(this._targetRate * 1);
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const float32 = input[0];

    // 重采样（线性插值，比最近邻更平滑）
    let resampled;
    if (this._ratio !== 1) {
      const newLen = Math.round(float32.length / this._ratio);
      resampled = new Float32Array(newLen);
      for (let i = 0; i < newLen; i++) {
        const srcIdx = i * this._ratio;
        const idx0 = Math.floor(srcIdx);
        const idx1 = Math.min(idx0 + 1, float32.length - 1);
        const frac = srcIdx - idx0;
        resampled[i] = float32[idx0] * (1 - frac) + float32[idx1] * frac;
      }
    } else {
      resampled = float32;
    }

    // Float32 → Int16
    const int16 = new Int16Array(resampled.length);
    for (let i = 0; i < resampled.length; i++) {
      int16[i] = Math.max(-32768, Math.min(32767, Math.round(resampled[i] * 32767)));
    }

    // 累积到 buffer
    this._buffer.push(int16);
    this._bufferSize += int16.length;

    // 达到 chunk 大小时发送
    if (this._bufferSize >= this._chunkSize) {
      // 合并 buffer
      const combined = new Int16Array(this._bufferSize);
      let offset = 0;
      for (const chunk of this._buffer) {
        combined.set(chunk, offset);
        offset += chunk.length;
      }
      this.port.postMessage({ type: 'audio', data: combined.buffer }, [combined.buffer]);
      this._buffer = [];
      this._bufferSize = 0;
    }

    return true;
  }
}

registerProcessor('pcm-capture-processor', PcmCaptureProcessor);
