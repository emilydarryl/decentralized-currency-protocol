# Soveroot PoW v1 Budgeted Cache Lower-Bound Screen

Status: **NON-CONSENSUS DIAGNOSTIC; TIME-MEMORY GATE NOT ASSESSED**

The previous trace treated a half-capacity cache as half the number of scratchpad words. That is optimistic because cached values need identities, versions, and replacement metadata. This screen instead caps the entire simulated value-cache representation at half of the declared scratchpad bytes.

The predeclared method is [`contrib/pow_research_v1/budgeted_cache_screen_v0.json`](../contrib/pow_research_v1/budgeted_cache_screen_v0.json).

## Accounted layouts

Two explicit entry sizes are evaluated:

- **compact, 16 bytes:** an 8-byte value, 4-byte word index, and 4-byte generation or replacement field;
- **conservative, 24 bytes:** an 8-byte value, 8-byte word/version identity, and 8-byte replacement field.

Both layouts consume at most half the scratchpad bytes. An executable attacker would have to reserve additional space for registers, accumulator, queues, checkpoints, stack, and allocator overhead, so these cache capacities remain optimistic.

## Policies

The online LRU simulation provides a simple implementable replacement baseline. The offline-optimal simulation sees the completed dynamic trace, evicts the value whose next required read is farthest away, and declines to retain values that will be overwritten before another read.

The offline policy is unattainable by a real online miner because future addresses depend on values not yet computed. Its miss count is therefore a lower bound: an online cache with the same capacity cannot do better on that trace.

## Interpretation

Neither policy generates an exact proof after a miss. The screen measures the minimum number of missing values that a later recomputation algorithm must confront under explicit representation costs. It cannot pass or reject the time-memory gate.

A full scratchpad checkpoint is larger than the entire half-memory budget. The next exact attacker must therefore combine bounded values with recomputation or a pebbling schedule; register-only checkpoints are insufficient to resume execution.
