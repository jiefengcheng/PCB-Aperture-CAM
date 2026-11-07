# Provisional T02 gap matching: one percent

Status: isolated implementation, not integrated. The active fresh full-board
job and installed app retain their captured prior code and checks.

The user selected a maximum 1% difference between neighboring shared gaps.
`contracts/t02_shared_gaps/settings.json` registers the replaceable provisional
parameter. Every new T02 plan captures its complete registry bytes and hash.
The comparison is `(maximum gap - minimum gap) / minimum gap <= 0.01` across
all source-qualified full spans in each group. Zero restores strict matching.
This is separate from the 50% rectangle exposure threshold and its 1% relative
allowance, production clearance and native geometric fidelity.

Qualified fixed walls retain their individual actual positions. Small original
differences do not require trimming earlier copper or forcing those walls onto
one exact plane. Source slot membership identifies each movable or fixed face;
the final accepted per-slot corridors and whole boundaries are still checked.
Optional rectangle projection remains deterministic and only reduces checked
whole centered proposals within the existing factor bounds.

The matching parameter is not a fresh copper allowance at every later step.
Once T02 accepts the actual slot positions, ordinary T05, remedy, retained prior
copper and actual export/reparse must preserve those frozen corridors. Pin
separation, source cores, integral joints, clearance, 20% budgets, complete-fill
vetoes and existing native fidelity stay unchanged.

Runtime is separately diagnosed under
`out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/runtime_profile_t02_01/`.
Fresh T02 construction took 1510.149 seconds for 10496 trial calls; the search
is repeated by both evaluation workers. A retained-operand diagnostic measured
3.263 seconds for source gap discovery, 0.027 for bank projection and 0.354 for
one complete gap check. Relaxing matching does not remove the main search and
geometry cost. No performance speedup or new full-board qualification is claimed.

Failed evidence remains unchanged. Other boards remain paused. `.DS_Store`
custody remains EXPLICIT_UNWAIVED_UNATTRIBUTED.
