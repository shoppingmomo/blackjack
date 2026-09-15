from dataclasses import dataclass


# AUDIT: This is an infinite-shoe model. Rules.decks is never used, and dealt
# cards are not removed, so generated EV/house edge cannot model finite-deck
# composition or card-removal effects even though the rules expose a deck count.
CARD_PROBS = {
	2: 1 / 13,
	3: 1 / 13,
	4: 1 / 13,
	5: 1 / 13,
	6: 1 / 13,
	7: 1 / 13,
	8: 1 / 13,
	9: 1 / 13,
	10: 4 / 13,
	11: 1 / 13,  # Ace
}


def normalize_total(total: int, soft_aces: int) -> tuple[int, int]:
	while total > 21 and soft_aces > 0:
		total -= 10
		soft_aces -= 1
	return total, soft_aces


def apply_card(total: int, soft_aces: int, card: int) -> tuple[int, int]:
	if card == 11:
		total += 11
		soft_aces += 1
	else:
		total += card
	return normalize_total(total, soft_aces)


def card_rank(card: int) -> int:
	return 10 if card == 10 else card


def card_total_value(rank: int) -> int:
	return 11 if rank == 11 else rank


@dataclass(frozen=True)
class PlayerState:
	total: int
	soft_aces: int
	pair_rank: int | None = None
	cards: int = 2
	can_double: bool = True
	can_split: bool = False
	from_split: bool = False
	from_split_aces: bool = False


@dataclass(frozen=True)
class DealerState:
	total: int
	soft_aces: int
	upcard: int | None = None


def make_player_state(card1: int, card2: int) -> PlayerState:
	total = 0
	soft_aces = 0
	total, soft_aces = apply_card(total, soft_aces, card1)
	total, soft_aces = apply_card(total, soft_aces, card2)

	r1 = card_rank(card1)
	r2 = card_rank(card2)
	is_pair = r1 == r2

	return PlayerState(
		total=total,
		soft_aces=soft_aces,
		pair_rank=r1 if is_pair else None,
		cards=2,
		can_double=True,
		can_split=is_pair,
		from_split=False,
		from_split_aces=False,
	)


def make_dealer_state(upcard: int) -> DealerState:
	if upcard == 11:
		return DealerState(total=11, soft_aces=1, upcard=11)
	return DealerState(total=upcard, soft_aces=0, upcard=upcard)


def make_split_base_state(pair_rank: int) -> PlayerState:
	total = card_total_value(pair_rank)
	soft_aces = 1 if pair_rank == 11 else 0
	# cards=1 means this hand is waiting for its post-split draw.
	return PlayerState(
		total=total,
		soft_aces=soft_aces,
		pair_rank=pair_rank,
		cards=1,
		can_double=False,
		can_split=False,
		from_split=True,
		from_split_aces=(pair_rank == 11),
	)


def draw_card(state: PlayerState | DealerState, card: int) -> PlayerState | DealerState:
	new_total, new_soft_aces = apply_card(state.total, state.soft_aces, card)

	if isinstance(state, DealerState):
		return DealerState(total=new_total, soft_aces=new_soft_aces, upcard=state.upcard)

	new_cards = state.cards + 1
	new_rank = card_rank(card)

	new_pair_rank = None
	new_can_split = False
	if state.cards == 1 and state.pair_rank is not None and new_cards == 2:
		if state.pair_rank == new_rank:
			new_pair_rank = new_rank
			new_can_split = True

	return PlayerState(
		total=new_total,
		soft_aces=new_soft_aces,
		pair_rank=new_pair_rank,
		cards=new_cards,
		can_double=(new_cards == 2),
		can_split=new_can_split,
		from_split=state.from_split,
		from_split_aces=state.from_split_aces,
	)