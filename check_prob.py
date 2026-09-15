from dealer import dealer_final_distribution
from state import make_dealer_state

# 驗證所有莊家明牌的條件/無條件機率和
for upcard in range(2, 12):
    for peek in (True, False):
        d_state = make_dealer_state(upcard)
        dist = dealer_final_distribution(d_state, dealer_hits_soft17=False, peek_blackjack=peek)
        prob_sum = sum(dist.values())
        assert abs(prob_sum - 1.0) < 1e-12, f"Upcard {upcard} 機率總和不為 1: {prob_sum}"
print("莊家狀態轉移率守恆檢驗通過！")