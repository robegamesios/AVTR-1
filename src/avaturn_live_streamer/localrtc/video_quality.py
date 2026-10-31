"""Video bitrate defaults for the local avatar demo.

aiortc's built-in codec factories read these module-level bitrate limits.
Apply our local-stream policy before constructing any peer connections;
keep the installed codec implementations unchanged.
"""

import os

from aiortc.codecs import h264, vpx


def configure_video_bitrates() -> dict[str, int]:
    minimum = int(os.environ.get("AVTR_VIDEO_MIN_BITRATE", "2000000"))
    target = int(os.environ.get("AVTR_VIDEO_BITRATE", "6000000"))
    maximum = int(os.environ.get("AVTR_VIDEO_MAX_BITRATE", "12000000"))
    if not 0 < minimum <= target <= maximum:
        raise ValueError("Video bitrates must satisfy 0 < minimum <= target <= maximum")
    for codec in (vpx, h264):
        codec.MIN_BITRATE = minimum
        codec.DEFAULT_BITRATE = target
        codec.MAX_BITRATE = maximum
    return {"minimum": minimum, "target": target, "maximum": maximum}
