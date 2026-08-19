# Metrics Catalog

Metrics must be defined before an experiment runs. A metric is evidence about
the measured workload; it does not by itself prove general superiority.

## Retrieval

- **Recall@k**: fraction of relevant items retrieved in the first k results;
  useful for coverage, but it does not measure ranking quality or answer truth.
- **Precision@k**: fraction of the first k results that are relevant; useful
  for ranking focus, but it can hide relevant items outside k.
- **MRR**: reciprocal rank of the first relevant result, averaged over queries;
  useful when the earliest supporting result matters, but ignores later results.
- **nDCG**: discounted ranking quality using graded relevance; useful when
  relevance has levels, but depends on a reliable grading scheme.

## Generation

- **Groundedness**: degree to which claims are supported by supplied evidence;
  it does not prove completeness or correctness of the evidence.
- **Unsupported claim rate**: proportion of claims without adequate support;
  useful for factuality risk, but depends on claim extraction and annotation.
- **Structured-output validity**: fraction of outputs that satisfy the schema;
  it does not establish semantic correctness.
- **Task correctness**: rate of outputs meeting the task rubric; it is workload-
  dependent and must be defined with an annotation protocol.

## Citation

- **Citation correctness**: whether a citation supports its associated claim;
  it does not measure whether all claims were cited.
- **Citation coverage**: fraction of claims with required citations; it does
  not mean those citations are correct.

## Verification

- **False pass rate**: unsafe outputs accepted by verification.
- **False block rate**: acceptable outputs rejected by verification.
- **Unsupported-claim reduction**: change in unsupported claim rate with a
  verifier; it requires comparable workloads and a baseline.

## Operational

- **Latency**: elapsed time under a stated measurement boundary.
- **Token usage**: input and output tokens under a stated provider accounting.
- **Estimated cost**: calculated provider cost for the recorded usage; it is an
  estimate and can change with pricing.
- **Failure rate**: fraction of runs or cases failing the defined execution
  contract; the denominator and failure classes must be explicit.

## Security

- **Attack success rate**: fraction of defined attacks that achieve their unsafe
  objective; it depends on the attack set and success definition.
- **False refusal rate**: benign requests refused by the safety strategy; it
  does not measure attack resistance alone.

## Matching

Precision@k, Recall@k, MRR, and nDCG measure ranked match quality. They require
an explicit relevance or ground-truth annotation process and do not establish
business value or causal user outcomes.
