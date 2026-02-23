import pandas as pd
from sklearn.ensemble import IsolationForest

class FaultAnalytics:
    """
    Local analytics on alarm records already stored in MongoDB.
    Replaces Cortex AI analytics for demo purposes.
    All models run on CPU using data already in your local MongoDB.
    """

    def __init__(self, alarm_records: list):
        # Convert models/dicts to pure dict list
        items = []
        for r in alarm_records:
            items.append(r if isinstance(r, dict) else r.model_dump())
        self.df = pd.DataFrame(items)

    def top_fault_categories(self, machine: str = None, top_n: int = 10) -> list:
        if self.df.empty: return []
        df = self.df[self.df["machine"] == machine] if machine else self.df
        counts = (
            df.groupby(["reason_level_1", "reason_level_2"])
              .size()
              .reset_index(name="count")
              .sort_values("count", ascending=False)
              .head(top_n)
        )
        return counts.to_dict("records")

    def anomalous_machines(self) -> list:
        if self.df.empty: return []
        counts = self.df.groupby("machine").size().reset_index(name="count")
        if len(counts) < 3:
            return []
        model = IsolationForest(contamination=0.1, random_state=42)
        counts["anomaly"] = model.fit_predict(counts[["count"]])
        return counts[counts["anomaly"] == -1]["machine"].tolist()

    def unclassified_alarms(self) -> list:
        if self.df.empty: return []
        return self.df[self.df["reason_level_1"].isna()]["alarm_id"].tolist()

    def electrical_fault_rate(self, machine: str = None) -> float:
        if self.df.empty: return 0.0
        df = self.df[self.df["machine"] == machine] if machine else self.df
        if len(df) == 0:
            return 0.0
        elec = df["reason_level_2"].str.contains(
            "electrical", case=False, na=False).sum()
        return round(float(elec) / len(df) * 100, 1)

    def monthly_alarm_trend(self, machine: str = None) -> dict:
        if self.df.empty: return {}
        if "extracted_at" not in self.df: return {}
        
        df = self.df[self.df["machine"] == machine] if machine else self.df
        df = df.copy()
        try:
            df["month"] = pd.to_datetime(df["extracted_at"]).dt.to_period("M")
            counts = df.groupby("month").size()
            return {str(k): int(v) for k, v in counts.items()}
        except:
            return {}
