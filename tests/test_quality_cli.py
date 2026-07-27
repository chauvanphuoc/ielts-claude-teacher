#!/usr/bin/env python3
"""Tests for W1 quality control plane commands in shared/ielts_cli.py.

Usage:
  .venv/bin/python3 -m pytest tests/test_quality_cli.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = PROJECT_ROOT / "shared" / "ielts_cli.py"
IELTS_DIR = PROJECT_ROOT / ".ielts"
QUALITY_DIR = IELTS_DIR / "quality"


class TestQualityCLI:
    def setup_method(self):
        # Start from clean quality dir to keep tests deterministic.
        if QUALITY_DIR.exists():
            shutil.rmtree(QUALITY_DIR)

    def _run_cli(self, args: list[str]):
        cmd = [str(PROJECT_ROOT / ".venv" / "bin" / "python3"), str(CLI_PATH)] + args
        return subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

    def _complete_phases_up_to_w3(self):
        self._run_cli(["quality", "phase-gate", "--action", "complete", "--phase", "w1", "--note", "w1 done"])
        self._run_cli(["quality", "phase-gate", "--action", "complete", "--phase", "w2", "--note", "w2 done"])
        self._run_cli(["quality", "phase-gate", "--action", "complete", "--phase", "w3", "--note", "w3 done"])

    def test_quality_init_creates_scaffold_and_contract_files(self):
        result = self._run_cli(["quality", "init"])
        assert result.returncode == 0, result.stderr or result.stdout

        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"

        assert (QUALITY_DIR / "config" / "thresholds-reading-v1.yaml").exists()
        assert (QUALITY_DIR / "config" / "trace-schema-v1.json").exists()
        assert (QUALITY_DIR / "runbooks" / "error-rescue-map.md").exists()
        assert (QUALITY_DIR / "baselines" / "baseline-template.json").exists()

    def test_run_manifest_creates_manifest_json(self):
        self._run_cli(["quality", "init"])

        result = self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-001",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout

        payload = json.loads(result.stdout)
        manifest_path = Path(payload["manifest"])
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["runId"] == "reading-manual-001"
        assert manifest["lane"] == "reading"
        assert manifest["trigger"] == "manual"
        assert manifest["sourceVersion"] == "prompt-v1"

    def test_run_manifest_dedupe_reuses_existing_run(self):
        self._run_cli(["quality", "init"])

        first = self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-001",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
                "--dedupe-key",
                "same-input",
            ]
        )
        assert first.returncode == 0, first.stderr or first.stdout

        second = self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-002",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
                "--dedupe-key",
                "same-input",
            ]
        )
        assert second.returncode == 0

        payload = json.loads(second.stdout)
        assert payload["status"] == "duplicate_skipped"
        assert payload["runId"] == "reading-manual-001"

    def test_baseline_record_happy_path_writes_file(self):
        self._run_cli(["quality", "init"])

        result = self._run_cli(
            [
                "quality",
                "baseline-record",
                "--lane",
                "reading",
                "--run-id",
                "reading-manual-001",
                "--trace-completeness",
                "0.88",
                "--replay-pass-rate",
                "0.81",
                "--content-fidelity-error-rate",
                "0.04",
                "--mttd-hours",
                "18",
                "--mttp-hours",
                "22",
                "--notes",
                "baseline capture",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout

        payload = json.loads(result.stdout)
        baseline_path = Path(payload["path"])
        assert baseline_path.exists()

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert baseline["runId"] == "reading-manual-001"
        assert baseline["metrics"]["traceCompleteness"] == 0.88
        assert baseline["metrics"]["replayPassRate"] == 0.81

    def test_baseline_record_rejects_out_of_range_metric(self):
        self._run_cli(["quality", "init"])

        result = self._run_cli(
            [
                "quality",
                "baseline-record",
                "--lane",
                "reading",
                "--run-id",
                "reading-manual-001",
                "--trace-completeness",
                "1.2",
                "--replay-pass-rate",
                "0.81",
                "--content-fidelity-error-rate",
                "0.04",
                "--mttd-hours",
                "18",
                "--mttp-hours",
                "22",
            ]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_trace_validate_splits_valid_and_invalid_records(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        trace_file = tmp_path / "trace.jsonl"
        valid_record = {
            "schemaVersion": "trace-v1",
            "runId": "reading-manual-001",
            "timestamp": "2026-07-27T10:00:00Z",
            "skill": "reading",
            "decisionType": "diagnose",
            "evidenceRefs": ["ev://reading/test-1/q1"],
            "rubricRefs": ["rubric://reading/v1"],
            "kcTargets": ["reading.main_idea"],
            "action": "assign targeted drill",
            "expectedOutcome": "reduce error on main idea",
            "confidence": 0.82,
            "sourceVersion": "prompt-v1",
        }
        invalid_record = {
            "schemaVersion": "trace-v1",
            "runId": "reading-manual-001",
            "timestamp": "2026-07-27T10:00:00Z",
            "skill": "reading",
            "decisionType": "diagnose",
            "evidenceRefs": [],
            "rubricRefs": ["rubric://reading/v1"],
            "kcTargets": ["reading.main_idea"],
            "action": "assign targeted drill",
            "expectedOutcome": "reduce error on main idea",
            "confidence": 0.82,
            # sourceVersion intentionally missing
        }

        with open(trace_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(valid_record) + "\n")
            f.write(json.dumps(invalid_record) + "\n")

        result = self._run_cli(["quality", "trace-validate", "--file", str(trace_file)])
        assert result.returncode == 1

        payload = json.loads(result.stdout)
        assert payload["status"] == "issues_found"
        assert payload["total"] == 2
        assert payload["valid"] == 1
        assert payload["invalid"] == 1

        valid_sink = QUALITY_DIR / "traces" / "2026-07-27.jsonl"
        invalid_sink = QUALITY_DIR / "traces" / "invalid-traces.jsonl"

        assert valid_sink.exists()
        assert invalid_sink.exists()

        invalid_lines = [line for line in invalid_sink.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(invalid_lines) >= 1

        parsed_invalid = json.loads(invalid_lines[-1])
        assert "errors" in parsed_invalid
        assert any("sourceVersion" in err for err in parsed_invalid["errors"])

    def test_trace_validate_rejects_manifest_lineage_mismatch(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-001",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        trace_file = tmp_path / "trace-mismatch.jsonl"
        mismatch_record = {
            "schemaVersion": "trace-v1",
            "runId": "wrong-run-id",
            "timestamp": "2026-07-27T10:00:00Z",
            "skill": "reading",
            "decisionType": "diagnose",
            "evidenceRefs": ["ev://reading/test-1/q1"],
            "rubricRefs": ["rubric://reading/v1"],
            "kcTargets": ["reading.main_idea"],
            "action": "assign targeted drill",
            "expectedOutcome": "reduce error on main idea",
            "confidence": 0.82,
            "sourceVersion": "prompt-v1",
        }
        trace_file.write_text(json.dumps(mismatch_record) + "\n", encoding="utf-8")

        result = self._run_cli(
            ["quality", "trace-validate", "--file", str(trace_file), "--run-id", "reading-manual-001"]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["invalid"] == 1

    def test_report_only_generates_eval_gate_recommendation(self):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-001",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-manual-001",
                "--trace-completeness",
                "0.88",
                "--replay-pass-rate",
                "0.81",
                "--content-fidelity-error-rate",
                "0.04",
                "--sample-size",
                "45",
                "--mode",
                "report-only",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout

        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["gateState"] == "green"

        eval_path = Path(payload["artifacts"]["evalSummary"])
        gate_path = Path(payload["artifacts"]["gate"])
        reco_path = Path(payload["artifacts"]["recommendation"])

        assert eval_path.exists()
        assert gate_path.exists()
        assert reco_path.exists()

        gate_data = json.loads(gate_path.read_text(encoding="utf-8"))
        assert gate_data["mode"] == "report-only"
        assert gate_data["state"] == "green"

    def test_gateset_register_creates_immutable_registry_artifact(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        dataset_file = tmp_path / "gateset.jsonl"
        rows = [
            {"caseId": "r-001", "questionType": "tfng", "kc": "reading.inference", "answer": "true"},
            {"caseId": "r-002", "questionType": "matching", "kc": "reading.scanning", "answer": "B"},
        ]
        dataset_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

        result = self._run_cli(
            [
                "quality",
                "gateset-register",
                "--lane",
                "reading",
                "--evalset-id",
                "evalset-v1",
                "--file",
                str(dataset_file),
                "--source-version",
                "dataset-20260727",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout

        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["immutable"] is True
        assert payload["key"] == "reading:evalset-v1"

        out_path = Path(payload["path"])
        assert out_path.exists()

        frozen = json.loads(out_path.read_text(encoding="utf-8"))
        assert frozen["frozen"] is True
        assert frozen["evalsetId"] == "evalset-v1"
        assert frozen["lane"] == "reading"
        assert frozen["caseCount"] == 2

    def test_gateset_register_rejects_duplicate_evalset_id(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        dataset_file = tmp_path / "gateset.json"
        dataset_file.write_text(
            json.dumps([
                {"caseId": "r-001", "questionType": "tfng", "kc": "reading.inference", "answer": "true"}
            ]),
            encoding="utf-8",
        )

        first = self._run_cli(
            [
                "quality",
                "gateset-register",
                "--lane",
                "reading",
                "--evalset-id",
                "evalset-v1",
                "--file",
                str(dataset_file),
            ]
        )
        assert first.returncode == 0, first.stderr or first.stdout

        second = self._run_cli(
            [
                "quality",
                "gateset-register",
                "--lane",
                "reading",
                "--evalset-id",
                "evalset-v1",
                "--file",
                str(dataset_file),
            ]
        )
        assert second.returncode == 1

        payload = json.loads(second.stdout)
        assert payload["status"] == "error"
        assert "immutable" in payload["message"].lower()

    def test_report_only_fails_on_coverage_guardrail_despite_aggregate_pass(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-coverage-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(
            json.dumps(
                {
                    "kc_buckets": {
                        "inference": {"passRate": 0.55, "caseCount": 6},
                        "detail": {"passRate": 0.80, "caseCount": 6},
                    },
                    "question_types": {
                        "tfng": {"passRate": 0.80, "caseCount": 6},
                        "matching": {"passRate": 0.80, "caseCount": 6},
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-manual-coverage-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.90",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--coverage-file",
                str(coverage_file),
                "--mode",
                "report-only",
            ]
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        gate = json.loads(Path(payload["artifacts"]["gate"]).read_text(encoding="utf-8"))
        assert gate["state"] in {"yellow", "red"}
        assert gate["checks"]["coverageGuardrails"] is False

    def test_report_only_coverage_nil_path_missing_section(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-coverage-2",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        coverage_file = tmp_path / "coverage-missing-section.json"
        coverage_file.write_text(
            json.dumps({"kc_buckets": {"inference": {"passRate": 0.8, "caseCount": 6}}}),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-manual-coverage-2",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.90",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--coverage-file",
                str(coverage_file),
            ]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_report_only_coverage_empty_path_rejects_empty_object(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-coverage-3",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        coverage_file = tmp_path / "coverage-empty.json"
        coverage_file.write_text(
            json.dumps({"kc_buckets": {}, "question_types": {}}),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-manual-coverage-3",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.90",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--coverage-file",
                str(coverage_file),
            ]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_report_only_coverage_error_path_rejects_non_object_json(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-manual-coverage-4",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        coverage_file = tmp_path / "coverage-list.json"
        coverage_file.write_text(json.dumps([{"bad": "shape"}]), encoding="utf-8")

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-manual-coverage-4",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.90",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--coverage-file",
                str(coverage_file),
            ]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_override_validate_happy_path(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        override_file = tmp_path / "override-ok.json"
        override_file.write_text(
            json.dumps(
                {
                    "overrideId": "ovr-001",
                    "runId": "reading-manual-001",
                    "requestedBy": "founder",
                    "approver": "founder",
                    "severity": "red",
                    "justification": "critical launch unblock",
                    "ticketRef": "QCP-101",
                    "requestedAt": "2026-07-27T10:00:00Z",
                    "expiresAt": "2026-07-28T10:00:00Z",
                    "rollbackPlan": "revert prompt to previous snapshot",
                    "postmortemDueAt": "2026-07-30T10:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(["quality", "override-validate", "--file", str(override_file)])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert Path(payload["path"]).exists()

    def test_override_validate_nil_path_missing_required_field(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        override_file = tmp_path / "override-missing.json"
        override_file.write_text(
            json.dumps(
                {
                    "overrideId": "ovr-002",
                    "runId": "reading-manual-001",
                    "requestedBy": "founder",
                    "approver": "founder",
                    "severity": "red",
                    "justification": "critical launch unblock",
                    "ticketRef": "QCP-101",
                    "requestedAt": "2026-07-27T10:00:00Z",
                    "expiresAt": "2026-07-28T10:00:00Z",
                    "rollbackPlan": "revert prompt to previous snapshot"
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(["quality", "override-validate", "--file", str(override_file)])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"
        assert any("postmortemDueAt" in e for e in payload["errors"])

    def test_override_validate_empty_path_rejects_empty_value(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        override_file = tmp_path / "override-empty.json"
        override_file.write_text(
            json.dumps(
                {
                    "overrideId": "ovr-003",
                    "runId": "reading-manual-001",
                    "requestedBy": "founder",
                    "approver": "founder",
                    "severity": "red",
                    "justification": "",
                    "ticketRef": "QCP-101",
                    "requestedAt": "2026-07-27T10:00:00Z",
                    "expiresAt": "2026-07-28T10:00:00Z",
                    "rollbackPlan": "revert prompt to previous snapshot",
                    "postmortemDueAt": "2026-07-30T10:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(["quality", "override-validate", "--file", str(override_file)])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"
        assert any("justification" in e for e in payload["errors"])

    def test_override_validate_error_path_rejects_bad_json_shape(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        override_file = tmp_path / "override-list.json"
        override_file.write_text(json.dumps([{"not": "object"}]), encoding="utf-8")

        result = self._run_cli(["quality", "override-validate", "--file", str(override_file)])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_soft_gate_founder_approval_mode_requires_ack(self):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "founder_approval"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-softgate-approval-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-softgate-approval-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        gate_data = json.loads(Path(payload["artifacts"]["gate"]).read_text(encoding="utf-8"))

        assert gate_data["state"] in {"yellow", "red"}
        assert gate_data["policy"]["approvalMode"] == "founder_approval"
        assert gate_data["policy"]["requiresFounderAcknowledgement"] is True
        assert gate_data["policy"]["mergeAllowed"] is False
        assert gate_data["approval"]["status"] == "pending"

    def test_soft_gate_founder_acknowledge_unblocks_merge(self):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "founder_approval"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-softgate-approval-2",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-softgate-approval-2",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        ack = self._run_cli(
            [
                "quality",
                "gate-acknowledge",
                "--run-id",
                "reading-softgate-approval-2",
                "--approved-by",
                "founder",
                "--note",
                "accept risk for release",
            ]
        )
        assert ack.returncode == 0, ack.stderr or ack.stdout

        ack_payload = json.loads(ack.stdout)
        gate_path = Path(ack_payload["gate"])
        gate_data = json.loads(gate_path.read_text(encoding="utf-8"))
        assert gate_data["policy"]["mergeAllowed"] is True
        assert gate_data["policy"]["approvalStatus"] == "approved"
        assert gate_data["approval"]["status"] == "approved"
        assert gate_data["approval"]["approvedBy"] == "founder"

    def test_soft_gate_auto_accepts_mode_skips_manual_ack(self):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "auto_accepts"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-softgate-auto-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-softgate-auto-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        gate_data = json.loads(Path(payload["artifacts"]["gate"]).read_text(encoding="utf-8"))

        assert gate_data["state"] in {"yellow", "red"}
        assert gate_data["policy"]["approvalMode"] == "auto_accepts"
        assert gate_data["policy"]["requiresFounderAcknowledgement"] is False
        assert gate_data["policy"]["mergeAllowed"] is True
        assert gate_data["approval"]["status"] == "auto_accepted"

    def test_budget_validate_happy_path(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        perf_file = tmp_path / "perf-ok.json"
        perf_file.write_text(
            json.dumps(
                {
                    "totalCasesExecuted": 40,
                    "peakMemoryMb": 700,
                    "concurrencyUsed": 2,
                    "stageDurationsSec": {
                        "setup": 20,
                        "replay": 600,
                        "evaluate": 120,
                        "gate": 20,
                        "recommendation": 20,
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(["quality", "budget-validate", "--file", str(perf_file)])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["passed"] is True

    def test_budget_validate_fails_when_timeout_exceeded(self, tmp_path: Path):
        self._run_cli(["quality", "init"])

        perf_file = tmp_path / "perf-fail.json"
        perf_file.write_text(
            json.dumps(
                {
                    "totalCasesExecuted": 40,
                    "peakMemoryMb": 700,
                    "concurrencyUsed": 2,
                    "stageDurationsSec": {
                        "setup": 20,
                        "replay": 1200,
                        "evaluate": 120,
                        "gate": 20,
                        "recommendation": 20,
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(["quality", "budget-validate", "--file", str(perf_file)])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "issues_found"
        assert payload["passed"] is False
        assert payload["checks"]["stageTimeouts"]["replay"]["passed"] is False

    def test_report_only_budget_enforcement_can_downgrade_gate(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-budget-enforce-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        perf_file = tmp_path / "perf-for-report.json"
        perf_file.write_text(
            json.dumps(
                {
                    "totalCasesExecuted": 100,
                    "peakMemoryMb": 1400,
                    "concurrencyUsed": 8,
                    "stageDurationsSec": {
                        "setup": 80,
                        "replay": 1100,
                        "evaluate": 500,
                        "gate": 80,
                        "recommendation": 80,
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-budget-enforce-1",
                "--trace-completeness",
                "0.95",
                "--replay-pass-rate",
                "0.95",
                "--content-fidelity-error-rate",
                "0.01",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
                "--performance-file",
                str(perf_file),
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        gate_data = json.loads(Path(payload["artifacts"]["gate"]).read_text(encoding="utf-8"))
        assert payload["performanceEnabled"] is True
        assert gate_data["checks"]["performanceBudgets"] is False
        assert gate_data["state"] in {"yellow", "red"}

    def test_week3_checkpoint_passes_when_all_criteria_met(self):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "auto_accepts"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-week3-pass-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-week3-pass-1",
                "--trace-completeness",
                "0.88",
                "--replay-pass-rate",
                "0.80",
                "--content-fidelity-error-rate",
                "0.04",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        result = self._run_cli(["quality", "week3-checkpoint", "--run-id", "reading-week3-pass-1"])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["accepted"] is True
        assert Path(payload["checkpoint"]).exists()

    def test_week3_checkpoint_fails_when_metrics_below_threshold(self):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "auto_accepts"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-week3-fail-metric-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-week3-fail-metric-1",
                "--trace-completeness",
                "0.88",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.04",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        result = self._run_cli(["quality", "week3-checkpoint", "--run-id", "reading-week3-fail-metric-1"])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "issues_found"
        assert payload["accepted"] is False
        assert payload["checks"]["replayPassRate"]["passed"] is False

    def test_week3_checkpoint_fails_when_soft_gate_not_operational(self):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-week3-fail-mode-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-week3-fail-mode-1",
                "--trace-completeness",
                "0.88",
                "--replay-pass-rate",
                "0.80",
                "--content-fidelity-error-rate",
                "0.04",
                "--sample-size",
                "45",
                "--mode",
                "report-only",
            ]
        )

        result = self._run_cli(["quality", "week3-checkpoint", "--run-id", "reading-week3-fail-mode-1"])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["accepted"] is False
        assert payload["checks"]["softGateOperational"]["passed"] is False

    def test_incident_dry_run_override_flow_creates_audit_artifacts(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "founder_approval"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-incident-override-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-incident-override-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        override_request = tmp_path / "incident-override-request.json"
        override_request.write_text(
            json.dumps(
                {
                    "overrideId": "ovr-incident-001",
                    "runId": "reading-incident-override-1",
                    "requestedBy": "founder",
                    "approver": "founder",
                    "severity": "red",
                    "justification": "incident dry-run approval",
                    "ticketRef": "QCP-INC-001",
                    "requestedAt": "2026-07-27T10:00:00Z",
                    "expiresAt": "2026-07-28T10:00:00Z",
                    "rollbackPlan": "revert to previous prompt snapshot",
                    "postmortemDueAt": "2026-07-30T10:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "incident-dry-run",
                "--run-id",
                "reading-incident-override-1",
                "--decision",
                "override",
                "--adjudicator",
                "founder",
                "--reason",
                "simulate launch incident",
                "--override-file",
                str(override_request),
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        incident_path = Path(payload["incidentArtifact"])
        assert incident_path.exists()

        incident = json.loads(incident_path.read_text(encoding="utf-8"))
        assert incident["completed"] is True
        step_names = [s["name"] for s in incident["steps"]]
        assert step_names == ["detect", "adjudicate", "action", "report"]
        assert incident["steps"][2]["decision"] == "override"
        assert incident["refs"]["override"] is not None
        assert Path(incident["refs"]["override"]).exists()

    def test_incident_dry_run_reject_flow_creates_report(self):
        self._run_cli(["quality", "init"])
        self._run_cli(["quality", "gate-approval-mode", "--set-mode", "founder_approval"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-incident-reject-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-incident-reject-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        result = self._run_cli(
            [
                "quality",
                "incident-dry-run",
                "--run-id",
                "reading-incident-reject-1",
                "--decision",
                "reject",
                "--adjudicator",
                "founder",
                "--reason",
                "simulate conservative release decision",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        incident = json.loads(Path(payload["incidentArtifact"]).read_text(encoding="utf-8"))
        assert incident["steps"][2]["decision"] == "reject"
        assert incident["steps"][2]["result"]["mergeOutcome"] == "rejected"

    def test_incident_dry_run_override_requires_override_file(self):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-incident-err-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-incident-err-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.70",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        result = self._run_cli(
            [
                "quality",
                "incident-dry-run",
                "--run-id",
                "reading-incident-err-1",
                "--decision",
                "override",
            ]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_artifact_publish_locks_paths_and_blocks_overwrite(self):
        self._run_cli(["quality", "init"])
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-publish-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-publish-1",
                "--trace-completeness",
                "0.90",
                "--replay-pass-rate",
                "0.80",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        publish = self._run_cli(
            ["quality", "artifact-publish", "--run-id", "reading-publish-1", "--published-by", "founder"]
        )
        assert publish.returncode == 0, publish.stderr or publish.stdout

        retry = self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-publish-1",
                "--trace-completeness",
                "0.95",
                "--replay-pass-rate",
                "0.90",
                "--content-fidelity-error-rate",
                "0.01",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )
        assert retry.returncode == 1
        payload = json.loads(retry.stdout)
        assert payload["status"] == "error"

    def test_phase_gate_enforces_sequential_completion(self):
        self._run_cli(["quality", "init"])

        out_of_order = self._run_cli(
            ["quality", "phase-gate", "--action", "complete", "--phase", "w3", "--note", "premature"]
        )
        assert out_of_order.returncode == 1
        payload = json.loads(out_of_order.stdout)
        assert payload["status"] == "error"

        w1 = self._run_cli(["quality", "phase-gate", "--action", "complete", "--phase", "w1", "--note", "done"])
        w2 = self._run_cli(["quality", "phase-gate", "--action", "complete", "--phase", "w2", "--note", "done"])
        w3 = self._run_cli(["quality", "phase-gate", "--action", "complete", "--phase", "w3", "--note", "done"])
        assert w1.returncode == 0
        assert w2.returncode == 0
        assert w3.returncode == 0

    def test_kt_pack_update_appends_maintenance_log(self):
        self._run_cli(["quality", "init"])
        result = self._run_cli(
            [
                "quality",
                "kt-pack-update",
                "--phase",
                "w2",
                "--summary",
                "updated onboarding and decision template",
                "--note",
                "added troubleshooting tip",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"

        kt_log = QUALITY_DIR / "runbooks" / "kt-pack-maintenance.md"
        assert kt_log.exists()
        assert "phase=w2" in kt_log.read_text(encoding="utf-8")

    def test_weekly_review_log_allows_one_entry_per_week(self):
        self._run_cli(["quality", "init"])
        first = self._run_cli(
            [
                "quality",
                "weekly-review-log",
                "--week-key",
                "2026-W31",
                "--achieved",
                "delivered c1 and c2",
                "--misses",
                "none",
                "--risks",
                "phase slippage",
                "--commitments",
                "finish c3 and c4",
            ]
        )
        assert first.returncode == 0, first.stderr or first.stdout

        second = self._run_cli(
            [
                "quality",
                "weekly-review-log",
                "--week-key",
                "2026-W31",
                "--achieved",
                "duplicate",
                "--misses",
                "duplicate",
                "--risks",
                "duplicate",
                "--commitments",
                "duplicate",
            ]
        )
        assert second.returncode == 1
        payload = json.loads(second.stdout)
        assert payload["status"] == "error"

    def test_shadow_dry_run_creates_read_only_disagreement_report(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._complete_phases_up_to_w3()
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-shadow-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-shadow-1",
                "--trace-completeness",
                "0.92",
                "--replay-pass-rate",
                "0.89",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        gate_path = QUALITY_DIR / "gates" / "reading-shadow-1.json"
        gate_before = gate_path.read_text(encoding="utf-8")

        shadow_file = tmp_path / "shadow-comparisons.json"
        shadow_file.write_text(
            json.dumps(
                {
                    "totalCases": 10,
                    "comparisons": [
                        {"caseId": "c1", "kcBucket": "coherence", "primaryOutcome": "pass", "shadowOutcome": "pass"},
                        {"caseId": "c2", "kcBucket": "coherence", "primaryOutcome": "pass", "shadowOutcome": "fail"},
                        {"caseId": "c3", "kcBucket": "task_response", "primaryOutcome": "fail", "shadowOutcome": "fail"},
                        {"caseId": "c4", "kcBucket": "task_response", "primaryOutcome": "pass", "shadowOutcome": "fail"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "shadow-dry-run",
                "--run-id",
                "reading-shadow-1",
                "--lane",
                "writing",
                "--file",
                str(shadow_file),
                "--sample-slice-ratio",
                "1.0",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["readOnly"] is True

        artifact = json.loads(Path(payload["artifact"]).read_text(encoding="utf-8"))
        assert artifact["summary"]["disagreementCases"] == 2
        assert artifact["readOnly"] is True
        assert "coherence" in artifact["byKcBucket"]

        gate_after = gate_path.read_text(encoding="utf-8")
        assert gate_after == gate_before

    def test_shadow_weekly_report_contains_kc_bucket_trend(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._complete_phases_up_to_w3()
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-shadow-weekly-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )

        shadow_file = tmp_path / "shadow-weekly.json"
        shadow_file.write_text(
            json.dumps(
                {
                    "totalCases": 6,
                    "comparisons": [
                        {"caseId": "c1", "kcBucket": "inference", "primaryOutcome": "pass", "shadowOutcome": "fail"},
                        {"caseId": "c2", "kcBucket": "inference", "primaryOutcome": "pass", "shadowOutcome": "pass"},
                        {"caseId": "c3", "kcBucket": "detail", "primaryOutcome": "fail", "shadowOutcome": "fail"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        self._run_cli(
            [
                "quality",
                "shadow-dry-run",
                "--run-id",
                "reading-shadow-weekly-1",
                "--file",
                str(shadow_file),
                "--sample-slice-ratio",
                "1.0",
            ]
        )

        result = self._run_cli(["quality", "shadow-weekly-report"])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        report = json.loads(Path(payload["artifact"]).read_text(encoding="utf-8"))
        assert report["version"] == "shadow-weekly-report-v1"
        assert "inference" in report["byKcBucket"]
        assert report["trend"]["inference"]

    def test_schema_compat_check_blocks_breaking_change_without_version_bump(self, tmp_path: Path):
        self._run_cli(["quality", "init"])
        self._complete_phases_up_to_w3()
        old_schema = tmp_path / "old-schema.json"
        new_schema = tmp_path / "new-schema.json"
        old_schema.write_text(
            json.dumps(
                {
                    "schemaVersion": "trace-v1",
                    "requiredFields": ["runId", "timestamp", "sourceVersion"],
                }
            ),
            encoding="utf-8",
        )
        new_schema.write_text(
            json.dumps(
                {
                    "schemaVersion": "trace-v1",
                    "requiredFields": ["runId", "timestamp"],
                }
            ),
            encoding="utf-8",
        )

        result = self._run_cli(
            [
                "quality",
                "schema-compat-check",
                "--old-schema",
                str(old_schema),
                "--new-schema",
                str(new_schema),
            ]
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["blocked"] is True
        assert payload["breakingChangeDetected"] is True

    def test_hard_gate_rehearsal_switches_and_rolls_back_mode(self):
        self._run_cli(["quality", "init"])
        self._complete_phases_up_to_w3()
        self._run_cli(
            [
                "quality",
                "run-manifest",
                "--run-id",
                "reading-rehearsal-1",
                "--lane",
                "reading",
                "--trigger",
                "manual",
                "--source-version",
                "prompt-v1",
            ]
        )
        self._run_cli(
            [
                "quality",
                "report-only",
                "--run-id",
                "reading-rehearsal-1",
                "--trace-completeness",
                "0.92",
                "--replay-pass-rate",
                "0.89",
                "--content-fidelity-error-rate",
                "0.02",
                "--sample-size",
                "45",
                "--mode",
                "soft-gate",
            ]
        )

        result = self._run_cli(
            [
                "quality",
                "hard-gate-rehearsal",
                "--run-id",
                "reading-rehearsal-1",
                "--rollback-to",
                "soft-gate",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert Path(payload["artifact"]).exists()
        assert payload["afterMode"] == "soft-gate"

    def test_hard_gate_promotion_check_promotes_when_criteria_met_and_approved(self):
        self._run_cli(["quality", "init"])
        self._complete_phases_up_to_w3()

        for i in range(1, 4):
            run_id = f"reading-promote-{i}"
            self._run_cli(
                [
                    "quality",
                    "run-manifest",
                    "--run-id",
                    run_id,
                    "--lane",
                    "reading",
                    "--trigger",
                    "nightly",
                    "--source-version",
                    "prompt-v1",
                    "--dedupe-key",
                    f"promote-cycle-{i}",
                ]
            )
            self._run_cli(
                [
                    "quality",
                    "report-only",
                    "--run-id",
                    run_id,
                    "--trace-completeness",
                    "0.95",
                    "--replay-pass-rate",
                    "0.90",
                    "--content-fidelity-error-rate",
                    "0.02",
                    "--sample-size",
                    "45",
                    "--mode",
                    "soft-gate",
                ]
            )

        result = self._run_cli(
            [
                "quality",
                "hard-gate-promotion-check",
                "--approved-by",
                "founder",
                "--promote",
            ]
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["promotable"] is True
        assert payload["promoted"] is True

        mode_result = self._run_cli(["quality", "gate-mode-switch"])
        mode_payload = json.loads(mode_result.stdout)
        assert mode_payload["mode"] == "hard-gate"

    # ── T1: emit_trace / trace-emit regression tests ──

    def test_trace_emit_happy_path_writes_jsonl_and_coach_note(self):
        """Regression: emit_trace() writes valid trace to JSONL and coach note to profile."""
        self._run_cli(["quality", "init"])
        self._run_cli(["init"])

        result = self._run_cli([
            "quality", "trace-emit",
            "--skill", "reading",
            "--decision-type", "diagnose",
            "--evidence-refs", "ev://reading/test-1/q1",
            "--rubric-refs", "rubric://reading/v1",
            "--kc-targets", "kc-read-tfng,kc-read-inference",
            "--action", "analyzed TF/NG answer pattern",
            "--expected-outcome", "identify NOT GIVEN confusion",
            "--confidence", "0.82",
            "--source-version", "prompt-v1",
        ])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"

        # Verify trace file exists and contains the record
        trace_files = sorted(QUALITY_DIR.glob("traces/*.jsonl"))
        valid_files = [f for f in trace_files if "invalid" not in f.name]
        assert len(valid_files) >= 1
        trace_data = json.loads(valid_files[0].read_text(encoding="utf-8").strip())
        assert trace_data["skill"] == "reading"
        assert trace_data["decisionType"] == "diagnose"
        assert trace_data["kcTargets"] == ["kc-read-tfng", "kc-read-inference"]
        assert trace_data["confidence"] == 0.82

        # Verify coach note was written to profile
        profile_path = PROJECT_ROOT / ".ielts" / "student-profile.json"
        assert profile_path.exists()
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        trace_notes = [n for n in profile.get("coachNotes", []) if n.get("category") == "trace"]
        assert len(trace_notes) >= 1
        assert "diagnose" in trace_notes[-1]["content"]

    def test_trace_emit_rejects_empty_evidence_refs(self):
        """Regression: emit_trace() rejects trace with empty evidenceRefs."""
        self._run_cli(["quality", "init"])

        result = self._run_cli([
            "quality", "trace-emit",
            "--skill", "reading",
            "--decision-type", "diagnose",
            "--evidence-refs", "",
            "--rubric-refs", "rubric://reading/v1",
            "--kc-targets", "kc-read-tfng",
            "--action", "test",
            "--expected-outcome", "test",
            "--confidence", "0.5",
        ])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

        # Verify invalid trace was written to invalid-traces.jsonl
        invalid_path = QUALITY_DIR / "traces" / "invalid-traces.jsonl"
        assert invalid_path.exists()

    def test_trace_emit_rejects_invalid_confidence(self):
        """Regression: emit_trace() rejects confidence outside [0,1]."""
        self._run_cli(["quality", "init"])
        result = self._run_cli([
            "quality", "trace-emit",
            "--skill", "reading", "--decision-type", "diagnose",
            "--evidence-refs", "ev://test",
            "--rubric-refs", "rubric://reading/v1",
            "--kc-targets", "kc-read-tfng",
            "--action", "test", "--expected-outcome", "test",
            "--confidence", "1.5",
        ])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_trace_emit_rejects_invalid_skill(self):
        """Regression: emit_trace() rejects non-allowed skill."""
        self._run_cli(["quality", "init"])
        result = self._run_cli([
            "quality", "trace-emit",
            "--skill", "math",
            "--decision-type", "diagnose",
            "--evidence-refs", "ev://test",
            "--rubric-refs", "rubric://reading/v1",
            "--kc-targets", "kc-read-tfng",
            "--action", "test", "--expected-outcome", "test",
            "--confidence", "0.5",
        ])
        # argparse catches invalid choice before reaching handler → returncode 2
        assert result.returncode != 0

    # ── E4: weekly-digest regression tests ──

    def test_weekly_digest_empty_week_returns_no_sessions(self):
        """Regression: weekly-digest on a week with no traces returns empty report."""
        self._run_cli(["quality", "init"])
        # Ensure no trace files exist for current week
        result = self._run_cli(["quality", "weekly-digest", "--week", "2026-W01"])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["totalTraces"] == 0

    def test_weekly_digest_with_traces_generates_report(self):
        """Regression: weekly-digest with traces produces proper digest."""
        self._run_cli(["quality", "init"])
        self._run_cli(["init"])  # also ensure .ielts/ dirs exist
        # Emit 3 traces for different skills
        for skill in ["reading", "writing", "listening"]:
            r = self._run_cli([
                "quality", "trace-emit",
                "--skill", skill, "--decision-type", "diagnose",
                "--evidence-refs", "ev://test",
                "--rubric-refs", "rubric://reading/v1",
                "--kc-targets", "kc-read-tfng",
                "--action", f"diagnosed {skill}",
                "--expected-outcome", "improve",
                "--confidence", "0.7",
            ])
            assert r.returncode == 0, f"trace-emit failed for {skill}: {r.stderr}"

        result = self._run_cli(["quality", "weekly-digest"])
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["totalTraces"] == 3
        assert payload["traceCompleteness"] == 1.0

        # Verify report files were written
        import re
        report_path = payload["report"]
        assert Path(report_path).exists()
        json_path = payload["jsonSummary"]
        assert Path(json_path).exists()
        summary = json.loads(Path(json_path).read_text(encoding="utf-8"))
        assert summary["totalTraces"] == 3
