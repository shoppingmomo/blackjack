
import json
import random
import time
from rules import Rules
from state import PlayerState, DealerState, draw_card, make_player_state, make_dealer_state, card_rank
from basic_strategy_solver import best_move
from house_edge import compute_player_ev_per_initial_bet

CARD_POOL = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11)

# ----------------------------------------------------
# 1. 預計算策略表 (Strategy Cache)，省去模擬中的所有 DP 計算
# ----------------------------------------------------
STRATEGY_CACHE = {}

def build_strategy_cache(rules: Rules):
    """預先為所有可能出現的手牌狀態建立策略查表"""
    global STRATEGY_CACHE
    STRATEGY_CACHE.clear()
    
    # 遍歷莊家明牌 2 ~ 11
    for upcard in range(2, 12):
        d_state = make_dealer_state(upcard)
        
        # 遍歷玩家起手牌 2~11, 2~11
        for c1 in range(2, 12):
            for c2 in range(2, 12):
                p_state = make_player_state(c1, c2)
                m, _ = best_move(p_state, d_state, rules)
                STRATEGY_CACHE[(p_state.total, p_state.soft_aces, p_state.cards, p_state.can_double, p_state.can_split, p_state.pair_rank, upcard)] = m

        # 遍歷補牌後的各種點數組合 (total: 4~21, soft_aces: 0~4, cards: 3~7)
        for total in range(4, 22):
            for soft in (0, 1):
                p_state = PlayerState(
                    total=total,
                    soft_aces=soft,
                    pair_rank=None,
                    cards=3,
                    can_double=False,
                    can_split=False,
                    from_split=False,
                )
                m, _ = best_move(p_state, d_state, rules)
                STRATEGY_CACHE[(total, soft, False, upcard)] = m

def fast_best_move(state: PlayerState, upcard: int, rules: Rules) -> str:
    """極速 O(1) 策略查詢"""
    if state.cards == 2:
        key = (state.total, state.soft_aces, state.cards, state.can_double, state.can_split, state.pair_rank, upcard)
        if key in STRATEGY_CACHE:
            return STRATEGY_CACHE[key]
    else:
        key = (state.total, state.soft_aces, False, upcard)
        if key in STRATEGY_CACHE:
            return STRATEGY_CACHE[key]
            
    # 若遇到極端手牌組合 (例如多張 Ace)，fallback 回原本計算
    m, _ = best_move(state, make_dealer_state(upcard), rules)
    return m

# ----------------------------------------------------
# 2. 高效模擬邏輯
# ----------------------------------------------------
def play_dealer_fast(d_total: int, d_soft: int, hits_soft17: bool) -> int:
    """純整數運算的莊家抽牌迴圈"""
    while d_total < 17 or (d_total == 17 and hits_soft17 and d_soft > 0):
        c = random.choice(CARD_POOL)
        if c == 11:
            d_total += 11
            d_soft += 1
        else:
            d_total += c
        while d_total > 21 and d_soft > 0:
            d_total -= 10
            d_soft -= 1
    return d_total

