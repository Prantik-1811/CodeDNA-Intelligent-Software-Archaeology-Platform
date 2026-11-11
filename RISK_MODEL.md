# CodeDNA risk model and evaluation plan

## Purpose and boundary

CodeDNA's repository risk score ranks files for engineering investigation. It is
not the probability that a file is defective, a vulnerability verdict, a CVSS
score, or a substitute for code review and security testing.

Keep two products distinct:

1. **Change risk / hotspot priority**: relative ranking based on repository
   structure, complexity, and historical change signals.
2. **Security findings**: rule-based or data-flow findings mapped to CWE, with
   evidence, confidence, and severity. Use OWASP Benchmark for Python to measure
   security detector accuracy. Do not relabel hotspot scores as vulnerabilities.

## Current CodeDNA score (policy v2)

Each available feature is normalized to `[0, 1]`, multiplied by its weight, and
the weighted sum is divided by the total weight of active evidence. The result
is on a 0–100 scale. Dividing by active evidence weight prevents missing inputs
from being silently treated as zero risk.

| Signal | Weight | Normalization / rule | Interpretation |
| --- | ---: | --- | --- |
| Cyclomatic complexity | 20% | `min(CC / 20, 1)` | Higher branching complexity warrants closer review. |
| File change frequency | 20% | `min(changes / 20, 1)` | Repeatedly changed files receive more attention. |
| Bug-fix history | 25% | `min(bug-fix commits / 5, 1)` | Prior bug-fix activity is a direct historical signal, but message keywords are noisy. |
| Code churn | 20% | `min((insertions + deletions) / 500, 1)` | Large cumulative churn increases review priority. |
| Dependency degree | 15% | `min((in + out edges) / 15, 1)` | Highly connected files can have broader change impact. |
| Contributor count | 0% | Descriptive only | Team size is not intrinsically risky and must not penalize collaboration. |

Weights sum to 100% over scored signals. Initial severity bands remain explicit
policy thresholds: low `<20`, medium `20–<45`, high `45–<70`, critical `≥70`.
These bands describe priority, not calibrated defect probabilities. Every
feature should expose raw value, normalized value, weight, and contribution.

### Important implementation caveats

- Complexity is currently calculated at file level and can sum decisions across
  many functions; applying a function-level threshold of 20 to that aggregate is
  a rough screen, not a standard-compliant complexity classification.
- Raw change counts and churn are lifetime totals, not recency-adjusted rates.
- Commit-message keywords approximate bug-fix history and can miss fixes or
  count non-fixes. A future version should use linked issue/fix labels and
  SZZ-style lineage with documented noise limits.
- Dependency degree is not centrality and can be inflated by graph coverage.
- The score is not empirically calibrated yet. Do not claim predictive accuracy.

## Standards and benchmark choice

- **Defect-proneness research** informs hotspot features: complexity, churn,
  change frequency, and bug history are candidate predictors. Their value must
  be measured on time-separated, project-separated labeled data; they are not
  universal causal rules.
- **Defects4J** is a good controlled benchmark for Java fault localization and
  repair research, but its current project/Java focus does not validate this
  Python-first file-level score.
- **ApacheJIT** is a more relevant research dataset for commit-level defect
  prediction and temporal train/test separation. It does not by itself validate
  CodeDNA's file-level score or all project populations.
- **OWASP Benchmark for Python** is the selected benchmark for a future
  security-finding engine: it has labeled vulnerable/non-vulnerable Python test
  cases and supports evaluating true/false positives and negatives. Benchmark
  performance must be reported by weakness category as well as overall.
- **CWE** should be used to label security weakness classes. **OWASP ASVS** is a
  verification requirements catalogue, not a defect-prediction dataset.
- **CVSS v4.0** is for scoring the severity of an identified vulnerability
  given exploitability and impact context. It must not be applied to a file
  hotspot with no confirmed vulnerability.

## Evaluation protocol before making accuracy claims

1. Freeze analyzer version, rules, thresholds, and dataset versions.
2. For security detection, run on OWASP Benchmark Python and compare findings
   with its expected-results labels. Report TP, FP, TN, FN, recall/TPR,
   precision, FPR, and F1 per CWE/category, plus runtime.
3. For defect-proneness, define the prediction unit (file or commit), label
   source, prediction horizon, and inclusion rules. Split chronologically and
   keep projects separate between training/tuning and final evaluation to avoid
   leakage. Compare against simple baselines such as changed-file count and
   complexity-only ranking.
4. Report ranking metrics useful for review budgets (top-k recall, precision
   among top-k, and effort-aware recall), calibration only if producing
   probabilities, and confidence intervals across projects.
5. Publish dataset/license notices, exclusions, versions, false-positive
   examples, and limitations. Never tune and report on the same held-out set.

## References

- [OWASP Benchmark](https://owasp.org/www-project-benchmark/)
- [OWASP Benchmark for Python](https://github.com/OWASP-Benchmark/BenchmarkPython)
- [OWASP guidance on static analysis limitations](https://devguide.owasp.org/en/05-implementation/05-static-analysis/)
- [CWE Top 25 and downloads](https://cwe.mitre.org/data/downloads.html)
- [OWASP ASVS 5.0](https://asvs.owasp.org/)
- [FIRST CVSS v4.0 specification](https://www.first.org/cvss/v4.0/specification-document)
- [Defects4J](https://github.com/rjust/defects4j)
- [ApacheJIT dataset](https://github.com/hosseinkshvrz/apachejit)
- [SEI, Predicting Software Assurance Using Quality and Reliability Measures](https://www.sei.cmu.edu/library/predicting-software-assurance-using-quality-and-reliability-measures/)
