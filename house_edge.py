
# %%
from dataclasses import fields, replace

from basic_strategy_solver import best_move
from rules import Rules
from state import CARD_PROBS, make_dealer_state, make_player_state


def _is_natural_blackjack(card1: int, card2: int) -> bool:
    return (card1 == 11 and card2 == 10) or (card1 == 10 and card2 == 11)


def _dealer_blackjack_prob_with_peek(upcard: int) -> float:
    if upcard == 10:
        return CARD_PROBS[11]
    if upcard == 11:
        return CARD_PROBS[10]
    return 0.0


def compute_player_ev_per_initial_bet(rules: Rules) -> float:
    ev_sum = 0.0
    # ENHC (no hole card) means the dealer never peeks.
    peek_game = not rules.european_no_hole_card

    for card1, p1 in CARD_PROBS.items():
        for card2, p2 in CARD_PROBS.items():
            player_state = make_player_state(card1, card2)
            player_natural = _is_natural_blackjack(card1, card2)

            for upcard, pu in CARD_PROBS.items():
                dealer_state = make_dealer_state(upcard)
                # Conditional decision EV after dealer BJ branch is excluded.
                continuation_rules = replace(
                    rules,
                    early_surrender=False,
                    allow_surrender=(rules.allow_surrender and rules.late_surrender),
                )
                _, continuation_actions = best_move(player_state, dealer_state, continuation_rules)
                best_ev_non_bj = max(continuation_actions.values())

                if peek_game and upcard in (10, 11):
                    # 美式 Peek 局：在此處手動還原條件機率與計算 Early Surrender
                    p_dealer_bj = _dealer_blackjack_prob_with_peek(upcard)
                    # AUDIT VERIFIED: best_ev_non_bj uses the peek-conditioned
                    # dealer distribution; this restores the excluded BJ branch.
                    # Player natural BJ therefore pushes against dealer natural BJ.
                    ev_if_dealer_bj = 0.0 if player_natural else -1.0

                    no_early_ev = p_dealer_bj * ev_if_dealer_bj + (1.0 - p_dealer_bj) * best_ev_non_bj

                    can_early_surrender = (
                        rules.allow_surrender
                        and rules.early_surrender
                        and (upcard != 11 or rules.surrender_vs_ace)
                    )
                    state_ev = max(-0.5, no_early_ev) if can_early_surrender else no_early_ev
                else:
                    # 歐式 ENHC 局 (Macau)：直接全部交給 best_move 計算
                    _, actions = best_move(player_state, dealer_state, rules)
                    state_ev = max(actions.values())

                ev_sum += p1 * p2 * pu * state_ev

    return ev_sum


def compute_house_edge_percent(rules: Rules) -> float:
    player_ev = compute_player_ev_per_initial_bet(rules)
    return -player_ev * 100.0


def main() -> None:
    rules = Rules()

    print("Blackjack House Edge Calculator")
    print("=" * 40)
    for f in fields(rules):
        print(f"  {f.name:<30} {getattr(rules, f.name)}")
    print("=" * 40)

    player_ev = compute_player_ev_per_initial_bet(rules)
    house_edge = -player_ev

    print(f"Player EV per initial bet : {player_ev:+.6f}")
    print(f"House edge               : {house_edge * 100:.4f}%")


if __name__ == "__main__":
    main()