def simulate_one_round_fast(rules: Rules) -> tuple:
    """返回 (payout, is_blackjack, trace) 元組"""
    # 發牌
    p1 = random.choice(CARD_POOL)
    p2 = random.choice(CARD_POOL)
    upcard = random.choice(CARD_POOL)
    hole = random.choice(CARD_POOL)

    dealer_is_bj = (upcard in (10, 11) and (card_rank(upcard) + card_rank(hole) == 21))
    player_state = make_player_state(p1, p2)
    player_is_bj = (player_state.total == 21 and player_state.cards == 2)

    trace = {
        "p1": p1,
        "p2": p2,
        "upcard": upcard,
        "hole": hole,
        # "dealer_is_bj": dealer_is_bj,
        # "player_initial_total": player_state.total,
        # "player_is_bj": player_is_bj,
    }
    
    # 歐式 ENHC (Macau) / 美式 Peek
    if not rules.european_no_hole_card:
        if dealer_is_bj:
            payout = 0.0 if player_is_bj else -1.0

            trace["end_reason"] = "dealer_blackjack"
            trace["total_net"] = payout

            return payout, False, trace

        if player_is_bj:
            payout = rules.blackjack_payout

            trace["end_reason"] = "player_blackjack"
            trace["total_net"] = payout

            return payout, True, trace
    else:
        if player_is_bj:
            payout = (
                0.0
                if dealer_is_bj
                else rules.blackjack_payout
            )

            trace["end_reason"] = "player_blackjack_enhc"
            trace["total_net"] = payout

            return payout, True, trace

    # 首輪決策
    move = fast_best_move(player_state, upcard, rules)
    
    if move == "SURRENDER":
        if upcard == 11 and not rules.surrender_vs_ace:
            pass
        else:
            trace["first_move"] = move
            trace["end_reason"] = "surrender"
            trace["total_net"] = -0.5

            return -0.5, False, trace

    finished_hands = []
    hand_traces = []

    if move == "SPLIT":
        pair_rank = player_state.pair_rank
        is_ace_split = (pair_rank == 11)
        remaining_resplits = max(0, rules.max_split_hands - 2)
        pending_hands = 2

        while pending_hands > 0:
            pending_hands -= 1
            c = random.choice(CARD_POOL)

            if is_ace_split:
                total = 11 + (11 if c == 11 else c)
                soft = 1 + (1 if c == 11 else 0)
            else:
                total = pair_rank + (11 if c == 11 else c)
                soft = 1 if c == 11 else 0

            while total > 21 and soft > 0:
                total -= 10
                soft -= 1

            this_hand = {
                "split_rank": pair_rank,
                "initial_draw": c,
                "start_total": total,
                "start_soft_aces": soft,
                "actions": []
            }

            can_resplit = (
                c == pair_rank
                and remaining_resplits > 0
                and (
                    not is_ace_split
                    or rules.resplit_aces
                )
            )

            hand = PlayerState(
                total=total,
                soft_aces=soft,
                pair_rank=pair_rank if c == pair_rank else None,
                cards=2,
                can_double=rules.allow_double_after_split,
                can_split=can_resplit,
                from_split=True,
                from_split_aces=is_ace_split,
            )

            if can_resplit:
                sub_move = fast_best_move(
                    hand,
                    upcard,
                    rules
                )

                if sub_move == "SPLIT":
                    this_hand["trace_type"] = "resplit_event"

                    this_hand["actions"].append({
                        "action": "SPLIT",
                        "remaining_resplits_before": (
                            remaining_resplits
                        )
                    })

                    hand_traces.append(this_hand)

                    remaining_resplits -= 1
                    pending_hands += 2
                    continue

            if (
                is_ace_split
                and rules.split_aces_one_card_only
            ):
                this_hand["trace_type"] = "finished_hand"

                this_hand["actions"].append({
                    "action": "FORCED_STAND",
                    "reason": "split_aces_one_card_only",
                    "final_total": hand.total,
                    "wager": 1.0
                })

                hand_traces.append(this_hand)
                finished_hands.append(
                    (hand.total, 1.0)
                )

                continue

            curr = hand

            while True:
                m = fast_best_move(
                    curr,
                    upcard,
                    rules
                )

                if m == "STAND":
                    this_hand["trace_type"] = "finished_hand"

                    this_hand["actions"].append({
                        "action": "STAND",
                        "final_total": curr.total,
                        "wager": 1.0
                    })

                    hand_traces.append(this_hand)
                    finished_hands.append(
                        (curr.total, 1.0)
                    )
                    break

                elif m == "DOUBLE" and curr.can_double:
                    dc = random.choice(CARD_POOL)

                    d_tot = (
                        curr.total
                        + (11 if dc == 11 else dc)
                    )

                    d_sft = (
                        curr.soft_aces
                        + (1 if dc == 11 else 0)
                    )

                    while d_tot > 21 and d_sft > 0:
                        d_tot -= 10
                        d_sft -= 1

                    this_hand["trace_type"] = "finished_hand"

                    this_hand["actions"].append({
                        "action": "DOUBLE",
                        "before_total": curr.total,
                        "draw_card": dc,
                        "final_total": d_tot,
                        "wager": 2.0
                    })

                    hand_traces.append(this_hand)
                    finished_hands.append(
                        (d_tot, 2.0)
                    )
                    break

                else:
                    hc = random.choice(CARD_POOL)

                    h_tot = (
                        curr.total
                        + (11 if hc == 11 else hc)
                    )

                    h_sft = (
                        curr.soft_aces
                        + (1 if hc == 11 else 0)
                    )

                    while h_tot > 21 and h_sft > 0:
                        h_tot -= 10
                        h_sft -= 1

                    this_hand["actions"].append({
                        "action": "HIT",
                        "before_total": curr.total,
                        "before_soft": curr.soft_aces,
                        "draw_card": hc,
                        "new_total": h_tot,
                        "new_soft": h_sft
                    })

                    if h_tot > 21:
                        this_hand["trace_type"] = "finished_hand"

                        this_hand["actions"].append({
                            "action": "BUST",
                            "final_total": h_tot,
                            "wager": 1.0
                        })

                        hand_traces.append(this_hand)
                        finished_hands.append(
                            (h_tot, 1.0)
                        )
                        break

                    curr = PlayerState(
                        total=h_tot,
                        soft_aces=h_sft,
                        cards=curr.cards + 1,
                        can_double=False,
                        can_split=False,
                        from_split=True
                    )


    else:
        this_hand = {
            "trace_type": "finished_hand",
            "start_total": player_state.total,
            "start_soft_aces": player_state.soft_aces,
            "actions": []
        }

        curr = player_state
        while True:
            m = fast_best_move(curr, upcard, rules)
            if m == "STAND":
                this_hand["trace_type"] = "finished_hand"
                this_hand["actions"].append({
                    "action": "STAND",
                    "final_total": curr.total,
                    "wager": 1.0
                })
                hand_traces.append(this_hand)

                finished_hands.append((curr.total, 1.0))
                break
            elif m == "DOUBLE" and curr.can_double:
                dc = random.choice(CARD_POOL)
                d_tot = curr.total + (11 if dc == 11 else dc)
                d_sft = curr.soft_aces + (1 if dc == 11 else 0)
                while d_tot > 21 and d_sft > 0:
                    d_tot -= 10
                    d_sft -= 1

                this_hand["trace_type"] = "finished_hand"
                this_hand["actions"].append({
                    "action": "DOUBLE",
                    "before_total": curr.total,
                    "draw_card": dc,
                    "final_total": d_tot,
                    "wager": 2.0
                })
                hand_traces.append(this_hand)

                finished_hands.append((d_tot, 2.0))
                break
            else:  # HIT
                hc = random.choice(CARD_POOL)
                h_tot = curr.total + (11 if hc == 11 else hc)
                h_sft = curr.soft_aces + (1 if hc == 11 else 0)
                while h_tot > 21 and h_sft > 0:
                    h_tot -= 10
                    h_sft -= 1

                this_hand["actions"].append({
                    "action": "HIT",
                    "before_total": curr.total,
                    "before_soft": curr.soft_aces,
                    "draw_card": hc,
                    "new_total": h_tot,
                    "new_soft": h_sft
                })

                if h_tot > 21:
                    this_hand["trace_type"] = "finished_hand"
                    this_hand["actions"].append({
                        "action": "BUST",
                        "final_total": h_tot,
                        "wager": 1.0
                    })
                    hand_traces.append(this_hand)

                    finished_hands.append((h_tot, 1.0))
                    break
                curr = PlayerState(total=h_tot, soft_aces=h_sft, cards=curr.cards + 1, can_double=False, can_split=False)

    # 莊家補牌
    d_init_tot = (11 if upcard == 11 else upcard) + (11 if hole == 11 else hole)
    d_init_sft = (1 if upcard == 11 else 0) + (1 if hole == 11 else 0)
    if d_init_tot > 21 and d_init_sft > 0:
        d_init_tot -= 10
        d_init_sft -= 1

    d_final = play_dealer_fast(d_init_tot, d_init_sft, rules.dealer_hits_soft17)

    # 結算
    total_net = 0.0
    for p_tot, wager in finished_hands:
        if dealer_is_bj:
            total_net += -1.0 if rules.original_bets_only else -wager
        elif p_tot > 21:
            total_net -= wager
        elif d_final > 21 or p_tot > d_final:
            total_net += wager
        elif p_tot < d_final:
            total_net -= wager

    # 追蹤
    trace["first_move"] = move
    trace["num_finished_hands"] = len(finished_hands)
    trace["num_resplits"] = sum(1 for item in hand_traces if item.get("trace_type") == "resplit_event")
    trace["finished_hands"] = finished_hands
    trace["hand_traces"] = hand_traces
    trace["dealer_initial_total"] = d_init_tot
    # trace["dealer_initial_soft"] = d_init_sft
    trace["dealer_final"] = d_final
    trace["total_net"] = total_net
    trace["end_reason"] = "normal"

    return total_net, False, trace

