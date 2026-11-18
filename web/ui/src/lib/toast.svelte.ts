// One transient confirmation at a time, rendered by Shell. Use it for
// success ("Copied", "Profile saved"). Errors never use a toast: show them
// inline with <Feedback tone="danger"> until the person resolves them.
class ToastState {
  message = $state<string | null>(null);

  show(message: string) {
    // Re-announce identical messages by clearing first.
    this.message = null;
    queueMicrotask(() => (this.message = message));
  }

  clear() {
    this.message = null;
  }
}

export const toast = new ToastState();
