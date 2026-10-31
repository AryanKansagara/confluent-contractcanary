# ContractCanary — Confluent-inspired semantic migration laboratory

Confluent provides Kafka-based data streaming and schema governance. ContractCanary tests a narrower problem: records can pass a declared reader's primitive-type checks while money or customer identity changes meaning during a version rollout.

**Implemented:** a dependency-free Python JSON-wire experiment with three authored order versions, explicit adjacent upgrade/downgrade functions, a mixed-version matrix, business-value oracle, unsupported-client outcomes, and greedy counterexample reduction. **Integration unverified:** no Kafka, Schema Registry, Avro, Protobuf, CEL, Java serializers, or managed Confluent rules execute here. This is a local semantic model, not a Confluent compatibility validator. The environment supplied Java but no compiler/serializer stack; Python keeps the authored transformations inspectable and has no inference hot path.

```sh
python -m unittest discover -v
python contractcanary.py --output demo.json
```

Python 3.11+; standard library only. The checked-in `demo.json` is generated output, not an invented benchmark: **144 cases, 0 safe-migration failures, 24 injected semantic violations**. In 20 of the 36 safe-path examples, bypassing migrations still passes instance-level type projection but changes business meaning. Repeated defects on same-version paths deliberately remain passing controls. This is a finite authored corpus, not a defect-detection accuracy estimate.

## How it works

Version 1 stores integer **major currency units**; versions 2 and 3 store integer minor units. USD uses 100 minor units, JPY uses 1. Version 3 renames `customer_id` to `customer`; the reader supplies an empty default when missing. Nullable discount contributes zero when absent. All versions project JSON onto declared primitive fields, so unchanged integer types do not reveal changed units.

`experiment(event, path, defect=..., client=...)` serializes and deserializes actual JSON at local transformation boundaries, then compares canonical net minor units, currency, and customer identity. Registered edges are only 1↔2 and 2↔3. A 1→3 jump, a client without rules, an unknown format/currency, or a fractional minor-to-major downcast is explicitly unsupported; no transformation is silently fabricated.

Injected defects include hardcoding 100 for JPY, dropping identity during rename, and discarding discount on downgrade. `minimize` removes optional fields, shrinks integer values to 0/1, and removes internal path steps while retaining a violation. It reports a greedy local minimum, not a globally smallest input. The demo reduces a large JPY event to a compact witness.

## Validation and next stages

Nine tests cover USD/JPY safe round trips, type-compatible unit changes, rename and discount regressions, unsupported clients/edges/downcasts, malformed numeric types, direct migration version rejection, and witness preservation. Safe and adverse results are independent assertions; the type-only baseline and semantic oracle are different checks.

Semantic invariants and currency scales are supplied assumptions. The model does not implement schema-level backward/forward/transitive compatibility, actual Confluent client rule support, or rollout deployment. Next stage: official serializer integration with a pinned registry, then the same matrix against real supported migration rules. This repository needs no credentials or broker. A live integration would require the vendor runtime and any applicable rule entitlements.

## Primary research

Confluent already provides schema compatibility modes and data-contract migration rules; this project investigates semantic rollout tests around those features rather than claiming those features are missing.

- [Schema evolution, compatibility, and rollout ordering](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)
- [Data contracts and migration rules](https://docs.confluent.io/cloud/current/sr/fundamentals/data-contracts.html)
- [Compatibility versus business structure](https://developer.confluent.io/patterns/event-stream/schema-compatibility/)
