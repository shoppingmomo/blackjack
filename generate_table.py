# %%
from dataclasses import replace

from basic_strategy_solver import best_move
from rules import Rules
from state import PlayerState, make_dealer_state, make_player_state


UPCARDS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

ACTION_SYMBOLS = {
	"HIT": "H",
	"DOUBLE": "D",
	"STAND": "S",
	"SURRENDER": "SUR",
	"SPLIT": "Y",
}


def build_hard_total_table(
	rules: Rules,
	min_total: int = 8,
	max_total: int = 17,
) -> dict:
	table = {}
	for total in range(min_total, max_total + 1):
		row = {}
		for upcard in UPCARDS:
			player_state = PlayerState(
				total=total,
				soft_aces=0,
				pair_rank=None,
				cards=2,
				can_double=True,
				can_split=False,
			)
			dealer_state = make_dealer_state(upcard)
			move, _ = best_move(player_state, dealer_state, rules)
			row[upcard] = move
		table[total] = row
	return table


def build_soft_total_table(rules: Rules) -> dict:
	table = {}
	rules_no_surrender = replace(rules, allow_surrender=False)
	for second_card in range(2, 10):
		label = f"A,{second_card}"
		row = {}
		for upcard in UPCARDS:
			player_state = make_player_state(11, second_card)
			dealer_state = make_dealer_state(upcard)
			move, actions = best_move(player_state, dealer_state, rules)

			if move == "DOUBLE":
				# Fallback after taking one more card when doubling is unavailable.
				non_double_state = PlayerState(
					total=player_state.total,
					soft_aces=player_state.soft_aces,
					pair_rank=None,
					cards=3,
					can_double=False,
					can_split=False,
				)
				_, fallback_actions = best_move(non_double_state, dealer_state, rules_no_surrender)
				fallback_move = "STAND" if fallback_actions["STAND"] >= fallback_actions["HIT"] else "HIT"
				row[upcard] = "Ds" if fallback_move == "STAND" else "Dh"
			else:
				row[upcard] = ACTION_SYMBOLS.get(move, move)
		table[label] = row
	return table


def build_pair_table(rules: Rules) -> dict:
	table = {}
	pair_ranks = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
	for rank in pair_ranks:
		label = "A,A" if rank == 11 else f"{rank},{rank}"
		card = 11 if rank == 11 else rank
		row = {}
		for upcard in UPCARDS:
			player_state = make_player_state(card, card)
			dealer_state = make_dealer_state(upcard)
			move, _ = best_move(player_state, dealer_state, rules)
			row[upcard] = move
		table[label] = row
	return table


def print_hard_total_table(table: dict) -> None:
	headers = ["P\\D"] + ["A" if u == 11 else str(u) for u in UPCARDS]
	print("\t".join(headers))

	for total in sorted(table):
		values = [str(total)] + [ACTION_SYMBOLS.get(table[total][u], table[total][u]) for u in UPCARDS]
		print("\t".join(values))


def print_labeled_table(table: dict) -> None:
	headers = ["P\\D"] + ["A" if u == 11 else str(u) for u in UPCARDS]
	print("\t".join(headers))
	for label in table:
		values = [label] + [table[label][u] for u in UPCARDS]
		print("\t".join(values))


def print_pair_table(table: dict) -> None:
	headers = ["P\\D"] + ["A" if u == 11 else str(u) for u in UPCARDS]
	print("\t".join(headers))
	for label in table:
		# values = [label] + ["Y" if table[label][u] == "SPLIT" else "N" for u in UPCARDS]
		values = [label] + ["Y" if table[label][u] == "SPLIT" else " " for u in UPCARDS]
		# values = [label] + [ACTION_SYMBOLS.get(table[label][u], table[label][u]) for u in UPCARDS]
		print("\t".join(values))


if __name__ == "__main__":
	rules = Rules()
	hard = build_hard_total_table(rules)
	soft = build_soft_total_table(rules)
	pair = build_pair_table(rules)

	from dataclasses import fields
	print("=" * 40)
	for f in fields(rules):
		print(f"  {f.name:<30} {getattr(rules, f.name)}")
	print("=" * 40)
	print("=== Hard Totals ===")
	print_hard_total_table(hard)
	print()
	print("=== Soft Totals ===")
	print_labeled_table(soft)
	print()
	print("=== Pair Splits ===")
	print_pair_table(pair)

