from dataclasses import asdict

import pandas as pd
import streamlit as st

from basic_strategy_solver import best_move
from generate_table import (
	ACTION_SYMBOLS,
	UPCARDS,
	build_hard_total_table,
	build_pair_table,
	build_soft_total_table,
)
from house_edge import compute_player_ev_per_initial_bet
from rules import Rules, make_rules
from state import make_dealer_state, make_player_state


CARD_OPTIONS = {str(value): value for value in range(2, 11)} | {"A": 11}
ACTION_LABELS = {
	"HIT": "Hit",
	"DOUBLE": "Double",
	"STAND": "Stand",
	"SPLIT": "Split",
	"SURRENDER": "Surrender",
}
ACTION_CELL_COLORS = {
	"H": "#ffd6d6",
	"S": "#d9f2d9",
	"D": "#cfe8ff",
	"SUR": "#ffe7b3",
	"Y": "#e7d6ff",
	"Ds": "#63cdda",
	"Dh": "#f4a261",
}


def format_card(card: int) -> str:
	return "A" if card == 11 else str(card)


def strategy_dataframe(table: dict, pair_table: bool = False) -> pd.DataFrame:
	data = {
		label: [
			"Y" if pair_table and row[upcard] == "SPLIT" else "" if pair_table else ACTION_SYMBOLS.get(row[upcard], row[upcard])
			for upcard in UPCARDS
		]
		for label, row in table.items()
	}
	dataframe = pd.DataFrame.from_dict(data, orient="index", columns=[format_card(card) for card in UPCARDS])
	return dataframe.style.applymap(
		lambda value: f"background-color: {ACTION_CELL_COLORS[value]}; color: #111827; font-weight: 700;"
		if value in ACTION_CELL_COLORS
		else "",
	)


def rule_key(name: str) -> str:
	return f"rule_{name}"


def load_rule_preset() -> None:
	"""Reset editable values when the casino preset changes."""
	preset = make_rules(st.session_state["rule_type"])
	for name, value in asdict(preset).items():
		if name != "rule_type":
			st.session_state[rule_key(name)] = value


def initialize_rule_controls() -> None:
	if "rule_type" not in st.session_state:
		st.session_state["rule_type"] = "Jeju"
	if rule_key("allow_double") not in st.session_state:
		load_rule_preset()


def editable_rules() -> Rules:
	initialize_rule_controls()
	with st.sidebar:
		st.selectbox("Casino preset", ["Jeju", "Macau"], key="rule_type", on_change=load_rule_preset)
		st.number_input("Blackjack payout", min_value=1.0, max_value=2.0, step=0.1, key=rule_key("blackjack_payout"))

		with st.expander("Dealer rules", expanded=True):
			st.checkbox("Dealer hits soft 17", key=rule_key("dealer_hits_soft17"))
			st.checkbox("European no hole card (ENHC)", key=rule_key("european_no_hole_card"))
			st.checkbox("Original bets only (OBO)", key=rule_key("original_bets_only"))

		with st.expander("Double and split rules", expanded=True):
			# st.checkbox("Allow double", key=rule_key("allow_double"))
			# st.checkbox("Allow split", key=rule_key("allow_split"))
			# st.checkbox("Double after split", key=rule_key("allow_double_after_split"))
			st.number_input("Maximum split hands", min_value=2, max_value=8, step=1, key=rule_key("max_split_hands"))
			st.checkbox("Resplit aces", key=rule_key("resplit_aces"))
			# st.checkbox("One card only after splitting aces", key=rule_key("split_aces_one_card_only"))
			# st.checkbox("Allow hitting split aces", key=rule_key("hit_split_aces"))
			# st.checkbox("Split 21 counts as blackjack", key=rule_key("split_21_counts_as_blackjack"))

		with st.expander("Surrender rules", expanded=True):
			# st.checkbox("Allow surrender", key=rule_key("allow_surrender"))
			st.checkbox("Early surrender", key=rule_key("early_surrender"))
			st.checkbox("Late surrender", key=rule_key("late_surrender"))
			st.checkbox("Allow surrender against ace", key=rule_key("surrender_vs_ace"))
			# st.checkbox("Allow surrender after split", key=rule_key("allow_surrender_after_split"))

		st.caption("This solver uses an infinite shoe, so deck count and card removal are not modeled.")

	values = {
		name: st.session_state[rule_key(name)]
		for name in asdict(make_rules(st.session_state["rule_type"]))
		if name not in {"rule_type", "decks"}
	}
	return Rules(rule_type=st.session_state["rule_type"], **values)


