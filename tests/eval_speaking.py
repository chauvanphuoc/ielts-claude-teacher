#!/usr/bin/env python3
"""IELTS Speaking Scoring Calibration Eval.

Validates that Claude's speaking scores are within ±0.5 bands of known benchmarks.
Uses transcripts as input (same format as SpeechRecognition output).

Usage:
  python3 tests/eval_speaking.py
  python3 tests/eval_speaking.py --check
"""

import json, sys

CALIBRATION_EXAMPLES = [
    {
        "band": 5.0,
        "description": "Band 5.0 — simple responses, hesitation, limited vocabulary, basic grammar",
        "transcript": "Well... I think... um... travelling is very good. I like to travel because... it's fun and you can see new places. I went to... um... a beach last year with my family. It was very nice. We swim in the sea and eat food. The weather was good. I think everyone should travel because... it makes you happy. Also you can learn about other cultures and... things like that. But travelling is expensive so not everyone can do it. I want to travel more in the future."
    },
    {
        "band": 6.5,
        "description": "Band 6.5 — speaks at length, adequate vocabulary, some complex structures with errors",
        "transcript": "I'd say travelling has become quite important in my life, particularly over the last few years. I try to take at least two trips each year — one within the country to explore places I haven't been, and one international trip if I can afford it. Last summer I went to Japan, which was actually a long-standing dream of mine. I spent two weeks travelling from Tokyo down to Kyoto and Osaka, and what struck me most was how seamlessly they blend centuries-old traditions with cutting-edge modernity. You can walk from a temple that's 800 years old straight into a district full of neon lights and robots. I think what I value most about travelling is the way it challenges your assumptions. Before I went, I had certain stereotypes about Japanese culture — that it would be very formal and perhaps difficult to connect with people. But I found that once you make an effort to understand the basic customs, people are incredibly warm and helpful. The experience has genuinely changed how I approach unfamiliar situations in my daily life."
    },
    {
        "band": 8.0,
        "description": "Band 8.0 — fluent, wide vocabulary, flexible structures, idiomatic, rare errors",
        "transcript": """Travel has been, without exaggeration, the single most formative influence on my worldview. I don't just mean in the superficial sense of collecting passport stamps or ticking destinations off a bucket list — I mean the kind of travel that fundamentally reshapes how you perceive your place in the world. I've been fortunate enough to spend extended periods in Southeast Asia, particularly Vietnam and Cambodia, and what I've taken away from those experiences goes far beyond the photographs.

What fascinates me is the way travel exposes the contingency of your own cultural assumptions. Things you've taken for granted as universal — the way people queue, the concept of personal space, attitudes toward time and punctuality — suddenly reveal themselves as culturally specific constructions. I vividly remember sitting in a café in Hanoi, watching the absolutely chaotic traffic flow with a kind of organic, unspoken order that somehow works despite appearing entirely lawless to Western eyes. That moment crystallised something for me: there are many valid ways to organise human life, and the way you grew up with is just one of them.

Of course, I'm acutely aware that the ability to travel extensively is a privilege, and I try to be mindful of the ethical dimensions — the environmental impact of air travel, the complex dynamics of tourism in developing economies, the fine line between cultural appreciation and appropriation. I've shifted toward slower, more immersive travel in recent years, spending longer in fewer places and prioritising genuine connection over itinerary completion. I find that approach not only more sustainable but infinitely more rewarding."""
    }
]

def evaluate_band_accuracy(predicted_band, known_band):
    diff = abs(predicted_band - known_band)
    return diff <= 0.5, diff

def main():
    print("=" * 60)
    print("IELTS Speaking Scoring Calibration Eval")
    print("=" * 60)
    print()
    print("Validates Claude's speaking scores against known benchmarks.")
    print("Uses transcripts (SpeechRecognition format).")
    print(f"Calibration examples: {len(CALIBRATION_EXAMPLES)}")
    print()

    for i, example in enumerate(CALIBRATION_EXAMPLES):
        print(f"--- Example {i+1}: {example['description']} ---")
        print(f"Expected band: {example['band']}")
        print(f"Transcript length: {len(example['transcript'].split())} words")
        print()
        print("Submit this transcript to Claude for scoring.")
        print(f"Expected: Band {example['band']} ± 0.5")
        print()

    print("=" * 60)
    print("PASS CRITERIA: All 3 examples score within ±0.5 bands")
    print("=" * 60)

if __name__ == "__main__":
    if "--check" in sys.argv:
        results = []
        for i, ex in enumerate(CALIBRATION_EXAMPLES):
            try:
                score = float(input(f"Band {ex['band']} transcript — Claude's score: "))
                ok, diff = evaluate_band_accuracy(score, ex['band'])
                results.append(ok)
                status = "PASS" if ok else f"FAIL (off by {diff:.1f})"
                print(f"  {status}")
            except (ValueError, EOFError):
                print("  SKIPPED")
        passed = sum(results)
        total = len(results)
        print(f"\nResults: {passed}/{total} passed")
        sys.exit(0 if passed == total else 1)
    else:
        main()
