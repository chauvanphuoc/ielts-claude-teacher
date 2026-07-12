#!/usr/bin/env python3
"""IELTS Pronunciation Assessment CLI — wraps Azure Speech Studio API.

Refactored from docs/IELTS_PracticeAndEvaluation/pronounce_assessment_file.py

Does TWO things in one API call:
  1. Speech-to-text (STT) — transcribes the audio
  2. Pronunciation assessment — scores accuracy, fluency, prosody, completeness

Usage:
  python3 pronounce_cli.py --audio recording.wav
  python3 pronounce_cli.py --audio recording.wav --reference "expected text"
  python3 pronounce_cli.py --audio recording.wav --json   # JSON output only

Input:  .wav audio file (other formats may work — test first)
Output: JSON to stdout: {transcript, accuracy, fluency, prosody, completeness,
                          pronScore, intonation, perWord: [...], error: null}
        Errors: {error: "message"} to stderr
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── Load .env ──
def _load_env():
    """Load AZURE_SPEECH_KEY and AZURE_SPEECH_REGION from .env file or environment."""
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip('"').strip("'")
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = val


_load_env()

SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")


def assess_pronunciation(audio_path, reference_text=None, language="en-US"):
    """Run Azure Speech pronunciation assessment on an audio file.

    Args:
        audio_path: Path to .wav audio file
        reference_text: Expected text (optional — leave empty for free speaking)
        language: Language code, default en-US

    Returns:
        dict with keys: transcript, accuracy, fluency, prosody, completeness,
                        pronScore, intonation, perWord, error
        error is None on success, or a string message on failure
    """
    if not SPEECH_KEY or SPEECH_KEY == "your_key_here":
        return {"error": "AZURE_SPEECH_KEY not set. Add it to .env file."}

    if not os.path.exists(audio_path):
        return {"error": f"Audio file not found: {audio_path}"}

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        return {"error": "azure-cognitiveservices-speech not installed. Run: uv pip install azure-cognitiveservices-speech"}

    try:
        speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

        # Pronunciation assessment config
        config_json = {
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
            "ScenarioId": "",
            "EnableMiscue": True,
            "EnableProsodyAssessment": True,
            "NBestPhonemeCount": 0,
        }
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            json_string=json.dumps(config_json)
        )
        if reference_text:
            pronunciation_config.reference_text = reference_text

        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            language=language,
            audio_config=audio_config,
        )
        pronunciation_config.apply_to(speech_recognizer)

        result = speech_recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript = result.text
            raw = json.loads(
                result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult
                )
            )
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return {"error": "No speech could be recognized in the audio file."}
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            return {
                "error": f"Speech recognition canceled: {cancellation.reason}. "
                f"Details: {cancellation.error_details}"
            }
        else:
            return {"error": f"Unknown result reason: {result.reason}"}

        # Parse pronunciation assessment results
        nbest = raw["NBest"][0]
        pa = nbest["PronunciationAssessment"]

        accuracy = pa["AccuracyScore"] / 100.0
        fluency = pa["FluencyScore"] / 100.0
        prosody_score = pa["ProsodyScore"] / 100.0
        completeness = pa["CompletenessScore"] / 100.0
        pron_score = pa["PronScore"] / 100.0

        # Per-word assessment
        per_word = []
        total_intonation = 0.0
        word_count = len(nbest.get("Words", []))

        for w in nbest.get("Words", []):
            wpa = w.get("PronunciationAssessment", {})
            intonation_data = (
                wpa.get("Feedback", {})
                .get("Prosody", {})
                .get("Intonation", {})
                .get("Monotone", {})
                .get("SyllablePitchDeltaConfidence", 0)
            )
            total_intonation += intonation_data

            per_word.append(
                {
                    "word": w.get("Word", ""),
                    "accuracy": wpa.get("AccuracyScore", 0) / 100.0,
                    "errorType": wpa.get("ErrorType", "None"),
                }
            )

        avg_intonation = total_intonation / word_count if word_count > 0 else 0.0

        return {
            "transcript": transcript,
            "accuracy": round(accuracy, 4),
            "fluency": round(fluency, 4),
            "prosody": round(prosody_score, 4),
            "completeness": round(completeness, 4),
            "pronScore": round(pron_score, 4),
            "intonation": round(avg_intonation, 4),
            "wordCount": word_count,
            "perWord": per_word,
            "error": None,
        }

    except Exception as e:
        return {"error": f"Assessment failed: {type(e).__name__}: {e}"}


def main():
    parser = argparse.ArgumentParser(
        description="IELTS Pronunciation Assessment via Azure Speech"
    )
    parser.add_argument(
        "--audio", required=True, help="Path to audio file (.wav recommended)"
    )
    parser.add_argument(
        "--reference", default=None, help="Expected/reference text (optional)"
    )
    parser.add_argument(
        "--language", default="en-US", help="Language code (default: en-US)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON only (no status messages)"
    )
    args = parser.parse_args()

    result = assess_pronunciation(args.audio, args.reference, args.language)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["error"]:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Transcript: {result['transcript']}")
            print(f"Accuracy:   {result['accuracy']:.2%}")
            print(f"Fluency:    {result['fluency']:.2%}")
            print(f"Prosody:    {result['prosody']:.2%}")
            print(f"Complete:   {result['completeness']:.2%}")
            print(f"PronScore:  {result['pronScore']:.2%}")
            print(f"Intonation: {result['intonation']:.4f}")
            print(f"Words:      {result['wordCount']}")

    if result["error"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
