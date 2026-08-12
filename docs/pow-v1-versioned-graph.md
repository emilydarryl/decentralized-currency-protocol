# Soveroot PoW v1 Versioned Scratch-Dependency Graph

Status: **NON-CONSENSUS FULL-MEMORY DIAGNOSTIC; NO POW GATE ASSESSED**

This Stage A artifact identifies the exact scratchpad write generation that supplies every mixing and finalization read. It also records the prior generation replaced by every write. The method is frozen in [`contrib/pow_research_v1/versioned_graph_v0.json`](../contrib/pow_research_v1/versioned_graph_v0.json).

## Why word addresses were insufficient

The earlier access trace recorded reads and writes by word address. A word can be overwritten many times, so an address alone does not identify the value a replay or pebbling schedule must regenerate.

The versioned graph assigns every write a one-based global generation. A read edge names its consumer, slot, word, and source generation; source generation zero means the word's initial zero value. A write record names its producer iteration, slot, word, new generation, and overwritten generation.

The commitment covers a domain-separated, byte-exact little-endian encoding. Fixed commitments exist for the canonical vectors and the deterministic smoke and standard profiles. Python streams the commitment while evaluating; the independent C++ implementation derives it from its observational trace. CI requires them to agree.

## Scope

This is an exact **scratch-dependency** graph. The canonical iteration order already supplies the machine-state dependency chain and remains implicit. Dataset reads are reproducible from public epoch context and their selectors; they are not versioned scratch values.

The extractor uses the ordinary full scratchpad to discover value-dependent addresses. It has future knowledge only after evaluation and therefore cannot represent an online mining strategy.

## Byte-accounted standard profile

For a 262,144-byte scratchpad and three passes, every fixed standard case has:

- 98,304 mixing iterations;
- 196,624 versioned read edges, including 16 final sample reads;
- 196,608 write generations;
- 163,840 writes that overwrite an earlier materialized generation;
- a 11,993,583-byte canonical commitment stream;
- a 7,995,648-byte optimistic packed logical graph model; and
- a 15,991,424-byte conservative logical graph model.

The attack's half-scratch ceiling is 131,072 bytes. The optimistic graph model is therefore about 61 times that ceiling, before allocator or process overhead. A timed attack must never retain this graph. It may only use offline analysis to derive a much smaller schedule whose executable state is independently charged.

The eight standard commitments and per-seed initial/materialized edge counts are frozen in [`versioned_graph_profiles_v0.json`](../contrib/pow_research_v1/vectors/versioned_graph_profiles_v0.json).

## Interpretation

Stage A closes the ambiguity in read-from identities and provides deterministic input for schedule research. It does not regenerate any missing value, execute within half memory, estimate online throughput, or pass the time-memory gate.

The next stage is an offline pebbling lower bound. Planner memory, future knowledge, and graph storage must be reported separately and excluded from claims about an executable miner.
