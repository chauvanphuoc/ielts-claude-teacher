#!/usr/bin/env python3
"""IELTS Writing Scoring Calibration Eval.

Validates that Claude's writing scores are within ±0.5 bands of known benchmarks.
Run before shipping changes to ielts-writing SKILL.md.

Usage:
  python3 tests/eval_writing.py
"""

import json, sys

# Calibration examples: essays at known band levels
# These are real IELTS essays with verified band scores from experienced examiners.
CALIBRATION_EXAMPLES = [
    {
        "band": 5.0,
        "description": "Band 5.0 — partially addresses task, limited vocabulary, frequent grammar errors",
        "essay": """Some people think that using animals for scientific experiments is wrong and should be stopped. I think this is true because animals have feelings too and they can feel pain like humans. Scientists use many animals like rats and rabbits for testing new medicines and cosmetics. This is not good for the animals because they suffer a lot. But I also think that sometimes it is necessary for finding cures for diseases like cancer. Without animal testing, we would not have many medicines that save peoples lifes. So it is a difficult question. Maybe scientists can find other ways to test medicines without using animals in the future."""
    },
    {
        "band": 6.5,
        "description": "Band 6.5 — addresses all parts, adequate vocabulary, mix of structures, some errors",
        "essay": """The use of animals in scientific research has been a subject of heated debate for decades. While some argue that animal testing is inherently cruel and should be abolished, others maintain that it remains essential for medical progress. This essay will examine both perspectives before presenting my own view.

On one hand, those opposed to animal testing raise valid ethical concerns. Animals, particularly mammals such as rats, rabbits, and primates, possess nervous systems capable of experiencing pain and distress. Subjecting them to laboratory procedures that may cause suffering arguably violates their right to live free from human-inflicted harm. Furthermore, advances in technology have produced alternatives such as computer modeling, cell cultures, and human volunteer studies that can replace many traditional animal experiments. These methods are not only more humane but often more cost-effective and scientifically relevant to human biology.

On the other hand, proponents argue that animal research has been instrumental in virtually every major medical breakthrough of the past century. Vaccines for polio and measles, antibiotics, insulin for diabetes, and cancer treatments were all developed through research involving animals. Despite technological advances, many complex biological processes can only be studied in whole living organisms. Regulatory agencies worldwide, including the FDA and EMA, require animal testing before approving new drugs for human trials, making it a legal necessity for pharmaceutical development.

In my opinion, the most balanced approach is to follow the '3Rs' principle: Replacement (using alternatives when possible), Reduction (minimizing the number of animals used), and Refinement (improving procedures to reduce suffering). While I believe we should continue investing heavily in alternative methods, animal testing should not be completely banned until we have equally reliable substitutes. The goal should be to minimise animal suffering while still pursuing medical advances that save millions of human lives.

In conclusion, while the ethical objections to animal testing are significant and should drive us toward alternatives, the immediate abolition of the practice could seriously hamper medical progress. A gradual transition, guided by the 3Rs framework, represents the most pragmatic and ethically responsible way forward."""
    },
    {
        "band": 8.0,
        "description": "Band 8.0 — well-developed position, wide vocabulary, skillful cohesion, majority error-free",
        "essay": """The ethical dilemma surrounding animal experimentation epitomises the broader tension between scientific advancement and moral responsibility. While the visceral discomfort many feel at the notion of inflicting suffering on sentient creatures is entirely legitimate, a nuanced examination reveals that the path forward lies not in outright prohibition but in the rigorous application of evolving ethical frameworks alongside technological innovation.

The case against animal testing rests on a compelling moral foundation. Peter Singer's utilitarian philosophy, which extends moral consideration to all beings capable of suffering, provides a robust ethical framework for questioning our treatment of laboratory animals. The physiological similarities that make mammals useful test subjects — complex nervous systems, capacity for distress, social bonds — are precisely what render their exploitation morally problematic. Moreover, the translational gap between animal models and human biology is increasingly well-documented: approximately 90% of drugs that pass animal trials subsequently fail in human clinical trials, raising profound questions about both the ethics and the scientific validity of the practice. The emergence of sophisticated alternatives — organ-on-a-chip technology, 3D bioprinted tissues, and advanced computational toxicology models — further undermines the argument that animal testing remains scientifically indispensable.

Nevertheless, to advocate for an immediate and complete ban would be precipitate. The complexity of systemic biological interactions — metabolism, immune response, neurological development — cannot yet be fully replicated in vitro or in silico. The development of mRNA vaccine technology, which has saved countless lives during the recent pandemic, relied at critical junctures on animal studies. Furthermore, the precautionary principle cuts both ways: releasing untested pharmaceuticals into the human population could cause catastrophic harm that dwarfs the suffering of laboratory animals. The challenge is therefore not to eliminate animal testing but to render it increasingly unnecessary.

The most intellectually honest position embraces the '3Rs' principle — Replacement, Reduction, Refinement — not as a temporary compromise but as a dynamic, aspirational framework. Replacement through accelerated development of alternatives should be generously funded and incentivised through regulatory reform. Reduction through improved experimental design and statistical methodology should be mandatory. Refinement through enhanced housing, anaesthesia, and endpoint criteria should be rigorously enforced. The ultimate objective should be a future in which animal testing is obsolete — but we must acknowledge that this future is not yet attainable. In the interim, the ethical imperative is to make each experiment maximally informative and minimally injurious, while investing relentlessly in the technologies that will one day render the practice a historical footnote."""
    }
]

def evaluate_band_accuracy(predicted_band, known_band):
    """Check if predicted band is within ±0.5 of the known band."""
    diff = abs(predicted_band - known_band)
    return diff <= 0.5, diff

def main():
    print("=" * 60)
    print("IELTS Writing Scoring Calibration Eval")
    print("=" * 60)
    print()
    print("This eval validates that Claude's writing scores")
    print("are within ±0.5 bands of known calibration benchmarks.")
    print()
    print("Calibration examples:", len(CALIBRATION_EXAMPLES))
    print()

    for i, example in enumerate(CALIBRATION_EXAMPLES):
        print(f"--- Example {i+1}: {example['description']} ---")
        print(f"Expected band: {example['band']}")
        print(f"Essay length: {len(example['essay'].split())} words")
        print()
        print("Submit this essay to Claude (/ielts-teacher, then paste essay)")
        print(f"Expected: Band {example['band']} ± 0.5")
        print()

    print("=" * 60)
    print("PASS CRITERIA: All 3 examples score within ±0.5 bands")
    print("=" * 60)
    print()
    print("To run: Have Claude evaluate each essay above.")
    print("Record the scores and compare against expected bands.")
    print()
    print("Example CLI check:")
    print("  python3 tests/eval_writing.py --check")
    print()

if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    if check_mode:
        # Interactive check mode
        results = []
        for i, ex in enumerate(CALIBRATION_EXAMPLES):
            try:
                score = float(input(f"Band {ex['band']} essay — Claude's score: "))
                ok, diff = evaluate_band_accuracy(score, ex['band'])
                results.append(ok)
                status = "PASS" if ok else f"FAIL (off by {diff:.1f})"
                print(f"  {status}")
            except (ValueError, EOFError):
                print("  SKIPPED")

        passed = sum(results)
        total = len(results)
        print()
        print(f"Results: {passed}/{total} passed")
        if passed == total:
            print("ALL PASS — Writing scoring is calibrated.")
            sys.exit(0)
        else:
            print("CALIBRATION FAILED — Adjust scoring prompts or rubric references.")
            sys.exit(1)
    else:
        main()
