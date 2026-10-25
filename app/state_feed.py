"""Live state for the web page, sent as small changes instead of whole copies.

The controller publishes a full snapshot about ten times a second. Before,
the page fetched the whole thing every 200 ms, including the full transcript
and answer, even when nothing had changed. Now:

* A read waits (long-poll) until something changes, or until ``wait`` runs out.
* The small settings part is sent only when it changed since the reader's revision.
* The transcript and answer are versioned. A reader sends the version it holds and
  gets back ``keep`` (how many leading characters are still right) plus ``add``
  (the new tail), so a live draft that rewrites its last words costs only that tail.

Only the common-prefix length between neighbouring versions is kept, never old
copies of the text, so memory stays flat however long the transcript gets.
"""
import json
import secrets
import threading

TEXT_KEYS = ('transcript', 'output')


def common_prefix(old, new):
    """Length of the shared start of two strings, with C-speed comparisons."""
    if new.startswith(old):
        return len(old)
    lo, hi = 0, min(len(old), len(new))
    # Invariant: old[:lo] == new[:lo]. Each probe copies only old[lo:mid].
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if new.startswith(old[lo:mid], lo):
            lo = mid
        else:
            hi = mid - 1
    return lo


class StateFeed:
    def __init__(self, window=256):
        self.window = window
        self.boot = secrets.token_hex(4)  # a restarted app never matches old versions
        self.changed = threading.Condition()
        self.rev = self.base_rev = 0
        self.base, self.base_json = {}, ''
        self.texts = {key: '' for key in TEXT_KEYS}
        self.versions = {key: 0 for key in TEXT_KEYS}
        # steps[key][v] = common-prefix length between version v and v + 1.
        self.steps = {key: {} for key in TEXT_KEYS}

    def publish(self, snapshot):
        snapshot = dict(snapshot)
        with self.changed:
            changed = False
            for key in TEXT_KEYS:
                new, old = str(snapshot.pop(key, '') or ''), self.texts[key]
                if new == old:
                    continue
                version, steps = self.versions[key], self.steps[key]
                steps[version] = common_prefix(old, new)
                steps.pop(version - self.window, None)
                self.versions[key], self.texts[key] = version + 1, new
                changed = True
            base_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            if base_json != self.base_json:
                self.base, self.base_json = snapshot, base_json
                self.base_rev = self.rev + 1
                changed = True
            if changed:
                self.rev += 1
                self.changed.notify_all()

    def wake(self):
        """Release waiting readers, e.g. when the app closes."""
        with self.changed:
            self.changed.notify_all()

    def read(self, rev=-1, boot='', versions=None, wait=0.0):
        """Return the JSON bytes a reader at ``rev`` / ``versions`` needs."""
        versions = versions or {}
        with self.changed:
            if boot != self.boot:
                rev, versions = -1, {}
            elif wait > 0 and rev == self.rev:
                self.changed.wait_for(lambda: self.rev != rev, timeout=wait)
            out = {'boot': self.boot, 'rev': self.rev}
            if not 0 <= rev <= self.rev or rev < self.base_rev:
                out['state'] = self.base
            for key in TEXT_KEYS:
                have, version, text = versions.get(key), self.versions[key], self.texts[key]
                if have == version:
                    continue
                entry = {'v': version}
                if isinstance(have, int) and version - self.window < have < version:
                    keep = min(self.steps[key][v] for v in range(have, version))
                    entry.update(keep=keep, add=text[keep:])
                else:
                    entry['text'] = text
                out[key] = entry
            return json.dumps(out, ensure_ascii=False).encode('utf-8')