@st.cache_data(show_spinner="Calculating house edge from all starting hands...")
def calculate_house_edge(rules: Rules) -> float:
	return compute_player_ev_per_initial_bet(rules)


st.set_page_config(page_title="Blackjack Strategy", page_icon="🂡", layout="wide")
st.title("Blackjack Strategy")

rules = editable_rules()
rule_type = rules.rule_type

calculator_tab, tables_tab, house_edge_tab = st.tabs(["Best move", "Strategy tables", "House edge"])

with calculator_tab:
	st.subheader("Hand calculator")
	card_columns = st.columns(3)
	with card_columns[0]:
		first_card = CARD_OPTIONS[st.selectbox("First card", list(CARD_OPTIONS), index=6)]
	with card_columns[1]:
		second_card = CARD_OPTIONS[st.selectbox("Second card", list(CARD_OPTIONS), index=6)]
	with card_columns[2]:
		dealer_card = CARD_OPTIONS[st.selectbox("Dealer upcard", list(CARD_OPTIONS), index=8)]

	player_state = make_player_state(first_card, second_card)
	move, action_evs = best_move(player_state, make_dealer_state(dealer_card), rules)
	st.metric("Recommended action", ACTION_LABELS[move])
	st.caption(
		f"Player: {format_card(first_card)}, {format_card(second_card)} "
		f"(total {player_state.total}) | Dealer: {format_card(dealer_card)}"
	)
	ev_frame = pd.DataFrame(
		[
			{"Action": ACTION_LABELS[action], "EV": value, "Recommended": action == move}
			for action, value in sorted(action_evs.items(), key=lambda item: item[1], reverse=True)
		]
	)
	st.dataframe(
		ev_frame,
		column_config={"EV": st.column_config.NumberColumn(format="%+.4f")},
		hide_index=True,
		width="stretch",
	)

with tables_tab:
	st.subheader(f"{rule_type} basic strategy")
	st.caption("H = Hit, S = Stand, D = Double, SUR = Surrender, Y = Split, Ds/Dh = Double otherwise Stand/Hit.")
	table_type = st.selectbox("Table", ["Hard totals", "Soft totals", "Pairs"])
	if table_type == "Hard totals":
		table = build_hard_total_table(rules)
		pair_table = False
	elif table_type == "Soft totals":
		table = build_soft_total_table(rules)
		pair_table = False
	else:
		table = build_pair_table(rules)
		pair_table = True
	st.dataframe(strategy_dataframe(table, pair_table), width="stretch")

with house_edge_tab:
	st.subheader("House edge")
	st.caption("Calculated from optimal basic strategy for the active rules and an infinite shoe.")
	if st.button("Calculate house edge", type="primary"):
		player_ev = calculate_house_edge(rules)
		st.session_state["house_edge_rules"] = rules
		st.session_state["house_edge_player_ev"] = player_ev

	if st.session_state.get("house_edge_rules") == rules:
		player_ev = st.session_state["house_edge_player_ev"]
		metric_columns = st.columns(2)
		metric_columns[0].metric("House edge", f"{-player_ev * 100:.4f}%")
		metric_columns[1].metric("Player EV per initial bet", f"{player_ev:+.6f}")
	else:
		st.info("Select the active rules in the sidebar, then calculate the house edge.")