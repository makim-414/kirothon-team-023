"""On-device OCR with Apple Vision (Korean + English). No network."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

LANGS = ["ko-KR", "en-US"]


def ocr_image(path: str | Path) -> str:
    """Return recognized text, one line per observation, top-to-bottom.

    Returns "" on failure (Requirement 3.3) and logs the error.
    """
    try:
        import Quartz
        import Vision
        from Foundation import NSURL
    except ImportError:  # non-macOS
        log.error("Apple Vision unavailable; OCR disabled")
        return ""

    try:
        url = NSURL.fileURLWithPath_(str(path))
        src = Quartz.CGImageSourceCreateWithURL(url, None)
        if src is None:
            raise ValueError(f"cannot open image: {path}")
        cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        if cg is None:
            raise ValueError(f"cannot decode image: {path}")

        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setRecognitionLanguages_(LANGS)
        req.setUsesLanguageCorrection_(True)

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(str(err))

        lines = []
        for obs in req.results() or []:
            cand = obs.topCandidates_(1)
            if not cand:
                continue
            box = obs.boundingBox()  # origin bottom-left, normalized
            top = 1.0 - (box.origin.y + box.size.height)
            lines.append((round(top, 2), box.origin.x, cand[0].string()))
        lines.sort(key=lambda t: (t[0], t[1]))
        return "\n".join(t[2] for t in lines)
    except Exception:
        log.exception("OCR failed for %s", path)
        return ""
