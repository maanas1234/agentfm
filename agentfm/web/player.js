export class AudioQueue {
  constructor(onStatusChange) {
    this.queue = [];
    this.playing = false;
    this.muted = false;
    this.onStatusChange = onStatusChange || (() => {});
  }

  enqueue(base64, mime) {
    if (!base64) return;
    this.queue.push({ base64, mime: mime || "audio/mpeg" });
    this._notify();
    if (!this.playing) this._playNext();
  }

  setMuted(muted) {
    this.muted = muted;
  }

  _playNext() {
    if (this.queue.length === 0) {
      this.playing = false;
      this._notify();
      return;
    }
    this.playing = true;
    const { base64, mime } = this.queue.shift();
    this._notify();

    if (this.muted) {
      this._playNext();
      return;
    }

    const audio = new Audio(`data:${mime};base64,${base64}`);
    audio.onended = () => this._playNext();
    audio.onerror = () => this._playNext();
    audio.play().catch(() => this._playNext());
  }

  _notify() {
    this.onStatusChange(this.queue.length, this.playing);
  }
}
