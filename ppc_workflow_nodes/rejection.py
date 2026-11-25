"""Public rejection object consumed as a VIDEO by SaveVideo on the error path.

SaveVideo.execute (ComfyUI comfy_extras/nodes_video.py) calls
``get_dimensions()`` before it builds an output path, then ``save_to(...)``.
The original IDE scripts raised ``ValueError(reason)`` from those two methods.
Additional VideoInput methods raise the same public reason so a later host
call cannot surface an AttributeError or write a file.
"""

from __future__ import annotations


class PublicRejectionVideo:
    def __init__(self, reason: str):
        self.reason = reason

    def _reject(self):
        raise ValueError(self.reason)

    def get_dimensions(self):
        self._reject()

    def get_components(self):
        self._reject()

    def get_duration(self):
        self._reject()

    def get_frame_count(self):
        self._reject()

    def get_frame_rate(self):
        self._reject()

    def get_stream_source(self):
        self._reject()

    def get_container_format(self):
        self._reject()

    def as_trimmed(self, start_time=None, duration=None, strict_duration=False):
        self._reject()

    def as_cropped(self, x=0, y=0, width=0, height=0):
        self._reject()

    def save_to(self, *args, **kwargs):
        self._reject()


def host_execution_blocker():
    """Return the host ExecutionBlocker class. Never a local stand-in."""
    from comfy_execution.graph_utils import ExecutionBlocker

    return ExecutionBlocker
