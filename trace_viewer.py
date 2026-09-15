# trace_viewer.py

# %%
import json
import pandas as pd


class TraceViewer:

    def __init__(self, jsonl_file: str):
        self.jsonl_file = jsonl_file

    def load_raw(self):
        """
        讀取 jsonl，回傳 list[dict]
        """
        records = []

        with open(
            self.jsonl_file,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        return records

    def load_dataframe(self):
        """
        讀取成 DataFrame
        """
        return pd.read_json(
            self.jsonl_file,
            lines=True
        )

    def show_head(self, n=5):
        df = self.load_dataframe()
        print(df.head(n))

    def show_round(self, round_no: int):
        records = self.load_raw()

        if round_no < 1 or round_no > len(records):
            print("找不到該局")
            return

        print(json.dumps(
            records[round_no - 1],
            ensure_ascii=False,
            indent=4
        ))

    def summary(self):
        df = self.load_dataframe()

        print("=" * 60)
        print("Trace Summary")
        print("=" * 60)

        print(f"總局數 : {len(df):,}")

        if "total_net" in df.columns:
            print(
                f"總 EV : {df['total_net'].mean():+.6f}"
            )

        if "end_reason" in df.columns:
            print("\n結束原因統計")

            print(
                df["end_reason"]
                .value_counts()
            )

    def filter(self, **kwargs):
        """
        viewer.filter(
            upcard=11,
            first_move="SURRENDER"
        )
        """
        df = self.load_dataframe()

        for k, v in kwargs.items():

            if k not in df.columns:
                raise ValueError(
                    f"{k} 不存在"
                )

            df = df[df[k] == v]

        return df


if __name__ == "__main__":

    viewer = TraceViewer(
        "blackjack_trace.jsonl"
    )

    viewer.summary()

    print("\n前五筆")
    viewer.show_head()

    print("\n第一局")
    viewer.show_round(1)