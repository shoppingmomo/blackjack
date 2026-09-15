from functools import lru_cache

from dealer import dealer_final_distribution
from state import CARD_PROBS, DealerState, PlayerState, draw_card, make_split_base_state


def _stand_payoff(
	player_total: int,
	is_blackjack_like: bool,
	dist: dict,
	win_amount: float,
	stake: float,
	original_bets_only: bool,
) -> float:
	ev = 0.0
	for outcome, p in dist.items():
		if outcome == "blackjack":
			# Dealer natural BJ (no-peek only). Player BJ pushes; OBO returns extra wagers.
			# AUDIT VERIFIED: a two-card, non-split player BJ contributes 0 here,
			# while it receives the configured payout against every non-natural 21.
			if is_blackjack_like:
				continue
			ev -= p * (1.0 if original_bets_only else stake)
		elif is_blackjack_like:
			# Player natural BJ beats every non-natural dealer hand, including hit-21.
			ev += p * win_amount
		elif outcome == "bust" or outcome < player_total:
			ev += p * win_amount
		elif outcome > player_total:
			ev -= p * stake
		# outcome == player_total → push, 0 contribution
	return ev


@lru_cache(maxsize=None)
def stand_ev(
	player_state: PlayerState,
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	peek_blackjack: bool = True,
	blackjack_payout: float = 1.5,
	split_21_counts_as_blackjack: bool = False,
	original_bets_only: bool = False,
) -> float:
	dist = dealer_final_distribution(dealer_state, dealer_hits_soft17, peek_blackjack=peek_blackjack)
	is_two_card_21 = player_state.total == 21 and player_state.cards == 2
	is_blackjack_like = is_two_card_21 and (
		not player_state.from_split or split_21_counts_as_blackjack
	)
	win_amount = blackjack_payout if is_blackjack_like else 1.0
	return _stand_payoff(
		player_state.total,
		is_blackjack_like,
		dist,
		win_amount,
		1.0,
		original_bets_only,
	)


@lru_cache(maxsize=None)
def best_no_split_ev(
	player_state: PlayerState,
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	allow_double: bool = True,
	peek_blackjack: bool = True,
	blackjack_payout: float = 1.5,
	split_21_counts_as_blackjack: bool = False,
	original_bets_only: bool = False,
) -> float:
	'''
	統一比較 STAND/HIT/DOUBLE 的最優 EV
	'''
	actions = [
		stand_ev(
			player_state,
			dealer_state,
			dealer_hits_soft17,
			peek_blackjack,
			blackjack_payout,
			split_21_counts_as_blackjack,
			original_bets_only,
		)
	]
	actions.append(
		hit_ev(
			player_state,
			dealer_state,
			dealer_hits_soft17,
			allow_double,
			peek_blackjack,
			blackjack_payout,
			split_21_counts_as_blackjack,
			original_bets_only,
		)
	)
	if allow_double and player_state.can_double:
		actions.append(
			double_ev(
				player_state,
				dealer_state,
				dealer_hits_soft17,
				peek_blackjack,
				blackjack_payout,
				split_21_counts_as_blackjack,
				original_bets_only,
			)
		)
	return max(actions)


@lru_cache(maxsize=None)
def hit_ev(
	player_state: PlayerState,
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	allow_double: bool = True,
	peek_blackjack: bool = True,
	blackjack_payout: float = 1.5,
	split_21_counts_as_blackjack: bool = False,
	original_bets_only: bool = False,
) -> float:
	ev = 0.0
	for card, p in CARD_PROBS.items():
		next_player_state = draw_card(player_state, card)

		if next_player_state.total > 21:
			ev -= p
			continue

		next_ev = best_no_split_ev(
			next_player_state,
			dealer_state,
			dealer_hits_soft17,
			allow_double,
			peek_blackjack,
			blackjack_payout,
			split_21_counts_as_blackjack,
			original_bets_only,
		)
		ev += p * next_ev

	return ev


@lru_cache(maxsize=None)
def double_ev(
	player_state: PlayerState,
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	peek_blackjack: bool = True,
	blackjack_payout: float = 1.5,
	split_21_counts_as_blackjack: bool = False,
	original_bets_only: bool = False,
) -> float:
	dist = dealer_final_distribution(dealer_state, dealer_hits_soft17, peek_blackjack=peek_blackjack)
	ev = 0.0
	for card, p in CARD_PROBS.items():
		next_player_state = draw_card(player_state, card)
		if next_player_state.total > 21:
			ev += p * -2.0
		else:
			# Doubled hand risks 2 units; under OBO only 1 is lost to a dealer natural BJ.
			ev += p * _stand_payoff(
				next_player_state.total,
				False,
				dist,
				2.0,
				2.0,
				original_bets_only,
			)
	return ev