def run_monte_carlo(rules: Rules, num_simulations: int = 5_000_000):
    print("建構策略快取 (Strategy Cache)...")
    build_strategy_cache(rules)

    print(f"開始極速蒙地卡羅模擬 (回合數: {num_simulations:,})...")
    start_time = time.time()

    total_ev = 0.0
    sum_sq = 0.0
    payouts = []  # 記錄每輪結果用於統計
    
    # 統計計數器
    wins = 0
    losses = 0
    ties = 0
    blackjacks = 0
    
    # 追踪最大回撤和最大利潤
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    max_profit = 0.0
    max_running_loss = 0.0  # 運行過程中曾跌到的最低點

    # 寫入追蹤
    trace_file = open(
        "blackjack_trace.jsonl",
        "w",
        encoding="utf-8"
    )

    for i in range(1, num_simulations + 1):
        payout, is_bj, trace = simulate_one_round_fast(rules)
        total_ev += payout
        sum_sq += payout * payout
        payouts.append(payout)
        
        # 統計勝敗平
        if payout > 0:
            wins += 1
        elif payout < 0:
            losses += 1
        else:
            ties += 1
        
        # 計算 BJ 次數 (從函數返回值直接得到)
        if is_bj:
            blackjacks += 1
        
        # 追踪運行累積值
        cumulative += payout
        if cumulative > peak:
            peak = cumulative
            max_profit = cumulative
        
        # 計算回撤
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        if cumulative < max_running_loss:
            max_running_loss = cumulative

        trace["round"] = i
        trace_file.write(
            json.dumps(trace, ensure_ascii=False)
        )
        trace_file.write("\n")

    trace_file.close()


    elapsed = time.time() - start_time
    
    # 計算基本統計
    mc_ev = total_ev / num_simulations
    variance = (sum_sq / num_simulations) - (mc_ev * mc_ev)
    std_dev = variance ** 0.5
    std_error = std_dev / (num_simulations ** 0.5)
    mc_house_edge = -mc_ev * 100.0
    mc_ci95 = 1.96 * std_error * 100.0
    
    # 計算勝率、敗率、平手率
    win_rate = (wins / num_simulations) * 100
    loss_rate = (losses / num_simulations) * 100
    tie_rate = (ties / num_simulations) * 100
    bj_rate = (blackjacks / num_simulations) * 100
    
    # 計算贏和輸時的平均支付
    win_payouts = [p for p in payouts if p > 0]
    loss_payouts = [p for p in payouts if p < 0]
    
    avg_win = sum(win_payouts) / len(win_payouts) if win_payouts else 0
    avg_loss = sum(loss_payouts) / len(loss_payouts) if loss_payouts else 0
    
    # 計算偏度 (Skewness) 和峰度 (Kurtosis)
    mean = mc_ev
    skewness = 0.0
    kurtosis_val = 0.0
    
    if num_simulations > 0:
        m3 = sum((p - mean) ** 3 for p in payouts) / num_simulations
        m4 = sum((p - mean) ** 4 for p in payouts) / num_simulations
        
        if std_dev > 0:
            skewness = m3 / (std_dev ** 3)
            kurtosis_val = (m4 / (std_dev ** 4)) - 3  # 超額峰度
    
    # RTP (Return to Player) = 100% - House Edge
    rtp = 100.0 - abs(mc_house_edge)
    
    # 信度區間範圍
    mc_he_lower = mc_house_edge - mc_ci95
    mc_he_upper = mc_house_edge + mc_ci95

    print("\n計算解析解 EV 中...")
    analytical_ev = compute_player_ev_per_initial_bet(rules)
    analytical_he = -analytical_ev * 100.0

    # ============ 詳細統計報告 ============
    print("\n" + "=" * 70)
    print("蒙地卡羅模擬統計報告 (Monte Carlo Simulation Statistics)")
    print("=" * 70)
    
    print("\n【基本統計資訊】")
    print(f"  模擬總回合數        : {num_simulations:,}")
    print(f"  模擬總耗時          : {elapsed:.2f} 秒")
    rate_per_sec = num_simulations / elapsed if elapsed > 0 else float('inf')
    print(f"  每秒模擬回合數      : {rate_per_sec:,.0f} 回合/秒")
    
    print("\n【勝負平統計】")
    print(f"  勝場數              : {wins:,} ({win_rate:.2f}%)")
    print(f"  敗場數              : {losses:,} ({loss_rate:.2f}%)")
    print(f"  平手數              : {ties:,} ({tie_rate:.2f}%)")
    print(f"  黑傑克比率          : {bj_rate:.2f}% ({blackjacks:,} 場)")
    
    # print("\n【收支分析】")
    # print(f"  平均每局 EV         : {mc_ev:+.6f}")
    # print(f"  勝場平均支付        : {avg_win:+.6f}")
    # print(f"  敗場平均虧損        : {avg_loss:+.6f}")
    # print(f"  Win/Loss 比率       : {abs(avg_win/avg_loss) if avg_loss != 0 else 0:.4f}")
    
    print("\n【風險指標】")
    print(f"  標準差 (波動率)     : {std_dev:.6f}")
    print(f"  標準誤差 (sigma/√n) : {std_error:.6f}")
    # print(f"  偏度 (Skewness)     : {skewness:+.6f}")
    # print(f"  峰度 (Kurtosis)     : {kurtosis_val:+.6f}")
    
    print("\n【運行風險】")
    print(f"  最終累積輸贏        : {cumulative:+.2f}")
    print(f"  最大運行利潤        : {max_profit:+.2f}")
    print(f"  最大運行虧損        : {max_running_loss:+.2f}")
    print(f"  最大運行回撤        : {max_drawdown:+.2f}")
    # print(f"  回撤率              : {(max_drawdown/max_profit*100):.2f}%" if max_profit > 0 else "  回撤率              : N/A")
    
    print("\n【House Edge 分析】")
    print(f"  解析解 House Edge   : {analytical_he:.4f}% (EV: {analytical_ev:+.6f})")
    print(f"  蒙地卡羅 House Edge : {mc_house_edge:.4f}%")
    print(f"  95% 信度區間        : [{mc_he_lower:.4f}%, {mc_he_upper:.4f}%]")
    print(f"  絕對誤差            : {abs(analytical_he - mc_house_edge):.4f}%")
    # print(f"  RTP (玩家回報率)    : {rtp:.4f}%")
    
    print("=" * 70 + "\n")

if __name__ == "__main__":
    rules = Rules()
    run_monte_carlo(rules, num_simulations=10000)