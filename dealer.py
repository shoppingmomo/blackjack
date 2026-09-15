from functools import lru_cache

from state import CARD_PROBS, DealerState, draw_card


@lru_cache(maxsize=None)
def dealer_distribution(
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
) -> dict:
	total = dealer_state.total
	soft_aces = dealer_state.soft_aces

	if total > 21:
		return {"bust": 1.0}

	if total > 17:
		return {total: 1.0}

	if total == 17:
		if not (dealer_hits_soft17 and soft_aces > 0):
			return {17: 1.0}

	result = {}
	for card, p in CARD_PROBS.items():
		next_state = draw_card(dealer_state, card)
		sub = dealer_distribution(next_state, dealer_hits_soft17)
		for k, v in sub.items():
			result[k] = result.get(k, 0.0) + p * v

	return result


@lru_cache(maxsize=None)
def dealer_final_distribution(
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	peek_blackjack: bool = True,
) -> dict:
	upcard = dealer_state.upcard
	if upcard not in (10, 11):
		return dealer_distribution(dealer_state, dealer_hits_soft17)

	bj_hole = 11 if upcard == 10 else 10
	bj_prob = CARD_PROBS[bj_hole]

	result = {}
	if not peek_blackjack:
		# No-peek / no hole card: dealer natural BJ is resolved after the player acts,
		# so keep it as a distinct outcome instead of folding it into a hit-21.
		result["blackjack"] = bj_prob

	# AUDIT VERIFIED: peek=True conditions the distribution on "dealer has no BJ";
	# peek=False retains the unconditional BJ branch. Both distributions sum to 1.
	denom = (1.0 - bj_prob) if peek_blackjack else 1.0
	for hole_card, hole_prob in CARD_PROBS.items():
		if hole_card == bj_hole:
			continue

		weight = hole_prob / denom if peek_blackjack else hole_prob
		state_after_hole = draw_card(dealer_state, hole_card)
		sub = dealer_distribution(state_after_hole, dealer_hits_soft17)
		for outcome, p in sub.items():
			result[outcome] = result.get(outcome, 0.0) + weight * p

	return result


def clear_dealer_cache() -> None:
	dealer_distribution.cache_clear()
	dealer_final_distribution.cache_clear()