@lru_cache(maxsize=None)
def _split_hands_ev(
	pair_rank: int,
	pending_hands: int,
	remaining_resplits: int,
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	allow_double_after_split: bool = True,
	peek_blackjack: bool = True,
	blackjack_payout: float = 1.5,
	split_21_counts_as_blackjack: bool = False,
	resplit_aces: bool = True,
	split_aces_one_card_only: bool = True,
	hit_split_aces: bool = False,
	original_bets_only: bool = False,
) -> float:
	if pending_hands == 0:
		return 0.0

	base_hand = make_split_base_state(pair_rank)
	is_ace_split = pair_rank == 11
	total_ev = 0.0

	for card, p in CARD_PROBS.items():
		hand_after_draw = draw_card(base_hand, card)

		can_resplit = (
			hand_after_draw.can_split
			and remaining_resplits > 0
			and (pair_rank != 11 or resplit_aces)
		)

		if can_resplit:
			# Replace this hand with two hands and consume one shared table-wide split.
			branch_ev = _split_hands_ev(
				pair_rank,
				pending_hands + 1,
				remaining_resplits - 1,
				dealer_state,
				dealer_hits_soft17,
				allow_double_after_split,
				peek_blackjack,
				blackjack_payout,
				split_21_counts_as_blackjack,
				resplit_aces,
				split_aces_one_card_only,
				hit_split_aces,
				original_bets_only,
			)
		else:
			next_state = PlayerState(
				total=hand_after_draw.total,
				soft_aces=hand_after_draw.soft_aces,
				pair_rank=None,
				cards=hand_after_draw.cards,
				can_double=allow_double_after_split and hand_after_draw.can_double,
				can_split=False,
				from_split=hand_after_draw.from_split,
				from_split_aces=hand_after_draw.from_split_aces,
			)

			if is_ace_split and split_aces_one_card_only:
				branch_ev = stand_ev(
					next_state,
					dealer_state,
					dealer_hits_soft17,
					peek_blackjack,
					blackjack_payout,
					split_21_counts_as_blackjack,
					original_bets_only,
				)
			elif is_ace_split and not hit_split_aces:
				stand_only = stand_ev(
					next_state,
					dealer_state,
					dealer_hits_soft17,
					peek_blackjack,
					blackjack_payout,
					split_21_counts_as_blackjack,
					original_bets_only,
				)
				hit_only = hit_ev(
					next_state,
					dealer_state,
					dealer_hits_soft17,
					allow_double_after_split,
					peek_blackjack,
					blackjack_payout,
					split_21_counts_as_blackjack,
					original_bets_only,
				)
				branch_ev = max(stand_only, hit_only)
			else:
				branch_ev = best_no_split_ev(
					next_state,
					dealer_state,
					dealer_hits_soft17,
					allow_double_after_split,
					peek_blackjack,
					blackjack_payout,
					split_21_counts_as_blackjack,
					original_bets_only,
				)

			branch_ev += _split_hands_ev(
				pair_rank,
				pending_hands - 1,
				remaining_resplits,
				dealer_state,
				dealer_hits_soft17,
				allow_double_after_split,
				peek_blackjack,
				blackjack_payout,
				split_21_counts_as_blackjack,
				resplit_aces,
				split_aces_one_card_only,
				hit_split_aces,
				original_bets_only,
			)

		total_ev += p * branch_ev

	return total_ev


@lru_cache(maxsize=None)
def split_ev(
	player_state: PlayerState,
	dealer_state: DealerState,
	dealer_hits_soft17: bool = True,
	allow_double_after_split: bool = True,
	peek_blackjack: bool = True,
	blackjack_payout: float = 1.5,
	split_21_counts_as_blackjack: bool = False,
	max_split_hands: int = 4,
	resplit_aces: bool = True,
	split_aces_one_card_only: bool = True,
	hit_split_aces: bool = False,
	original_bets_only: bool = False,
) -> float:
	if not player_state.can_split or player_state.pair_rank is None:
		return float("-inf")

	remaining_resplits = max(0, max_split_hands - 2)
	conditional_peek = peek_blackjack
	dealer_bj_prob = 0.0
	if original_bets_only and not peek_blackjack and dealer_state.upcard in (10, 11):
		bj_hole = 11 if dealer_state.upcard == 10 else 10
		dealer_bj_prob = CARD_PROBS[bj_hole]
		conditional_peek = True

	continuation_ev = _split_hands_ev(
		player_state.pair_rank,
		2,
		remaining_resplits,
		dealer_state,
		dealer_hits_soft17,
		allow_double_after_split,
		conditional_peek,
		blackjack_payout,
		split_21_counts_as_blackjack,
		resplit_aces,
		split_aces_one_card_only,
		hit_split_aces,
		False if dealer_bj_prob else original_bets_only,
	)

	# Under OBO, dealer natural BJ cancels the whole split tree and loses only
	# the single wager that existed before the player split.
	return (1.0 - dealer_bj_prob) * continuation_ev - dealer_bj_prob


def surrender_ev() -> float:
	return -0.5


def clear_ev_cache() -> None:
	stand_ev.cache_clear()
	best_no_split_ev.cache_clear()
	hit_ev.cache_clear()
	double_ev.cache_clear()
	_split_hands_ev.cache_clear()
	split_ev.cache_clear()
