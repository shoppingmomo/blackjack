from dataclasses import dataclass


RULE_OVERRIDES = {
	"Jeju": {},
	"Macau": {
		"early_surrender": True,
		"late_surrender": False,
		"surrender_vs_ace": False,
		"resplit_aces": False,
		"european_no_hole_card": True,
	},
}


@dataclass(frozen=True)
class Rules:
	rule_type: str = 'Jeju'
	decks: int = 6
	blackjack_payout: float = 1.5
	# Double / Split base toggles
	allow_double: bool = True
	allow_split: bool = True
	allow_double_after_split: bool = True
	# Split detail rules
	max_split_hands: int = 4
	split_aces_one_card_only: bool = True
	hit_split_aces: bool = False
	split_21_counts_as_blackjack: bool = False


	if rule_type == 'Jeju':
		'''
		Jeju
		'''
		dealer_hits_soft17: bool = False
		# Surrender rules
		allow_surrender: bool = True
		early_surrender: bool = False
		late_surrender: bool = True #晚降: 莊家先看有無BJ再決定投降
		surrender_vs_ace: bool = True # 跟Macau主要差在這裡
		allow_surrender_after_split: bool = False # 死代碼，目前沒有任何地方呼叫此參數後有真正使用，若永遠為False可暫時不理會
		resplit_aces: bool = True
		# European no hole card (ENHC): Jeju 為 peek 局(有底牌)，故關閉
		european_no_hole_card: bool = False # ENHC=False 即美式有底牌會 peek 的局
		original_bets_only: bool = False # Original Bets Only (OBO): peek 局用不到，設 False

	elif rule_type == 'Macau':
		'''
		Macau
		'''
		dealer_hits_soft17: bool = False #目前澳門規則是莊家軟17停牌，若要改成軟17要補牌，請改成True
		# Surrender rules
		allow_surrender: bool = True
		early_surrender: bool = True 
		late_surrender: bool = False #晚降: 莊家先看有無BJ再決定投降，但因為澳門不會peek，所以不會有late surrender
		surrender_vs_ace: bool = False # 跟Jeju主要差在這裡
		allow_surrender_after_split: bool = False # 死代碼，目前沒有任何地方呼叫此參數後有真正使用，若永遠為False可暫時不理會
		resplit_aces: bool = False
		# European no hole card (ENHC): 莊家不拿底牌/不 peek，玩家行動後才結算莊家 BJ
		european_no_hole_card: bool = True # ENHC=True 即歐式無底牌不會 peek 的局
		original_bets_only: bool = False # Original Bets Only (OBO): 莊家天生 BJ 時只沒收原注，加倍/分牌的額外注退還 # 若賭場為全沒收(含加倍分牌)請改為 False


def make_rules(rule_type: str = "Jeju") -> Rules:
	"""Create the supported casino rule set selected by the user."""
	if rule_type not in RULE_OVERRIDES:
		raise ValueError(f"Unsupported rule type: {rule_type}")
	return Rules(rule_type=rule_type, **RULE_OVERRIDES[rule_type])

