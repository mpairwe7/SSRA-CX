"""Runnable entrypoint for `python -m ssra_voice`."""

from __future__ import annotations

import json

from ssra_core import LocaleCode

from ssra_voice import MAX_VOICE_WER_GATE, resolve_hf_voice_model_cache


def main() -> int:
    en_asr = resolve_hf_voice_model_cache(LocaleCode.EN)
    print(
        json.dumps(
            {
                "status": "ok",
                "service": "ssra-voice",
                "wer_launch_gate": MAX_VOICE_WER_GATE,
                "primary_asr_repo": en_asr.asr_repo_id,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
