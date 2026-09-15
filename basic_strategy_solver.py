
"""Blackjack Basic Strategy Solver entry point."""

# %%
from ev import double_ev, hit_ev, split_ev, stand_ev, surrender_ev
from rules import Rules
from state import CARD_PROBS, DealerState, PlayerState, draw_card, make_dealer_state, make_player_state


def best_move(player_state: PlayerState, dealer_state: DealerState, rules: Rules):
    # ENHC (no hole card) means the dealer never peeks.
    peek = not rules.european_no_hole_card
    obo = rules.original_bets_only
    dealer_upcard = dealer_state.upcard
    dealer_is_ace = (dealer_upcard == 11)
    on_split_hand = getattr(player_state, "from_split", False)

    # 1. 基礎動作 (STAND / HIT / DOUBLE / SPLIT)
    actions = {
        "STAND": stand_ev(
            player_state,
            dealer_state,
            rules.dealer_hits_soft17,
            peek,
            rules.blackjack_payout,
            rules.split_21_counts_as_blackjack,
            obo,
        ),
    }

    is_natural_blackjack = (
        player_state.total == 21
        and player_state.cards == 2
        and not player_state.from_split
    )
    if is_natural_blackjack:
        return "STAND", actions

    actions["HIT"] = hit_ev(
        player_state,
        dealer_state,
        rules.dealer_hits_soft17,
        rules.allow_double,
        peek,
        rules.blackjack_payout,
        rules.split_21_counts_as_blackjack,
        obo,
    )

    if rules.allow_double and player_state.can_double:
        actions["DOUBLE"] = double_ev(
            player_state,
            dealer_state,
            rules.dealer_hits_soft17,
            peek,
            rules.blackjack_payout,
            rules.split_21_counts_as_blackjack,
            obo,
        )

    if rules.allow_split and player_state.can_split and player_state.pair_rank is not None:
        actions["SPLIT"] = split_ev(
            player_state,
            dealer_state,
            rules.dealer_hits_soft17,
            rules.allow_double_after_split,
            peek,
            rules.blackjack_payout,
            rules.split_21_counts_as_blackjack,
            rules.max_split_hands,
            rules.resplit_aces,
            rules.split_aces_one_card_only,
            rules.hit_split_aces,
            obo,
        )

    # 2. 投降合法性判斷
    can_surrender = rules.allow_surrender
    if on_split_hand and not rules.allow_surrender_after_split:
        can_surrender = False
    if dealer_is_ace and not rules.surrender_vs_ace:
        can_surrender = False
    
    # 3. 澳門早降 (ENHC Early Surrender) vs 美式 Peek 早降處理
    # 美式 peek 局 (peek=True) 的各動作 EV 先前被條件化剔除了莊家 BJ，需還原後與早降 -0.5 比較
    is_american_early_surrender = (
        can_surrender
        and rules.early_surrender
        and peek
        and dealer_upcard in (10, 11)
    )
    if is_american_early_surrender:
        dealer_bj_probability = CARD_PROBS[11 if dealer_upcard == 10 else 10]
        actions = {
            action: -dealer_bj_probability + (1.0 - dealer_bj_probability) * action_ev
            for action, action_ev in actions.items()
        }

    # 歐式無底牌 (ENHC, peek=False) 的 actions 已經內含莊家 BJ 結算，直接比較 -0.5
    if can_surrender and (rules.early_surrender or rules.late_surrender):
        actions["SURRENDER"] = surrender_ev()

    move = max(actions, key=actions.get)
    return move, actions


if __name__ == "__main__":
    rules = Rules()

    from dataclasses import fields

    print("Blackjack Basic Strategy Solver")
    print("=" * 40)
    for f in fields(rules):
        print(f"  {f.name:<30} {getattr(rules, f.name)}")
    print("=" * 40)
    print("輸入格式: <card1> <card2> <dealer_upcard>  (牌值 2-10, A=11)")
    print("輸入 q 離開\n")

    while True:
        try:
            raw = input(">>> ").strip()
            if raw.lower() == "q":
                break

            parts = raw.split()
            if len(parts) != 3:
                print("請輸入三個數字，例如: 8 8 11")
                continue

            card1, card2, dealer_upcard = int(parts[0]), int(parts[1]), int(parts[2])

            if not all(v in range(2, 12) for v in (card1, card2, dealer_upcard)):
                print("牌值必須介於 2~11 (A=11)")
                continue

            player_state = make_player_state(card1, card2)
            dealer_state = make_dealer_state(dealer_upcard)

            move, evs = best_move(
                player_state=player_state,
                dealer_state=dealer_state,
                rules=rules,
            )

            print(
                f"  手牌={player_state.total}{'(soft)' if player_state.soft_aces else ''}"
                f"  莊家={dealer_upcard if dealer_upcard != 11 else 'A'}"
                f"  -> Best Move: {move}"
            )
            for action, ev in sorted(evs.items(), key=lambda x: -x[1]):
                marker = " <--" if action == move else ""
                print(f"    {action:<10} EV=  {ev:+.4f}{marker}")
            print()

        except ValueError:
            print("請輸入有效整數")
        except KeyboardInterrupt:
            break
